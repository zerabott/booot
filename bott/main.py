#!/usr/bin/env python3
"""
Main entry point for Replit deployment
This file will be automatically run by Replit
"""

import os
import sys
import logging
from datetime import datetime

# Load environment variables from .env file if not running on Replit
try:
    from dotenv import load_dotenv
    load_dotenv()  # Load .env file
except ImportError:
    # If python-dotenv is not available, continue without it
    pass

# Set up logging for Replit
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def check_environment():
    """Check if all required environment variables are set"""
    required_vars = [
        'BOT_TOKEN',
        'CHANNEL_ID', 
        'BOT_USERNAME',
        'ADMIN_ID_1'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        logger.error(f"❌ Missing required environment variables: {missing_vars}")
        logger.error("Please set these in your Replit secrets.")
        return False
    
    logger.info("✅ All required environment variables are set")
    return True

def main():
    """Main startup function"""
    logger.info("🚀 Starting Telegram Confession Bot on Replit")
    logger.info(f"⏰ Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    logger.info("=" * 50)
    
    # Check environment variables
    if not check_environment():
        sys.exit(1)
    
    # Import and run the bot
    try:
        logger.info("📱 Initializing bot...")
        from bot import main as bot_main
        logger.info("✅ Bot modules loaded successfully")
        
        logger.info("🔄 Starting bot polling...")
        bot_main()
        
    except Exception as e:
        logger.error(f"❌ Fatal error starting bot: {e}")
        logging.exception("Fatal error during bot startup")
        sys.exit(1)

if __name__ == "__main__":
    main()
