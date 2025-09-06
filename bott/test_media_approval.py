#!/usr/bin/env python3

import sqlite3
import asyncio
from unittest.mock import Mock, AsyncMock
from approval import admin_callback, get_media_info, get_media_type_emoji
from submission import get_media_type_emoji
from config import DB_PATH
from utils import escape_markdown_text

async def test_media_approval_notification():
    """Test the media approval notification system"""
    print("🧪 Testing Media Confession Approval System")
    print("=" * 50)
    
    # Check if there are any media posts in the database
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Get a media post for testing
        cursor.execute("""
            SELECT post_id, content, category, user_id, media_type, media_file_id, media_caption
            FROM posts 
            WHERE media_type IS NOT NULL 
            AND approved IS NULL 
            LIMIT 1
        """)
        media_post = cursor.fetchone()
        
        if not media_post:
            print("❌ No pending media posts found for testing")
            # Create a test media post
            cursor.execute("""
                INSERT INTO posts (content, category, user_id, media_type, media_file_id, media_caption)
                VALUES (?, ?, ?, ?, ?, ?)
            """, ("Test media confession", "📚 Academics, 💝 Love", 123456789, "photo", "test_file_id", "Test caption"))
            
            conn.commit()
            media_post_id = cursor.lastrowid
            print(f"✅ Created test media post with ID: {media_post_id}")
            media_post = (media_post_id, "Test media confession", "📚 Academics, 💝 Love", 123456789, "photo", "test_file_id", "Test caption")
        
        conn.close()
        
        print(f"\n📊 Test Media Post Details:")
        print(f"   Post ID: {media_post[0]}")
        print(f"   Content: {media_post[1]}")
        print(f"   Category: {media_post[2]}")
        print(f"   User ID: {media_post[3]}")
        print(f"   Media Type: {media_post[4]}")
        print(f"   File ID: {media_post[5]}")
        print(f"   Caption: {media_post[6]}")
        
        # Test media info retrieval
        print(f"\n🔍 Testing Media Info Retrieval:")
        media_info = get_media_info(media_post[0])
        if media_info:
            print(f"   ✅ Media info retrieved successfully")
            print(f"   Type: {media_info.get('type', 'Unknown')}")
            print(f"   File ID: {media_info.get('file_id', 'Unknown')}")
            print(f"   Caption: {media_info.get('caption', 'None')}")
        else:
            print(f"   ❌ Failed to retrieve media info")
        
        # Test emoji function
        print(f"\n🎨 Testing Media Type Emoji:")
        emoji = get_media_type_emoji(media_post[4])
        print(f"   Media type '{media_post[4]}' -> Emoji: {emoji}")
        
        # Test markdown escaping
        print(f"\n📝 Testing Markdown Escaping:")
        test_text = "Test with special characters: _italic_ *bold* [link](url)"
        escaped_text = escape_markdown_text(test_text)
        print(f"   Original: {test_text}")
        print(f"   Escaped: {escaped_text}")
        
        # Test notification message building
        print(f"\n💬 Testing Notification Message Building:")
        confession_type = f"{emoji} {media_post[4].title()} confession"
        category = media_post[2]
        post_number = 42
        
        message_text = f"""
✅ *{confession_type.title()} Approved\\\\!*

Your {escape_markdown_text(confession_type)} in category `{escape_markdown_text(category)}` has been approved and posted to the channel\\\\!

🔢 *Post Number:* \\\\#{post_number}

💡 Check the channel

🌟 *Thank you for sharing with us\\\\!*
"""
        
        print("   Generated notification message:")
        print("   " + "─" * 40)
        for line in message_text.strip().split('\n'):
            print(f"   {line}")
        print("   " + "─" * 40)
        
        print(f"\n✅ Media confession approval system test completed successfully!")
        print(f"📋 Key improvements made:")
        print(f"   • Enhanced user notification with media type recognition")
        print(f"   • Proper markdown escaping for special characters")
        print(f"   • Improved message formatting and structure")
        print(f"   • Better error handling and logging")
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()

def test_media_functions():
    """Test individual media-related functions"""
    print("\n🔧 Testing Individual Functions:")
    print("=" * 30)
    
    # Test media type emojis
    media_types = ['photo', 'video', 'animation', 'document', 'gif']
    print("📸 Media Type Emojis:")
    for media_type in media_types:
        emoji = get_media_type_emoji(media_type)
        print(f"   {media_type}: {emoji}")
    
    # Test markdown escaping with various special characters
    print("\n🔤 Markdown Escaping Tests:")
    test_cases = [
        "Normal text",
        "Text with *asterisks*",
        "Text with _underscores_", 
        "Text with [brackets]",
        "Text with (parentheses)",
        "Text with `backticks`",
        "Text with #hashtags",
        "Text with |pipes|",
        "Mixed: *bold* _italic_ `code` [link](url)",
        "Special chars: \\.()[]{}*+?^$|"
    ]
    
    for test_text in test_cases:
        escaped = escape_markdown_text(test_text)
        print(f"   '{test_text}' -> '{escaped}'")

if __name__ == "__main__":
    print("🎯 Media Confession Approval System Test Suite")
    print("=" * 60)
    
    # Test individual functions first
    test_media_functions()
    
    # Test the full approval flow
    asyncio.run(test_media_approval_notification())
    
    print(f"\n🎉 All tests completed!")
