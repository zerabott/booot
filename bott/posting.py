from db import get_db

def get_post_content(post_id):
    """Get the content of a specific post"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT content FROM posts WHERE post_id = ?', (post_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None