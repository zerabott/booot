import sqlite3
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import ADMIN_IDS, CHANNEL_ID, BOT_USERNAME, DB_PATH
from db import get_comment_count
from submission import get_post_with_media, is_media_post, get_media_info, get_media_type_emoji

# Import ranking system integration
from ranking_integration import award_points_for_confession_approval, RankingIntegration

def approve_post(post_id, message_id, post_number):
    """Approve a post and save channel message ID with sequential post number"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE posts SET approved=1, channel_message_id=?, post_number=? WHERE post_id=?",
            (message_id, post_number, post_id)
        )
        conn.commit()

def reject_post(post_id):
    """Reject a post"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE posts SET approved=0 WHERE post_id=?", (post_id,))
        conn.commit()

def get_next_post_number():
    """Get the next sequential post number for approved posts"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(post_number) FROM posts WHERE post_number IS NOT NULL")
        result = cursor.fetchone()
        return (result[0] + 1) if result[0] is not None else 1

def flag_post(post_id):
    """Flag a post for review"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE posts SET flagged=1 WHERE post_id=?", (post_id,))
        conn.commit()

def block_user(user_id):
    """Block a user"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET blocked=1 WHERE user_id=?", (user_id,))
        conn.commit()

def unblock_user(user_id):
    """Unblock a user"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET blocked=0 WHERE user_id=?", (user_id,))
        conn.commit()

def get_post_by_id(post_id):
    """Get a specific post by ID"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM posts WHERE post_id=?", (post_id,))
        return cursor.fetchone()

def is_blocked_user(user_id):
    """Check if user is blocked"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT blocked FROM users WHERE user_id=?", (user_id,))
        result = cursor.fetchone()
        return result and result[0] == 1

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle admin approval/rejection callbacks"""
    if not update or not update.callback_query:
        return
    
    query = update.callback_query
    await query.answer()
    
    if not query or not query.data:
        return
    
    data = query.data
    admin_id = None
    if update and update.effective_user:
        admin_id = update.effective_user.id
    
    if admin_id not in ADMIN_IDS:
        try:
            await query.edit_message_text("❗ You are not authorized to moderate.")
        except:
            pass
        return

    if data.startswith("approve_"):
        post_id = int(data.split("_")[1])
        post = get_post_by_id(post_id)
        if not post:
            try:
                await query.edit_message_text("❗ Post not found.")
            except:
                pass
            return
        
        # Check if post is already approved (prevent duplicate approvals)
        # Use safe indexing to avoid index out of range errors
        if len(post) > 5 and post[5] == 1:  # approved field is at index 5
            try:
                await query.edit_message_text(
                    "✅ Approved by another admin\\!\n\n"
                    "This post was already approved by a different admin\\. "
                    "You can still view it in the channel\\.",
                    parse_mode="MarkdownV2"
                )
            except:
                pass
            return
        
        # Check if post is already rejected
        if len(post) > 5 and post[5] == 0:  # approved field is at index 5
            try:
                await query.edit_message_text(
                    "❌ Already rejected\\!\n\n"
                    "This post was already rejected by a different admin\\. "
                    "No further action is needed\\.",
                    parse_mode="MarkdownV2"
                )
            except:
                pass
            return
        
        # Get submitter info
        submitter_id = post[4]  # user_id is at index 4
        category = post[2]  # category is at index 2
        
        # Initialize post_number to None
        post_number = None
        
        try:
            # Get the next sequential post number
            post_number = get_next_post_number()
            
            # Get current comment count
            comment_count = get_comment_count(post_id)
            
            # Create inline buttons for the channel post
            bot_username_clean = BOT_USERNAME.lstrip('@')
            keyboard = [
                [
                    InlineKeyboardButton(
                        "💬 Add Comment", 
                        url=f"https://t.me/{bot_username_clean}?start=comment_{post_id}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        f"👀 See Comments ({comment_count})", 
                        url=f"https://t.me/{bot_username_clean}?start=view_{post_id}"
                    )
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Convert categories into hashtags
            categories = post[2]  # category is at index 2
            # Create the category hashtags
            categories_text = " ".join(
                [f"#{cat.strip().replace(' ', '')}" for cat in categories.split(",")]
            )
            
            # Check if this is a media post
            is_media = False
            media_info = None
            
            # Get media information
            media_info = get_media_info(post_id)
            if media_info:
                is_media = True
            
            # Award points for approved confession
            submitter_id = post[4]  # user_id is at index 4
            
            # Try to post to the channel
            # Initialize variables
            content = post[1]  # content is at index 1
            msg = None
            
            # Check if this is a media post
            if is_media and media_info:
                # Prepare caption with post number, text content, and hashtags
                caption_text = f"<b>Confess # {post_number}</b>\n\n"
                
                # Add text content if available
                if content and content.strip():
                
                    caption_text += f"{content}\n\n"
                
                # Add media caption if available and different from main content
                if media_info.get('caption') and media_info['caption'] != content:
                    caption_text += f"{media_info['caption']}\n\n"
                
                # Add hashtags
                caption_text += categories_text
                
                # Send media message based on type
                if media_info['type'] == 'photo':
                    msg = await context.bot.send_photo(
                        chat_id=CHANNEL_ID,
                        photo=media_info['file_id'],
                        caption=caption_text,
                        parse_mode="HTML",
                        reply_markup=reply_markup
                    )
                elif media_info['type'] == 'video':
                    msg = await context.bot.send_video(
                        chat_id=CHANNEL_ID,
                        video=media_info['file_id'],
                        caption=caption_text,
                        parse_mode="HTML",
                        reply_markup=reply_markup
                    )
                elif media_info['type'] == 'animation':
                    msg = await context.bot.send_animation(
                        chat_id=CHANNEL_ID,
                        animation=media_info['file_id'],
                        caption=caption_text,
                        parse_mode="HTML",
                        reply_markup=reply_markup
                    )
                else:
                    # Fallback to text message if media type is not supported
                    msg = await context.bot.send_message(
                        chat_id=CHANNEL_ID,
                        text=f"<b>Confess # {post_number}</b>\n\n"
                            f"<i>[Media type '{media_info['type']}' not supported]</i>\n\n"
                            f"{content}\n\n"
                            f"{categories_text}",
                        parse_mode="HTML",
                        reply_markup=reply_markup
                    )
            else:
                # Media info not found, fallback to text
                msg = await context.bot.send_message(
                    chat_id=CHANNEL_ID,
                    text=f"<b>Confess # {post_number}</b>\n\n"
                        f"<i>[Media not available]</i>\n\n"
                        f"{content}\n\n"
                        f"{categories_text}",
                    parse_mode="HTML",
                    reply_markup=reply_markup
                )
            
            # Update the post with the channel message ID and post number
            if msg:
                approve_post(post_id, msg.message_id, post_number)
                
            try:
                await query.edit_message_text(f"✅ Approved and posted to channel as Post #{post_number}.")
            except:
                pass
            
            # Award points for approved confession
            if admin_id is not None:
                await award_points_for_confession_approval(submitter_id, post_id, admin_id, context)
            
            # Notify the submitter with media support
            if submitter_id:
                try:
                    # Import escape function for proper markdown formatting
                    from utils import escape_markdown_text
                    
                    # Determine confession type for notification
                    confession_type = "confession"
                    if is_media and media_info:
                        media_type_name = media_info['type'].title()
                        emoji = get_media_type_emoji(media_info['type'])
                        confession_type = f"{emoji} {media_type_name} confession"
                    
                    # Generate proper channel link if possible
                    channel_link_text = f"[View in Channel](https://t.me/c/{abs(CHANNEL_ID)}/{msg.message_id})" if msg and CHANNEL_ID < 0 else "Check the channel"
                    
                    # Build the notification message with proper escaping
                    message_text = f"""
✅ *{confession_type.title()} Approved\\!*

Your {escape_markdown_text(confession_type)} in category `{escape_markdown_text(category)}` has been approved and posted to the channel\\!

🔢 *Post Number:* \\#{post_number}

💡 {channel_link_text}

🌟 *Thank you for sharing with us\\!*
"""
                    
                    # Create keyboard with helpful buttons
                    keyboard = [
                        [InlineKeyboardButton("🆕 Submit New Confession", callback_data="start_confession")],
                        [InlineKeyboardButton("📋 View My Stats", callback_data="my_stats")],
                        [InlineKeyboardButton("🏠 Main Menu", callback_data="menu")]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    # Send notification with proper formatting
                    await context.bot.send_message(
                        chat_id=submitter_id,
                        text=message_text,
                        parse_mode="MarkdownV2",
                        reply_markup=reply_markup,
                        disable_web_page_preview=False
                    )
                except Exception as e:
                    logging.warning(f"Could not notify user {submitter_id}: {e}")
                    
        except Exception as e:
            logging.error(f"Failed to post to channel: {e}")
            try:
                await query.edit_message_text(f"❗ Failed to post to channel: {e}")
            except:
                pass

    elif data.startswith("reject_"):
        # Get post details
        post_id = int(data.split("_")[1])
        post = get_post_by_id(post_id)
        if not post:
            try:
                await query.edit_message_text("❗ Post not found.")
            except:
                pass
            return
        
        # Check if post is already rejected (prevent duplicate rejections)
        # Use safe indexing to avoid index out of range errors
        if len(post) > 5 and post[5] == 0:  # approved field is at index 5
            try:
                # Get post number if it exists
                post_number = None
                try:
                    post_number = get_next_post_number()
                except:
                    pass
                
                await query.edit_message_text(
                    f"❌ This post has already been rejected by another admin\\. \nYou can still view it in the channel as post #{post_number if post_number is not None else 'unknown'}\\.",
                    parse_mode="MarkdownV2"
                )
            except:
                pass
            return

        # Check if post is already approved
        if len(post) > 5 and post[5] == 1:  # approved field is at index 5
            try:
                # Get post number if it exists
                post_number = None
                try:
                    post_number = get_next_post_number()
                except:
                    pass
                
                await query.edit_message_text(
                    f"✅ Already approved by another admin\\!\n\nThis post was already approved and posted to the channel as post #{post_number if post_number is not None else 'unknown'}\\.",
                    parse_mode="MarkdownV2"
                )
            except:
                pass
            return
        
        # Get submitter info
        submitter_id = post[4]  # user_id is at index 4
        category = post[2]  # category is at index 2
        
        # Reject the post
        reject_post(post_id)
        
        try:
            await query.edit_message_text("❌ Submission rejected.")
        except:
            pass
        
        # Deduct points for rejected confession
        if update and update.effective_user and query and query.data and admin_id is not None:
            await RankingIntegration.handle_confession_rejected(submitter_id, post_id, admin_id)
        
        # Notify the submitter
        if submitter_id:
            try:
                await context.bot.send_message(
                    chat_id=submitter_id,
                    text=f"❌ Your confession in category <b>{category}</b> was rejected by the admins.",
                    parse_mode="HTML"
                )
            except Exception as e:
                logging.warning(f"Could not notify user {submitter_id}: {e}")

    elif data.startswith("flag_"):
        # Handle flagging
        post_id = int(data.split("_")[1])
        flag_post(post_id)
        
        try:
            await query.edit_message_text("🚩 Submission flagged for review.")
        except:
            pass

    elif data.startswith("block_"):
        # Handle blocking
        block_uid = int(data.split("_")[1])
        block_user(block_uid)
        
        try:
            await query.edit_message_text(f"⛔ User {block_uid} blocked.")
        except:
            pass

    elif data.startswith("unblock_"):
        # Handle unblocking
        block_uid = int(data.split("_")[1])
        unblock_user(block_uid)
        
        try:
            await query.edit_message_text(f"✅ User {block_uid} unblocked.")
        except:
            pass

    # Handle other cases
