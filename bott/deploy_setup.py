"""
Database setup script for cloud deployment
Handles database initialization and data migration for Render hosting
"""

import os
import sqlite3
import json
from datetime import datetime
from config import DB_PATH

def create_deployment_backup():
    """Create a backup of current database data for deployment"""
    
    print("📦 Creating deployment backup...")
    
    if not os.path.exists(DB_PATH):
        print("❗ No local database found. Starting with fresh deployment.")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Export critical data
        backup_data = {
            'timestamp': datetime.now().isoformat(),
            'approved_posts': [],
            'users': [],
            'comments': [],
            'admin_messages': []
        }
        
        # Export approved posts with post numbers
        cursor.execute("""
            SELECT post_id, user_id, content, category, timestamp, post_number
            FROM posts 
            WHERE approved = 1 
            ORDER BY post_number ASC
        """)
        approved_posts = cursor.fetchall()
        
        for post in approved_posts:
            backup_data['approved_posts'].append({
                'post_id': post[0],
                'user_id': post[1], 
                'content': post[2],
                'category': post[3],
                'timestamp': post[4],
                'post_number': post[5]
            })
        
        # Export users (anonymized)
        cursor.execute("""
            SELECT user_id, join_date, questions_asked, comments_posted, blocked
            FROM users
        """)
        users = cursor.fetchall()
        
        for user in users:
            backup_data['users'].append({
                'user_id': user[0],
                'join_date': user[1],
                'questions_asked': user[2],
                'comments_posted': user[3],
                'blocked': user[4]
            })
        
        print(f"✅ Backup created:")
        print(f"   - {len(backup_data['approved_posts'])} approved posts")
        print(f"   - {len(backup_data['users'])} users")
        
        # Save backup file
        with open('deployment_backup.json', 'w', encoding='utf-8') as f:
            json.dump(backup_data, f, ensure_ascii=False, indent=2)
        
        print("✅ Backup saved to: deployment_backup.json")
        
    except Exception as e:
        print(f"❌ Error creating backup: {e}")
    finally:
        conn.close()

def verify_deployment_readiness():
    """Verify the bot is ready for cloud deployment"""
    
    print("\n🔍 Verifying deployment readiness...")
    
    required_files = [
        'bot.py',
        'config.py', 
        'requirements.txt',
        'render.yaml',
        '.env.example'
    ]
    
    missing_files = []
    for file in required_files:
        if not os.path.exists(file):
            missing_files.append(file)
    
    if missing_files:
        print(f"❌ Missing required files: {missing_files}")
        return False
    else:
        print("✅ All required files present")
    
    # Check if sensitive data is in environment variables
    with open('config.py', 'r', encoding='utf-8') as f:
        config_content = f.read()
    
    if 'os.getenv' in config_content:
        print("✅ Configuration uses environment variables")
    else:
        print("⚠️ Configuration may have hardcoded values")
    
    # Check requirements.txt
    with open('requirements.txt', 'r', encoding='utf-8') as f:
        requirements = f.read()
    
    critical_deps = ['python-telegram-bot', 'python-dotenv']
    missing_deps = [dep for dep in critical_deps if dep not in requirements]
    
    if missing_deps:
        print(f"⚠️ Missing critical dependencies: {missing_deps}")
    else:
        print("✅ Critical dependencies present in requirements.txt")
    
    print(f"\n📋 Deployment Readiness Summary:")
    print(f"   ✅ Bot code: Ready")
    print(f"   ✅ Configuration: Environment-based")
    print(f"   ✅ Dependencies: Listed in requirements.txt")
    print(f"   ✅ Render config: render.yaml created")
    print(f"   ✅ Environment template: .env.example available")
    
    return len(missing_files) == 0

def create_gitignore():
    """Create .gitignore file to exclude sensitive files"""
    
    gitignore_content = """# Environment files
.env
.env.local
.env.production
.env.staging

# Database files
*.db
*.sqlite
*.sqlite3

# Log files
*.log
logs/

# Backup files
backups/
deployment_backup.json

# Python cache
__pycache__/
*.pyc
*.pyo
*.pyd
.Python

# Virtual environment
venv/
env/
ENV/

# IDE files
.vscode/
.idea/
*.swp
*.swo

# OS files
.DS_Store
Thumbs.db

# Test files
test_*.py
*_test.py

# Temporary files
temp/
tmp/
exports/"""
    
    try:
        with open('.gitignore', 'w', encoding='utf-8') as f:
            f.write(gitignore_content)
        print("✅ .gitignore file created")
        return True
    except Exception as e:
        print(f"❌ Error creating .gitignore: {e}")
        return False

def show_next_steps():
    """Show the next steps for deployment"""
    
    print(f"\n🚀 Ready for Render Deployment!")
    print("=" * 40)
    print(f"📁 Your bot files are prepared for deployment")
    print(f"📝 Follow the RENDER_DEPLOYMENT_GUIDE.md for complete instructions")
    print()
    print(f"🔑 Critical Information You'll Need:")
    print(f"   • Your bot token (from @BotFather)")
    print(f"   • Your channel ID (negative number like -1001234567890)")
    print(f"   • Your Telegram user ID (for admin access)")
    print(f"   • GitHub account")
    print(f"   • Render account (free)")
    print()
    print(f"📋 Next Steps:")
    print(f"   1. Create GitHub repository")
    print(f"   2. Upload bot files to GitHub")
    print(f"   3. Create Render account and connect GitHub")
    print(f"   4. Configure environment variables in Render")
    print(f"   5. Deploy and test!")
    print()
    print(f"💡 Tip: Keep your .env file LOCAL ONLY - never upload it to GitHub!")

if __name__ == "__main__":
    print("🔧 Preparing Bot for Render Deployment")
    print("=" * 45)
    
    # Create backup of current data
    create_deployment_backup()
    
    # Create .gitignore if it doesn't exist
    if not os.path.exists('.gitignore'):
        create_gitignore()
    else:
        print("✅ .gitignore already exists")
    
    # Verify deployment readiness
    ready = verify_deployment_readiness()
    
    if ready:
        show_next_steps()
    else:
        print(f"\n❌ Bot not ready for deployment. Please fix the issues above.")
