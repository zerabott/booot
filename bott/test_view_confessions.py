#!/usr/bin/env python3
"""Test script to simulate view_my_confessions_callback and identify media sending issues"""

from db import get_user_posts
import sqlite3
from config import DB_PATH
from utils import escape_markdown_text

def simulate_view_confessions():
    """Simulate the view_my_confessions_callback logic"""
    
    # Find a user who has media posts
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT DISTINCT user_id FROM posts WHERE media_type IS NOT NULL LIMIT 1')
    result = cursor.fetchone()
    
    if not result:
        print("No media posts found in database")
        return
    
    user_id = result[0]
    print(f"Simulating view_my_confessions_callback for user_id: {user_id}\n")
    
    posts = get_user_posts(user_id, 10)
    
    if not posts:
        print("No posts found for this user")
        return
        
    print(f"Found {len(posts)} posts. Processing each one...\n")
    
    media_posts_attempted = 0
    media_posts_that_would_send = 0
    text_posts = 0
    
    for post in posts:
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

        status_emoji = "✅" if approved == 1 else "⏳" if approved is None else "❌"
        status_text = "Approved" if approved == 1 else "Pending" if approved is None else "Rejected"

        print(f"Processing Post #{post_number} (ID: {post_id}):")
        print(f"  Content: {content[:50]}{'...' if len(content) > 50 else ''}")
        print(f"  Category: {category}")
        print(f"  Status: {status_text}")
        print(f"  Comments: {comment_count}")
        
        # Test the media detection logic
        if media_type and media_file_id:
            media_posts_attempted += 1
            print(f"  Media Type: {media_type}")
            print(f"  Media File ID: {media_file_id[:30]}...")
            print(f"  Media Caption: {media_caption}")
            print(f"  -> WOULD ATTEMPT TO SEND AS MEDIA")
            
            # Simulate the caption creation
            try:
                caption_text = f"*{escape_markdown_text(category)}*\\n\\n"
                
                if content and content.strip():
                    caption_text += f"{escape_markdown_text(content)}\\n\\n"
                elif media_caption and media_caption.strip():
                    caption_text += f"{escape_markdown_text(media_caption)}\\n\\n"
                
                caption_text += f"*\\\\#{post_number}* {status_emoji} {escape_markdown_text(status_text)} \\\\| "
                caption_text += f"💬 {comment_count} comments"
                
                print(f"  -> Caption would be: {caption_text[:100]}...")
                
                # Check if file ID looks valid
                if len(media_file_id) > 20 and media_file_id.startswith(('AgAC', 'BAAC', 'CgAC', 'BgAC')):
                    media_posts_that_would_send += 1
                    print(f"  -> ✅ File ID looks valid, would likely send successfully")
                else:
                    print(f"  -> ⚠️ File ID looks suspicious, might fail to send")
                    
            except Exception as e:
                print(f"  -> ❌ Error creating caption: {e}")
        else:
            text_posts += 1
            print(f"  -> WOULD SEND AS TEXT POST")
            
            # Simulate text message creation
            try:
                confession_text = f"*{escape_markdown_text(category)}*\\n\\n{escape_markdown_text(content)}\\n\\n"
                confession_text += f"*\\\\#{post_number}* {status_emoji} {escape_markdown_text(status_text)} \\\\| "
                confession_text += f"💬 {comment_count} comments"
                print(f"  -> Text would be: {confession_text[:100]}...")
                print(f"  -> ✅ Would send as text successfully")
            except Exception as e:
                print(f"  -> ❌ Error creating text: {e}")
        
        print()
    
    print("Summary:")
    print(f"  Total posts: {len(posts)}")
    print(f"  Media posts attempted: {media_posts_attempted}")
    print(f"  Media posts that would likely succeed: {media_posts_that_would_send}")
    print(f"  Text posts: {text_posts}")
    
    if media_posts_attempted != media_posts_that_would_send:
        print(f"  ⚠️ {media_posts_attempted - media_posts_that_would_send} media posts might fail due to invalid file IDs")
    
    conn.close()

if __name__ == "__main__":
    simulate_view_confessions()
