"""
Enhanced error handling system for the confession bot
"""

import asyncio
import traceback
import sys
from functools import wraps
from typing import Optional, Callable, Any
from datetime import datetime, timedelta
from collections import defaultdict

from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import NetworkError, TimedOut, BadRequest, Forbidden, RetryAfter, TelegramError

from logger import get_logger
from config import ADMIN_IDS

logger = get_logger('error_handler')


class ErrorTracker:
    """Track errors and implement circuit breaker pattern"""
    
    def __init__(self):
        self.error_counts = defaultdict(int)
        self.last_errors = defaultdict(list)
        self.circuit_breakers = defaultdict(lambda: {'open': False, 'last_failure': None})
    
    def add_error(self, error_type: str, context: str = ""):
        """Add an error occurrence"""
        now = datetime.now()
        key = f"{error_type}:{context}"
        
        self.error_counts[key] += 1
        self.last_errors[key].append(now)
        
        # Keep only errors from the last hour
        cutoff = now - timedelta(hours=1)
        self.last_errors[key] = [
            error_time for error_time in self.last_errors[key] 
            if error_time > cutoff
        ]
        
        # Check if circuit breaker should open
        recent_errors = len(self.last_errors[key])
        if recent_errors >= 10:  # Too many errors in 1 hour
            self.circuit_breakers[key]['open'] = True
            self.circuit_breakers[key]['last_failure'] = now
            logger.error(f"Circuit breaker opened for {key} due to {recent_errors} errors")
    
    def is_circuit_open(self, error_type: str, context: str = "") -> bool:
        """Check if circuit breaker is open"""
        key = f"{error_type}:{context}"
        circuit = self.circuit_breakers[key]
        
        if not circuit['open']:
            return False
        
        # Auto-close circuit after 30 minutes
        if circuit['last_failure']:
            time_since_failure = datetime.now() - circuit['last_failure']
            if time_since_failure > timedelta(minutes=30):
                circuit['open'] = False
                logger.info(f"Circuit breaker auto-closed for {key}")
                return False
        
        return True
    
    def get_error_stats(self) -> dict:
        """Get error statistics"""
        return {
            'total_errors': sum(self.error_counts.values()),
            'error_types': dict(self.error_counts),
            'open_circuits': [
                key for key, circuit in self.circuit_breakers.items() 
                if circuit['open']
            ]
        }


# Global error tracker
error_tracker = ErrorTracker()


class RetryHandler:
    """Handle retries with exponential backoff"""
    
    @staticmethod
    async def retry_with_backoff(
        func: Callable,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        backoff_factor: float = 2.0,
        exceptions: tuple = (Exception,)
    ):
        """Retry function with exponential backoff"""
        last_exception = None
        
        for attempt in range(max_retries + 1):
            try:
                return await func() if asyncio.iscoroutinefunction(func) else func()
            except exceptions as e:
                last_exception = e
                
                if attempt == max_retries:
                    break
                
                delay = min(base_delay * (backoff_factor ** attempt), max_delay)
                logger.warning(f"Retry {attempt + 1}/{max_retries} after {delay}s delay: {str(e)}")
                await asyncio.sleep(delay)
        
        raise last_exception


def handle_telegram_errors(func):
    """Decorator to handle Telegram-specific errors"""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        try:
            return await func(update, context, *args, **kwargs)
        except Forbidden as e:
            # User blocked the bot or insufficient permissions
            logger.warning(f"Forbidden error for user {update.effective_user.id}: {e}")
            error_tracker.add_error('forbidden', str(update.effective_user.id))
            return None
            
        except BadRequest as e:
            # Invalid request (message too long, invalid format, etc.)
            logger.error(f"Bad request: {e}")
            error_tracker.add_error('bad_request', func.__name__)
            
            # Try to send a user-friendly error message
            try:
                if update.message:
                    await update.message.reply_text(
                        "❗ Sorry, there was an issue processing your request. Please try again."
                    )
                elif update.callback_query:
                    await update.callback_query.answer("❗ Something went wrong. Please try again.")
            except:
                pass  # If we can't even send an error message, give up
            return None
            
        except TimedOut as e:
            # Request timed out
            logger.error(f"Request timed out: {e}")
            error_tracker.add_error('timeout', func.__name__)
            
            # Retry the operation
            try:
                return await RetryHandler.retry_with_backoff(
                    lambda: func(update, context, *args, **kwargs),
                    max_retries=2,
                    exceptions=(TimedOut, NetworkError)
                )
            except:
                try:
                    if update.message:
                        await update.message.reply_text(
                            "⏱️ The request timed out. Please try again in a moment."
                        )
                except:
                    pass
            return None
            
        except RetryAfter as e:
            # Rate limited by Telegram
            logger.warning(f"Rate limited by Telegram: {e}")
            error_tracker.add_error('rate_limited', func.__name__)
            
            await asyncio.sleep(e.retry_after)
            try:
                return await func(update, context, *args, **kwargs)
            except:
                pass
            return None
            
        except NetworkError as e:
            # Network connectivity issues
            logger.error(f"Network error: {e}")
            error_tracker.add_error('network', func.__name__)
            
            # Retry with backoff
            try:
                return await RetryHandler.retry_with_backoff(
                    lambda: func(update, context, *args, **kwargs),
                    max_retries=3,
                    exceptions=(NetworkError,)
                )
            except:
                try:
                    if update.message:
                        await update.message.reply_text(
                            "🌐 Network error occurred. Please try again later."
                        )
                except:
                    pass
            return None
            
        except TelegramError as e:
            # Generic Telegram error
            logger.error(f"Telegram error in {func.__name__}: {e}")
            error_tracker.add_error('telegram_generic', func.__name__)
            
            try:
                if update.message:
                    await update.message.reply_text(
                        "❗ A Telegram error occurred. Please try again."
                    )
                elif update.callback_query:
                    await update.callback_query.answer("❗ Error occurred. Please try again.")
            except:
                pass
            return None
            
        except Exception as e:
            # Unexpected error
            logger.error(f"Unexpected error in {func.__name__}: {e}", exc_info=True)
            error_tracker.add_error('unexpected', func.__name__)
            
            # Notify admins of unexpected errors
            await notify_admins_of_error(context, e, func.__name__, update)
            
            try:
                if update.message:
                    await update.message.reply_text(
                        "❗ An unexpected error occurred. The administrators have been notified."
                    )
                elif update.callback_query:
                    await update.callback_query.answer("❗ Unexpected error. Admins notified.")
            except:
                pass
            return None
    
    return wrapper


def handle_database_errors(func):
    """Decorator to handle database-specific errors"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)
        except Exception as e:
            error_name = type(e).__name__
            logger.error(f"Database error in {func.__name__}: {error_name} - {str(e)}")
            error_tracker.add_error('database', func.__name__)
            
            # Check if we should stop processing due to too many database errors
            if error_tracker.is_circuit_open('database', func.__name__):
                logger.critical("Database circuit breaker open - refusing to process request")
                return None, "Database temporarily unavailable"
            
            # Retry for transient errors
            if 'locked' in str(e).lower() or 'busy' in str(e).lower():
                try:
                    await asyncio.sleep(0.1)  # Brief pause for SQLite lock
                    return await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)
                except:
                    pass
            
            return None, f"Database error: {error_name}"
    
    return wrapper


def escape_markdown_v2(text: str) -> str:
    """Escape special characters for MarkdownV2"""
    escape_chars = r'_*[]()~`>#+-=|{}.!\\'
    for char in escape_chars:
        text = text.replace(char, f'\\{char}')
    return text

async def notify_admins_of_error(context: ContextTypes.DEFAULT_TYPE, error: Exception, function_name: str, update: Update = None):
    """Notify admins of critical errors"""
    error_info = {
        'type': type(error).__name__,
        'message': str(error)[:500],  # Truncate message to prevent overflow
        'function': function_name,
        'timestamp': datetime.now().isoformat(),
        'user_id': update.effective_user.id if update and update.effective_user else 'Unknown',
        'traceback': traceback.format_exc()[:1000]  # Truncate traceback
    }
    
    # Create a safe HTML message instead of Markdown
    admin_message = f"""🚨 <b>Critical Error Alert</b>

<b>Error Type:</b> {error_info['type']}
<b>Function:</b> {error_info['function']}
<b>User ID:</b> {error_info['user_id']}
<b>Time:</b> {error_info['timestamp']}

<b>Error Message:</b>
<pre>{error_info['message']}</pre>

<b>Traceback:</b>
<pre>{error_info['traceback']}</pre>"""
    
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=admin_message,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Failed to notify admin {admin_id} of error: {e}")
            # Fallback to plain text if HTML also fails
            try:
                simple_message = f"🚨 Error in {function_name}: {str(error)[:200]}"
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=simple_message
                )
            except:
                pass  # If we can't send any notification, log it


class HealthMonitor:
    """Monitor system health and performance"""
    
    def __init__(self):
        self.start_time = datetime.now()
        self.request_count = 0
        self.error_count = 0
        
    def record_request(self):
        """Record a request"""
        self.request_count += 1
        
    def record_error(self):
        """Record an error"""
        self.error_count += 1
        
    def get_health_status(self) -> dict:
        """Get current health status"""
        uptime = datetime.now() - self.start_time
        error_rate = (self.error_count / max(self.request_count, 1)) * 100
        
        return {
            'status': 'healthy' if error_rate < 5 else 'degraded' if error_rate < 20 else 'unhealthy',
            'uptime_seconds': int(uptime.total_seconds()),
            'uptime_human': str(uptime),
            'total_requests': self.request_count,
            'total_errors': self.error_count,
            'error_rate_percent': round(error_rate, 2),
            'error_stats': error_tracker.get_error_stats()
        }
        
    def reset_stats(self):
        """Reset health statistics"""
        self.request_count = 0
        self.error_count = 0
        self.start_time = datetime.now()


# Global health monitor
health_monitor = HealthMonitor()


def monitor_function_performance(func):
    """Decorator to monitor function performance"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = datetime.now()
        health_monitor.record_request()
        
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
                
            duration = (datetime.now() - start_time).total_seconds()
            
            # Log slow operations
            if duration > 5.0:  # Slower than 5 seconds
                logger.warning(f"Slow operation: {func.__name__} took {duration:.2f}s")
                
            return result
            
        except Exception as e:
            health_monitor.record_error()
            raise
    
    return wrapper


# Global error handler for the application
async def global_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Global error handler for unhandled exceptions"""
    logger.error("Global error handler triggered", exc_info=context.error)
    
    # Track the error
    error_tracker.add_error('global', 'unhandled')
    
    # Notify admins
    if isinstance(update, Update):
        await notify_admins_of_error(context, context.error, 'global_handler', update)
    
    # Try to send a user-friendly message
    try:
        if isinstance(update, Update) and update.effective_user:
            if update.message:
                await update.message.reply_text(
                    "❗ An unexpected error occurred. Our administrators have been notified and will look into it."
                )
            elif update.callback_query:
                await update.callback_query.answer(
                    "❗ An error occurred. Please try again later.",
                    show_alert=True
                )
    except Exception:
        logger.error("Failed to send error message to user", exc_info=True)
