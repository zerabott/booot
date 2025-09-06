#!/usr/bin/env python3
"""
Simple test to verify bot token validity
"""

import asyncio
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def test_bot_token():
    """Test if bot token is valid"""
    try:
        import telegram
        bot_token = os.getenv("BOT_TOKEN")
        print(f"Testing bot token: {bot_token[:10]}...")
        
        bot = telegram.Bot(token=bot_token)
        
        # Try to get bot info
        print("Attempting to connect to Telegram...")
        me = await bot.get_me()
        
        print("✅ Bot token is valid!")
        print(f"   Bot name: {me.first_name}")
        print(f"   Bot username: @{me.username}")
        print(f"   Bot ID: {me.id}")
        
        return True
        
    except telegram.error.Unauthorized:
        print("❌ Bot token is invalid or revoked!")
        print("   Please check your bot token in .env file")
        return False
        
    except Exception as e:
        print(f"❌ Network error: {e}")
        print("   This could be due to:")
        print("   - Network connectivity issues")
        print("   - Firewall/proxy blocking connection")
        print("   - Temporary Telegram server issues")
        return False

if __name__ == "__main__":
    asyncio.run(test_bot_token())
