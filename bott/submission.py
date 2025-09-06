import sqlite3
from config import (
    DB_PATH, MAX_PHOTO_SIZE_MB, MAX_VIDEO_SIZE_MB, MAX_GIF_SIZE_MB,
    MAX_CAPTION_LENGTH, SUPPORTED_MEDIA_TYPES, SUPPORTED_VIDEO_FORMATS,
    SUPPORTED_IMAGE_FORMATS, ALLOW_MEDIA_CONFESSIONS
)

def validate_media(file, media_type):
    """Validate media file size and type"""
    if not ALLOW_MEDIA_CONFESSIONS:
        return False, "Media confessions are currently disabled."
    
    if media_type not in SUPPORTED_MEDIA_TYPES:
        return False, f"Unsupported media type: {media_type}"
    
    # Check file size
    file_size_mb = file.file_size / (1024 * 1024) if file.file_size else 0
    
    if media_type == 'photo':
        if file_size_mb > MAX_PHOTO_SIZE_MB:
            return False, f"Photo size exceeds {MAX_PHOTO_SIZE_MB}MB limit."
    elif media_type == 'video':
        if file_size_mb > MAX_VIDEO_SIZE_MB:
            return False, f"Video size exceeds {MAX_VIDEO_SIZE_MB}MB limit."
    elif media_type == 'animation':  # GIFs
        if file_size_mb > MAX_GIF_SIZE_MB:
            return False, f"GIF size exceeds {MAX_GIF_SIZE_MB}MB limit."
    elif media_type == 'document':
        # For documents, check if it's a supported image or video format
        if hasattr(file, 'file_name') and file.file_name:
            file_ext = '.' + file.file_name.split('.')[-1].lower() if '.' in file.file_name else ''
            if file_ext not in SUPPORTED_IMAGE_FORMATS and file_ext not in SUPPORTED_VIDEO_FORMATS:
                return False, f"Unsupported file format: {file_ext}"
        if file_size_mb > max(MAX_PHOTO_SIZE_MB, MAX_VIDEO_SIZE_MB):
            return False, f"File size exceeds maximum limit."
    
    return True, None

def validate_caption(caption):
    """Validate media caption length"""
    if caption and len(caption) > MAX_CAPTION_LENGTH:
        return False, f"Caption exceeds {MAX_CAPTION_LENGTH} character limit."
    return True, None

def get_media_type_emoji(media_type):
    """Get emoji for media type"""
    emoji_map = {
        'photo': '📷',
        'video': '🎥',
        'animation': '🎞️',
        'gif': '🎞️',
        'document': '📎'
    }
    return emoji_map.get(media_type, '📎')

def save_submission(user_id, content, category, media_type=None, file_id=None, caption=None, media_data=None):
    """Save a new submission to the database"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            if media_data:
                # Save media submission (new complex format)
                cursor.execute("""
                    INSERT INTO posts (
                        content, category, user_id, media_type, media_file_id, 
                        media_file_unique_id, media_caption, media_file_size, 
                        media_mime_type, media_duration, media_width, 
                        media_height, media_thumbnail_file_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    content,  # Can be None for media-only posts
                    category,
                    user_id,
                    media_data.get('type'),
                    media_data.get('file_id'),
                    media_data.get('file_unique_id'),
                    media_data.get('caption'),
                    media_data.get('file_size'),
                    media_data.get('mime_type'),
                    media_data.get('duration'),
                    media_data.get('width'),
                    media_data.get('height'),
                    media_data.get('thumbnail_file_id')
                ))
            elif media_type and file_id:
                # Save media submission (simple format, for compatibility)
                cursor.execute(
                    "INSERT INTO posts (content, category, user_id, media_type, media_file_id, media_caption) VALUES (?, ?, ?, ?, ?, ?)",
                    (content, category, user_id, media_type, file_id, caption)
                )
            else:
                # Save text-only submission (original functionality)
                cursor.execute(
                    "INSERT INTO posts (content, category, user_id) VALUES (?, ?, ?)",
                    (content, category, user_id)
                )
            
            post_id = cursor.lastrowid
            
            # Update user stats
            cursor.execute(
                "UPDATE users SET questions_asked = questions_asked + 1 WHERE user_id = ?",
                (user_id,)
            )
            conn.commit()
            return post_id, None
    except Exception as e:
        return None, f"Database error: {str(e)}"

def get_pending_submissions():
    """Get all submissions pending approval"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM posts WHERE approved IS NULL ORDER BY timestamp DESC")
        return cursor.fetchall()

def get_recent_posts(limit=10):
    """Get recent approved posts with comment counts"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT p.*, 
                   COALESCE(c.comment_count, 0) as comment_count
            FROM posts p
            LEFT JOIN (
                SELECT post_id, COUNT(*) as comment_count
                FROM comments
                GROUP BY post_id
            ) c ON p.post_id = c.post_id
            WHERE p.approved = 1
            ORDER BY p.timestamp DESC
            LIMIT ?
        ''', (limit,))
        return cursor.fetchall()

def get_post_by_id(post_id):
    """Get a specific post by ID with comment count"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT p.*, 
                   COALESCE(c.comment_count, 0) as comment_count
            FROM posts p
            LEFT JOIN (
                SELECT post_id, COUNT(*) as comment_count
                FROM comments
                GROUP BY post_id
            ) c ON p.post_id = c.post_id
            WHERE p.post_id = ?
        ''', (post_id,))
        return cursor.fetchone()

def get_todays_posts():
    """Get all approved posts from today"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT p.post_id, p.content, p.category, p.timestamp, p.approved,
                   COALESCE(c.comment_count, 0) as comment_count, p.post_number
            FROM posts p
            LEFT JOIN (
                SELECT post_id, COUNT(*) as comment_count
                FROM comments
                GROUP BY post_id
            ) c ON p.post_id = c.post_id
            WHERE p.approved = 1 
            AND date(p.timestamp) = date('now')
            ORDER BY p.timestamp DESC
        ''', ())
        return cursor.fetchall()

def get_todays_posts_with_media():
    """Get all approved posts from today including media information"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT p.post_id, p.content, p.category, p.timestamp, p.user_id, p.approved, 
                   p.channel_message_id, p.flagged, p.likes, p.post_number,
                   p.media_type, p.media_file_id, p.media_file_unique_id, p.media_caption,
                   p.media_file_size, p.media_mime_type, p.media_duration, 
                   p.media_width, p.media_height, p.media_thumbnail_file_id,
                   COALESCE(c.comment_count, 0) as comment_count
            FROM posts p
            LEFT JOIN (
                SELECT post_id, COUNT(*) as comment_count
                FROM comments
                GROUP BY post_id
            ) c ON p.post_id = c.post_id
            WHERE p.approved = 1
            AND date(p.timestamp) = date('now')
            ORDER BY p.timestamp DESC
        ''', ())
        return cursor.fetchall()

def get_post_with_media(post_id):
    """Get a specific post by ID including media information"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT p.post_id, p.content, p.category, p.timestamp, p.user_id, p.approved, 
                   p.channel_message_id, p.flagged, p.likes, p.post_number,
                   p.media_type, p.media_file_id, p.media_file_unique_id, p.media_caption,
                   p.media_file_size, p.media_mime_type, p.media_duration, 
                   p.media_width, p.media_height, p.media_thumbnail_file_id,
                   COALESCE(c.comment_count, 0) as comment_count
            FROM posts p
            LEFT JOIN (
                SELECT post_id, COUNT(*) as comment_count
                FROM comments
                GROUP BY post_id
            ) c ON p.post_id = c.post_id
            WHERE p.post_id = ?
        ''', (post_id,))
        return cursor.fetchone()

def get_recent_posts_with_media(limit=10):
    """Get recent approved posts including media information"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT p.post_id, p.content, p.category, p.timestamp, p.user_id, p.approved, 
                   p.channel_message_id, p.flagged, p.likes, p.post_number,
                   p.media_type, p.media_file_id, p.media_file_unique_id, p.media_caption,
                   p.media_file_size, p.media_mime_type, p.media_duration, 
                   p.media_width, p.media_height, p.media_thumbnail_file_id,
                   COALESCE(c.comment_count, 0) as comment_count
            FROM posts p
            LEFT JOIN (
                SELECT post_id, COUNT(*) as comment_count
                FROM comments
                GROUP BY post_id
            ) c ON p.post_id = c.post_id
            WHERE p.approved = 1
            ORDER BY p.timestamp DESC
            LIMIT ?
        ''', (limit,))
        return cursor.fetchall()

def get_pending_submissions_with_media():
    """Get all submissions pending approval including media information"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT post_id, content, category, timestamp, user_id, approved, 
                   channel_message_id, flagged, likes, post_number,
                   media_type, media_file_id, media_file_unique_id, media_caption,
                   media_file_size, media_mime_type, media_duration, 
                   media_width, media_height, media_thumbnail_file_id
            FROM posts 
            WHERE approved IS NULL 
            ORDER BY timestamp DESC
        ''')
        return cursor.fetchall()

def is_media_post(post_id):
    """Check if a post contains media"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT media_type FROM posts WHERE post_id = ?",
            (post_id,)
        )
        result = cursor.fetchone()
        return result and result[0] is not None

def get_media_info(post_id):
    """Get media information for a specific post"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT media_type, media_file_id, media_file_unique_id, media_caption,
                      media_file_size, media_mime_type, media_duration, 
                      media_width, media_height, media_thumbnail_file_id
               FROM posts WHERE post_id = ?""",
            (post_id,)
        )
        result = cursor.fetchone()
        if result and result[0]:  # Check if media_type is not None
            return {
                'type': result[0],
                'file_id': result[1],
                'file_unique_id': result[2],
                'caption': result[3],
                'file_size': result[4],
                'mime_type': result[5],
                'duration': result[6],
                'width': result[7],
                'height': result[8],
                'thumbnail_file_id': result[9]
            }
        return None

def get_user_posts(user_id, limit=20):
    """Get user's confession history"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT p.post_id, p.content, p.category, p.timestamp, p.approved,
                   COALESCE(c.comment_count, 0) as comment_count, p.post_number
            FROM posts p
            LEFT JOIN (
                SELECT post_id, COUNT(*) as comment_count
                FROM comments
                GROUP BY post_id
            ) c ON p.post_id = c.post_id
            WHERE p.user_id = ?
            ORDER BY p.timestamp DESC
            LIMIT ?
        ''', (user_id, limit))
        return cursor.fetchall()
