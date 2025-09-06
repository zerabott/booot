#!/usr/bin/env python3
"""
Startup script for Replit deployment
Ensures proper initialization and error handling
"""

import os
import sys
import logging
from datetime import datetime

def setup_logging():
    """Set up logging for production"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )

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
        print(f"❌ Missing required environment variables: {missing_vars}")
        print("Please set these in your Replit secrets.")
        return False
    
    print("✅ All required environment variables are set")
    return True

def main():
    """Main startup function"""
    print(f"🚀 Starting Telegram Confession Bot on Replit")
    print(f"⏰ Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 50)
    
    # Set up logging
    setup_logging()
    
    # Check environment variables
    if not check_environment():
        sys.exit(1)
    
    # Import and run the bot
    try:
        print("📱 Initializing bot...")
        from bot import main as bot_main
        print("✅ Bot modules loaded successfully")
        
        print("🔄 Starting bot polling...")
        bot_main()
        
    except Exception as e:
        print(f"❌ Fatal error starting bot: {e}")
        logging.exception("Fatal error during bot startup")
        sys.exit(1)

if __name__ == "__main__":
    main()
