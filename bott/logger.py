"""
Enhanced logging system for the confession bot
"""

import os
import sys
import logging
import logging.handlers
from datetime import datetime
from typing import Optional
import json
from pathlib import Path

from config import LOG_LEVEL, LOG_FILE, LOGS_DIR


class JsonFormatter(logging.Formatter):
    """JSON formatter for structured logging"""
    
    def format(self, record):
        log_entry = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        # Add exception info if present
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
        
        # Add extra fields
        if hasattr(record, 'user_id'):
            log_entry['user_id'] = record.user_id
        if hasattr(record, 'post_id'):
            log_entry['post_id'] = record.post_id
        if hasattr(record, 'action'):
            log_entry['action'] = record.action
            
        return json.dumps(log_entry)


class BotLogger:
    """Enhanced logging system for the bot"""
    
    def __init__(self):
        self.logger = logging.getLogger('confession_bot')
        self.setup_logging()
        
    def setup_logging(self):
        """Setup comprehensive logging configuration"""
        # Create logs directory
        os.makedirs(LOGS_DIR, exist_ok=True)
        
        # Set log level
        log_level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)
        self.logger.setLevel(log_level)
        
        # Clear existing handlers
        self.logger.handlers.clear()
        
        # Console handler with colored output
        console_handler = logging.StreamHandler(sys.stdout)
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        console_handler.setLevel(log_level)
        
        # File handler with rotation
        log_path = os.path.join(LOGS_DIR, LOG_FILE)
        file_handler = logging.handlers.RotatingFileHandler(
            log_path,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        file_handler.setLevel(logging.DEBUG)
        
        # JSON file handler for structured logs
        json_log_path = os.path.join(LOGS_DIR, 'bot_structured.log')
        json_handler = logging.handlers.RotatingFileHandler(
            json_log_path,
            maxBytes=10*1024*1024,
            backupCount=5
        )
        json_handler.setFormatter(JsonFormatter())
        json_handler.setLevel(logging.INFO)
        
        # Error file handler
        error_log_path = os.path.join(LOGS_DIR, 'errors.log')
        error_handler = logging.handlers.RotatingFileHandler(
            error_log_path,
            maxBytes=5*1024*1024,
            backupCount=3
        )
        error_handler.setFormatter(file_formatter)
        error_handler.setLevel(logging.ERROR)
        
        # Add all handlers
        self.logger.addHandler(console_handler)
        self.logger.addHandler(file_handler)
        self.logger.addHandler(json_handler)
        self.logger.addHandler(error_handler)
        
        # Set up other loggers
        logging.getLogger('telegram').setLevel(logging.WARNING)
        logging.getLogger('httpx').setLevel(logging.WARNING)
        
    def log_user_action(self, user_id: int, action: str, details: str = "", **kwargs):
        """Log user action with context"""
        extra = {'user_id': user_id, 'action': action, **kwargs}
        self.logger.info(f"User {user_id} - {action}: {details}", extra=extra)
        
    def log_admin_action(self, admin_id: int, action: str, target_id: Optional[int] = None, details: str = ""):
        """Log admin action"""
        extra = {'user_id': admin_id, 'action': f'admin_{action}'}
        if target_id:
            extra['target_id'] = target_id
        self.logger.info(f"Admin {admin_id} - {action}: {details}", extra=extra)
        
    def log_confession_submission(self, user_id: int, post_id: int, category: str):
        """Log confession submission"""
        extra = {'user_id': user_id, 'post_id': post_id, 'action': 'confession_submitted'}
        self.logger.info(f"Confession submitted by user {user_id}, post_id: {post_id}, category: {category}", extra=extra)
        
    def log_confession_approval(self, admin_id: int, post_id: int, approved: bool):
        """Log confession approval/rejection"""
        action = 'confession_approved' if approved else 'confession_rejected'
        extra = {'user_id': admin_id, 'post_id': post_id, 'action': action}
        status = 'approved' if approved else 'rejected'
        self.logger.info(f"Admin {admin_id} {status} confession {post_id}", extra=extra)
        
    def log_comment_action(self, user_id: int, post_id: int, comment_id: int, action: str):
        """Log comment-related actions"""
        extra = {'user_id': user_id, 'post_id': post_id, 'comment_id': comment_id, 'action': f'comment_{action}'}
        self.logger.info(f"User {user_id} - comment {action} on post {post_id}, comment {comment_id}", extra=extra)
        
    def log_error(self, error: Exception, context: str = "", **kwargs):
        """Log error with context"""
        extra = {'action': 'error', **kwargs}
        self.logger.error(f"Error in {context}: {str(error)}", exc_info=error, extra=extra)
        
    def log_security_event(self, event_type: str, user_id: Optional[int] = None, details: str = ""):
        """Log security-related events"""
        extra = {'action': f'security_{event_type}'}
        if user_id:
            extra['user_id'] = user_id
        self.logger.warning(f"Security event - {event_type}: {details}", extra=extra)
        
    def log_performance(self, operation: str, duration: float, **kwargs):
        """Log performance metrics"""
        extra = {'action': 'performance', 'operation': operation, 'duration': duration, **kwargs}
        self.logger.info(f"Performance - {operation} took {duration:.2f}s", extra=extra)


# Global logger instance
bot_logger = BotLogger()
logger = bot_logger.logger


def get_logger(name: str = None) -> logging.Logger:
    """Get a logger instance"""
    if name:
        return logging.getLogger(f'confession_bot.{name}')
    return logger
