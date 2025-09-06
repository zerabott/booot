#!/usr/bin/env python3
"""
Bot Instance Manager
Helps prevent multiple bot instances from running simultaneously
"""

import os
import sys
import time
import psutil
import signal
from pathlib import Path

def find_bot_processes():
    """Find running bot processes"""
    bot_processes = []
    current_pid = os.getpid()
    
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if proc.info['name'] == 'python.exe' or proc.info['name'] == 'python':
                cmdline = ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else ''
                if ('bot.py' in cmdline or 'start_bot.py' in cmdline) and proc.info['pid'] != current_pid:
                    bot_processes.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    
    return bot_processes

def stop_bot_instances():
    """Stop all running bot instances"""
    processes = find_bot_processes()
    
    if not processes:
        print("✅ No running bot instances found.")
        return True
    
    print(f"🔍 Found {len(processes)} bot instance(s) running.")
    
    for proc in processes:
        try:
            print(f"🛑 Stopping bot process {proc.pid}...")
            proc.terminate()
            
            # Wait for graceful shutdown
            try:
                proc.wait(timeout=5)
                print(f"✅ Process {proc.pid} stopped gracefully.")
            except psutil.TimeoutExpired:
                print(f"⚠️  Process {proc.pid} didn't stop gracefully, forcing...")
                proc.kill()
                proc.wait()
                print(f"✅ Process {proc.pid} force-stopped.")
                
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            print(f"⚠️  Could not stop process {proc.pid}: {e}")
    
    # Final check
    time.sleep(1)
    remaining = find_bot_processes()
    if remaining:
        print(f"⚠️  {len(remaining)} process(es) still running.")
        return False
    
    print("✅ All bot instances stopped successfully.")
    return True

def start_bot():
    """Start the bot after ensuring no other instances are running"""
    print("🤖 Starting University Confession Bot...")
    
    # Stop any existing instances
    if not stop_bot_instances():
        print("❌ Failed to stop all existing instances. Please check manually.")
        return False
    
    # Wait a moment
    print("⏳ Waiting 2 seconds...")
    time.sleep(2)
    
    # Start the bot
    try:
        print("🚀 Launching bot...")
        os.system("python start_bot.py")
        return True
    except Exception as e:
        print(f"❌ Failed to start bot: {e}")
        return False

def check_status():
    """Check if bot is running"""
    processes = find_bot_processes()
    
    if not processes:
        print("❌ Bot is not running.")
        return False
    
    print(f"✅ Bot is running ({len(processes)} instance(s)):")
    for proc in processes:
        try:
            print(f"   📍 PID: {proc.pid} | Command: {' '.join(proc.cmdline())}")
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            print(f"   📍 PID: {proc.pid} | Command: <access denied>")
    
    return True

def main():
    """Main function"""
    if len(sys.argv) < 2:
        print("🤖 Bot Instance Manager")
        print("=" * 30)
        print("Usage:")
        print("  python bot_manager.py start   - Start the bot (stops existing instances first)")
        print("  python bot_manager.py stop    - Stop all bot instances")
        print("  python bot_manager.py status  - Check bot status")
        print("  python bot_manager.py restart - Restart the bot")
        return
    
    command = sys.argv[1].lower()
    
    if command == "start":
        start_bot()
    elif command == "stop":
        stop_bot_instances()
    elif command == "status":
        check_status()
    elif command == "restart":
        print("🔄 Restarting bot...")
        stop_bot_instances()
        time.sleep(2)
        start_bot()
    else:
        print(f"❌ Unknown command: {command}")

if __name__ == "__main__":
    main()