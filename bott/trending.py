"""
Trending and Popular Posts Module
Handles fetching of trending posts, most commented posts, and rising posts
"""

import sqlite3
from datetime import datetime, timedelta
from typing import List, Tuple, Optional
from config import DB_PATH
from logger import get_logger

logger = get_logger('trending')

def get_most_commented_posts_24h(limit: int = 10) -> List[Tuple]:
    """Get posts with most comments in the last 24 hours"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            # Get posts from last 24 hours ordered by comment count
            yesterday = (datetime.now() - timedelta(days=1)).isoformat()
            
            cursor.execute("""
                SELECT p.post_id, p.content, p.category, p.timestamp, 
                       COUNT(c.comment_id) as comment_count,
                       p.approved, p.channel_message_id, p.post_number,
                       p.media_type, p.media_file_id, p.media_file_unique_id, p.media_caption,
                       p.media_file_size, p.media_mime_type, p.media_duration, 
                       p.media_width, p.media_height, p.media_thumbnail_file_id
                FROM posts p 
                LEFT JOIN comments c ON p.post_id = c.post_id 
                WHERE p.approved = 1 
                AND p.timestamp >= ?
                GROUP BY p.post_id 
                ORDER BY comment_count DESC, p.timestamp DESC 
                LIMIT ?
            """, (yesterday, limit))
            
            return cursor.fetchall()
            
    except Exception as e:
        logger.error(f"Error getting most commented posts (24h): {e}")
        return []

def get_posts_with_most_liked_comments(limit: int = 10) -> List[Tuple]:
    """Get posts that have comments with the most likes"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            # Get posts ordered by total likes on their comments
            cursor.execute("""
                SELECT p.post_id, p.content, p.category, p.timestamp,
                       COUNT(c.comment_id) as comment_count,
                       COALESCE(SUM(c.likes), 0) as total_comment_likes,
                       p.approved, p.channel_message_id, p.post_number,
                       p.media_type, p.media_file_id, p.media_file_unique_id, p.media_caption,
                       p.media_file_size, p.media_mime_type, p.media_duration, 
                       p.media_width, p.media_height, p.media_thumbnail_file_id
                FROM posts p 
                LEFT JOIN comments c ON p.post_id = c.post_id 
                WHERE p.approved = 1 
                GROUP BY p.post_id 
                HAVING total_comment_likes > 0
                ORDER BY total_comment_likes DESC, comment_count DESC, p.timestamp DESC 
                LIMIT ?
            """, (limit,))
            
            return cursor.fetchall()
            
    except Exception as e:
        logger.error(f"Error getting posts with most liked comments: {e}")
        return []

def get_rising_posts(limit: int = 10) -> List[Tuple]:
    """Get posts that are gaining traction fast (recent posts with growing engagement)"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            # Get posts from last 12 hours ordered by engagement rate
            twelve_hours_ago = (datetime.now() - timedelta(hours=12)).isoformat()
            
            cursor.execute("""
                SELECT p.post_id, p.content, p.category, p.timestamp,
                       COUNT(c.comment_id) as comment_count,
                       COALESCE(SUM(c.likes), 0) as total_comment_likes,
                       p.approved, p.channel_message_id, p.post_number,
                       -- Calculate engagement score based on recency and activity
                       (COUNT(c.comment_id) * 2 + COALESCE(SUM(c.likes), 0)) * 
                       (CASE 
                           WHEN p.timestamp >= ? THEN 3
                           WHEN p.timestamp >= datetime('now', '-6 hours') THEN 2
                           ELSE 1
                       END) as engagement_score,
                       p.media_type, p.media_file_id, p.media_file_unique_id, p.media_caption,
                       p.media_file_size, p.media_mime_type, p.media_duration, 
                       p.media_width, p.media_height, p.media_thumbnail_file_id
                FROM posts p 
                LEFT JOIN comments c ON p.post_id = c.post_id 
                WHERE p.approved = 1 
                AND p.timestamp >= datetime('now', '-24 hours')
                GROUP BY p.post_id 
                HAVING comment_count > 0 OR total_comment_likes > 0
                ORDER BY engagement_score DESC, p.timestamp DESC 
                LIMIT ?
            """, (twelve_hours_ago, limit))
            
            return cursor.fetchall()
            
    except Exception as e:
        logger.error(f"Error getting rising posts: {e}")
        return []

def get_trending_posts(limit: int = 15) -> List[Tuple]:
    """Get overall trending posts - combination of most commented and rising"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            # Get trending posts from last 48 hours with weighted scoring
            two_days_ago = (datetime.now() - timedelta(days=2)).isoformat()
            
            cursor.execute("""
                SELECT p.post_id, p.content, p.category, p.timestamp,
                       COUNT(c.comment_id) as comment_count,
                       COALESCE(SUM(c.likes), 0) as total_comment_likes,
                       p.approved, p.channel_message_id, p.post_number,
                       -- Trending score: comments worth more than likes, recent posts get bonus
                       (COUNT(c.comment_id) * 5 + COALESCE(SUM(c.likes), 0) * 2) * 
                       (CASE 
                           WHEN p.timestamp >= datetime('now', '-12 hours') THEN 2.5
                           WHEN p.timestamp >= datetime('now', '-24 hours') THEN 2.0
                           WHEN p.timestamp >= datetime('now', '-48 hours') THEN 1.5
                           ELSE 1.0
                       END) as trending_score,
                       p.media_type, p.media_file_id, p.media_file_unique_id, p.media_caption,
                       p.media_file_size, p.media_mime_type, p.media_duration, 
                       p.media_width, p.media_height, p.media_thumbnail_file_id
                FROM posts p 
                LEFT JOIN comments c ON p.post_id = c.post_id 
                WHERE p.approved = 1 
                AND p.timestamp >= ?
                GROUP BY p.post_id 
                HAVING trending_score > 0
                ORDER BY trending_score DESC, p.timestamp DESC 
                LIMIT ?
            """, (two_days_ago, limit))
            
            return cursor.fetchall()
            
    except Exception as e:
        logger.error(f"Error getting trending posts: {e}")
        return []

def get_popular_today_posts(limit: int = 15) -> List[Tuple]:
    """Get today's most popular posts"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            # Get today's posts ordered by engagement
            today = datetime.now().strftime('%Y-%m-%d')
            
            cursor.execute("""
                SELECT p.post_id, p.content, p.category, p.timestamp,
                       COUNT(c.comment_id) as comment_count,
                       COALESCE(SUM(c.likes), 0) as total_comment_likes,
                       p.approved, p.channel_message_id, p.post_number,
                       -- Today's popularity score
                       (COUNT(c.comment_id) * 3 + COALESCE(SUM(c.likes), 0)) as popularity_score,
                       p.media_type, p.media_file_id, p.media_file_unique_id, p.media_caption,
                       p.media_file_size, p.media_mime_type, p.media_duration, 
                       p.media_width, p.media_height, p.media_thumbnail_file_id
                FROM posts p 
                LEFT JOIN comments c ON p.post_id = c.post_id 
                WHERE p.approved = 1 
                AND DATE(p.timestamp) = DATE('now')
                GROUP BY p.post_id 
                ORDER BY popularity_score DESC, comment_count DESC, p.timestamp DESC 
                LIMIT ?
            """, (limit,))
            
            return cursor.fetchall()
            
    except Exception as e:
        logger.error(f"Error getting popular today posts: {e}")
        return []

def get_post_engagement_stats(post_id: int) -> Optional[dict]:
    """Get engagement statistics for a specific post"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    COUNT(c.comment_id) as comment_count,
                    COALESCE(SUM(c.likes), 0) as total_likes,
                    COALESCE(SUM(c.dislikes), 0) as total_dislikes,
                    COUNT(DISTINCT c.user_id) as unique_commenters
                FROM comments c 
                WHERE c.post_id = ?
            """, (post_id,))
            
            result = cursor.fetchone()
            if result:
                return {
                    'comment_count': result[0],
                    'total_likes': result[1],
                    'total_dislikes': result[2],
                    'unique_commenters': result[3],
                    'engagement_ratio': result[1] / max(result[2], 1)  # likes/dislikes ratio
                }
            return None
            
    except Exception as e:
        logger.error(f"Error getting engagement stats for post {post_id}: {e}")
        return None
