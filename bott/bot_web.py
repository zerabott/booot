#!/usr/bin/env python3
"""
Web Service Wrapper for Telegram Bot on Render
Runs the bot with proper logging, environment checks, and webhook integration
"""

from flask import Flask, jsonify, request
import os
import sys
import logging
from datetime import datetime
from telegram import Bot, Update
from telegram.ext import Dispatcher
from bot import dp  # Import your Dispatcher from bot.py

# ------------------- Logging -------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# ------------------- Environment -------------------
required_vars = ["BOT_TOKEN", "CHANNEL_ID", "BOT_USERNAME", "ADMIN_ID_1"]
missing_vars = [var for var in required_vars if not os.getenv(var)]
if missing_vars:
    logger.error(f"❌ Missing environment variables: {missing_vars}")
    sys.exit(1)

TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(TOKEN)
dispatcher = dp  # your Dispatcher from bot.py

# ------------------- Bot Status -------------------
bot_status = {"running": True, "start_time": datetime.utcnow(), "last_activity": None}

# ------------------- Flask App -------------------
app = Flask(__name__)

@app.route("/", methods=["GET"])
def home():
    """Basic health check"""
    return jsonify({
        "status": "healthy",
        "service": "Telegram Confession Bot",
        "timestamp": datetime.utcnow().isoformat(),
        "bot_running": bot_status["running"],
        "uptime": (datetime.utcnow() - bot_status["start_time"]).total_seconds()
    })

@app.route("/health", methods=["GET"])
def health():
    """Detailed health check"""
    return jsonify({
        "status": "ok" if bot_status["running"] else "error",
        "bot_status": bot_status,
        "environment": {var: bool(os.getenv(var)) for var in required_vars}
    })

@app.route("/ping", methods=["GET"])
def ping():
    """Simple ping endpoint"""
    return "pong"

@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    """Telegram webhook endpoint"""
    try:
        update = Update.de_json(request.get_json(force=True), bot)
        dispatcher.process_update(update)
        bot_status["last_activity"] = datetime.utcnow()
        return "ok"
    except Exception as e:
        logger.error(f"❌ Error processing update: {e}")
        return "error", 500

# ------------------- Start Flask -------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"🚀 Starting Telegram Confession Bot Web Service on 0.0.0.0:{port}")
    logger.info(f"⏰ Start time: {bot_status['start_time'].strftime('%Y-%m-%d %H:%M:%S UTC')}")
    logger.info("=" * 50)
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
