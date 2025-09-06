#!/usr/bin/env python3
"""Test script to verify media file IDs are valid and can be sent"""

import sqlite3
from config import DB_PATH
from db import get_user_posts
from utils import escape_markdown_text

def test_media_file_ids():
    """Test if media file IDs are still valid"""
    
    # Find a user who has media posts
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT DISTINCT user_id FROM posts WHERE media_type IS NOT NULL LIMIT 1')
    result = cursor.fetchone()
    
    if not result:
        print("No media posts found in database")
        return
    
    user_id = result[0]
    print(f"Testing media file IDs for user_id: {user_id}\n")
    
    posts = get_user_posts(user_id, 10)
    
    if not posts:
        print("No posts found for this user")
        return
        
    print(f"Found {len(posts)} posts. Analyzing media file IDs...\n")
    
    media_posts = []
    text_posts = []
    
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
        
        print(f"Post #{post_number} (ID: {post_id}):")
        print(f"  Content: {content[:50]}{'...' if len(content) > 50 else ''}")
        print(f"  Category: {category}")
        print(f"  Status: {status_text}")
        print(f"  Comments: {comment_count}")
        
        if media_type and media_file_id:
            print(f"  Media Type: {media_type}")
            print(f"  Media File ID: {media_file_id}")
            print(f"  Media Caption: {media_caption}")
            
            # Analyze file ID structure
            file_id_analysis = analyze_file_id(media_file_id, media_type)
            print(f"  File ID Analysis: {file_id_analysis}")
            
            # Check if it would be processed by the bot
            would_send_as_media = check_bot_processing(media_type, media_file_id, content, media_caption, category, post_number, status_emoji, status_text, comment_count, timestamp)
            if would_send_as_media:
                print(f"  -> ✅ WOULD BE SENT AS {media_type.upper()} MEDIA")
                media_posts.append(post)
            else:
                print(f"  -> ❌ WOULD FALL BACK TO TEXT")
                text_posts.append(post)
        else:
            print(f"  -> 📝 WOULD BE SENT AS TEXT POST")
            text_posts.append(post)
        
        print()
    
    print("="*60)
    print("SUMMARY:")
    print(f"📱 Total posts that SHOULD appear as media: {len(media_posts)}")
    print(f"📝 Total posts that would be text: {len(text_posts)}")
    print()
    
    if media_posts:
        print("🎯 MEDIA POSTS BREAKDOWN:")
        media_counts = {}
        for post in media_posts:
            media_type = post[7]
            if media_type in media_counts:
                media_counts[media_type] += 1
            else:
                media_counts[media_type] = 1
        
        for media_type, count in media_counts.items():
            print(f"  {media_type}: {count} posts")
        
        print("\n🔍 DETAILED MEDIA ANALYSIS:")
        for post in media_posts:
            post_number = post[6] if len(post) > 6 and post[6] is not None else post[0]
            media_type = post[7]
            media_file_id = post[8]
            approved = post[4]
            
            approval_status = "✅ Approved" if approved == 1 else "⏳ Pending" if approved is None else "❌ Rejected"
            print(f"  Post #{post_number}: {media_type} - {approval_status}")
            print(f"    File ID: {media_file_id[:40]}...")
            print(f"    Length: {len(media_file_id)} chars")
    
    if len(media_posts) > 0:
        print(f"\n🤔 DIAGNOSIS:")
        print(f"   Your database contains {len(media_posts)} media posts that should appear as media.")
        print(f"   If these are showing as text in the bot, possible causes:")
        print(f"   1. 🕰️ File IDs have expired (Telegram file IDs can expire)")
        print(f"   2. 🔄 Bot restart needed to pick up code changes") 
        print(f"   3. 🚫 Bot lacks permissions to send media")
        print(f"   4. 📱 Client/app issue showing media")
        print(f"   5. 🐛 Bot code not running the updated version")
    else:
        print(f"\n❌ NO MEDIA POSTS FOUND:")
        print(f"   This explains why only text posts appear!")
        print(f"   To fix: Submit confessions with photos/videos/GIFs")
    
    conn.close()

def analyze_file_id(file_id, media_type):
    """Analyze a Telegram file ID structure"""
    if not file_id:
        return "❌ Empty file ID"
    
    length = len(file_id)
    
    # Telegram file ID patterns
    patterns = {
        'photo': ['AgAC', 'AQAC', 'BgAC'],
        'video': ['BAAC', 'BQAC'],
        'animation': ['CgAC', 'CQAC'],  # GIFs
        'document': ['BgAC', 'BwAC', 'CAAC']
    }
    
    expected_patterns = patterns.get(media_type, [])
    starts_correctly = any(file_id.startswith(pattern) for pattern in expected_patterns)
    
    analysis_parts = []
    
    if starts_correctly:
        analysis_parts.append("✅ Valid prefix")
    else:
        analysis_parts.append(f"⚠️ Unusual prefix (starts with {file_id[:4]})")
    
    if length > 50:
        analysis_parts.append("✅ Good length")
    elif length > 30:
        analysis_parts.append("⚠️ Short length")
    else:
        analysis_parts.append("❌ Very short")
    
    # Check for common valid patterns
    if all(c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_' for c in file_id):
        analysis_parts.append("✅ Valid chars")
    else:
        analysis_parts.append("❌ Invalid chars")
    
    return " | ".join(analysis_parts)

def check_bot_processing(media_type, media_file_id, content, media_caption, category, post_number, status_emoji, status_text, comment_count, timestamp):
    """Simulate the bot's processing logic for media posts"""
    
    # This simulates the exact logic from view_my_confessions_callback
    if not media_type or not media_file_id:
        return False
    
    # Create caption like the bot would
    try:
        caption_text = f"*{escape_markdown_text(category)}*\\n\\n"
        
        if content and content.strip():
            caption_text += f"{escape_markdown_text(content)}\\n\\n"
        elif media_caption and media_caption.strip():
            caption_text += f"{escape_markdown_text(media_caption)}\\n\\n"
        
        caption_text += f"*\\\\#{post_number}* {status_emoji} {escape_markdown_text(status_text)} \\\\| "
        caption_text += f"💬 {comment_count} comments"
        
        # Check if media type is supported
        supported_types = ['photo', 'video', 'animation', 'document']
        if media_type in supported_types:
            return True
        else:
            return False
            
    except Exception as e:
        return False

if __name__ == "__main__":
    test_media_file_ids()
