import sqlite3
import csv
from datetime import datetime
from config import DB_PATH, ADMIN_IDS

def report_abuse(user_id, target_type, target_id, reason):
    """Report abuse for a post or comment"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        
        # Check if user has already reported this content
        cursor.execute(
            "SELECT COUNT(*) FROM reports WHERE user_id = ? AND target_type = ? AND target_id = ?",
            (user_id, target_type, target_id)
        )
        existing_report = cursor.fetchone()[0]
        
        if existing_report > 0:
            # User has already reported this content, return current count without adding duplicate
            cursor.execute(
                "SELECT COUNT(*) FROM reports WHERE target_type = ? AND target_id = ?",
                (target_type, target_id)
            )
            return cursor.fetchone()[0]
        
        # Insert new report since it's not a duplicate
        cursor.execute(
            "INSERT INTO reports (user_id, target_type, target_id, reason) VALUES (?, ?, ?, ?)",
            (user_id, target_type, target_id, reason)
        )
        
        # Check if this target has reached the report threshold (5 reports)
        cursor.execute(
            "SELECT COUNT(*) FROM reports WHERE target_type = ? AND target_id = ?",
            (target_type, target_id)
        )
        report_count = cursor.fetchone()[0]
        
        conn.commit()
        
        # Return report count for notification handling
        return report_count

def get_reports():
    """Get all abuse reports"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM reports ORDER BY timestamp DESC")
        return cursor.fetchall()

def get_flagged_content():
    """Get all flagged posts and comments"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        
        # Get flagged posts
        cursor.execute("SELECT 'post', post_id, content, category, timestamp FROM posts WHERE flagged = 1")
        flagged_posts = cursor.fetchall()
        
        # Get flagged comments
        cursor.execute("SELECT 'comment', comment_id, content, post_id, timestamp FROM comments WHERE flagged = 1")
        flagged_comments = cursor.fetchall()
        
        return flagged_posts + flagged_comments

def export_confessions_csv():
    """Export all confessions to CSV"""
    filename = f"confessions_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM posts")
        posts = cursor.fetchall()
    
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['post_id', 'content', 'category', 'timestamp', 'user_id', 'approved', 'channel_message_id', 'flagged', 'likes'])
        writer.writerows(posts)
    
    return filename

def export_comments_csv():
    """Export all comments to CSV"""
    filename = f"comments_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM comments")
        comments = cursor.fetchall()
    
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['comment_id', 'post_id', 'user_id', 'content', 'parent_comment_id', 'timestamp', 'likes', 'dislikes', 'flagged'])
        writer.writerows(comments)
    
    return filename

def get_content_details(target_type, target_id):
    """Get details about reported content"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        
        if target_type == 'comment':
            cursor.execute(
                "SELECT comment_id, post_id, content, timestamp FROM comments WHERE comment_id = ?",
                (target_id,)
            )
        elif target_type == 'post':
            cursor.execute(
                "SELECT post_id, content, category, timestamp FROM posts WHERE post_id = ?",
                (target_id,)
            )
        else:
            return None
            
        return cursor.fetchone()

async def notify_admins_about_reports(context, target_type, target_id, report_count):
    """Notify admins when content reaches report threshold"""
    if report_count < 5:
        return False
    
    # Get content details
    content_details = get_content_details(target_type, target_id)
    if not content_details:
        return False
    
    from utils import escape_markdown_text, truncate_text
    
    if target_type == 'comment':
        comment_id, post_id, content, timestamp = content_details
        preview = truncate_text(content, 200)
        admin_text = f"""
🚨 *URGENT: Comment Reported {report_count} Times*

*Comment ID:* #{comment_id}
*Post ID:* #{post_id}
*Timestamp:* {escape_markdown_text(timestamp[:16])}
*Reports:* {report_count}

*Content:*
{escape_markdown_text(preview)}

⚠️ This content has reached the report threshold and needs immediate review\\.

Use `/reports` to view all reports or take action via database\\.
"""
    else:  # post
        post_id, content, category, timestamp = content_details
        preview = truncate_text(content, 200)
        admin_text = f"""
🚨 *URGENT: Post Reported {report_count} Times*

*Post ID:* #{post_id}
*Category:* {escape_markdown_text(category)}
*Timestamp:* {escape_markdown_text(timestamp[:16])}
*Reports:* {report_count}

*Content:*
{escape_markdown_text(preview)}

⚠️ This content has reached the report threshold and needs immediate review\\.

Use `/reports` to view all reports or take action\\.
"""
    
    # Send to all admins
    success_count = 0
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=admin_text,
                parse_mode="MarkdownV2"
            )
            success_count += 1
        except Exception as e:
            print(f"Failed to send report notification to admin {admin_id}: {e}")
    
    return success_count > 0

def export_users_csv():
    """Export all users to CSV"""
    filename = f"users_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users")
        users = cursor.fetchall()
    
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['user_id', 'username', 'first_name', 'last_name', 'join_date', 'questions_asked', 'comments_posted', 'blocked'])
        writer.writerows(users)
    
    return filename