# Telegram Confession Bot - Replit Deployment Guide

## 🚀 Quick Deployment on Replit

This Telegram confession bot has been optimized for deployment on Replit. Follow these steps to get your bot up and running.

### 1. Required Replit Secrets

In your Replit project, go to the **Secrets** tab (🔐 icon) and add the following environment variables:

#### ✅ Required Variables:
- `BOT_TOKEN` - Your Telegram bot token from @BotFather
- `CHANNEL_ID` - The channel ID where confessions will be posted (use negative number for channels)
- `BOT_USERNAME` - Your bot's username (without @)
- `ADMIN_ID_1` - Your Telegram user ID (primary admin)

#### 🔧 Optional Variables (with defaults):
- `ADMIN_ID_2`, `ADMIN_ID_3`, etc. - Additional admin IDs
- `MAX_CONFESSION_LENGTH` - Maximum characters per confession (default: 4000)
- `MAX_COMMENT_LENGTH` - Maximum characters per comment (default: 500)
- `MAX_CONFESSIONS_PER_HOUR` - Rate limit for confessions (default: 5)
- `MAX_COMMENTS_PER_HOUR` - Rate limit for comments (default: 20)
- `LOG_LEVEL` - Logging level (default: INFO)
- `ENABLE_SENTIMENT_ANALYSIS` - Enable sentiment analysis (default: true)
- `ENABLE_PROFANITY_FILTER` - Enable profanity filtering (default: true)

### 2. How to Get Required Values

#### Bot Token:
1. Message @BotFather on Telegram
2. Create a new bot with `/newbot`
3. Copy the token and add it to `BOT_TOKEN` secret

#### Channel ID:
1. Add your bot to the channel as an admin
2. Forward a message from the channel to @userinfobot
3. Copy the channel ID (negative number) and add it to `CHANNEL_ID` secret

#### Admin ID:
1. Message @userinfobot on Telegram
2. Copy your user ID and add it to `ADMIN_ID_1` secret

### 3. Deployment Steps

1. **Import Project**: Upload all files to your Replit project
2. **Set Secrets**: Add all required environment variables in Replit Secrets
3. **Run**: Click the "Run" button - Replit will automatically use `main.py`

### 4. Features

✅ **Core Features:**
- Anonymous confession submission with categories
- Admin approval system
- Comment system with likes/dislikes/replies
- User statistics and ranking system
- Rate limiting and spam protection
- Content moderation and reporting
- Admin dashboard and management tools

✅ **Replit Optimizations:**
- Removed dotenv dependency (uses Replit secrets directly)
- Simplified requirements for faster deployment
- SQLite database (no Redis needed)
- Optimized logging for Replit console

### 5. Bot Commands

**User Commands:**
- `/start` - Start the bot and show main menu
- `/menu` - Return to main menu

**Admin Commands:**
- `/admin` - Show admin panel
- `/stats` - View channel statistics
- `/pending` - View pending submissions
- `/messages` - View user messages to admins
- `/reply <message_id> <reply>` - Reply to user message
- `/reports` - View reported content
- `/users [user_id]` - User management
- `/block <user_id>` - Block a user
- `/unblock <user_id>` - Unblock a user
- `/blocked` - List blocked users

### 6. Important Notes

🔒 **Security**: All secrets are stored securely in Replit and never exposed in the code.

📁 **Database**: Uses SQLite database file (`confessions.db`) which persists in Replit.

🔄 **Updates**: The bot will automatically restart when you make code changes.

📊 **Monitoring**: Check the console for logs and error messages.

### 7. Troubleshooting

❌ **Bot not responding**: Check that all required secrets are set correctly

❌ **Permission errors**: Ensure bot is admin in the channel

❌ **Import errors**: Replit will automatically install dependencies from requirements.txt

📞 **Need help?**: Check the logs in the Replit console for error details
