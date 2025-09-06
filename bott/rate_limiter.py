"""
Advanced rate limiting system for the confession bot
"""

import time
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from collections import defaultdict
import json

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None

from config import (
    REDIS_HOST, REDIS_PORT, REDIS_DB, REDIS_URL,
    MAX_CONFESSIONS_PER_HOUR, MAX_COMMENTS_PER_HOUR, MAX_ADMIN_MESSAGES_PER_DAY
)
from logger import get_logger

logger = get_logger('rate_limiter')


class InMemoryRateLimiter:
    """In-memory rate limiter as fallback"""
    
    def __init__(self):
        self.requests: Dict[str, list] = defaultdict(list)
        self.last_cleanup = time.time()
        
    def is_allowed(self, key: str, limit: int, window_seconds: int) -> Tuple[bool, int]:
        """Check if request is allowed and return remaining time if blocked"""
        now = time.time()
        
        # Clean old requests periodically
        if now - self.last_cleanup > 60:  # Cleanup every minute
            self._cleanup_old_requests()
            self.last_cleanup = now
        
        # Get requests for this key
        requests = self.requests[key]
        
        # Remove old requests outside the window
        cutoff = now - window_seconds
        requests[:] = [req_time for req_time in requests if req_time > cutoff]
        
        if len(requests) >= limit:
            # Calculate when the oldest request will expire
            oldest_request = min(requests)
            remaining_time = int(oldest_request + window_seconds - now)
            return False, max(0, remaining_time)
        
        # Add current request
        requests.append(now)
        return True, 0
        
    def _cleanup_old_requests(self):
        """Clean up old request records"""
        now = time.time()
        for key in list(self.requests.keys()):
            # Keep only requests from the last hour
            self.requests[key][:] = [
                req_time for req_time in self.requests[key] 
                if now - req_time < 3600
            ]
            # Remove empty lists
            if not self.requests[key]:
                del self.requests[key]


class RedisRateLimiter:
    """Redis-based rate limiter for distributed systems"""
    
    def __init__(self):
        self.available = False
        if not REDIS_AVAILABLE or redis is None:
            logger.info("Redis module not available, falling back to in-memory rate limiting")
            return
            
        try:
            self.redis_client = redis.from_url(
                REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            # Test connection
            self.redis_client.ping()
            self.available = True
            logger.info("Redis rate limiter initialized successfully")
        except Exception as e:
            logger.warning(f"Redis not available, falling back to in-memory: {e}")
            self.available = False
            
    def is_allowed(self, key: str, limit: int, window_seconds: int) -> Tuple[bool, int]:
        """Check if request is allowed using sliding window"""
        if not self.available:
            return True, 0
            
        try:
            now = time.time()
            pipeline = self.redis_client.pipeline()
            
            # Remove old entries
            pipeline.zremrangebyscore(key, 0, now - window_seconds)
            
            # Count current entries
            pipeline.zcard(key)
            
            # Add current request
            pipeline.zadd(key, {str(now): now})
            
            # Set expiration
            pipeline.expire(key, window_seconds)
            
            results = pipeline.execute()
            
            current_count = results[1]  # Count after cleanup
            
            if current_count >= limit:
                # Get the oldest entry to calculate remaining time
                oldest_entries = self.redis_client.zrange(key, 0, 0, withscores=True)
                if oldest_entries:
                    oldest_time = oldest_entries[0][1]
                    remaining_time = int(oldest_time + window_seconds - now)
                    return False, max(0, remaining_time)
                    
            return True, 0
            
        except Exception as e:
            logger.error(f"Redis rate limiter error: {e}")
            return True, 0  # Allow request if Redis fails


class RateLimiter:
    """Main rate limiter with fallback support"""
    
    def __init__(self):
        self.redis_limiter = RedisRateLimiter()
        self.memory_limiter = InMemoryRateLimiter()
        
    def is_allowed(self, key: str, limit: int, window_seconds: int) -> Tuple[bool, int]:
        """Check if request is allowed"""
        if self.redis_limiter.available:
            return self.redis_limiter.is_allowed(key, limit, window_seconds)
        else:
            return self.memory_limiter.is_allowed(key, limit, window_seconds)
    
    def check_confession_limit(self, user_id: int) -> Tuple[bool, int]:
        """Check confession submission rate limit"""
        key = f"confessions:{user_id}"
        return self.is_allowed(key, MAX_CONFESSIONS_PER_HOUR, 3600)
    
    def check_comment_limit(self, user_id: int) -> Tuple[bool, int]:
        """Check comment submission rate limit"""
        key = f"comments:{user_id}"
        return self.is_allowed(key, MAX_COMMENTS_PER_HOUR, 3600)
    
    def check_admin_message_limit(self, user_id: int) -> Tuple[bool, int]:
        """Check admin message rate limit"""
        key = f"admin_messages:{user_id}"
        return self.is_allowed(key, MAX_ADMIN_MESSAGES_PER_DAY, 86400)
    
    def check_reaction_limit(self, user_id: int, limit: int = 100, window: int = 3600) -> Tuple[bool, int]:
        """Check reaction rate limit (likes/dislikes)"""
        key = f"reactions:{user_id}"
        return self.is_allowed(key, limit, window)
    
    def check_view_limit(self, user_id: int, limit: int = 200, window: int = 3600) -> Tuple[bool, int]:
        """Check view rate limit for browsing"""
        key = f"views:{user_id}"
        return self.is_allowed(key, limit, window)
    
    def get_remaining_time_text(self, remaining_seconds: int) -> str:
        """Convert remaining seconds to human-readable text"""
        if remaining_seconds <= 0:
            return "now"
        elif remaining_seconds < 60:
            return f"{remaining_seconds} second{'s' if remaining_seconds != 1 else ''}"
        elif remaining_seconds < 3600:
            minutes = remaining_seconds // 60
            return f"{minutes} minute{'s' if minutes != 1 else ''}"
        else:
            hours = remaining_seconds // 3600
            return f"{hours} hour{'s' if hours != 1 else ''}"


# Global rate limiter instance
rate_limiter = RateLimiter()


class RateLimitTracker:
    """Track rate limit violations and implement progressive penalties"""
    
    def __init__(self):
        self.violations: Dict[int, list] = defaultdict(list)
        
    def add_violation(self, user_id: int, violation_type: str):
        """Add a rate limit violation"""
        now = time.time()
        self.violations[user_id].append({
            'time': now,
            'type': violation_type
        })
        
        # Keep only violations from the last 24 hours
        cutoff = now - 86400
        self.violations[user_id] = [
            v for v in self.violations[user_id] if v['time'] > cutoff
        ]
        
        # Log security event for repeated violations
        recent_violations = len(self.violations[user_id])
        if recent_violations >= 5:
            logger.warning(
                f"User {user_id} has {recent_violations} rate limit violations in 24h",
                extra={'user_id': user_id, 'action': 'security_rate_limit_violations'}
            )
    
    def get_penalty_multiplier(self, user_id: int) -> float:
        """Get penalty multiplier based on violation history"""
        violations_24h = len(self.violations.get(user_id, []))
        
        if violations_24h >= 10:
            return 4.0  # 4x longer cooldown
        elif violations_24h >= 5:
            return 2.0  # 2x longer cooldown
        elif violations_24h >= 3:
            return 1.5  # 1.5x longer cooldown
        else:
            return 1.0  # Normal cooldown
    
    def should_temp_block(self, user_id: int) -> bool:
        """Check if user should be temporarily blocked"""
        violations_24h = len(self.violations.get(user_id, []))
        return violations_24h >= 15


# Global violation tracker
violation_tracker = RateLimitTracker()


def handle_rate_limit_decorator(limit_type: str):
    """Decorator to handle rate limiting for bot functions"""
    def decorator(func):
        async def wrapper(update, context, *args, **kwargs):
            user_id = update.effective_user.id
            
            # Choose appropriate rate limit check
            if limit_type == 'confession':
                allowed, remaining = rate_limiter.check_confession_limit(user_id)
                message = f"⏱️ You can submit up to {MAX_CONFESSIONS_PER_HOUR} confessions per hour. Please wait {rate_limiter.get_remaining_time_text(remaining)} before submitting another."
            elif limit_type == 'comment':
                allowed, remaining = rate_limiter.check_comment_limit(user_id)
                message = f"⏱️ You can post up to {MAX_COMMENTS_PER_HOUR} comments per hour. Please wait {rate_limiter.get_remaining_time_text(remaining)} before commenting again."
            elif limit_type == 'admin_message':
                allowed, remaining = rate_limiter.check_admin_message_limit(user_id)
                message = f"⏱️ You can send up to {MAX_ADMIN_MESSAGES_PER_DAY} messages to admins per day. Please wait {rate_limiter.get_remaining_time_text(remaining)} before sending another."
            else:
                allowed, remaining = True, 0
                message = "⏱️ Please slow down and try again later."
            
            if not allowed:
                # Apply penalty multiplier for repeat offenders
                multiplier = violation_tracker.get_penalty_multiplier(user_id)
                if multiplier > 1.0:
                    adjusted_remaining = int(remaining * multiplier)
                    message = f"⏱️ Due to repeated rate limit violations, you must wait {rate_limiter.get_remaining_time_text(adjusted_remaining)} before trying again."
                
                # Add violation
                violation_tracker.add_violation(user_id, limit_type)
                
                # Check for temp block
                if violation_tracker.should_temp_block(user_id):
                    message = "⛔ Your account has been temporarily restricted due to excessive rate limit violations. Please contact an administrator."
                    logger.warning(f"User {user_id} temporarily blocked for rate limit violations")
                
                # Send rate limit message
                if update.message:
                    await update.message.reply_text(message)
                elif update.callback_query:
                    await update.callback_query.answer(message, show_alert=True)
                
                return None
                
            # Call the original function
            return await func(update, context, *args, **kwargs)
        return wrapper
    return decorator
