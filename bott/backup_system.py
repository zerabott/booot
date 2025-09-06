"""
Automated backup system for the confession bot
"""

import os
import shutil
import sqlite3
import hashlib
import gzip
from datetime import datetime, timedelta
from typing import List, Tuple, Optional
import schedule
import threading
import time

from config import DB_PATH, BACKUPS_DIR, ENABLE_AUTO_BACKUP, BACKUP_INTERVAL_HOURS
from logger import get_logger

logger = get_logger('backup_system')


class BackupManager:
    """Manages database backups with automated scheduling"""
    
    def __init__(self, db_path: str = DB_PATH, backup_dir: str = BACKUPS_DIR):
        self.db_path = db_path
        self.backup_dir = backup_dir
        self.running = False
        self._ensure_backup_directory()
        
    def _ensure_backup_directory(self):
        """Create backup directory if it doesn't exist"""
        os.makedirs(self.backup_dir, exist_ok=True)
        logger.info(f"Backup directory: {self.backup_dir}")
    
    def calculate_file_checksum(self, file_path: str) -> str:
        """Calculate MD5 checksum of a file"""
        hash_md5 = hashlib.md5()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception as e:
            logger.error(f"Failed to calculate checksum for {file_path}: {e}")
            return ""
    
    def get_record_count(self, db_path: str) -> int:
        """Get total record count from database"""
        try:
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                
                # Count records from main tables
                tables = ['users', 'posts', 'comments', 'reactions', 'admin_messages']
                total_records = 0
                
                for table in tables:
                    try:
                        cursor.execute(f"SELECT COUNT(*) FROM {table}")
                        count = cursor.fetchone()[0]
                        total_records += count
                    except sqlite3.OperationalError:
                        # Table might not exist
                        pass
                
                return total_records
        except Exception as e:
            logger.error(f"Failed to count records: {e}")
            return 0
    
    def create_backup(self, backup_type: str = "manual") -> Tuple[bool, str]:
        """Create a database backup"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"confession_bot_backup_{timestamp}.db"
            backup_path = os.path.join(self.backup_dir, backup_filename)
            
            # Create backup by copying the database file
            logger.info(f"Creating backup: {backup_filename}")
            shutil.copy2(self.db_path, backup_path)
            
            # Verify backup integrity
            if not os.path.exists(backup_path):
                return False, "Backup file was not created"
            
            # Get file info
            file_size = os.path.getsize(backup_path)
            record_count = self.get_record_count(backup_path)
            checksum = self.calculate_file_checksum(backup_path)
            
            # Compress backup
            compressed_path = f"{backup_path}.gz"
            with open(backup_path, 'rb') as f_in:
                with gzip.open(compressed_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            
            # Remove uncompressed version
            os.remove(backup_path)
            
            # Log backup metadata
            self._log_backup_metadata(
                backup_filename + ".gz",
                os.path.getsize(compressed_path),
                record_count,
                backup_type,
                checksum
            )
            
            logger.info(f"Backup created successfully: {backup_filename}.gz ({file_size} bytes, {record_count} records)")
            return True, f"Backup created: {backup_filename}.gz"
            
        except Exception as e:
            logger.error(f"Failed to create backup: {e}")
            return False, f"Backup failed: {str(e)}"
    
    def _log_backup_metadata(self, filename: str, file_size: int, record_count: int, backup_type: str, checksum: str):
        """Log backup metadata to database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO backup_metadata (filename, file_size, record_count, backup_type, checksum)
                    VALUES (?, ?, ?, ?, ?)
                """, (filename, file_size, record_count, backup_type, checksum))
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to log backup metadata: {e}")
    
    def list_backups(self, limit: int = 10) -> List[dict]:
        """List available backups"""
        backups = []
        try:
            # Get backups from filesystem
            backup_files = []
            for filename in os.listdir(self.backup_dir):
                if filename.startswith("confession_bot_backup_") and filename.endswith(".gz"):
                    file_path = os.path.join(self.backup_dir, filename)
                    backup_files.append({
                        'filename': filename,
                        'path': file_path,
                        'size': os.path.getsize(file_path),
                        'created': datetime.fromtimestamp(os.path.getctime(file_path))
                    })
            
            # Sort by creation time (newest first)
            backup_files.sort(key=lambda x: x['created'], reverse=True)
            
            # Get metadata from database if available
            try:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT filename, file_size, record_count, backup_type, created_at, checksum
                        FROM backup_metadata
                        ORDER BY created_at DESC
                        LIMIT ?
                    """, (limit,))
                    
                    metadata_dict = {}
                    for row in cursor.fetchall():
                        metadata_dict[row[0]] = {
                            'file_size': row[1],
                            'record_count': row[2],
                            'backup_type': row[3],
                            'created_at': row[4],
                            'checksum': row[5]
                        }
                    
                    # Merge filesystem and database info
                    for backup_file in backup_files[:limit]:
                        filename = backup_file['filename']
                        backup_info = {
                            'filename': filename,
                            'path': backup_file['path'],
                            'size': backup_file['size'],
                            'created': backup_file['created']
                        }
                        
                        if filename in metadata_dict:
                            backup_info.update(metadata_dict[filename])
                        
                        backups.append(backup_info)
            
            except sqlite3.OperationalError:
                # backup_metadata table might not exist
                backups = backup_files[:limit]
            
        except Exception as e:
            logger.error(f"Failed to list backups: {e}")
        
        return backups
    
    def restore_backup(self, backup_filename: str) -> Tuple[bool, str]:
        """Restore database from backup"""
        try:
            backup_path = os.path.join(self.backup_dir, backup_filename)
            
            if not os.path.exists(backup_path):
                return False, f"Backup file not found: {backup_filename}"
            
            # Create a backup of current database
            current_backup = f"pre_restore_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
            current_backup_path = os.path.join(self.backup_dir, current_backup)
            shutil.copy2(self.db_path, current_backup_path)
            
            # Decompress backup if needed
            if backup_filename.endswith('.gz'):
                temp_db_path = backup_path[:-3]  # Remove .gz extension
                with gzip.open(backup_path, 'rb') as f_in:
                    with open(temp_db_path, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                source_path = temp_db_path
            else:
                source_path = backup_path
            
            # Verify backup integrity
            try:
                with sqlite3.connect(source_path) as test_conn:
                    test_conn.execute("SELECT COUNT(*) FROM sqlite_master")
            except sqlite3.Error as e:
                if backup_filename.endswith('.gz') and os.path.exists(temp_db_path):
                    os.remove(temp_db_path)
                return False, f"Backup file is corrupted: {e}"
            
            # Replace current database
            shutil.copy2(source_path, self.db_path)
            
            # Clean up temporary file
            if backup_filename.endswith('.gz') and os.path.exists(temp_db_path):
                os.remove(temp_db_path)
            
            logger.info(f"Database restored from backup: {backup_filename}")
            return True, f"Database restored from {backup_filename}"
            
        except Exception as e:
            logger.error(f"Failed to restore backup: {e}")
            return False, f"Restore failed: {str(e)}"
    
    def cleanup_old_backups(self, keep_days: int = 30, keep_count: int = 10):
        """Clean up old backup files"""
        try:
            cutoff_date = datetime.now() - timedelta(days=keep_days)
            backups = self.list_backups(limit=100)  # Get more backups for cleanup
            
            # Sort by creation date
            backups.sort(key=lambda x: x['created'], reverse=True)
            
            # Keep the most recent backups, delete the rest
            deleted_count = 0
            for i, backup in enumerate(backups):
                if i >= keep_count or backup['created'] < cutoff_date:
                    try:
                        os.remove(backup['path'])
                        deleted_count += 1
                        logger.info(f"Deleted old backup: {backup['filename']}")
                    except Exception as e:
                        logger.error(f"Failed to delete backup {backup['filename']}: {e}")
            
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} old backups")
            
        except Exception as e:
            logger.error(f"Failed to cleanup old backups: {e}")
    
    def get_backup_stats(self) -> dict:
        """Get backup statistics"""
        try:
            backups = self.list_backups(limit=100)
            
            if not backups:
                return {
                    'total_backups': 0,
                    'total_size': 0,
                    'latest_backup': None,
                    'oldest_backup': None
                }
            
            total_size = sum(backup['size'] for backup in backups)
            latest_backup = max(backups, key=lambda x: x['created'])
            oldest_backup = min(backups, key=lambda x: x['created'])
            
            return {
                'total_backups': len(backups),
                'total_size': total_size,
                'total_size_mb': round(total_size / 1024 / 1024, 2),
                'latest_backup': latest_backup['created'],
                'oldest_backup': oldest_backup['created'],
                'backup_directory': self.backup_dir
            }
            
        except Exception as e:
            logger.error(f"Failed to get backup stats: {e}")
            return {'error': str(e)}
    
    def start_auto_backup(self):
        """Start automated backup scheduling"""
        if not ENABLE_AUTO_BACKUP:
            logger.info("Auto backup is disabled in configuration")
            return
        
        if self.running:
            logger.info("Auto backup is already running")
            return
        
        def run_backup():
            logger.info("Running scheduled backup...")
            success, message = self.create_backup("auto")
            if success:
                logger.info(f"Scheduled backup completed: {message}")
                # Clean up old backups
                self.cleanup_old_backups()
            else:
                logger.error(f"Scheduled backup failed: {message}")
        
        # Schedule backups
        schedule.every(BACKUP_INTERVAL_HOURS).hours.do(run_backup)
        
        def scheduler_thread():
            while self.running:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
        
        self.running = True
        thread = threading.Thread(target=scheduler_thread, daemon=True)
        thread.start()
        
        logger.info(f"Auto backup started - running every {BACKUP_INTERVAL_HOURS} hours")
    
    def stop_auto_backup(self):
        """Stop automated backup scheduling"""
        self.running = False
        schedule.clear()
        logger.info("Auto backup stopped")


# Global backup manager
backup_manager = BackupManager()


def create_manual_backup() -> Tuple[bool, str]:
    """Create a manual backup"""
    return backup_manager.create_backup("manual")


def start_backup_system():
    """Initialize and start the backup system"""
    logger.info("Initializing backup system...")
    backup_manager.start_auto_backup()


def get_backup_status() -> dict:
    """Get current backup system status"""
    return {
        'auto_backup_enabled': ENABLE_AUTO_BACKUP,
        'backup_interval_hours': BACKUP_INTERVAL_HOURS,
        'backup_directory': BACKUPS_DIR,
        'is_running': backup_manager.running,
        **backup_manager.get_backup_stats()
    }
