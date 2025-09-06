#!/usr/bin/env python3
"""
Cleanup script to prepare the bot for Render deployment
Removes unnecessary files and optimizes the project structure
"""

import os
import shutil
import glob
from pathlib import Path

def cleanup_files():
    """Remove unnecessary files for deployment"""
    
    # Current directory
    project_dir = Path(__file__).parent
    
    print("🧹 Cleaning up project for deployment...")
    
    # Files to remove (exact matches)
    files_to_remove = [
        "confessions.db",
        "confessions.db.backup", 
        "confession_bot.db",
        "db.sqlite",
        "final_backup_20250901_044309.db",
        "your_database_file.db",
        "deployment_backup.json",
        "start_bot.bat"
    ]
    
    # Pattern-based files to remove
    patterns_to_remove = [
        "test_*.py",
        "*_test.py", 
        "*_migration.py",
        "setup_*.py",
        "fix_*.py",
        "check_*.py",
        "debug_*.py",
        "verify_*.py",
        "prepare_*.py",
        "reset_*.py",
        "add_post_number_migration.py"
    ]
    
    # Directories to remove
    dirs_to_remove = [
        "logs",
        "backups", 
        "__pycache__"
    ]
    
    removed_count = 0
    
    # Remove specific files
    for filename in files_to_remove:
        file_path = project_dir / filename
        if file_path.exists():
            try:
                file_path.unlink()
                print(f"  ❌ Removed: {filename}")
                removed_count += 1
            except Exception as e:
                print(f"  ⚠️  Could not remove {filename}: {e}")
    
    # Remove pattern-based files
    for pattern in patterns_to_remove:
        for file_path in project_dir.glob(pattern):
            if file_path.is_file():
                try:
                    file_path.unlink()
                    print(f"  ❌ Removed: {file_path.name}")
                    removed_count += 1
                except Exception as e:
                    print(f"  ⚠️  Could not remove {file_path.name}: {e}")
    
    # Remove directories
    for dirname in dirs_to_remove:
        dir_path = project_dir / dirname
        if dir_path.exists() and dir_path.is_dir():
            try:
                shutil.rmtree(dir_path)
                print(f"  📁❌ Removed directory: {dirname}")
                removed_count += 1
            except Exception as e:
                print(f"  ⚠️  Could not remove directory {dirname}: {e}")
    
    print(f"\n✅ Cleanup complete! Removed {removed_count} items.")
    print("\n📁 Remaining files optimized for Render deployment:")
    
    # Show remaining Python files
    python_files = list(project_dir.glob("*.py"))
    for py_file in sorted(python_files):
        if py_file.name != "cleanup_for_deploy.py":
            print(f"  📄 {py_file.name}")

def create_gitignore_deploy():
    """Create a deployment-optimized .gitignore"""
    project_dir = Path(__file__).parent
    gitignore_path = project_dir / ".gitignore"
    
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

# Development and test files
test_*.py
*_test.py
*_migration.py
setup_*.py
fix_*.py
check_*.py
debug_*.py
verify_*.py
prepare_*.py
reset_*.py
cleanup_for_deploy.py

# Documentation (keep only essential)
*.md
!README.md
!RENDER_DEPLOY_GUIDE.md

# Temporary files
temp/
tmp/
exports/
"""
    
    with open(gitignore_path, 'w') as f:
        f.write(gitignore_content)
    
    print("📝 Updated .gitignore for deployment")

if __name__ == "__main__":
    print("🚀 Preparing Telegram Bot for Render Deployment")
    print("=" * 50)
    
    cleanup_files()
    create_gitignore_deploy()
    
    print("\n" + "=" * 50)
    print("✅ Project is ready for Render deployment!")
    print("\n📋 Next steps:")
    print("1. Push code to GitHub repository")
    print("2. Create Render web service")
    print("3. Set environment variables")
    print("4. Deploy!")
    print("\n📖 See RENDER_DEPLOY_GUIDE.md for detailed instructions")
