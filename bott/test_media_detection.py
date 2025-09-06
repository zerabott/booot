#!/usr/bin/env python3
"""Test script to debug media detection in view_my_confessions_callback"""

from db import get_user_posts
import sqlite3
from config import DB_PATH

def test_media_detection():
    """Test the media detection logic from view_my_confessions_callback"""
    
    # Find a user who has media posts
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT DISTINCT user_id FROM posts WHERE media_type IS NOT NULL LIMIT 1')
    result = cursor.fetchone()
    
    if not result:
        print("No media posts found in database")
        return
    
    user_id = result[0]
    print(f"Testing media detection for user_id: {user_id}")
    
    posts = get_user_posts(user_id, 10)
    print(f"Total posts retrieved: {len(posts)}\n")
    
    media_posts_found = 0
    text_posts_found = 0
    
    for i, post in enumerate(posts, 1):
        post_id = post[0]
        content = post[1]
        category = post[2]
        timestamp = post[3]
        approved = post[4]
        comment_count = post[5]
        post_number = post[6] if len(post) > 6 and post[6] is not None else post_id
        media_type = post[7] if len(post) > 7 else None
        media_file_id = post[8] if len(post) > 8 else None
        media_caption = post[10] if len(post) > 10 else None
        
        print(f"Post {i} (ID: {post_id}):")
        print(f"  Content: {content}")
        print(f"  Category: {category}")
        print(f"  Approved: {approved}")
        print(f"  Media Type: {media_type}")
        print(f"  Media File ID: {media_file_id[:30] + '...' if media_file_id else 'None'}")
        print(f"  Media Caption: {media_caption}")
        
        # Test the media detection logic from bot.py
        if media_type and media_file_id:
            media_posts_found += 1
            print(f"  -> DETECTED AS MEDIA POST")
            print(f"  -> Would send as {media_type}")
        else:
            text_posts_found += 1
            print(f"  -> DETECTED AS TEXT POST")
        
        print()
    
    print(f"Summary:")
    print(f"  Media posts detected: {media_posts_found}")
    print(f"  Text posts detected: {text_posts_found}")
    print(f"  Total posts: {len(posts)}")
    
    # Check database directly for comparison
    cursor.execute('''
        SELECT COUNT(*) FROM posts 
        WHERE user_id = ? AND media_type IS NOT NULL
    ''', (user_id,))
    actual_media_count = cursor.fetchone()[0]
    
    cursor.execute('''
        SELECT COUNT(*) FROM posts 
        WHERE user_id = ? AND media_type IS NULL
    ''', (user_id,))
    actual_text_count = cursor.fetchone()[0]
    
    print(f"\nDatabase verification:")
    print(f"  Actual media posts in DB: {actual_media_count}")
    print(f"  Actual text posts in DB: {actual_text_count}")
    
    if media_posts_found != actual_media_count:
        print(f"  ❌ MISMATCH! Detection found {media_posts_found} but DB has {actual_media_count}")
    else:
        print(f"  ✅ Media detection is working correctly")
    
    conn.close()

if __name__ == "__main__":
    test_media_detection()
