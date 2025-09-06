"""
Admin Deletion Functions
Handles permanent deletion of posts, comments, and associated data
"""

import sqlite3
import logging
from datetime import datetime
from db import DB_PATH, get_db
from config import CHANNEL_ID

logger = logging.getLogger(__name__)

def delete_post_completely(post_id: int, admin_user_id: int) -> tuple[bool, dict]:
    """
    Completely delete a post and all associated data including:
    - Comments and their replies
    - All reactions on comments
    - All reports related to the post and its comments
    - The post itself
    
    Returns (success, deletion_stats)
    """
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # First, verify the post exists and get its details
        cursor.execute("SELECT post_id, content, category, approved, channel_message_id FROM posts WHERE post_id = ?", (post_id,))
        post_data = cursor.fetchone()
        
        if not post_data:
            return False, f"Post #{post_id} not found"
        
        post_id_db, content, category, approved, channel_message_id = post_data
        
        # Start transaction
        cursor.execute("BEGIN TRANSACTION")
        
        try:
            # Get all comment IDs associated with this post (including replies)
            cursor.execute("SELECT comment_id FROM comments WHERE post_id = ?", (post_id,))
            comment_ids = [row[0] for row in cursor.fetchall()]
            
            deletion_stats = {
                'comments_deleted': len(comment_ids),
                'reactions_deleted': 0,
                'reports_deleted': 0
            }
            
            if comment_ids:
                # Delete all reactions on these comments (from reactions table)
                placeholders = ','.join(['?' for _ in comment_ids])
                cursor.execute(f"SELECT COUNT(*) FROM reactions WHERE target_type = 'comment' AND target_id IN ({placeholders})", comment_ids)
                reactions_count = cursor.fetchone()[0]
                deletion_stats['reactions_deleted'] = reactions_count
                
                cursor.execute(f"DELETE FROM reactions WHERE target_type = 'comment' AND target_id IN ({placeholders})", comment_ids)
                
                # Delete all reports on these comments
                cursor.execute(f"SELECT COUNT(*) FROM reports WHERE target_type = 'comment' AND target_id IN ({placeholders})", comment_ids)
                comment_reports_count = cursor.fetchone()[0]
                deletion_stats['reports_deleted'] += comment_reports_count
                
                cursor.execute(f"DELETE FROM reports WHERE target_type = 'comment' AND target_id IN ({placeholders})", comment_ids)
                
                # Delete all comments
                cursor.execute("DELETE FROM comments WHERE post_id = ?", (post_id,))
            
            # Delete reports on the post itself
            cursor.execute("SELECT COUNT(*) FROM reports WHERE target_type = 'post' AND target_id = ?", (post_id,))
            post_reports_count = cursor.fetchone()[0]
            deletion_stats['reports_deleted'] += post_reports_count
            
            cursor.execute("DELETE FROM reports WHERE target_type = 'post' AND target_id = ?", (post_id,))
            
            # Delete any reactions on the post (if they exist)
            cursor.execute("DELETE FROM reactions WHERE target_type = 'post' AND target_id = ?", (post_id,))
            
            # Finally, delete the post itself
            cursor.execute("DELETE FROM posts WHERE post_id = ?", (post_id,))
            
            # Log the deletion action
            log_admin_deletion(
                admin_user_id=admin_user_id,
                action_type="DELETE_POST",
                target_type="post",
                target_id=post_id,
                details={
                    "content_preview": content[:100] + "..." if len(content) > 100 else content,
                    "category": category,
                    "was_approved": bool(approved),
                    "channel_message_id": channel_message_id,
                    "deletion_stats": deletion_stats,
                    "reason": "Admin deletion"
                }
            )
            
            # Commit the transaction
            cursor.execute("COMMIT")
            conn.close()
            
            success_msg = f"Post #{post_id} completely deleted:\n"
            success_msg += f"• Post deleted\n"
            success_msg += f"• {deletion_stats['comments_deleted']} comments deleted\n"
            success_msg += f"• {deletion_stats['reactions_deleted']} reactions deleted\n"
            success_msg += f"• {deletion_stats['reports_deleted']} reports deleted"
            
            return True, deletion_stats
            
        except Exception as e:
            cursor.execute("ROLLBACK")
            conn.close()
            logger.error(f"Error during post deletion transaction: {e}")
            return False, f"Database error during deletion: {str(e)}"
            
    except Exception as e:
        logger.error(f"Error deleting post {post_id}: {e}")
        return False, f"Error deleting post: {str(e)}"


def delete_comment_completely(comment_id: int, admin_user_id: int) -> tuple[bool, dict]:
    """
    Completely delete a comment and all associated data including:
    - All replies to this comment
    - All reactions on the comment and its replies
    - All reports related to the comment and its replies
    
    Returns (success, deletion_stats)
    """
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # First, verify the comment exists and get its details
        cursor.execute("SELECT comment_id, post_id, content, parent_comment_id FROM comments WHERE comment_id = ?", (comment_id,))
        comment_data = cursor.fetchone()
        
        if not comment_data:
            return False, f"Comment #{comment_id} not found"
        
        comment_id_db, post_id, content, parent_comment_id = comment_data
        
        # Start transaction
        cursor.execute("BEGIN TRANSACTION")
        
        try:
            deletion_stats = {
                'comments_deleted': 1,  # The main comment
                'replies_deleted': 0,
                'reactions_deleted': 0,
                'reports_deleted': 0
            }
            
            # Get all reply IDs to this comment
            cursor.execute("SELECT comment_id FROM comments WHERE parent_comment_id = ?", (comment_id,))
            reply_ids = [row[0] for row in cursor.fetchall()]
            deletion_stats['replies_deleted'] = len(reply_ids)
            
            # Collect all comment IDs that will be deleted (main comment + replies)
            all_comment_ids = [comment_id] + reply_ids
            
            if all_comment_ids:
                # Delete all reactions on these comments (from reactions table)
                placeholders = ','.join(['?' for _ in all_comment_ids])
                cursor.execute(f"SELECT COUNT(*) FROM reactions WHERE target_type = 'comment' AND target_id IN ({placeholders})", all_comment_ids)
                reactions_count = cursor.fetchone()[0]
                deletion_stats['reactions_deleted'] = reactions_count
                
                cursor.execute(f"DELETE FROM reactions WHERE target_type = 'comment' AND target_id IN ({placeholders})", all_comment_ids)
                
                # Delete all reports on these comments
                cursor.execute(f"SELECT COUNT(*) FROM reports WHERE target_type = 'comment' AND target_id IN ({placeholders})", all_comment_ids)
                reports_count = cursor.fetchone()[0]
                deletion_stats['reports_deleted'] = reports_count
                
                cursor.execute(f"DELETE FROM reports WHERE target_type = 'comment' AND target_id IN ({placeholders})", all_comment_ids)
                
                # Delete all replies first
                if reply_ids:
                    cursor.execute("DELETE FROM comments WHERE parent_comment_id = ?", (comment_id,))
                
                # Delete the main comment
                cursor.execute("DELETE FROM comments WHERE comment_id = ?", (comment_id,))
            
            # Log the deletion action
            log_admin_deletion(
                admin_user_id=admin_user_id,
                action_type="DELETE_COMMENT",
                target_type="comment",
                target_id=comment_id,
                details={
                    "post_id": post_id,
                    "content_preview": content[:100] + "..." if len(content) > 100 else content,
                    "is_reply": bool(parent_comment_id),
                    "parent_comment_id": parent_comment_id,
                    "deletion_stats": deletion_stats,
                    "reason": "Admin deletion"
                }
            )
            
            # Commit the transaction
            cursor.execute("COMMIT")
            conn.close()
            
            return True, deletion_stats
            
        except Exception as e:
            cursor.execute("ROLLBACK")
            conn.close()
            logger.error(f"Error during comment deletion transaction: {e}")
            return False, f"Database error during deletion: {str(e)}"
            
    except Exception as e:
        logger.error(f"Error deleting comment {comment_id}: {e}")
        return False, f"Error deleting comment: {str(e)}"


def log_admin_deletion(admin_user_id: int, action_type: str, target_type: str, target_id: int, details: dict):
    """
    Log admin deletion actions for audit purposes
    """
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Create admin_actions table if it doesn't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS admin_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_user_id INTEGER NOT NULL,
                action_type TEXT NOT NULL,
                target_type TEXT NOT NULL,
                target_id INTEGER NOT NULL,
                details TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Insert the log entry
        import json
        cursor.execute("""
            INSERT INTO admin_actions (admin_user_id, action_type, target_type, target_id, details)
            VALUES (?, ?, ?, ?, ?)
        """, (admin_user_id, action_type, target_type, target_id, json.dumps(details)))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Admin {admin_user_id} performed {action_type} on {target_type} #{target_id}")
        
    except Exception as e:
        logger.error(f"Error logging admin deletion: {e}")


def get_post_details_for_deletion(post_id: int) -> dict:
    """
    Get post details for deletion confirmation
    """
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT p.post_id, p.content, p.category, p.timestamp, p.approved, 
                   p.channel_message_id, p.post_number,
                   COUNT(c.comment_id) as comment_count
            FROM posts p
            LEFT JOIN comments c ON p.post_id = c.post_id
            WHERE p.post_id = ?
            GROUP BY p.post_id
        """, (post_id,))
        
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            return None
        
        post_data = {
            'id': result[0],
            'content': result[1],
            'category': result[2],
            'timestamp': result[3],
            'approved': result[4],
            'channel_message_id': result[5],
            'post_number': result[6],
            'comment_count': result[7]
        }
        
        return post_data
        
    except Exception as e:
        logger.error(f"Error getting post details: {e}")
        return None


def get_comment_details_for_deletion(comment_id: int) -> dict:
    """
    Get comment details for deletion confirmation
    """
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT c.comment_id, c.post_id, c.content, c.timestamp, c.parent_comment_id,
                   COUNT(replies.comment_id) as reply_count
            FROM comments c
            LEFT JOIN comments replies ON c.comment_id = replies.parent_comment_id
            WHERE c.comment_id = ?
            GROUP BY c.comment_id
        """, (comment_id,))
        
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            return None
        
        comment_data = {
            'id': result[0],
            'post_id': result[1],
            'content': result[2],
            'timestamp': result[3],
            'parent_comment_id': result[4],
            'reply_count': result[5]
        }
        
        return comment_data
        
    except Exception as e:
        logger.error(f"Error getting comment details: {e}")
        return None


def clear_reports_for_content(target_type: str, target_id: int) -> tuple[bool, int]:
    """
    Clear all reports for a specific piece of content without deleting the content
    """
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Count reports before deletion
        cursor.execute("SELECT COUNT(*) FROM reports WHERE target_type = ? AND target_id = ?", (target_type, target_id))
        report_count = cursor.fetchone()[0]
        
        if report_count == 0:
            return True, 0
        
        # Delete the reports
        cursor.execute("DELETE FROM reports WHERE target_type = ? AND target_id = ?", (target_type, target_id))
        
        # Log the action (using dummy admin user ID since it's not passed)
        log_admin_deletion(
            admin_user_id=0,  # Dummy admin user ID
            action_type="CLEAR_REPORTS",
            target_type=target_type,
            target_id=target_id,
            details={
                "reports_cleared": report_count,
                "reason": "Admin cleared reports"
            }
        )
        
        conn.commit()
        conn.close()
        
        return True, report_count
        
    except Exception as e:
        logger.error(f"Error clearing reports: {e}")
        return False, 0


async def delete_channel_message(context, channel_message_id: int) -> tuple[bool, str]:
    """
    Delete a message from the channel
    """
    try:
        if not channel_message_id:
            return True, "No channel message to delete"
        
        await context.bot.delete_message(
            chat_id=CHANNEL_ID,
            message_id=channel_message_id
        )
        
        return True, "Channel message deleted"
        
    except Exception as e:
        logger.warning(f"Could not delete channel message {channel_message_id}: {e}")
        return False, f"Could not delete channel message: {str(e)}"
