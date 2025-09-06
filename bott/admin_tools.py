"""
Advanced admin tools for the confession bot
"""

import sqlite3
import os
import shutil
import json
import csv
import zipfile
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import asyncio
import aiofiles

from config import DB_PATH, BACKUPS_DIR, EXPORTS_DIR, ADMIN_IDS
from logger import get_logger
from error_handler import handle_database_errors
from analytics import analytics_manager

logger = get_logger('admin_tools')


@dataclass
class SearchResult:
    """Search result item"""
    type: str  # 'post' or 'comment'
    id: int
    content: str
    user_id: int
    timestamp: str
    metadata: Dict[str, Any]


@dataclass
class BackupInfo:
    """Backup information"""
    backup_id: int
    filename: str
    file_size: int
    record_count: int
    backup_type: str
    created_at: str
    checksum: str


class SearchManager:
    """Advanced search functionality for admins"""
    
    @handle_database_errors
    def search_content(self, query: str, content_type: str = "all", 
                      date_from: str = None, date_to: str = None,
                      user_id: int = None, limit: int = 50) -> List[SearchResult]:
        """Search through posts and comments"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            results = []
            
            # Search posts
            if content_type in ["all", "posts"]:
                post_query = """
                    SELECT p.post_id, p.content, p.user_id, p.timestamp, p.category, p.status, p.flagged
                    FROM posts p
                    WHERE p.content LIKE ?
                """
                params = [f"%{query}%"]
                
                if date_from:
                    post_query += " AND DATE(p.timestamp) >= ?"
                    params.append(date_from)
                
                if date_to:
                    post_query += " AND DATE(p.timestamp) <= ?"
                    params.append(date_to)
                
                if user_id:
                    post_query += " AND p.user_id = ?"
                    params.append(user_id)
                
                post_query += " ORDER BY p.timestamp DESC LIMIT ?"
                params.append(limit // 2 if content_type == "all" else limit)
                
                cursor.execute(post_query, params)
                
                for row in cursor.fetchall():
                    results.append(SearchResult(
                        type="post",
                        id=row[0],
                        content=row[1],
                        user_id=row[2],
                        timestamp=row[3],
                        metadata={
                            "category": row[4],
                            "status": row[5],
                            "flagged": row[6]
                        }
                    ))
            
            # Search comments
            if content_type in ["all", "comments"]:
                comment_query = """
                    SELECT c.comment_id, c.content, c.user_id, c.timestamp, c.post_id, c.likes, c.dislikes, c.flagged
                    FROM comments c
                    WHERE c.content LIKE ?
                """
                params = [f"%{query}%"]
                
                if date_from:
                    comment_query += " AND DATE(c.timestamp) >= ?"
                    params.append(date_from)
                
                if date_to:
                    comment_query += " AND DATE(c.timestamp) <= ?"
                    params.append(date_to)
                
                if user_id:
                    comment_query += " AND c.user_id = ?"
                    params.append(user_id)
                
                comment_query += " ORDER BY c.timestamp DESC LIMIT ?"
                params.append(limit // 2 if content_type == "all" else limit)
                
                cursor.execute(comment_query, params)
                
                for row in cursor.fetchall():
                    results.append(SearchResult(
                        type="comment",
                        id=row[0],
                        content=row[1],
                        user_id=row[2],
                        timestamp=row[3],
                        metadata={
                            "post_id": row[4],
                            "likes": row[5],
                            "dislikes": row[6],
                            "flagged": row[7]
                        }
                    ))
            
            return sorted(results, key=lambda x: x.timestamp, reverse=True)[:limit]
    
    @handle_database_errors
    def search_users(self, query: str, include_blocked: bool = True) -> List[Dict[str, Any]]:
        """Search for users"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            user_query = """
                SELECT u.user_id, u.username, u.first_name, u.last_name, u.join_date, u.blocked,
                       COUNT(DISTINCT p.post_id) as post_count,
                       COUNT(DISTINCT c.comment_id) as comment_count
                FROM users u
                LEFT JOIN posts p ON u.user_id = p.user_id
                LEFT JOIN comments c ON u.user_id = c.user_id
                WHERE (u.username LIKE ? OR u.first_name LIKE ? OR u.last_name LIKE ? OR u.user_id = ?)
            """
            params = [f"%{query}%", f"%{query}%", f"%{query}%"]
            
            # Try to parse query as user_id
            try:
                user_id = int(query)
                params.append(user_id)
            except ValueError:
                params.append(-1)  # Invalid user_id
            
            if not include_blocked:
                user_query += " AND u.blocked = 0"
            
            user_query += " GROUP BY u.user_id ORDER BY u.join_date DESC LIMIT 20"
            
            cursor.execute(user_query, params)
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    "user_id": row[0],
                    "username": row[1],
                    "first_name": row[2],
                    "last_name": row[3],
                    "join_date": row[4],
                    "blocked": bool(row[5]),
                    "post_count": row[6],
                    "comment_count": row[7]
                })
            
            return results


class BulkActionsManager:
    """Handle bulk administrative actions"""
    
    @handle_database_errors
    def bulk_approve_posts(self, post_ids: List[int], admin_id: int) -> Dict[str, Any]:
        """Bulk approve multiple posts"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            # Get posts to approve
            placeholders = ','.join(['?' for _ in post_ids])
            cursor.execute(f"""
                SELECT post_id, content, category, user_id
                FROM posts 
                WHERE post_id IN ({placeholders}) AND (status = 'pending' OR status IS NULL)
            """, post_ids)
            
            posts_to_approve = cursor.fetchall()
            
            if not posts_to_approve:
                return {"success": False, "message": "No eligible posts found for approval"}
            
            # Approve posts
            cursor.execute(f"""
                UPDATE posts 
                SET status = 'approved' 
                WHERE post_id IN ({placeholders}) AND (status = 'pending' OR status IS NULL)
            """, post_ids)
            
            approved_count = cursor.rowcount
            
            # Log moderation actions
            for post_id, content, category, user_id in posts_to_approve:
                cursor.execute("""
                    INSERT INTO moderation_log (moderator_id, target_type, target_id, action, reason)
                    VALUES (?, 'post', ?, 'bulk_approve', 'Bulk approval by admin')
                """, (admin_id, post_id))
            
            conn.commit()
            
            return {
                "success": True,
                "approved_count": approved_count,
                "message": f"Successfully approved {approved_count} posts"
            }
    
    @handle_database_errors
    def bulk_reject_posts(self, post_ids: List[int], admin_id: int, reason: str = "") -> Dict[str, Any]:
        """Bulk reject multiple posts"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            # Get posts to reject
            placeholders = ','.join(['?' for _ in post_ids])
            cursor.execute(f"""
                SELECT post_id, content, category, user_id
                FROM posts 
                WHERE post_id IN ({placeholders}) AND (status = 'pending' OR status IS NULL)
            """, post_ids)
            
            posts_to_reject = cursor.fetchall()
            
            if not posts_to_reject:
                return {"success": False, "message": "No eligible posts found for rejection"}
            
            # Reject posts
            cursor.execute(f"""
                UPDATE posts 
                SET status = 'rejected' 
                WHERE post_id IN ({placeholders}) AND (status = 'pending' OR status IS NULL)
            """, post_ids)
            
            rejected_count = cursor.rowcount
            
            # Log moderation actions
            for post_id, content, category, user_id in posts_to_reject:
                cursor.execute("""
                    INSERT INTO moderation_log (moderator_id, target_type, target_id, action, reason)
                    VALUES (?, 'post', ?, 'bulk_reject', ?)
                """, (admin_id, post_id, reason or "Bulk rejection by admin"))
            
            conn.commit()
            
            return {
                "success": True,
                "rejected_count": rejected_count,
                "message": f"Successfully rejected {rejected_count} posts"
            }
    
    @handle_database_errors
    def bulk_delete_comments(self, comment_ids: List[int], admin_id: int, reason: str = "") -> Dict[str, Any]:
        """Bulk delete comments"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            # Log deletions first
            placeholders = ','.join(['?' for _ in comment_ids])
            cursor.execute(f"""
                SELECT comment_id, content, user_id
                FROM comments 
                WHERE comment_id IN ({placeholders})
            """, comment_ids)
            
            comments_to_delete = cursor.fetchall()
            
            for comment_id, content, user_id in comments_to_delete:
                cursor.execute("""
                    INSERT INTO moderation_log (moderator_id, target_type, target_id, action, reason)
                    VALUES (?, 'comment', ?, 'bulk_delete', ?)
                """, (admin_id, comment_id, reason or "Bulk deletion by admin"))
            
            # Delete comments
            cursor.execute(f"""
                DELETE FROM comments 
                WHERE comment_id IN ({placeholders})
            """, comment_ids)
            
            deleted_count = cursor.rowcount
            conn.commit()
            
            return {
                "success": True,
                "deleted_count": deleted_count,
                "message": f"Successfully deleted {deleted_count} comments"
            }
    
    @handle_database_errors
    def bulk_block_users(self, user_ids: List[int], admin_id: int, reason: str = "") -> Dict[str, Any]:
        """Bulk block users"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            # Update users
            placeholders = ','.join(['?' for _ in user_ids])
            cursor.execute(f"""
                UPDATE users 
                SET blocked = 1 
                WHERE user_id IN ({placeholders}) AND blocked = 0
            """, user_ids)
            
            blocked_count = cursor.rowcount
            
            # Log actions
            for user_id in user_ids:
                cursor.execute("""
                    INSERT INTO moderation_log (moderator_id, target_type, target_id, action, reason)
                    VALUES (?, 'user', ?, 'bulk_block', ?)
                """, (admin_id, user_id, reason or "Bulk block by admin"))
            
            conn.commit()
            
            return {
                "success": True,
                "blocked_count": blocked_count,
                "message": f"Successfully blocked {blocked_count} users"
            }


class BackupManager:
    """Handle automated backups and exports"""
    
    def __init__(self):
        # Create directories if they don't exist
        os.makedirs(BACKUPS_DIR, exist_ok=True)
        os.makedirs(EXPORTS_DIR, exist_ok=True)
    
    @handle_database_errors
    def create_backup(self, backup_type: str = "manual") -> Tuple[bool, str]:
        """Create a database backup"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"confession_bot_backup_{timestamp}.db"
            backup_path = os.path.join(BACKUPS_DIR, backup_filename)
            
            # Copy database file
            shutil.copy2(DB_PATH, backup_path)
            
            # Get file size and record count
            file_size = os.path.getsize(backup_path)
            record_count = self._get_database_record_count()
            
            # Calculate checksum
            checksum = self._calculate_file_checksum(backup_path)
            
            # Save backup metadata
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO backup_metadata (filename, file_size, record_count, backup_type, checksum)
                    VALUES (?, ?, ?, ?, ?)
                """, (backup_filename, file_size, record_count, backup_type, checksum))
                conn.commit()
            
            logger.info(f"Backup created successfully: {backup_filename}")
            return True, backup_filename
            
        except Exception as e:
            logger.error(f"Backup creation failed: {e}")
            return False, str(e)
    
    @handle_database_errors
    def get_backup_list(self) -> List[BackupInfo]:
        """Get list of available backups"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT backup_id, filename, file_size, record_count, backup_type, created_at, checksum
                FROM backup_metadata
                ORDER BY created_at DESC
            """)
            
            return [BackupInfo(*row) for row in cursor.fetchall()]
    
    def cleanup_old_backups(self, keep_count: int = 10):
        """Clean up old backup files"""
        try:
            backups = self.get_backup_list()
            
            if len(backups) <= keep_count:
                return
            
            backups_to_delete = backups[keep_count:]
            
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                
                for backup in backups_to_delete:
                    # Delete physical file
                    backup_path = os.path.join(BACKUPS_DIR, backup.filename)
                    if os.path.exists(backup_path):
                        os.remove(backup_path)
                    
                    # Remove from metadata
                    cursor.execute("DELETE FROM backup_metadata WHERE backup_id = ?", (backup.backup_id,))
                
                conn.commit()
                
            logger.info(f"Cleaned up {len(backups_to_delete)} old backups")
            
        except Exception as e:
            logger.error(f"Backup cleanup failed: {e}")
    
    def _get_database_record_count(self) -> int:
        """Get total number of records in database"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            tables = ['posts', 'comments', 'users', 'reactions', 'reports', 'admin_messages']
            total_count = 0
            
            for table in tables:
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    total_count += cursor.fetchone()[0]
                except sqlite3.OperationalError:
                    pass  # Table might not exist
            
            return total_count
    
    def _calculate_file_checksum(self, file_path: str) -> str:
        """Calculate MD5 checksum of file"""
        import hashlib
        
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()


class ExportManager:
    """Handle data exports in various formats"""
    
    def __init__(self):
        os.makedirs(EXPORTS_DIR, exist_ok=True)
    
    @handle_database_errors
    def export_posts_csv(self, date_from: str = None, date_to: str = None, 
                        status_filter: str = None) -> Tuple[bool, str]:
        """Export posts to CSV"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"posts_export_{timestamp}.csv"
            filepath = os.path.join(EXPORTS_DIR, filename)
            
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                
                query = """
                    SELECT p.post_id, p.content, p.category, p.timestamp, p.user_id, 
                           p.status, p.flagged, p.likes, p.sentiment_score, p.sentiment_label,
                           COUNT(c.comment_id) as comment_count
                    FROM posts p
                    LEFT JOIN comments c ON p.post_id = c.post_id
                    WHERE 1=1
                """
                params = []
                
                if date_from:
                    query += " AND DATE(p.timestamp) >= ?"
                    params.append(date_from)
                
                if date_to:
                    query += " AND DATE(p.timestamp) <= ?"
                    params.append(date_to)
                
                if status_filter == 'approved':
                    query += " AND p.status = 'approved'"
                elif status_filter == 'rejected':
                    query += " AND p.status = 'rejected'"
                elif status_filter == 'pending':
                    query += " AND (p.status = 'pending' OR p.status IS NULL)"
                
                query += " GROUP BY p.post_id ORDER BY p.timestamp DESC"
                
                cursor.execute(query, params)
                
                with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    
                    # Write header
                    writer.writerow([
                        'Post ID', 'Content', 'Category', 'Timestamp', 'User ID',
                        'Approved', 'Flagged', 'Likes', 'Sentiment Score', 'Sentiment Label',
                        'Comment Count'
                    ])
                    
                    # Write data
                    for row in cursor.fetchall():
                        writer.writerow(row)
            
            logger.info(f"Posts exported to CSV: {filename}")
            return True, filename
            
        except Exception as e:
            logger.error(f"CSV export failed: {e}")
            return False, str(e)
    
    @handle_database_errors
    def export_analytics_report(self, days_back: int = 30) -> Tuple[bool, str]:
        """Export comprehensive analytics report"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"analytics_report_{timestamp}.json"
            filepath = os.path.join(EXPORTS_DIR, filename)
            
            # Generate comprehensive report
            report = analytics_manager.generate_comprehensive_report(days_back)
            
            # Save to file
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, default=str)
            
            logger.info(f"Analytics report exported: {filename}")
            return True, filename
            
        except Exception as e:
            logger.error(f"Analytics export failed: {e}")
            return False, str(e)
    
    @handle_database_errors
    def export_user_data(self, user_id: int) -> Tuple[bool, str]:
        """Export all data for a specific user (GDPR compliance)"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"user_data_export_{user_id}_{timestamp}.json"
            filepath = os.path.join(EXPORTS_DIR, filename)
            
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                
                # Get user info
                cursor.execute("""
                    SELECT user_id, username, first_name, last_name, join_date, blocked
                    FROM users WHERE user_id = ?
                """, (user_id,))
                user_info = cursor.fetchone()
                
                if not user_info:
                    return False, "User not found"
                
                # Get posts
                cursor.execute("""
                    SELECT post_id, content, category, timestamp, status, flagged, likes
                    FROM posts WHERE user_id = ?
                """, (user_id,))
                posts = [dict(zip([col[0] for col in cursor.description], row)) 
                        for row in cursor.fetchall()]
                
                # Get comments
                cursor.execute("""
                    SELECT comment_id, post_id, content, timestamp, likes, dislikes, flagged
                    FROM comments WHERE user_id = ?
                """, (user_id,))
                comments = [dict(zip([col[0] for col in cursor.description], row)) 
                           for row in cursor.fetchall()]
                
                # Get reactions
                cursor.execute("""
                    SELECT target_type, target_id, reaction_type, timestamp
                    FROM reactions WHERE user_id = ?
                """, (user_id,))
                reactions = [dict(zip([col[0] for col in cursor.description], row)) 
                           for row in cursor.fetchall()]
                
                # Get admin messages
                cursor.execute("""
                    SELECT message_id, user_message, admin_reply, timestamp, replied
                    FROM admin_messages WHERE user_id = ?
                """, (user_id,))
                messages = [dict(zip([col[0] for col in cursor.description], row)) 
                           for row in cursor.fetchall()]
                
                # Compile export data
                export_data = {
                    "export_info": {
                        "user_id": user_id,
                        "export_timestamp": datetime.now().isoformat(),
                        "export_type": "complete_user_data"
                    },
                    "user_info": dict(zip(['user_id', 'username', 'first_name', 'last_name', 'join_date', 'blocked'], user_info)),
                    "posts": posts,
                    "comments": comments,
                    "reactions": reactions,
                    "admin_messages": messages
                }
                
                # Save to file
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, indent=2, default=str)
            
            logger.info(f"User data exported: {filename}")
            return True, filename
            
        except Exception as e:
            logger.error(f"User data export failed: {e}")
            return False, str(e)


class AutomationManager:
    """Handle automated admin tasks"""
    
    def __init__(self):
        self.backup_manager = BackupManager()
    
    async def run_daily_maintenance(self):
        """Run daily automated maintenance tasks"""
        try:
            logger.info("Starting daily maintenance tasks")
            
            # Create automated backup
            success, result = self.backup_manager.create_backup("auto")
            if success:
                logger.info(f"Daily backup created: {result}")
            else:
                logger.error(f"Daily backup failed: {result}")
            
            # Clean up old backups
            self.backup_manager.cleanup_old_backups(keep_count=30)
            
            # Update daily statistics
            analytics_manager.update_daily_stats()
            
            # Clean up old notifications (older than 30 days)
            await self._cleanup_old_notifications()
            
            # Clean up old activity logs (older than 90 days)
            await self._cleanup_old_activity_logs()
            
            logger.info("Daily maintenance tasks completed")
            
        except Exception as e:
            logger.error(f"Daily maintenance failed: {e}")
    
    @handle_database_errors
    async def _cleanup_old_notifications(self, days_old: int = 30):
        """Clean up old notifications"""
        cutoff_date = (datetime.now() - timedelta(days=days_old)).strftime('%Y-%m-%d')
        
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM notifications 
                WHERE read = 1 AND DATE(created_at) < ?
            """, (cutoff_date,))
            
            deleted_count = cursor.rowcount
            conn.commit()
            
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} old notifications")
    
    @handle_database_errors
    async def _cleanup_old_activity_logs(self, days_old: int = 90):
        """Clean up old activity logs"""
        cutoff_date = (datetime.now() - timedelta(days=days_old)).strftime('%Y-%m-%d')
        
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM user_activity_log 
                WHERE DATE(timestamp) < ?
            """, (cutoff_date,))
            
            deleted_count = cursor.rowcount
            conn.commit()
            
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} old activity log entries")


# Global instances
search_manager = SearchManager()
bulk_actions_manager = BulkActionsManager()
backup_manager = BackupManager()
export_manager = ExportManager()
automation_manager = AutomationManager()


# Helper functions for admin commands
def is_admin(user_id: int) -> bool:
    """Check if user is an admin"""
    return user_id in ADMIN_IDS


async def schedule_daily_maintenance():
    """Schedule daily maintenance to run at 2 AM"""
    while True:
        now = datetime.now()
        next_run = now.replace(hour=2, minute=0, second=0, microsecond=0)
        
        if next_run <= now:
            next_run += timedelta(days=1)
        
        wait_seconds = (next_run - now).total_seconds()
        await asyncio.sleep(wait_seconds)
        
        await automation_manager.run_daily_maintenance()


def format_search_results(results: List[SearchResult], max_content_length: int = 100) -> str:
    """Format search results for display"""
    if not results:
        return "No results found."
    
    formatted = f"Found {len(results)} results:\n\n"
    
    for i, result in enumerate(results, 1):
        content_preview = result.content[:max_content_length] + "..." if len(result.content) > max_content_length else result.content
        
        formatted += f"{i}. {result.type.title()} ID: {result.id}\n"
        formatted += f"   User: {result.user_id}\n"
        formatted += f"   Date: {result.timestamp}\n"
        formatted += f"   Content: {content_preview}\n"
        
        if result.type == "post":
            formatted += f"   Category: {result.metadata.get('category', 'N/A')}\n"
            status = result.metadata.get('status')
            status_text = status.title() if status else 'Pending'
            formatted += f"   Status: {status_text}\n"
        elif result.type == "comment":
            formatted += f"   Post ID: {result.metadata.get('post_id')}\n"
            formatted += f"   Likes: {result.metadata.get('likes', 0)} | Dislikes: {result.metadata.get('dislikes', 0)}\n"
        
        formatted += "\n"
    
    return formatted
