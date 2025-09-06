import sqlite3
from config import DB_PATH
from utils import format_join_date

def get_user_stats(user_id):
    """Get comprehensive user statistics"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        
        # Get basic user info
        cursor.execute('''
            SELECT username, first_name, last_name, join_date, 
                   questions_asked, comments_posted, blocked
            FROM users WHERE user_id = ?
        ''', (user_id,))
        
        user_info = cursor.fetchone()
        if not user_info:
            return None
        
        # Get approved confessions count
        cursor.execute(
            "SELECT COUNT(*) FROM posts WHERE user_id = ? AND approved = 1",
            (user_id,)
        )
        approved_confessions = cursor.fetchone()[0]
        
        # Get pending confessions count
        cursor.execute(
            "SELECT COUNT(*) FROM posts WHERE user_id = ? AND approved IS NULL",
            (user_id,)
        )
        pending_confessions = cursor.fetchone()[0]
        
        # Get rejected confessions count
        cursor.execute(
            "SELECT COUNT(*) FROM posts WHERE user_id = ? AND approved = 0",
            (user_id,)
        )
        rejected_confessions = cursor.fetchone()[0]
        
        # Get total likes received on comments
        cursor.execute('''
            SELECT SUM(c.likes) 
            FROM comments c 
            WHERE c.user_id = ?
        ''', (user_id,))
        
        likes_received = cursor.fetchone()[0] or 0
        
        return {
            'user_id': user_id,
            'username': user_info[0],
            'first_name': user_info[1],
            'last_name': user_info[2],
            'join_date': user_info[3],
            'total_confessions': user_info[4],
            'approved_confessions': approved_confessions,
            'pending_confessions': pending_confessions,
            'rejected_confessions': rejected_confessions,
            'comments_posted': user_info[5],
            'likes_received': likes_received,
            'blocked': bool(user_info[6])
        }

def get_channel_stats():
    """Get overall channel statistics"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        
        # Total approved posts
        cursor.execute("SELECT COUNT(*) FROM posts WHERE approved = 1")
        total_posts = cursor.fetchone()[0]
        
        # Total comments
        cursor.execute("SELECT COUNT(*) FROM comments")
        total_comments = cursor.fetchone()[0]
        
        # Total users
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        
        # Pending submissions
        cursor.execute("SELECT COUNT(*) FROM posts WHERE approved IS NULL")
        pending_posts = cursor.fetchone()[0]
        
        # Total reactions
        cursor.execute("SELECT COUNT(*) FROM reactions")
        total_reactions = cursor.fetchone()[0]
        
        # Flagged content
        cursor.execute("SELECT COUNT(*) FROM posts WHERE flagged = 1")
        flagged_posts = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM comments WHERE flagged = 1")
        flagged_comments = cursor.fetchone()[0]
        
        return {
            'total_posts': total_posts,
            'total_comments': total_comments,
            'total_users': total_users,
            'pending_posts': pending_posts,
            'total_reactions': total_reactions,
            'flagged_posts': flagged_posts,
            'flagged_comments': flagged_comments
        }