"""
Notification UI Components for Smart Notifications System
Handles user interfaces for notification preferences and settings
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config import CATEGORIES
from notifications import (
    get_user_preferences, 
    update_user_preferences,
    get_post_subscribers
)
from utils import escape_markdown_text

logger = logging.getLogger(__name__)

async def handle_notification_preferences_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle notification preference callbacks"""
    query = update.callback_query
    await query.answer()
    
    if not query.data:
        return False
    
    data = query.data
    user_id = update.effective_user.id
    
    # Toggle comment notifications
    if data == "toggle_comment_notif":
        await toggle_comment_notifications(update, context)
        return True
    
    # Toggle daily digest
    elif data == "toggle_daily_digest":
        await toggle_daily_digest(update, context)
        return True
    
    # Toggle trending alerts
    elif data == "toggle_trending":
        await toggle_trending_alerts(update, context)
        return True
    
    # Manage favorite categories
    elif data == "manage_categories":
        await show_category_management(update, context)
        return True
    
    # Set digest time
    elif data == "set_digest_time":
        await show_digest_time_options(update, context)
        return True
    
    # Category selection
    elif data.startswith("fav_cat_"):
        await handle_favorite_category_toggle(update, context)
        return True
    
    # Time selection
    elif data.startswith("digest_time_"):
        await handle_digest_time_selection(update, context)
        return True
    
    # Notification history
    elif data == "notification_history":
        await show_notification_history(update, context)
        return True
    
    # Back to notification settings
    elif data == "back_to_notif_settings":
        from notifications import show_notification_settings
        await show_notification_settings(update, context)
        return True
    
    return False

async def toggle_comment_notifications(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Toggle comment notifications setting"""
    user_id = update.effective_user.id
    prefs = get_user_preferences(user_id)
    
    # Toggle the setting
    prefs['comment_notifications'] = not prefs['comment_notifications']
    
    # Update preferences
    success = update_user_preferences(user_id, prefs)
    
    if success:
        status = "enabled" if prefs['comment_notifications'] else "disabled"
        await update.callback_query.answer(f"Comment notifications {status}!")
        
        # Refresh the settings page
        from notifications import show_notification_settings
        await show_notification_settings(update, context)
    else:
        await update.callback_query.answer("❗ Error updating preferences. Please try again.")

async def toggle_daily_digest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Toggle daily digest setting"""
    user_id = update.effective_user.id
    prefs = get_user_preferences(user_id)
    
    # Toggle the setting
    prefs['daily_digest'] = not prefs['daily_digest']
    
    # Update preferences
    success = update_user_preferences(user_id, prefs)
    
    if success:
        status = "enabled" if prefs['daily_digest'] else "disabled"
        await update.callback_query.answer(f"Daily digest {status}!")
        
        # Refresh the settings page
        from notifications import show_notification_settings
        await show_notification_settings(update, context)
    else:
        await update.callback_query.answer("❗ Error updating preferences. Please try again.")

async def toggle_trending_alerts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Toggle trending alerts setting"""
    user_id = update.effective_user.id
    prefs = get_user_preferences(user_id)
    
    # Toggle the setting
    prefs['trending_alerts'] = not prefs['trending_alerts']
    
    # Update preferences
    success = update_user_preferences(user_id, prefs)
    
    if success:
        status = "enabled" if prefs['trending_alerts'] else "disabled"
        await update.callback_query.answer(f"Trending alerts {status}!")
        
        # Refresh the settings page
        from notifications import show_notification_settings
        await show_notification_settings(update, context)
    else:
        await update.callback_query.answer("❗ Error updating preferences. Please try again.")

async def show_category_management(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show favorite category management interface"""
    user_id = update.effective_user.id
    prefs = get_user_preferences(user_id)
    favorite_categories = prefs['favorite_categories']
    
    category_text = """
❤️ *Manage Favorite Categories*

Select categories you want to get notifications for when new posts are approved:

*Current Favorites:*
"""
    
    if favorite_categories:
        for cat in favorite_categories:
            category_text += f"• {escape_markdown_text(cat)}\n"
    else:
        category_text += "None selected\n"
    
    category_text += "\nTap categories to add/remove them:"
    
    # Create keyboard with categories
    keyboard = []
    for i, category in enumerate(CATEGORIES):
        is_favorite = category in favorite_categories
        emoji = "❤️" if is_favorite else "🤍"
        button_text = f"{emoji} {category}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"fav_cat_{i}")])
    
    keyboard.append([
        InlineKeyboardButton("✅ Done", callback_data="back_to_notif_settings"),
        InlineKeyboardButton("🗑️ Clear All", callback_data="clear_all_categories")
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.edit_message_text(
        category_text,
        reply_markup=reply_markup,
        parse_mode="MarkdownV2"
    )

async def handle_favorite_category_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle favorite category toggle"""
    query = update.callback_query
    user_id = update.effective_user.id
    
    # Extract category index
    category_index = int(query.data.replace("fav_cat_", ""))
    category = CATEGORIES[category_index]
    
    # Get current preferences
    prefs = get_user_preferences(user_id)
    favorite_categories = prefs['favorite_categories']
    
    # Toggle category
    if category in favorite_categories:
        favorite_categories.remove(category)
        await query.answer(f"❌ Removed {category}")
    else:
        favorite_categories.append(category)
        await query.answer(f"❤️ Added {category}")
    
    # Update preferences
    prefs['favorite_categories'] = favorite_categories
    success = update_user_preferences(user_id, prefs)
    
    if success:
        # Refresh the category management page
        await show_category_management(update, context)
    else:
        await query.answer("❗ Error updating preferences. Please try again.")

async def show_digest_time_options(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show digest time selection options"""
    user_id = update.effective_user.id
    prefs = get_user_preferences(user_id)
    current_time = prefs['digest_time']
    
    time_text = f"""
⏰ *Set Daily Digest Time*

Current time: {escape_markdown_text(current_time)}

Choose when you'd like to receive your daily digest:
"""
    
    # Time options
    time_options = [
        ("06:00", "🌅 6:00 AM - Early Morning"),
        ("09:00", "☕ 9:00 AM - Morning Coffee"),
        ("12:00", "🕐 12:00 PM - Lunch Break"),
        ("15:00", "☀️ 3:00 PM - Afternoon"),
        ("18:00", "🌆 6:00 PM - Evening"),
        ("21:00", "🌙 9:00 PM - Night"),
        ("00:00", "🌃 12:00 AM - Late Night")
    ]
    
    keyboard = []
    for time_value, time_label in time_options:
        current_marker = " ✅" if time_value == current_time else ""
        button_text = f"{time_label}{current_marker}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"digest_time_{time_value}")])
    
    keyboard.append([
        InlineKeyboardButton("🔙 Back to Settings", callback_data="back_to_notif_settings")
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.edit_message_text(
        time_text,
        reply_markup=reply_markup,
        parse_mode="MarkdownV2"
    )

async def handle_digest_time_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle digest time selection"""
    query = update.callback_query
    user_id = update.effective_user.id
    
    # Extract time
    new_time = query.data.replace("digest_time_", "")
    
    # Get current preferences
    prefs = get_user_preferences(user_id)
    prefs['digest_time'] = new_time
    
    # Update preferences
    success = update_user_preferences(user_id, prefs)
    
    if success:
        await query.answer(f"⏰ Digest time set to {new_time}!")
        
        # Go back to notification settings
        from notifications import show_notification_settings
        await show_notification_settings(update, context)
    else:
        await query.answer("❗ Error updating time. Please try again.")

async def show_notification_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's notification history"""
    user_id = update.effective_user.id
    
    # Get notification history from database
    import sqlite3
    from config import DB_PATH
    
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT notification_type, title, content, sent_at, delivered, clicked,
                   related_post_id, related_comment_id
            FROM notification_history 
            WHERE user_id = ? 
            ORDER BY sent_at DESC 
            LIMIT 10
        ''', (user_id,))
        history = cursor.fetchall()
    
    if not history:
        history_text = """
📊 *Notification History*

No notification history found. 

Start using the bot to receive personalized notifications!
"""
        keyboard = [[InlineKeyboardButton("🔙 Back to Settings", callback_data="back_to_notif_settings")]]
    else:
        history_text = f"""
📊 *Notification History*

Your recent notifications ({len(history)} shown):

"""
        
        for i, (notif_type, title, content, sent_at, delivered, clicked, post_id, comment_id) in enumerate(history, 1):
            # Format notification type
            type_emoji = {
                'comment': '💬',
                'favorite_category': '❤️',
                'trending': '🔥',
                'daily_digest': '📅'
            }.get(notif_type, '🔔')
            
            # Format time
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(sent_at)
                time_str = dt.strftime('%m/%d %H:%M')
            except:
                time_str = sent_at[:16] if sent_at else "Unknown"
            
            # Status indicators
            status = ""
            if delivered:
                status += "✅"
            if clicked:
                status += "👆"
            
            history_text += f"{i}\\. {type_emoji} *{escape_markdown_text(title)}*\n"
            history_text += f"   {escape_markdown_text(time_str)} {status}\n"
            history_text += f"   {escape_markdown_text(content[:50])}{'\\.\\.\\.' if len(content) > 50 else ''}\n\n"
        
        keyboard = [
            [
                InlineKeyboardButton("🔄 Refresh", callback_data="notification_history"),
                InlineKeyboardButton("🗑️ Clear History", callback_data="clear_history")
            ],
            [InlineKeyboardButton("🔙 Back to Settings", callback_data="back_to_notif_settings")]
        ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.edit_message_text(
        history_text,
        reply_markup=reply_markup,
        parse_mode="MarkdownV2"
    )

async def show_notification_menu_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show notification menu when user selects 🔔 Smart Notifications from main menu"""
    user_id = update.effective_user.id if update.effective_user else update.message.from_user.id
    prefs = get_user_preferences(user_id)
    
    # Count active notifications
    active_count = sum([
        prefs['comment_notifications'],
        prefs['daily_digest'],
        prefs['trending_alerts']
    ])
    
    menu_text = f"""
🔔 *Smart Notifications*

Get personalized notifications about:
• 💬 When your confessions get comments
• ❤️ Posts in your favorite categories  
• 📅 Daily/Weekly digest summaries
• 🔥 Trending post alerts

*Current Status:* {active_count}/3 active

Configure your notification preferences:
"""
    
    keyboard = [
        [
            InlineKeyboardButton("⚙️ Notification Settings", callback_data="notification_settings")
        ],
        [
            InlineKeyboardButton("❤️ Favorite Categories", callback_data="manage_categories"),
            InlineKeyboardButton("📊 History", callback_data="notification_history")
        ],
        [
            InlineKeyboardButton("🔔 Test Notification", callback_data="test_notification"),
            InlineKeyboardButton("🏠 Main Menu", callback_data="menu")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if hasattr(update, 'callback_query') and update.callback_query:
        await update.callback_query.edit_message_text(
            menu_text,
            reply_markup=reply_markup,
            parse_mode="MarkdownV2"
        )
    else:
        await update.message.reply_text(
            menu_text,
            reply_markup=reply_markup,
            parse_mode="MarkdownV2"
        )

async def send_test_notification(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a test notification to user"""
    query = update.callback_query
    user_id = update.effective_user.id
    
    from notifications import send_notification
    
    # Create test notification
    title = "Test Notification"
    content = "This is a test notification to verify your settings are working correctly! 🎉"
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Working Great!", callback_data="back_to_notif_settings")]
    ])
    
    success = await send_notification(
        context, user_id, "test", title, content, keyboard=keyboard
    )
    
    if success:
        await query.answer("✅ Test notification sent!")
        await query.edit_message_text(
            "🔔 *Test Notification Sent!*\n\nCheck if you received the test notification\\. If not, please check your Telegram notification settings\\.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back to Settings", callback_data="back_to_notif_settings")]
            ]),
            parse_mode="MarkdownV2"
        )
    else:
        await query.answer("❗ Failed to send test notification")

async def handle_clear_all_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Clear all favorite categories"""
    user_id = update.effective_user.id
    prefs = get_user_preferences(user_id)
    prefs['favorite_categories'] = []
    
    success = update_user_preferences(user_id, prefs)
    if success:
        await update.callback_query.answer("🗑️ All categories cleared!")
        await show_category_management(update, context)
    else:
        await update.callback_query.answer("❗ Error clearing categories")

async def handle_clear_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Clear notification history"""
    user_id = update.effective_user.id
    
    try:
        import sqlite3
        from config import DB_PATH
        
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM notification_history WHERE user_id = ?', (user_id,))
            conn.commit()
        
        await update.callback_query.answer("🗑️ History cleared!")
        await show_notification_history(update, context)
    except Exception as e:
        logger.error(f"Error clearing notification history: {e}")
        await update.callback_query.answer("❗ Error clearing history")

# Export functions for use in main bot
__all__ = [
    'handle_notification_preferences_callback',
    'show_notification_menu_item',
    'send_test_notification',
    'handle_clear_all_categories',
    'handle_clear_history'
]
