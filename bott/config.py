import os
import logging
from typing import List, Optional

# Load environment variables from .env file if not running on Replit
try:
    from dotenv import load_dotenv
    load_dotenv()  # Load .env file
except ImportError:
    # If python-dotenv is not available, continue without it
    pass

# Note: Replit provides environment variables directly through os.environ
# For local development, we use dotenv to load from .env file

class ConfigError(Exception):
    """Configuration error exception"""
    pass

def get_env_var(var_name: str, default: Optional[str] = None, required: bool = True) -> str:
    """Get environment variable with validation"""
    value = os.getenv(var_name, default)
    if required and not value:
        raise ConfigError(f"Required environment variable {var_name} is not set")
    return value

def get_env_int(var_name: str, default: Optional[int] = None, required: bool = True) -> int:
    """Get integer environment variable with validation"""
    value = os.getenv(var_name)
    if not value:
        if required:
            raise ConfigError(f"Required environment variable {var_name} is not set")
        return default
    try:
        return int(value)
    except ValueError:
        raise ConfigError(f"Environment variable {var_name} must be an integer")

def get_env_bool(var_name: str, default: bool = False) -> bool:
    """Get boolean environment variable"""
    value = os.getenv(var_name, str(default)).lower()
    return value in ('true', '1', 'yes', 'on')

# Critical Configuration (Required)
try:
    BOT_TOKEN = get_env_var("BOT_TOKEN")
    CHANNEL_ID = get_env_int("CHANNEL_ID")
    BOT_USERNAME = get_env_var("BOT_USERNAME")
    
    # Get all admin IDs
    ADMIN_IDS = []
    admin_id_1 = get_env_int("ADMIN_ID_1", required=True)
    ADMIN_IDS.append(admin_id_1)
    
    # Add additional admin IDs if they exist
    for i in range(2, 10):  # Support up to 9 admins
        admin_id = get_env_int(f"ADMIN_ID_{i}", required=False)
        if admin_id:
            ADMIN_IDS.append(admin_id)
            
except ConfigError as e:
    logging.error(f"Configuration error: {e}")
    raise

# Database Configuration
DB_PATH = get_env_var("DB_PATH", "confessions.db", required=False)

# Redis Configuration
REDIS_URL = get_env_var("REDIS_URL", "redis://localhost:6379/0", required=False)
REDIS_HOST = get_env_var("REDIS_HOST", "localhost", required=False)
REDIS_PORT = get_env_int("REDIS_PORT", 6379, required=False)
REDIS_DB = get_env_int("REDIS_DB", 0, required=False)

# Logging Configuration
LOG_LEVEL = get_env_var("LOG_LEVEL", "INFO", required=False)
LOG_FILE = get_env_var("LOG_FILE", "confession_bot.log", required=False)

# Rate Limiting Configuration
MAX_CONFESSIONS_PER_HOUR = get_env_int("MAX_CONFESSIONS_PER_HOUR", 5, required=False)
MAX_COMMENTS_PER_HOUR = get_env_int("MAX_COMMENTS_PER_HOUR", 20, required=False)
MAX_ADMIN_MESSAGES_PER_DAY = get_env_int("MAX_ADMIN_MESSAGES_PER_DAY", 3, required=False)

# Feature Flags
ENABLE_SENTIMENT_ANALYSIS = get_env_bool("ENABLE_SENTIMENT_ANALYSIS", True)
ENABLE_PROFANITY_FILTER = get_env_bool("ENABLE_PROFANITY_FILTER", True)
ENABLE_AUTO_BACKUP = get_env_bool("ENABLE_AUTO_BACKUP", True)
BACKUP_INTERVAL_HOURS = get_env_int("BACKUP_INTERVAL_HOURS", 24, required=False)

# Content Limits
MAX_CONFESSION_LENGTH = get_env_int("MAX_CONFESSION_LENGTH", 4000, required=False)
MAX_COMMENT_LENGTH = get_env_int("MAX_COMMENT_LENGTH", 500, required=False)
COMMENTS_PER_PAGE = get_env_int("COMMENTS_PER_PAGE", 5, required=False)
DAILY_DIGEST_LIMIT = get_env_int("DAILY_DIGEST_LIMIT", 5, required=False)

# Media Configuration
ALLOW_MEDIA_CONFESSIONS = get_env_bool("ALLOW_MEDIA_CONFESSIONS", True)
MAX_PHOTO_SIZE_MB = get_env_int("MAX_PHOTO_SIZE_MB", 10, required=False)
MAX_VIDEO_SIZE_MB = get_env_int("MAX_VIDEO_SIZE_MB", 50, required=False)
MAX_GIF_SIZE_MB = get_env_int("MAX_GIF_SIZE_MB", 20, required=False)
MAX_CAPTION_LENGTH = get_env_int("MAX_CAPTION_LENGTH", 1000, required=False)

# Supported Media Types and Formats
SUPPORTED_MEDIA_TYPES = ['photo', 'video', 'animation', 'document']
SUPPORTED_IMAGE_FORMATS = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']
SUPPORTED_VIDEO_FORMATS = ['.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm']

# Notification Settings
ENABLE_NOTIFICATIONS = get_env_bool("ENABLE_NOTIFICATIONS", True)
NOTIFICATION_COOLDOWN_MINUTES = get_env_int("NOTIFICATION_COOLDOWN_MINUTES", 60, required=False)

# Categories for confessions
CATEGORIES = [
    " Academics",
    " Love", 
    " Crushes",
    " Relationships",
    " Funny",
    " Embarrassing",
    " Secrets",
    " Personal Thoughts",
    " Experiences",
    " Friendship",
    " Campus Life",
    " Money",
    " Food & Lifestyle",
    " Dorm",
    " Mental Health",
    " Cultural",
    " Tech",
    "‍ Teachers",
    " Religious",
    " Random",
    " Weird",
    "‍ Family"
]

# Enhanced spam detection words
SPAM_WORDS = [
    "spam", "viagra", "casino", "porn", "http://", "https://", "www.", 
    "sex", "drugs", "bitcoin", "crypto", "investment", "earn money", 
    "free money", "click here", "buy now", "limited time", "act now",
    "congratulations", "winner", "prize", "lottery", "inheritance",
    "nigerian prince", "bank account", "wire transfer", "paypal",
    "western union", "moneygram", "urgent", "confidential",
    "telegram", "whatsapp", "phone number", "contact me", "dm me"
]

# Profanity filter words (basic set - expand as needed)
PROFANITY_WORDS = [
    # Add your profanity words here based on your community guidelines
    # This is a basic example - you should customize based on your needs
    "badword1", "badword2"  # Replace with actual words
]

# Sentiment analysis thresholds
SENTIMENT_THRESHOLDS = {
    "very_negative": -0.8,
    "negative": -0.3,
    "neutral": 0.3,
    "positive": 0.8
}

# File paths
LOGS_DIR = "logs"
BACKUPS_DIR = "backups"
EXPORTS_DIR = "exports"
TEMP_DIR = "temp"

# Help text
HELP_TEXT = """
🎓 *University Confession Bot Help*

*Main Features:*
• 🙊 Submit anonymous confessions/questions
• 📰 View recent approved posts
• 💬 Comment on posts anonymously
• 👍👎 React to comments
• 📊 Check your submission statistics
• 📞 Contact administrators anonymously

*How to use:*
1\\. Choose "🙊 Confess/Ask Question" to submit
2\\. Select a category for your confession
3\\. Write your message \\(up to 4000 characters\\)
4\\. Wait for admin approval
5\\. Once approved, it will be posted to the channel

*Privacy:*
All submissions and comments are completely anonymous\\. Your identity is never revealed to other users or in the channel\\.

*Rules:*
• No spam, harassment, or inappropriate content
• Be respectful to others
• Follow university guidelines
• Admins reserve the right to reject submissions

*Need help?* Use "📞 Contact Admin" to send a message to administrators\\.
"""