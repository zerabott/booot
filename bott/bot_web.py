#!/usr/bin/env python3
"""
Web Service Wrapper for Telegram Bot on Render
Runs the bot in a thread while maintaining a web server for health checks
"""

from flask import Flask, jsonify
import threading
import os
import sys
import logging
from datetime import datetime
import time

# Set up logging for production
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
bot_status = {"running": False, "start_time": None, "last_activity": None}

@app.route('/')
def home():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "Telegram Confession Bot",
        "timestamp": datetime.now().isoformat(),
        "bot_running": bot_status["running"],
        "uptime": (datetime.now() - bot_status["start_time"]).total_seconds() if bot_status["start_time"] else 0
    })

@app.route('/health')
def health():
    """Detailed health check"""
    return jsonify({
        "status": "ok" if bot_status["running"] else "error",
        "bot_status": bot_status,
        "environment": {
            "bot_token_set": bool(os.getenv("BOT_TOKEN")),
            "channel_id_set": bool(os.getenv("CHANNEL_ID")),
            "admin_id_set": bool(os.getenv("ADMIN_ID_1"))
        }
    })

@app.route('/ping')
def ping():
    """Simple ping endpoint"""
    return "pong"

def run_bot():
    """Run the Telegram bot"""
    try:
        logger.info("🚀 Starting Telegram bot thread...")
        bot_status["start_time"] = datetime.now()
        bot_status["running"] = True
        
        # Import and run the bot
        from bot import main as bot_main
        logger.info("✅ Bot modules loaded successfully")
        
        bot_main()
        
    except Exception as e:
        logger.error(f"❌ Bot thread error: {e}")
        bot_status["running"] = False
        raise

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
        return False
    
    logger.info("✅ All required environment variables are set")
    return True

if __name__ == "__main__":
    logger.info("🚀 Starting Telegram Confession Bot Web Service")
    logger.info(f"⏰ Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    logger.info("=" * 50)
    
    # Check environment variables
    if not check_environment():
        logger.error("Environment check failed. Exiting.")
        sys.exit(1)
    
    # Start the bot in a separate thread
    logger.info("📱 Starting bot thread...")
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    # Give the bot a moment to start
    time.sleep(2)
    
    # Run Flask web server on the port Render provides
    port = int(os.environ.get("PORT", 10000))
    logger.info(f"🌐 Starting web server on port {port}...")
    
    app.run(
        host="0.0.0.0", 
        port=port, 
        debug=False,
        use_reloader=False  # Important: disable reloader in production
    )
