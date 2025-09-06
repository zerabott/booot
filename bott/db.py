import sqlite3
import datetime
from config import DB_PATH

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute('PRAGMA foreign_keys = ON')
    return conn

def init_db():
    """Initialize database with enhanced schema"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Users table with join date tracking
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        join_date TEXT DEFAULT CURRENT_TIMESTAMP,
        questions_asked INTEGER DEFAULT 0,
        comments_posted INTEGER DEFAULT 0,
        blocked INTEGER DEFAULT 0
    )''')
    
    # Posts table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS posts (
        post_id INTEGER PRIMARY KEY AUTOINCREMENT,
        content TEXT NOT NULL,
        category TEXT NOT NULL,
        timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
        user_id INTEGER NOT NULL,
        approved INTEGER DEFAULT NULL,
        channel_message_id INTEGER,
        flagged INTEGER DEFAULT 0,
        likes INTEGER DEFAULT 0,
        post_number INTEGER DEFAULT NULL,
        FOREIGN KEY(user_id) REFERENCES users(user_id)
    )''')
    
    # Comments table with enhanced structure
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS comments (
        comment_id INTEGER PRIMARY KEY AUTOINCREMENT,
        post_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        content TEXT NOT NULL,
        parent_comment_id INTEGER,
        timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
        likes INTEGER DEFAULT 0,
        dislikes INTEGER DEFAULT 0,
        flagged INTEGER DEFAULT 0,
        FOREIGN KEY(post_id) REFERENCES posts(post_id),
        FOREIGN KEY(user_id) REFERENCES users(user_id),
        FOREIGN KEY(parent_comment_id) REFERENCES comments(comment_id)
    )''')
    
    # Likes/Reactions table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS reactions (
        reaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        target_type TEXT NOT NULL, -- "post" or "comment"
        target_id INTEGER NOT NULL,
        reaction_type TEXT NOT NULL, -- "like" or "dislike"
        timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, target_type, target_id),
        FOREIGN KEY(user_id) REFERENCES users(user_id)
    )''')
    
    # Reports table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS reports (
        report_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        target_type TEXT NOT NULL,
        target_id INTEGER NOT NULL,
        reason TEXT,
        timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(user_id)
    )''')
    
    # Admin messages table for admin-user communication
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS admin_messages (
        message_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        admin_id INTEGER,
        user_message TEXT,
        admin_reply TEXT,
        timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
        replied INTEGER DEFAULT 0,
        FOREIGN KEY(user_id) REFERENCES users(user_id)
    )''')
    
    # Ranking system tables
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS user_rankings (
        user_id INTEGER PRIMARY KEY,
        total_points INTEGER DEFAULT 0,
        weekly_points INTEGER DEFAULT 0,
        monthly_points INTEGER DEFAULT 0,
        current_rank_id INTEGER DEFAULT 1,
        rank_progress REAL DEFAULT 0.0,
        total_achievements INTEGER DEFAULT 0,
        highest_rank_achieved INTEGER DEFAULT 1,
        consecutive_days INTEGER DEFAULT 0,
        last_login_date TEXT,
        last_activity TEXT DEFAULT CURRENT_TIMESTAMP,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(user_id)
    )''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS point_transactions (
        transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        points_change INTEGER NOT NULL,
        transaction_type TEXT NOT NULL,
        reference_id INTEGER,
        reference_type TEXT,
        description TEXT,
        timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(user_id)
    )''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS user_achievements (
        achievement_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        achievement_type TEXT NOT NULL,
        achievement_name TEXT NOT NULL,
        achievement_description TEXT,
        points_awarded INTEGER DEFAULT 0,
        is_special INTEGER DEFAULT 0,
        metadata TEXT,
        achieved_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(user_id)
    )''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS rank_definitions (
        rank_id INTEGER PRIMARY KEY,
        rank_name TEXT NOT NULL,
        rank_emoji TEXT NOT NULL,
        min_points INTEGER NOT NULL,
        max_points INTEGER,
        special_perks TEXT,
        is_special INTEGER DEFAULT 0
    )''')
    
    # Check if rank_definitions table has the correct columns before inserting
    try:
        # Test if the table has the correct schema by attempting to select from min_points
        cursor.execute("SELECT min_points FROM rank_definitions LIMIT 1")
        
        # If we get here, the table has the correct schema, so insert default rank definitions
        cursor.execute('''
        INSERT OR IGNORE INTO rank_definitions (rank_id, rank_name, rank_emoji, min_points, max_points, special_perks, is_special)
        VALUES 
            (1, 'Freshman', '🥉', 0, 99, '{}', 0),
            (2, 'Sophomore', '🥈', 100, 249, '{}', 0),
            (3, 'Junior', '🥇', 250, 499, '{}', 0),
            (4, 'Senior', '🏆', 500, 999, '{"daily_confessions": 8}', 0),
            (5, 'Graduate', '🎓', 1000, 1999, '{"daily_confessions": 10, "priority_review": true}', 0),
            (6, 'Master', '👑', 2000, 4999, '{"daily_confessions": 15, "priority_review": true, "comment_highlight": true}', 1),
            (7, 'Legend', '🌟', 5000, NULL, '{"all_perks": true, "unlimited_daily": true, "legend_badge": true}', 1)
        ''')
    except sqlite3.OperationalError as e:
        if "no such column: min_points" in str(e):
            print("Warning: rank_definitions table exists but has old schema. Run migrations to fix.")
            # Skip inserting for now - migrations will handle this
        else:
            raise e
    
    conn.commit()
    conn.close()

def add_user(user_id, username=None, first_name=None, last_name=None):
    """Add or update user information"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO users (user_id, username, first_name, last_name, join_date, questions_asked, comments_posted, blocked)
            VALUES (?, ?, ?, ?, 
                COALESCE((SELECT join_date FROM users WHERE user_id = ? AND join_date IS NOT NULL), CURRENT_TIMESTAMP),
                COALESCE((SELECT questions_asked FROM users WHERE user_id = ?), 0),
                COALESCE((SELECT comments_posted FROM users WHERE user_id = ?), 0),
                COALESCE((SELECT blocked FROM users WHERE user_id = ?), 0)
            )
        ''', (user_id, username, first_name, last_name, user_id, user_id, user_id, user_id))
        conn.commit()

def get_user_info(user_id):
    """Get complete user information"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT user_id, username, first_name, last_name, join_date, 
                   questions_asked, comments_posted, blocked
            FROM users WHERE user_id = ?
        ''', (user_id,))
        return cursor.fetchone()

def get_comment_count(post_id):
    """Get total comment count for a post (including replies)"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM comments WHERE post_id = ?', (post_id,))
        result = cursor.fetchone()
        return result[0] if result else 0

def is_blocked_user(user_id):
    """Check if user is blocked"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT blocked FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        return result and result[0] == 1

def get_user_posts(user_id, limit=10):
    """Get user's posts with status, comment count, and media information"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT p.post_id, p.content, p.category, p.timestamp, p.approved,
                   COUNT(c.comment_id) as comment_count, p.post_number,
                   p.media_type, p.media_file_id, p.media_file_unique_id, p.media_caption,
                   p.media_file_size, p.media_mime_type, p.media_duration, 
                   p.media_width, p.media_height, p.media_thumbnail_file_id
            FROM posts p
            LEFT JOIN comments c ON p.post_id = c.post_id
            WHERE p.user_id = ?
            GROUP BY p.post_id, p.content, p.category, p.timestamp, p.approved, p.post_number,
                     p.media_type, p.media_file_id, p.media_file_unique_id, p.media_caption,
                     p.media_file_size, p.media_mime_type, p.media_duration, 
                     p.media_width, p.media_height, p.media_thumbnail_file_id
            ORDER BY p.timestamp DESC
            LIMIT ?
        ''', (user_id, limit))
        return cursor.fetchall()
        
def get_post_author_id(post_id):
    """Get the user_id of the post author"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT user_id FROM posts WHERE post_id = ?', (post_id,))
        result = cursor.fetchone()
        return result[0] if result else None
