#!/usr/bin/env python3

import sqlite3

def check_posts_schema():
    try:
        conn = sqlite3.connect('confessions.db')
        cursor = conn.cursor()
        
        # Get posts table schema
        cursor.execute("PRAGMA table_info(posts)")
        columns = cursor.fetchall()
        
        print('Posts table schema:')
        for column in columns:
            print(f'  {column[1]} ({column[2]}) - Default: {column[4]} - Not Null: {column[3]}')
        
        # Check if media columns exist
        media_columns = [
            'media_type', 'media_file_id', 'media_file_unique_id', 'media_caption',
            'media_file_size', 'media_mime_type', 'media_duration', 
            'media_width', 'media_height', 'media_thumbnail_file_id'
        ]
        
        existing_columns = [col[1] for col in columns]
        
        print('\nMedia columns status:')
        for col in media_columns:
            status = "✅ EXISTS" if col in existing_columns else "❌ MISSING"
            print(f'  {col}: {status}')
        
        # Check if there are any posts with media
        cursor.execute("SELECT COUNT(*) FROM posts WHERE media_type IS NOT NULL")
        media_posts = cursor.fetchone()[0] if 'media_type' in existing_columns else 0
        print(f'\nPosts with media: {media_posts}')
        
        conn.close()
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_posts_schema()
