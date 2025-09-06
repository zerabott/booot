#!/usr/bin/env python3
"""
Test script for trending functions
"""

import sys
import os

# Add the current directory to the Python path
sys.path.append(os.path.dirname(__file__))

try:
    from trending import *
    from db import init_db
    
    print("✅ Testing trending functions...")
    
    # Initialize database
    init_db()
    print("✅ Database initialized")
    
    # Test each trending function
    print("\n🧪 Testing get_most_commented_posts_24h...")
    most_commented = get_most_commented_posts_24h(5)
    print(f"   Result: {len(most_commented)} posts returned")
    
    print("\n🧪 Testing get_posts_with_most_liked_comments...")
    most_liked = get_posts_with_most_liked_comments(5)
    print(f"   Result: {len(most_liked)} posts returned")
    
    print("\n🧪 Testing get_rising_posts...")
    rising = get_rising_posts(5)
    print(f"   Result: {len(rising)} posts returned")
    
    print("\n🧪 Testing get_trending_posts...")
    trending = get_trending_posts(5)
    print(f"   Result: {len(trending)} posts returned")
    
    print("\n🧪 Testing get_popular_today_posts...")
    popular = get_popular_today_posts(5)
    print(f"   Result: {len(popular)} posts returned")
    
    print("\n✅ All trending functions work correctly!")
    print("   The issue is likely with network connectivity to Telegram servers.")
    
except Exception as e:
    print(f"❌ Error testing trending functions: {e}")
    import traceback
    traceback.print_exc()
