# 🚀 Render Deployment Guide for Telegram Bot

## 📋 Pre-deployment Checklist

✅ **Project Structure Optimized**
- Removed unnecessary development files
- Updated `.gitignore` for production
- Configured web service wrapper (`bot_web.py`)
- Created `Procfile` for deployment

✅ **Configuration Files Ready**
- `render.yaml` - Configured as web service for free 24/7 hosting
- `requirements.txt` - All dependencies included
- `runtime.txt` - Python 3.11.8 specified
- `bot_web.py` - Web service wrapper with health checks

## 🔧 Required Environment Variables

Set these in your Render service dashboard:

### Critical Variables (Required)
```
BOT_TOKEN=your_telegram_bot_token_from_botfather
CHANNEL_ID=your_telegram_channel_id_number
BOT_USERNAME=your_bot_username_without_@
ADMIN_ID_1=your_telegram_user_id_as_admin
```

### Optional Variables (Recommended)
```
PORT=10000
LOG_LEVEL=INFO
MAX_CONFESSIONS_PER_HOUR=5
MAX_COMMENTS_PER_HOUR=20
ENABLE_SENTIMENT_ANALYSIS=true
ENABLE_PROFANITY_FILTER=true
```

## 📦 Deployment Steps

### 1. Create Render Account
- Go to [render.com](https://render.com)
- Sign up with GitHub (recommended)

### 2. Connect GitHub Repository
- Push your code to a GitHub repository
- Connect the repository to Render

### 3. Create Web Service
- Click "New +" → "Web Service"
- Select your repository
- Choose these settings:
  - **Service Type**: Web Service
  - **Environment**: Python 3
  - **Region**: Choose closest to your users
  - **Branch**: main (or master)
  - **Build Command**: `pip install -r requirements.txt`
  - **Start Command**: `python bot_web.py`

### 4. Set Environment Variables
- In the Render dashboard, go to "Environment"
- Add all required environment variables listed above

### 5. Deploy
- Click "Create Web Service"
- Wait for deployment to complete (5-10 minutes)

## 🔍 How to Get Required Values

### BOT_TOKEN
1. Message [@BotFather](https://t.me/botfather) on Telegram
2. Create a new bot: `/newbot`
3. Copy the token provided

### CHANNEL_ID
1. Create a Telegram channel
2. Add your bot as admin
3. Forward a message from the channel to [@userinfobot](https://t.me/userinfobot)
4. Copy the channel ID (will be negative number)

### ADMIN_ID_1
1. Message [@userinfobot](https://t.me/userinfobot)
2. Copy your user ID

### BOT_USERNAME
- The username you set for your bot (without @)

## 🌐 After Deployment

### Health Checks
Your bot will be available at:
- `https://your-service-name.onrender.com/` - Main health check
- `https://your-service-name.onrender.com/health` - Detailed status
- `https://your-service-name.onrender.com/ping` - Simple ping

### Monitoring
- Check Render logs for any errors
- Test bot functionality in Telegram
- Monitor the health check endpoints

## 🆓 Free Tier Limitations

**Render Free Tier:**
- ✅ 24/7 uptime for web services
- ✅ 750 hours/month (more than enough)
- ⚠️ Service may sleep after 15 minutes of inactivity
- ⚠️ 512 MB RAM limit
- ⚠️ Slower build times

**Important:** The web service approach keeps your bot running 24/7 for free by maintaining an HTTP endpoint.

## 🔧 Troubleshooting

### Common Issues:
1. **Build fails**: Check requirements.txt for conflicting versions
2. **Bot doesn't respond**: Verify environment variables are set correctly
3. **Service crashes**: Check logs in Render dashboard
4. **Database issues**: SQLite works fine for small/medium bots

### Support Resources:
- Render Documentation: [docs.render.com](https://docs.render.com)
- Telegram Bot API: [core.telegram.org/bots/api](https://core.telegram.org/bots/api)

## 📝 Final Notes

- Your bot data will persist across deployments
- Free tier includes automatic SSL certificates
- Render provides automatic deployments on git push
- Monitor your bot through the health endpoints and Render dashboard
