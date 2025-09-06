#!/usr/bin/env python3
"""
Bot Instance Manager
Prevents multiple bot instances from running simultaneously
"""

import os
import sys
import signal
import atexit
import logging
from pathlib import Path
from typing import Optional

# Only import fcntl on Unix-like systems
if not sys.platform.startswith('win'):
    import fcntl

logger = logging.getLogger(__name__)

class BotInstanceManager:
    """Manages bot instance lifecycle and prevents multiple instances"""
    
    def __init__(self, lock_file: str = "bot.lock"):
        self.lock_file = Path(lock_file)
        self.lock_fd: Optional[int] = None
        self.is_locked = False
    
    def acquire_lock(self) -> bool:
        """Acquire exclusive lock to prevent multiple instances"""
        try:
            # Create lock file if it doesn't exist
            if not self.lock_file.exists():
                self.lock_file.touch()
            
            # Open lock file
            self.lock_fd = os.open(self.lock_file, os.O_WRONLY | os.O_CREAT)
            
            # Try to acquire exclusive lock (non-blocking)
            fcntl.flock(self.lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            
            # Write current PID to lock file
            os.write(self.lock_fd, str(os.getpid()).encode())
            os.fsync(self.lock_fd)
            
            self.is_locked = True
            logger.info(f"✅ Bot instance lock acquired (PID: {os.getpid()})")
            
            # Register cleanup handlers
            atexit.register(self.release_lock)
            signal.signal(signal.SIGTERM, self._signal_handler)
            signal.signal(signal.SIGINT, self._signal_handler)
            
            return True
            
        except (OSError, IOError) as e:
            if e.errno in (11, 35):  # EAGAIN or EWOULDBLOCK
                # Another instance is running
                logger.error("❌ Another bot instance is already running!")
                self._show_running_instance()
                return False
            else:
                logger.error(f"❌ Failed to acquire lock: {e}")
                return False
    
    def _show_running_instance(self):
        """Show information about the running instance"""
        try:
            if self.lock_file.exists():
                with open(self.lock_file, 'r') as f:
                    pid = f.read().strip()
                    if pid.isdigit():
                        logger.error(f"Running instance PID: {pid}")
                        
                        # Check if process is actually running
                        try:
                            os.kill(int(pid), 0)  # Signal 0 just checks if process exists
                            logger.error("The process is still active.")
                        except ProcessLookupError:
                            logger.warning("The process appears to be dead. You may need to remove the lock file manually.")
                            logger.warning(f"Lock file location: {self.lock_file.absolute()}")
        except Exception as e:
            logger.error(f"Could not read lock file: {e}")
    
    def release_lock(self):
        """Release the instance lock"""
        if self.is_locked and self.lock_fd is not None:
            try:
                fcntl.flock(self.lock_fd, fcntl.LOCK_UN)
                os.close(self.lock_fd)
                
                # Remove lock file
                if self.lock_file.exists():
                    self.lock_file.unlink()
                
                self.is_locked = False
                self.lock_fd = None
                logger.info("🔓 Bot instance lock released")
                
            except Exception as e:
                logger.error(f"Error releasing lock: {e}")
    
    def _signal_handler(self, signum, frame):
        """Handle termination signals"""
        logger.info(f"Received signal {signum}, shutting down...")
        self.release_lock()
        sys.exit(0)
    
    def force_remove_lock(self):
        """Force remove lock file (use with caution)"""
        if self.lock_file.exists():
            self.lock_file.unlink()
            logger.warning("🗑️ Lock file forcibly removed")
    
    def check_if_running(self) -> bool:
        """Check if another instance is running without acquiring lock"""
        if not self.lock_file.exists():
            return False
        
        try:
            # Try to open and lock briefly
            test_fd = os.open(self.lock_file, os.O_WRONLY)
            fcntl.flock(test_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            
            # If we get here, no other instance is running
            fcntl.flock(test_fd, fcntl.LOCK_UN)
            os.close(test_fd)
            return False
            
        except (OSError, IOError):
            # Another instance is running
            return True


# Alternative Windows-compatible implementation
class WindowsBotInstanceManager:
    """Windows-compatible bot instance manager using file-based locking"""
    
    def __init__(self, lock_file: str = "bot.lock"):
        self.lock_file = Path(lock_file)
        self.is_locked = False
    
    def acquire_lock(self) -> bool:
        """Acquire exclusive lock for Windows"""
        try:
            if self.lock_file.exists():
                # Check if the PID in the file is still running
                with open(self.lock_file, 'r') as f:
                    old_pid = f.read().strip()
                    
                if old_pid.isdigit() and self._is_process_running(int(old_pid)):
                    logger.error(f"❌ Another bot instance is already running! (PID: {old_pid})")
                    return False
                else:
                    # Old process is dead, remove stale lock
                    self.lock_file.unlink()
            
            # Create new lock file with current PID
            with open(self.lock_file, 'w') as f:
                f.write(str(os.getpid()))
            
            self.is_locked = True
            logger.info(f"✅ Bot instance lock acquired (PID: {os.getpid()})")
            
            # Register cleanup
            atexit.register(self.release_lock)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to acquire lock: {e}")
            return False
    
    def _is_process_running(self, pid: int) -> bool:
        """Check if a process with given PID is running (Windows)"""
        try:
            import psutil
            return psutil.pid_exists(pid)
        except ImportError:
            # Fallback method
            try:
                os.kill(pid, 0)
                return True
            except OSError:
                return False
    
    def release_lock(self):
        """Release the instance lock"""
        if self.is_locked and self.lock_file.exists():
            try:
                self.lock_file.unlink()
                self.is_locked = False
                logger.info("🔓 Bot instance lock released")
            except Exception as e:
                logger.error(f"Error releasing lock: {e}")
    
    def force_remove_lock(self):
        """Force remove lock file"""
        if self.lock_file.exists():
            self.lock_file.unlink()
            logger.warning("🗑️ Lock file forcibly removed")


def get_instance_manager() -> 'BotInstanceManager':
    """Get appropriate instance manager for the platform"""
    if sys.platform.startswith('win'):
        return WindowsBotInstanceManager()
    else:
        return BotInstanceManager()


# Convenience functions
def ensure_single_instance() -> bool:
    """Ensure only one bot instance is running"""
    manager = get_instance_manager()
    return manager.acquire_lock()


def force_remove_lock():
    """Force remove any existing lock files"""
    manager = get_instance_manager()
    manager.force_remove_lock()


if __name__ == "__main__":
    """Command line interface for managing bot instances"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Bot Instance Manager")
    parser.add_argument("--check", action="store_true", help="Check if bot is running")
    parser.add_argument("--force-unlock", action="store_true", help="Force remove lock file")
    
    args = parser.parse_args()
    
    manager = get_instance_manager()
    
    if args.check:
        if hasattr(manager, 'check_if_running'):
            running = manager.check_if_running()
        else:
            # Windows fallback
            running = manager.lock_file.exists()
        
        if running:
            print("🟢 Bot instance is currently running")
            manager._show_running_instance() if hasattr(manager, '_show_running_instance') else None
            sys.exit(1)
        else:
            print("🔴 No bot instance is currently running")
            sys.exit(0)
    
    elif args.force_unlock:
        manager.force_remove_lock()
        print("🔓 Lock file removed")
        sys.exit(0)
    
    else:
        parser.print_help()
