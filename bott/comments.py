import sqlite3
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from config import DB_PATH, COMMENTS_PER_PAGE, CHANNEL_ID, BOT_USERNAME
from utils import escape_markdown_text
from db import get_comment_count
from submission import is_media_post, get_media_info

def save_comment(post_id, content, user_id, parent_comment_id=None):
    """Save a comment to the database"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO comments (post_id, content, user_id, parent_comment_id) VALUES (?, ?, ?, ?)",
                (post_id, content, user_id, parent_comment_id)
            )
            comment_id = cursor.lastrowid
            
            # Update user stats
            cursor.execute(
                "UPDATE users SET comments_posted = comments_posted + 1 WHERE user_id = ?",
                (user_id,)
            )
            conn.commit()
            return comment_id, None
    except Exception as e:
        return None, f"Database error: {str(e)}"

def get_post_with_channel_info(post_id):
    """Get post information including channel message ID"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT post_id, content, category, channel_message_id, approved FROM posts WHERE post_id = ?",
            (post_id,)
        )
        return cursor.fetchone()

def get_comments_paginated(post_id, page=1):
    """Get comments for a post with pagination (parent comments only)"""
    offset = (page - 1) * COMMENTS_PER_PAGE
    
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        
        # Get total count of parent comments
        cursor.execute(
            "SELECT COUNT(*) FROM comments WHERE post_id = ? AND parent_comment_id IS NULL",
            (post_id,)
        )
        total_comments = cursor.fetchone()[0]
        
        # Get paginated parent comments with row numbers for sequential numbering
        cursor.execute('''
            SELECT comment_id, content, timestamp, likes, dislikes, flagged,
                   ROW_NUMBER() OVER (ORDER BY timestamp ASC) as comment_number
            FROM comments 
            WHERE post_id = ? AND parent_comment_id IS NULL 
            ORDER BY timestamp ASC
            LIMIT ? OFFSET ?
        ''', (post_id, COMMENTS_PER_PAGE, offset))
        
        comments = cursor.fetchall()
        
        # For each comment, get its replies with sequential reply numbering
        comments_with_replies = []
        for comment in comments:
            comment_id = comment[0]
            cursor.execute('''
                SELECT comment_id, content, timestamp, likes, dislikes,
                       ROW_NUMBER() OVER (ORDER BY timestamp ASC) as reply_number
                FROM comments 
                WHERE parent_comment_id = ? 
                ORDER BY timestamp ASC
                LIMIT 3
            ''', (comment_id,))
            replies = cursor.fetchall()
            
            # Count total replies
            cursor.execute(
                "SELECT COUNT(*) FROM comments WHERE parent_comment_id = ?",
                (comment_id,)
            )
            total_replies = cursor.fetchone()[0]
            
            comments_with_replies.append({
                'comment': comment,
                'replies': replies,
                'total_replies': total_replies
            })
        
        total_pages = (total_comments + COMMENTS_PER_PAGE - 1) // COMMENTS_PER_PAGE
        
        return comments_with_replies, page, total_pages, total_comments

def get_comment_by_id(comment_id):
    """Get a specific comment by ID"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM comments WHERE comment_id = ?",
            (comment_id,)
        )
        return cursor.fetchone()

def react_to_comment(user_id, comment_id, reaction_type):
    """Add or update reaction to a comment"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            # Check existing reaction
            cursor.execute(
                "SELECT reaction_type FROM reactions WHERE user_id = ? AND target_type = 'comment' AND target_id = ?",
                (user_id, comment_id)
            )
            existing = cursor.fetchone()
            
            if existing:
                if existing[0] == reaction_type:
                    # Remove reaction if same type
                    cursor.execute(
                        "DELETE FROM reactions WHERE user_id = ? AND target_type = 'comment' AND target_id = ?",
                        (user_id, comment_id)
                    )
                    # Update comment counts
                    if reaction_type == 'like':
                        cursor.execute(
                            "UPDATE comments SET likes = likes - 1 WHERE comment_id = ?",
                            (comment_id,)
                        )
                    else:
                        cursor.execute(
                            "UPDATE comments SET dislikes = dislikes - 1 WHERE comment_id = ?",
                            (comment_id,)
                        )
                    action = "removed"
                else:
                    # Update reaction type
                    cursor.execute(
                        "UPDATE reactions SET reaction_type = ? WHERE user_id = ? AND target_type = 'comment' AND target_id = ?",
                        (reaction_type, user_id, comment_id)
                    )
                    # Update comment counts
                    if existing[0] == 'like':
                        cursor.execute(
                            "UPDATE comments SET likes = likes - 1, dislikes = dislikes + 1 WHERE comment_id = ?",
                            (comment_id,)
                        )
                    else:
                        cursor.execute(
                            "UPDATE comments SET likes = likes + 1, dislikes = dislikes - 1 WHERE comment_id = ?",
                            (comment_id,)
                        )
                    action = "changed"
            else:
                # Add new reaction
                cursor.execute(
                    "INSERT INTO reactions (user_id, target_type, target_id, reaction_type) VALUES (?, 'comment', ?, ?)",
                    (user_id, comment_id, reaction_type)
                )
                # Update comment counts
                if reaction_type == 'like':
                    cursor.execute(
                        "UPDATE comments SET likes = likes + 1 WHERE comment_id = ?",
                        (comment_id,)
                    )
                else:
                    cursor.execute(
                        "UPDATE comments SET dislikes = dislikes + 1 WHERE comment_id = ?",
                        (comment_id,)
                    )
                action = "added"
            
            conn.commit()
            
            # Return current counts along with action
            cursor.execute(
                "SELECT likes, dislikes FROM comments WHERE comment_id = ?",
                (comment_id,)
            )
            counts = cursor.fetchone()
            current_likes = counts[0] if counts else 0
            current_dislikes = counts[1] if counts else 0
            
            return True, action, current_likes, current_dislikes
    except Exception as e:
        return False, str(e), 0, 0

def flag_comment(comment_id):
    """Flag a comment for review"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE comments SET flagged = 1 WHERE comment_id = ?", (comment_id,))
        conn.commit()

def get_user_reaction(user_id, comment_id):
    """Get user's reaction to a specific comment"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT reaction_type FROM reactions WHERE user_id = ? AND target_type = 'comment' AND target_id = ?",
            (user_id, comment_id)
        )
        result = cursor.fetchone()
        return result[0] if result else None

def get_comment_sequential_number(comment_id):
    """Get the sequential number of a comment within its post"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        
        # First get the comment's post_id and check if it's a reply
        cursor.execute(
            "SELECT post_id, parent_comment_id FROM comments WHERE comment_id = ?",
            (comment_id,)
        )
        comment_info = cursor.fetchone()
        
        if not comment_info:
            return None
        
        post_id, parent_comment_id = comment_info
        
        if parent_comment_id:  # This is a reply
            # Get the sequential reply number within the parent comment
            cursor.execute("""
                SELECT COUNT(*) FROM comments 
                WHERE parent_comment_id = ? AND comment_id <= ?
                ORDER BY timestamp ASC
            """, (parent_comment_id, comment_id))
            result = cursor.fetchone()
            return result[0] if result else 1
        else:  # This is a main comment
            # Get the sequential comment number within the post
            cursor.execute("""
                SELECT COUNT(*) FROM comments 
                WHERE post_id = ? AND parent_comment_id IS NULL AND comment_id <= ?
                ORDER BY timestamp ASC
            """, (post_id, comment_id))
            result = cursor.fetchone()
            return result[0] if result else 1

def get_parent_comment_for_reply(comment_id):
    """Get the parent comment details for a reply comment"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        
        # Get the reply comment details
        cursor.execute(
            "SELECT parent_comment_id FROM comments WHERE comment_id = ?",
            (comment_id,)
        )
        result = cursor.fetchone()
        
        if not result or not result[0]:
            return None  # Not a reply
        
        parent_comment_id = result[0]
        
        # Get the parent comment details
        cursor.execute(
            "SELECT comment_id, post_id, content, timestamp FROM comments WHERE comment_id = ?",
            (parent_comment_id,)
        )
        parent_comment = cursor.fetchone()
        
        if parent_comment:
            # Get the sequential number of the parent comment
            parent_sequential_number = get_comment_sequential_number(parent_comment_id)
            return {
                'comment_id': parent_comment[0],
                'post_id': parent_comment[1],
                'content': parent_comment[2],
                'timestamp': parent_comment[3],
                'sequential_number': parent_sequential_number
            }
        
        return None

async def update_channel_message_comment_count(context, post_id):
    """Update the comment count on the channel message"""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        # Get post info including channel message ID and post_number
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT post_id, content, category, channel_message_id, approved, post_number FROM posts WHERE post_id = ?",
                (post_id,)
            )
            post_info = cursor.fetchone()
        
        if not post_info or not post_info[3]:  # No channel_message_id
            return False, "No channel message found"
        
        post_id, content, category, channel_message_id, approved, post_number = post_info
        
        if approved != 1:  # Not approved
            return False, "Post not approved"
        
        # Get current comment count
        comment_count = get_comment_count(post_id)
        
        # Create updated inline buttons with new comment count
        # Strip @ symbol from BOT_USERNAME for URL
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
        
        # ✅ Preserve the original post structure format exactly like approval.py
        # Convert categories into hashtags
        categories_text = " ".join(
            [f"#{cat.strip().replace(' ', '')}" for cat in category.split(",")]
        )
        
        # Check if this is a media post
        if is_media_post(post_id):
            # Get media information
            media_info = get_media_info(post_id)
            
            if media_info:
                # Prepare caption with post number, text content, and hashtags (same as approval.py)
                caption_text = f"<b>Confess # {post_number}</b>"
                
                # Add text content if available
                if content and content.strip():
                    caption_text += f"\n\n{content}"
                
                # Add media caption if available and different from main content
                if media_info.get('caption') and media_info['caption'] != content:
                    caption_text += f"\n\n{media_info['caption']}"
                
                # Add hashtags
                caption_text += f"\n\n{categories_text}"
                
                # Update media message caption
                await context.bot.edit_message_caption(
                    chat_id=CHANNEL_ID,
                    message_id=channel_message_id,
                    caption=caption_text,
                    parse_mode="HTML",
                    reply_markup=reply_markup
                )
            else:
                # Media info not found, try as text message fallback
                await context.bot.edit_message_text(
                    chat_id=CHANNEL_ID,
                    message_id=channel_message_id,
                    text=f"<b>Confess # {post_number}</b>\n\n{content}\n\n{categories_text}",
                    parse_mode="HTML",
                    reply_markup=reply_markup
                )
        else:
            # Text-only post - use edit_message_text
            await context.bot.edit_message_text(
                chat_id=CHANNEL_ID,
                message_id=channel_message_id,
                text=f"<b>Confess # {post_number}</b>\n\n{content}\n\n{categories_text}",
                parse_mode="HTML",
                reply_markup=reply_markup
            )
        
        return True, f"Updated comment count to {comment_count}"
    
    except Exception as e:
        return False, f"Failed to update channel message: {str(e)}"
