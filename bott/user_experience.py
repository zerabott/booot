"""
Enhanced user experience features for the confession bot
"""

import sqlite3
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import asyncio

from config import DB_PATH, MAX_CONFESSION_LENGTH, MAX_COMMENT_LENGTH
from logger import get_logger
from error_handler import handle_database_errors

logger = get_logger('user_experience')


@dataclass
class Draft:
    """Represents a confession draft"""
    draft_id: int
    user_id: int
    content: str
    category: Optional[str]
    created_at: str
    updated_at: str


@dataclass
class ScheduledConfession:
    """Represents a scheduled confession"""
    schedule_id: int
    user_id: int
    content: str
    category: str
    scheduled_for: str
    status: str
    created_at: str


@dataclass
class UserPreferences:
    """User preferences and settings"""
    user_id: int
    notification_enabled: bool
    daily_digest_enabled: bool
    language: str
    timezone: str
    created_at: str
    updated_at: str


@dataclass
class Notification:
    """User notification"""
    notification_id: int
    user_id: int
    type: str
    title: str
    message: str
    data: Optional[str]
    read: bool
    created_at: str
    read_at: Optional[str]


class DraftManager:
    """Manage confession drafts"""
    
    @handle_database_errors
    def save_draft(self, user_id: int, content: str, category: str = None) -> Tuple[Optional[int], Optional[str]]:
        """Save or update a draft"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            # Check if user already has a draft
            cursor.execute("""
                SELECT draft_id FROM confession_drafts WHERE user_id = ?
            """, (user_id,))
            
            existing_draft = cursor.fetchone()
            
            if existing_draft:
                # Update existing draft
                cursor.execute("""
                    UPDATE confession_drafts 
                    SET content = ?, category = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE draft_id = ?
                """, (content, category, existing_draft[0]))
                return existing_draft[0], None
            else:
                # Create new draft
                cursor.execute("""
                    INSERT INTO confession_drafts (user_id, content, category)
                    VALUES (?, ?, ?)
                """, (user_id, content, category))
                return cursor.lastrowid, None
    
    @handle_database_errors
    def get_user_draft(self, user_id: int) -> Optional[Draft]:
        """Get user's current draft"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT draft_id, user_id, content, category, created_at, updated_at
                FROM confession_drafts 
                WHERE user_id = ?
            """, (user_id,))
            
            result = cursor.fetchone()
            if result:
                return Draft(*result)
            return None
    
    @handle_database_errors
    def delete_draft(self, user_id: int) -> bool:
        """Delete user's draft"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM confession_drafts WHERE user_id = ?
            """, (user_id,))
            return cursor.rowcount > 0
    
    @handle_database_errors
    def get_all_drafts(self, user_id: int) -> List[Draft]:
        """Get all drafts for a user (in case we support multiple drafts later)"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT draft_id, user_id, content, category, created_at, updated_at
                FROM confession_drafts 
                WHERE user_id = ?
                ORDER BY updated_at DESC
            """, (user_id,))
            
            return [Draft(*row) for row in cursor.fetchall()]


class SchedulingManager:
    """Manage scheduled confessions"""
    
    @handle_database_errors
    def schedule_confession(self, user_id: int, content: str, category: str, scheduled_for: datetime) -> Tuple[Optional[int], Optional[str]]:
        """Schedule a confession for future posting"""
        # Validate scheduling time (must be at least 1 hour in the future)
        if scheduled_for < datetime.now() + timedelta(hours=1):
            return None, "Cannot schedule confessions less than 1 hour in advance"
        
        # Limit scheduling to 30 days in the future
        if scheduled_for > datetime.now() + timedelta(days=30):
            return None, "Cannot schedule confessions more than 30 days in advance"
        
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            # Check user's scheduled confession limit (max 5 pending)
            cursor.execute("""
                SELECT COUNT(*) FROM scheduled_confessions 
                WHERE user_id = ? AND status = 'pending'
            """, (user_id,))
            
            pending_count = cursor.fetchone()[0]
            if pending_count >= 5:
                return None, "You can have a maximum of 5 pending scheduled confessions"
            
            # Insert scheduled confession
            cursor.execute("""
                INSERT INTO scheduled_confessions (user_id, content, category, scheduled_for)
                VALUES (?, ?, ?, ?)
            """, (user_id, content, category, scheduled_for.isoformat()))
            
            return cursor.lastrowid, None
    
    @handle_database_errors
    def get_user_scheduled_confessions(self, user_id: int) -> List[ScheduledConfession]:
        """Get user's scheduled confessions"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT schedule_id, user_id, content, category, scheduled_for, 
                       status, created_at, posted_at, post_id
                FROM scheduled_confessions 
                WHERE user_id = ?
                ORDER BY scheduled_for ASC
            """, (user_id,))
            
            results = []
            for row in cursor.fetchall():
                results.append(ScheduledConfession(
                    schedule_id=row[0],
                    user_id=row[1],
                    content=row[2],
                    category=row[3],
                    scheduled_for=row[4],
                    status=row[5],
                    created_at=row[6]
                ))
            
            return results
    
    @handle_database_errors
    def get_pending_scheduled_confessions(self) -> List[ScheduledConfession]:
        """Get all pending scheduled confessions ready to be posted"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT schedule_id, user_id, content, category, scheduled_for, 
                       status, created_at, posted_at, post_id
                FROM scheduled_confessions 
                WHERE status = 'pending' AND scheduled_for <= ?
                ORDER BY scheduled_for ASC
            """, (datetime.now().isoformat(),))
            
            results = []
            for row in cursor.fetchall():
                results.append(ScheduledConfession(
                    schedule_id=row[0],
                    user_id=row[1],
                    content=row[2],
                    category=row[3],
                    scheduled_for=row[4],
                    status=row[5],
                    created_at=row[6]
                ))
            
            return results
    
    @handle_database_errors
    def cancel_scheduled_confession(self, user_id: int, schedule_id: int) -> bool:
        """Cancel a scheduled confession"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE scheduled_confessions 
                SET status = 'cancelled'
                WHERE schedule_id = ? AND user_id = ? AND status = 'pending'
            """, (schedule_id, user_id))
            
            return cursor.rowcount > 0
    
    @handle_database_errors
    def mark_scheduled_confession_posted(self, schedule_id: int, post_id: int) -> bool:
        """Mark a scheduled confession as posted"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE scheduled_confessions 
                SET status = 'posted', posted_at = CURRENT_TIMESTAMP, post_id = ?
                WHERE schedule_id = ?
            """, (post_id, schedule_id))
            
            return cursor.rowcount > 0


class PreferencesManager:
    """Manage user preferences"""
    
    @handle_database_errors
    def get_user_preferences(self, user_id: int) -> UserPreferences:
        """Get user preferences, create default if not exists"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT user_id, notification_enabled, daily_digest_enabled, 
                       language, timezone, created_at, updated_at
                FROM user_preferences WHERE user_id = ?
            """, (user_id,))
            
            result = cursor.fetchone()
            if result:
                return UserPreferences(*result)
            
            # Create default preferences
            cursor.execute("""
                INSERT INTO user_preferences (user_id) VALUES (?)
            """, (user_id,))
            
            # Fetch the newly created preferences
            cursor.execute("""
                SELECT user_id, notification_enabled, daily_digest_enabled, 
                       language, timezone, created_at, updated_at
                FROM user_preferences WHERE user_id = ?
            """, (user_id,))
            
            return UserPreferences(*cursor.fetchone())
    
    @handle_database_errors
    def update_preferences(self, user_id: int, **kwargs) -> bool:
        """Update user preferences"""
        valid_fields = ['notification_enabled', 'daily_digest_enabled', 'language', 'timezone']
        updates = {k: v for k, v in kwargs.items() if k in valid_fields}
        
        if not updates:
            return False
        
        # Ensure user preferences record exists
        self.get_user_preferences(user_id)
        
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            set_clause = ', '.join([f"{k} = ?" for k in updates.keys()])
            values = list(updates.values()) + [user_id]
            
            cursor.execute(f"""
                UPDATE user_preferences 
                SET {set_clause}, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
            """, values)
            
            return cursor.rowcount > 0


class NotificationManager:
    """Manage user notifications"""
    
    @handle_database_errors
    def create_notification(self, user_id: int, type: str, title: str, message: str, data: str = None) -> Optional[int]:
        """Create a new notification"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO notifications (user_id, type, title, message, data)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, type, title, message, data))
            
            return cursor.lastrowid
    
    @handle_database_errors
    def get_user_notifications(self, user_id: int, unread_only: bool = False, limit: int = 20) -> List[Notification]:
        """Get user notifications"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            query = """
                SELECT notification_id, user_id, type, title, message, data, read, created_at, read_at
                FROM notifications 
                WHERE user_id = ?
            """
            params = [user_id]
            
            if unread_only:
                query += " AND read = 0"
            
            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(query, params)
            return [Notification(*row) for row in cursor.fetchall()]
    
    @handle_database_errors
    def mark_notification_read(self, user_id: int, notification_id: int) -> bool:
        """Mark a notification as read"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE notifications 
                SET read = 1, read_at = CURRENT_TIMESTAMP
                WHERE notification_id = ? AND user_id = ?
            """, (notification_id, user_id))
            
            return cursor.rowcount > 0
    
    @handle_database_errors
    def mark_all_notifications_read(self, user_id: int) -> int:
        """Mark all notifications as read for a user"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE notifications 
                SET read = 1, read_at = CURRENT_TIMESTAMP
                WHERE user_id = ? AND read = 0
            """, (user_id,))
            
            return cursor.rowcount
    
    @handle_database_errors
    def get_unread_count(self, user_id: int) -> int:
        """Get count of unread notifications"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM notifications 
                WHERE user_id = ? AND read = 0
            """, (user_id,))
            
            return cursor.fetchone()[0]
    
    def notify_confession_approved(self, user_id: int, post_id: int, category: str):
        """Send notification when confession is approved"""
        self.create_notification(
            user_id=user_id,
            type="confession_approved",
            title="Confession Approved! 🎉",
            message=f"Your confession in category '{category}' has been approved and posted to the channel.",
            data=json.dumps({"post_id": post_id, "category": category})
        )
    
    def notify_confession_rejected(self, user_id: int, category: str, reason: str = ""):
        """Send notification when confession is rejected"""
        message = f"Your confession in category '{category}' was not approved."
        if reason:
            message += f" Reason: {reason}"
        
        self.create_notification(
            user_id=user_id,
            type="confession_rejected",
            title="Confession Not Approved",
            message=message,
            data=json.dumps({"category": category, "reason": reason})
        )
    
    def notify_comment_reply(self, user_id: int, post_id: int, comment_id: int):
        """Send notification when someone replies to user's comment"""
        self.create_notification(
            user_id=user_id,
            type="comment_reply",
            title="Someone Replied to Your Comment 💬",
            message="Someone replied to one of your comments. Check it out!",
            data=json.dumps({"post_id": post_id, "comment_id": comment_id})
        )
    
    def notify_scheduled_confession_posted(self, user_id: int, post_id: int, category: str):
        """Send notification when scheduled confession is posted"""
        self.create_notification(
            user_id=user_id,
            type="scheduled_posted",
            title="Scheduled Confession Posted ⏰",
            message=f"Your scheduled confession in category '{category}' has been posted to the channel.",
            data=json.dumps({"post_id": post_id, "category": category})
        )


class HistoryManager:
    """Manage user history with advanced filtering"""
    
    @handle_database_errors
    def get_user_confession_history(self, user_id: int, status_filter: str = None, 
                                   category_filter: str = None, limit: int = 20, 
                                   offset: int = 0) -> Tuple[List[Dict], int]:
        """Get user's confession history with filtering"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            # Build query with filters
            query = """
                SELECT p.post_id, p.content, p.category, p.timestamp, p.approved, 
                       COUNT(c.comment_id) as comment_count,
                       COALESCE(p.likes, 0) as likes
                FROM posts p
                LEFT JOIN comments c ON p.post_id = c.post_id
                WHERE p.user_id = ?
            """
            params = [user_id]
            
            if status_filter:
                if status_filter == 'approved':
                    query += " AND p.approved = 1"
                elif status_filter == 'rejected':
                    query += " AND p.approved = 0"
                elif status_filter == 'pending':
                    query += " AND p.approved IS NULL"
            
            if category_filter:
                query += " AND p.category = ?"
                params.append(category_filter)
            
            query += " GROUP BY p.post_id ORDER BY p.timestamp DESC"
            
            # Get total count for pagination
            count_query = query.replace("SELECT p.post_id, p.content, p.category, p.timestamp, p.approved, COUNT(c.comment_id) as comment_count, COALESCE(p.likes, 0) as likes", "SELECT COUNT(DISTINCT p.post_id)")
            count_query = count_query.replace("GROUP BY p.post_id ORDER BY p.timestamp DESC", "")
            
            cursor.execute(count_query, params)
            total_count = cursor.fetchone()[0]
            
            # Get paginated results
            query += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            
            cursor.execute(query, params)
            results = []
            
            for row in cursor.fetchall():
                status = "Approved" if row[4] == 1 else "Pending" if row[4] is None else "Rejected"
                results.append({
                    'post_id': row[0],
                    'content': row[1][:200] + "..." if len(row[1]) > 200 else row[1],
                    'category': row[2],
                    'timestamp': row[3],
                    'status': status,
                    'comment_count': row[5],
                    'likes': row[6]
                })
            
            return results, total_count
    
    @handle_database_errors
    def get_user_comment_history(self, user_id: int, limit: int = 20, offset: int = 0) -> Tuple[List[Dict], int]:
        """Get user's comment history"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            # Get total count
            cursor.execute("""
                SELECT COUNT(*) FROM comments WHERE user_id = ?
            """, (user_id,))
            total_count = cursor.fetchone()[0]
            
            # Get paginated results
            cursor.execute("""
                SELECT c.comment_id, c.post_id, c.content, c.timestamp, 
                       c.likes, c.dislikes, p.category
                FROM comments c
                JOIN posts p ON c.post_id = p.post_id
                WHERE c.user_id = ?
                ORDER BY c.timestamp DESC
                LIMIT ? OFFSET ?
            """, (user_id, limit, offset))
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    'comment_id': row[0],
                    'post_id': row[1],
                    'content': row[2][:100] + "..." if len(row[2]) > 100 else row[2],
                    'timestamp': row[3],
                    'likes': row[4],
                    'dislikes': row[5],
                    'post_category': row[6]
                })
            
            return results, total_count
    
    @handle_database_errors
    def get_user_activity_summary(self, user_id: int, days_back: int = 30) -> Dict[str, Any]:
        """Get user activity summary"""
        start_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')
        
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            # Recent confessions
            cursor.execute("""
                SELECT COUNT(*), 
                       COUNT(CASE WHEN approved = 1 THEN 1 END) as approved,
                       COUNT(CASE WHEN approved = 0 THEN 1 END) as rejected,
                       COUNT(CASE WHEN approved IS NULL THEN 1 END) as pending
                FROM posts 
                WHERE user_id = ? AND DATE(timestamp) >= ?
            """, (user_id, start_date))
            confession_stats = cursor.fetchone()
            
            # Recent comments
            cursor.execute("""
                SELECT COUNT(*), SUM(likes), SUM(dislikes)
                FROM comments 
                WHERE user_id = ? AND DATE(timestamp) >= ?
            """, (user_id, start_date))
            comment_stats = cursor.fetchone()
            
            # Most active categories
            cursor.execute("""
                SELECT category, COUNT(*) as count
                FROM posts 
                WHERE user_id = ? AND DATE(timestamp) >= ?
                GROUP BY category
                ORDER BY count DESC
                LIMIT 3
            """, (user_id, start_date))
            top_categories = cursor.fetchall()
            
            return {
                'period_days': days_back,
                'confessions': {
                    'total': confession_stats[0],
                    'approved': confession_stats[1],
                    'rejected': confession_stats[2],
                    'pending': confession_stats[3]
                },
                'comments': {
                    'total': comment_stats[0] or 0,
                    'likes_received': comment_stats[1] or 0,
                    'dislikes_received': comment_stats[2] or 0
                },
                'top_categories': [{'category': cat, 'count': count} for cat, count in top_categories]
            }


# Global managers
draft_manager = DraftManager()
scheduling_manager = SchedulingManager()
preferences_manager = PreferencesManager()
notification_manager = NotificationManager()
history_manager = HistoryManager()


async def process_scheduled_confessions():
    """Background task to process scheduled confessions"""
    try:
        pending_confessions = scheduling_manager.get_pending_scheduled_confessions()
        
        for confession in pending_confessions:
            # Here you would integrate with your main confession posting system
            # For now, we'll just mark it as posted (you'll need to integrate this properly)
            logger.info(f"Processing scheduled confession {confession.schedule_id}")
            
            # This would be replaced with actual posting logic
            # post_id = await post_scheduled_confession(confession)
            # if post_id:
            #     scheduling_manager.mark_scheduled_confession_posted(confession.schedule_id, post_id)
            #     notification_manager.notify_scheduled_confession_posted(
            #         confession.user_id, post_id, confession.category
            #     )
        
    except Exception as e:
        logger.error(f"Error processing scheduled confessions: {e}")


def format_confession_preview(content: str, max_length: int = 100) -> str:
    """Format confession content for preview"""
    if len(content) <= max_length:
        return content
    return content[:max_length-3] + "..."


def get_relative_time(timestamp_str: str) -> str:
    """Get human-readable relative time"""
    try:
        timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        now = datetime.now()
        diff = now - timestamp
        
        if diff.days > 0:
            return f"{diff.days} day{'s' if diff.days != 1 else ''} ago"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        else:
            return "Just now"
    except:
        return timestamp_str
