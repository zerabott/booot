from flask import Flask, request, jsonify
from telegram import Bot, Update
from telegram.ext import Dispatcher
import os
import logging

# Setup logging
import sys
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Read bot token from environment variable
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    logger.error("❌ BOT_TOKEN is not set in environment variables!")
    raise ValueError("BOT_TOKEN environment variable is required")

# Initialize bot and dispatcher
bot = Bot(TOKEN)
from bot import dp  # Import your Dispatcher from bot.py
dispatcher = dp

# Initialize Flask app
app = Flask(__name__)

# Health check route
@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "bot_running": True,
        "service": "Telegram Confession Bot"
    })

# Telegram webhook route
@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    """Handle incoming updates from Telegram"""
    try:
        update = Update.de_json(request.get_json(force=True), bot)
        dispatcher.process_update(update)
        return "ok"
    except Exception as e:
        logger.error(f"Error processing update: {e}")
        return "error", 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"Starting Flask server on 0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port)
