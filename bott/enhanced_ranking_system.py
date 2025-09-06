#!/usr/bin/env python3
"""
Enhanced Ranking System with Improved Point Balance and New Achievements
"""

import sqlite3
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass

DB_PATH = 'confessions.db'

@dataclass
class UserRank:
    """User ranking information"""
    rank_name: str
    rank_emoji: str
    total_points: int
    points_to_next: int
    next_rank_points: int
    is_special_rank: bool = False
    special_perks: Optional[Dict[str, Any]] = None
    rank_level: int = 0
    streak_days: int = 0

@dataclass
class EnhancedAchievement:
    """Enhanced achievement with more details"""
    achievement_type: str
    achievement_name: str
    achievement_description: str
    points_awarded: int
    is_special: bool = False
    is_hidden: bool = False
    prerequisite: str = None
    category: str = "general"
    difficulty: str = "easy"  # easy, medium, hard, legendary

@dataclass
class UserRank:
    """User ranking information"""
    rank_name: str
    rank_emoji: str
    total_points: int
    points_to_next: int
    next_rank_points: int
    is_special_rank: bool = False
    special_perks: Optional[Dict[str, Any]] = None
    rank_level: int = 0
    streak_days: int = 0

class EnhancedPointSystem:
    """Improved point system with better balance and streak multipliers"""
    
    # Rebalanced point values for better progression
    POINT_VALUES = {
        # Confession activities (increased rewards for quality content)
        'confession_submitted': 15,  # +5 from original
        'confession_approved': 35,  # +10 from original
        'confession_featured': 75,  # +25 from original
        'confession_liked': 3,  # +1 from original
        'confession_100_likes': 150,  # +50 from original
        'confession_viral': 200,  # New: 200+ likes
        'confession_popular': 100,  # +25 from original
        'confession_trending': 125,  # New: appears in trending
        
        # Comment activities (better rewards for engagement)
        'comment_posted': 8,  # +3 from original
        'comment_liked': 2,  # +1 from original
        'comment_helpful': 25,  # +10 from original
        'comment_thread_starter': 15,  # +5 from original
        'quality_comment': 30,  # +10 from original
        'comment_viral': 50,  # New: 50+ likes on comment
        'comment_discussion_spark': 40,  # New: comment leads to 10+ replies
        
        # Daily activities with streak multipliers
        'daily_login': 5,  # +3 from original
        'consecutive_days_bonus': 10,  # +5 from original
        'week_streak': 50,  # +25 from original
        'month_streak': 200,  # +100 from original
        'quarter_streak': 500,  # New: 90 days
        'year_streak': 1000,  # New: 365 days
        
        # Social activities (encourage positive interaction)
        'reaction_given': 2,  # +1 from original
        'helping_others': 20,  # +10 from original
        'positive_interaction': 10,  # +5 from original
        'community_support': 25,  # New: helping new users
        'mentor_activity': 30,  # New: consistent helpful behavior
        
        # Special activities and milestones
        'first_confession': 75,  # +25 from original
        'first_comment': 30,  # +10 from original
        'milestone_reached': 150,  # +50 from original
        'community_contribution': 50,  # +20 from original
        'seasonal_participation': 75,  # New: participating in events
        'achievement_hunter': 25,  # New: earning achievements
        
        # Quality bonuses (new system)
        'high_quality_content': 40,  # Admin-marked quality content
        'educational_content': 35,  # Helpful/educational posts
        'creative_content': 30,  # Creative or artistic posts
        'discussion_catalyst': 45,  # Content that sparks good discussions
        
        # Penalty points (reduced penalties, focus on education)
        'content_rejected': -3,  # Reduced from -5
        'spam_detected': -10,  # Reduced from -15
        'inappropriate_content': -20,  # Reduced from -25
        'excessive_negativity': -15,  # New: consistently negative behavior
        
        # Bonus point events (new system)
        'weekend_bonus': 5,  # Extra points on weekends
        'holiday_bonus': 10,  # Special holidays
        'anniversary_bonus': 15,  # Bot anniversary
        'milestone_celebration': 20,  # Community milestones
        'feedback_participation': 25,  # Participating in surveys/feedback
    }
    
    @staticmethod
    def calculate_points(activity_type: str, **kwargs) -> int:
        """Enhanced point calculation with multipliers and context"""
        base_points = EnhancedPointSystem.POINT_VALUES.get(activity_type, 0)
        
        # Apply streak multipliers
        if activity_type == 'consecutive_days_bonus':
            consecutive_days = kwargs.get('consecutive_days', 0)
            if consecutive_days >= 365:  # Year streak
                return base_points * 5
            elif consecutive_days >= 90:  # Quarter streak
                return base_points * 3
            elif consecutive_days >= 30:  # Month streak
                return base_points * 2
            elif consecutive_days >= 7:  # Week streak
                return base_points * 1.5
        
        # Quality content multipliers
        elif activity_type in ['confession_approved', 'comment_posted']:
            content_length = kwargs.get('content_length', 0)
            quality_score = kwargs.get('quality_score', 0)  # Admin can set 1-5
            
            # Length bonus
            if content_length > 500:
                base_points += 15
            elif content_length > 200:
                base_points += 8
            
            # Quality multiplier (if admin rates content)
            if quality_score >= 4:
                base_points = int(base_points * 1.5)
            elif quality_score >= 3:
                base_points = int(base_points * 1.2)
        
        # Engagement multipliers
        elif activity_type in ['confession_liked', 'comment_liked']:
            like_count = kwargs.get('like_count', 0)
            if like_count >= 200:
                return base_points * 5
            elif like_count >= 100:
                return base_points * 4
            elif like_count >= 50:
                return base_points * 3
            elif like_count >= 20:
                return base_points * 2
        
        # Time-based bonuses
        current_hour = datetime.now().hour
        day_of_week = datetime.now().weekday()
        
        # Weekend bonus (Friday-Sunday)
        if day_of_week >= 4 and activity_type in ['confession_submitted', 'comment_posted']:
            base_points = int(base_points * 1.1)
        
        # Night owl bonus (10 PM - 6 AM)
        if (current_hour >= 22 or current_hour <= 6) and activity_type in ['confession_submitted']:
            base_points = int(base_points * 1.05)
        
        return max(0, int(base_points))
    
    @staticmethod
    def get_streak_multiplier(consecutive_days: int) -> float:
        """Calculate streak multiplier based on consecutive days"""
        if consecutive_days >= 365:
            return 3.0
        elif consecutive_days >= 90:
            return 2.5
        elif consecutive_days >= 30:
            return 2.0
        elif consecutive_days >= 14:
            return 1.5
        elif consecutive_days >= 7:
            return 1.2
        elif consecutive_days >= 3:
            return 1.1
        else:
            return 1.0

class EnhancedAchievementSystem:
    """Comprehensive achievement system with multiple categories"""
    
    def get_all_achievements(self) -> List[EnhancedAchievement]:
        """Get all available achievements"""
        return [
            # First Time Achievements
            EnhancedAchievement('first_confession', '🎯 First Steps', 'Posted your first confession', 75, category="milestone"),
            EnhancedAchievement('first_comment', '💬 First Voice', 'Made your first comment', 30, category="milestone"),
            EnhancedAchievement('first_like', '👍 First Appreciation', 'Received your first like', 15, category="milestone"),
            EnhancedAchievement('first_week', '📅 Week Warrior', 'Active for 7 consecutive days', 50, category="streak"),
            
            # Content Creation Achievements
            EnhancedAchievement('confession_milestone_10', '📝 Storyteller', 'Posted 10 confessions', 100, category="content"),
            EnhancedAchievement('confession_milestone_25', '📚 Author', 'Posted 25 confessions', 200, category="content"),
            EnhancedAchievement('confession_milestone_50', '✍️ Prolific Writer', 'Posted 50 confessions', 350, category="content"),
            EnhancedAchievement('confession_milestone_100', '🖋️ Master Writer', 'Posted 100 confessions', 500, True, category="content", difficulty="hard"),
            EnhancedAchievement('confession_milestone_250', '📖 Literary Legend', 'Posted 250 confessions', 1000, True, category="content", difficulty="legendary"),
            
            # Engagement Achievements
            EnhancedAchievement('comment_milestone_25', '💬 Conversationalist', 'Made 25 comments', 75, category="engagement"),
            EnhancedAchievement('comment_milestone_100', '🗣️ Community Voice', 'Made 100 comments', 200, category="engagement"),
            EnhancedAchievement('comment_milestone_250', '🎙️ Discussion Leader', 'Made 250 comments', 400, category="engagement"),
            EnhancedAchievement('comment_milestone_500', '📢 Community Ambassador', 'Made 500 comments', 750, True, category="engagement", difficulty="hard"),
            
            # Popularity Achievements
            EnhancedAchievement('viral_confession', '🔥 Viral Sensation', 'Got 100+ likes on a confession', 250, True, category="popularity"),
            EnhancedAchievement('super_viral', '🌟 Internet Famous', 'Got 250+ likes on a confession', 500, True, category="popularity", difficulty="hard"),
            EnhancedAchievement('trending_master', '📈 Trending King/Queen', 'Had 5 posts in trending', 400, True, category="popularity", difficulty="medium"),
            EnhancedAchievement('comment_celebrity', '💎 Comment Star', 'Got 50+ likes on a single comment', 200, True, category="popularity"),
            
            # Streak Achievements
            EnhancedAchievement('week_streak', '🔥 Week Warrior', '7 consecutive days active', 100, category="streak"),
            EnhancedAchievement('month_streak', '💪 Monthly Master', '30 consecutive days active', 300, True, category="streak"),
            EnhancedAchievement('quarter_streak', '🏆 Quarter Champion', '90 consecutive days active', 750, True, category="streak", difficulty="hard"),
            EnhancedAchievement('half_year_streak', '👑 Dedication King/Queen', '180 consecutive days active', 1200, True, category="streak", difficulty="legendary"),
            EnhancedAchievement('year_streak', '🌟 Ultimate Devotee', '365 consecutive days active', 2500, True, category="streak", difficulty="legendary"),
            
            # Special Time-based Achievements
            EnhancedAchievement('early_bird', '🌅 Early Bird', 'Posted 10 confessions before 8 AM', 100, category="time"),
            EnhancedAchievement('night_owl', '🦉 Night Owl', 'Posted 15 confessions after 10 PM', 100, category="time"),
            EnhancedAchievement('weekend_warrior', '🎉 Weekend Warrior', 'Posted 20 confessions on weekends', 125, category="time"),
            EnhancedAchievement('midnight_poster', '🌙 Midnight Confessor', 'Posted at exactly midnight 5 times', 150, True, is_hidden=True, category="time"),
            
            # Quality and Community Achievements
            EnhancedAchievement('quality_contributor', '💎 Quality Contributor', '10 high-quality posts (admin rated)', 300, True, category="quality"),
            EnhancedAchievement('helpful_commenter', '🤝 Community Helper', '25 helpful comments (admin marked)', 200, category="quality"),
            EnhancedAchievement('mentor', '🎓 Community Mentor', 'Helped 10 new users', 250, True, category="community"),
            EnhancedAchievement('peacemaker', '☮️ Peacemaker', 'Resolved 5 conflicts positively', 200, True, category="community"),
            
            # Hidden/Secret Achievements
            EnhancedAchievement('easter_egg', '🥚 Easter Egg Hunter', 'Found a hidden feature', 100, True, True, category="secret"),
            EnhancedAchievement('palindrome', '🔄 Palindrome Master', 'Posted confession #101, #111, #121, etc.', 150, True, True, category="secret"),
            EnhancedAchievement('lucky_777', '🍀 Lucky 777', 'Reached exactly 777 points', 77, True, True, category="secret"),
            EnhancedAchievement('speed_demon', '⚡ Speed Demon', 'Posted 5 confessions in 1 hour', 100, True, True, category="secret"),
            
            # Seasonal/Event Achievements
            EnhancedAchievement('holiday_spirit', '🎄 Holiday Spirit', 'Active during holiday season', 150, category="seasonal"),
            EnhancedAchievement('new_year_resolution', '🎊 New Year, New Me', 'Posted confession on New Year', 200, True, category="seasonal"),
            EnhancedAchievement('valentine_confessor', '💕 Love Confessor', 'Posted love-themed confession on Valentine\'s', 175, True, category="seasonal"),
            EnhancedAchievement('anniversary_celebrant', '🎂 Anniversary Celebrant', 'Active during bot anniversary', 300, True, category="seasonal"),
            
            # Milestone Achievements
            EnhancedAchievement('point_milestone_1000', '🎯 Thousand Club', 'Reached 1,000 points', 150, category="points"),
            EnhancedAchievement('point_milestone_5000', '🏆 Five Thousand Elite', 'Reached 5,000 points', 500, True, category="points"),
            EnhancedAchievement('point_milestone_10000', '👑 Ten Thousand Legend', 'Reached 10,000 points', 1000, True, category="points", difficulty="legendary"),
            
            # Meta Achievements
            EnhancedAchievement('achievement_hunter', '🏅 Achievement Hunter', 'Unlocked 10 achievements', 200, category="meta"),
            EnhancedAchievement('completionist', '💯 Completionist', 'Unlocked 25 achievements', 500, True, category="meta", difficulty="hard"),
            EnhancedAchievement('legend', '🌟 Living Legend', 'Unlocked 40 achievements', 1000, True, category="meta", difficulty="legendary"),
        ]
    
    def check_achievement_qualification(self, user_id: int, achievement: EnhancedAchievement) -> bool:
        """Enhanced achievement qualification checking"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        try:
            # Check if user already has this achievement
            cursor.execute("""
                SELECT COUNT(*) FROM user_achievements 
                WHERE user_id = ? AND achievement_type = ?
            """, (user_id, achievement.achievement_type))
            
            if cursor.fetchone()[0] > 0:
                return False
            
            # Check prerequisites if any
            if achievement.prerequisite:
                cursor.execute("""
                    SELECT COUNT(*) FROM user_achievements 
                    WHERE user_id = ? AND achievement_type = ?
                """, (user_id, achievement.prerequisite))
                
                if cursor.fetchone()[0] == 0:
                    return False
            
            # Specific achievement checks
            if achievement.achievement_type.startswith('confession_milestone_'):
                target = int(achievement.achievement_type.split('_')[-1])
                cursor.execute('SELECT COUNT(*) FROM posts WHERE user_id = ? AND approved = 1', (user_id,))
                count = cursor.fetchone()[0]
                return count >= target
            
            elif achievement.achievement_type.startswith('comment_milestone_'):
                target = int(achievement.achievement_type.split('_')[-1])
                cursor.execute('SELECT COUNT(*) FROM comments WHERE user_id = ?', (user_id,))
                count = cursor.fetchone()[0]
                return count >= target
            
            elif achievement.achievement_type.startswith('point_milestone_'):
                target = int(achievement.achievement_type.split('_')[-1])
                cursor.execute('SELECT total_points FROM user_rankings WHERE user_id = ?', (user_id,))
                result = cursor.fetchone()
                if result:
                    return result[0] >= target
            
            elif achievement.achievement_type == 'achievement_hunter':
                cursor.execute('SELECT total_achievements FROM user_rankings WHERE user_id = ?', (user_id,))
                result = cursor.fetchone()
                return result and result[0] >= 10
            
            elif achievement.achievement_type == 'completionist':
                cursor.execute('SELECT total_achievements FROM user_rankings WHERE user_id = ?', (user_id,))
                result = cursor.fetchone()
                return result and result[0] >= 25
            
            # Add more specific checks as needed...
            
            return False
            
        except Exception as e:
            print(f"Error checking achievement {achievement.achievement_type}: {e}")
            return False
        finally:
            conn.close()

def install_enhanced_achievements():
    """Install all enhanced achievements into the database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    achievement_system = EnhancedAchievementSystem()
    all_achievements = achievement_system.get_all_achievements()
    
    print("=== INSTALLING ENHANCED ACHIEVEMENTS ===")
    
    # Create achievements definition table if it doesn't exist
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS achievement_definitions (
            achievement_type TEXT PRIMARY KEY,
            achievement_name TEXT NOT NULL,
            achievement_description TEXT NOT NULL,
            points_awarded INTEGER NOT NULL,
            is_special INTEGER DEFAULT 0,
            is_hidden INTEGER DEFAULT 0,
            prerequisite TEXT,
            category TEXT DEFAULT 'general',
            difficulty TEXT DEFAULT 'easy',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    installed_count = 0
    updated_count = 0
    
    for achievement in all_achievements:
        # Check if achievement already exists
        cursor.execute("""
            SELECT COUNT(*) FROM achievement_definitions WHERE achievement_type = ?
        """, (achievement.achievement_type,))
        
        exists = cursor.fetchone()[0] > 0
        
        if exists:
            # Update existing achievement
            cursor.execute("""
                UPDATE achievement_definitions 
                SET achievement_name = ?, achievement_description = ?, points_awarded = ?,
                    is_special = ?, is_hidden = ?, prerequisite = ?, category = ?, difficulty = ?
                WHERE achievement_type = ?
            """, (
                achievement.achievement_name, achievement.achievement_description, 
                achievement.points_awarded, int(achievement.is_special), int(achievement.is_hidden),
                achievement.prerequisite, achievement.category, achievement.difficulty,
                achievement.achievement_type
            ))
            updated_count += 1
        else:
            # Insert new achievement
            cursor.execute("""
                INSERT INTO achievement_definitions 
                (achievement_type, achievement_name, achievement_description, points_awarded,
                 is_special, is_hidden, prerequisite, category, difficulty)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                achievement.achievement_type, achievement.achievement_name, 
                achievement.achievement_description, achievement.points_awarded,
                int(achievement.is_special), int(achievement.is_hidden),
                achievement.prerequisite, achievement.category, achievement.difficulty
            ))
            installed_count += 1
    
    conn.commit()
    conn.close()
    
    print(f"✅ Installed {installed_count} new achievements")
    print(f"🔄 Updated {updated_count} existing achievements")
    print(f"🎯 Total achievements available: {len(all_achievements)}")
    
    # Show achievement categories
    categories = {}
    for achievement in all_achievements:
        if achievement.category not in categories:
            categories[achievement.category] = []
        categories[achievement.category].append(achievement)
    
    print(f"\n📊 Achievement Categories:")
    for category, achievements in categories.items():
        special_count = sum(1 for a in achievements if a.is_special)
        hidden_count = sum(1 for a in achievements if a.is_hidden)
        print(f"  {category.title()}: {len(achievements)} achievements ({special_count} special, {hidden_count} hidden)")

def test_enhanced_point_system():
    """Test the enhanced point system with various scenarios"""
    print("\n=== TESTING ENHANCED POINT SYSTEM ===")
    
    test_cases = [
        # (activity_type, kwargs, expected_description)
        ('confession_submitted', {'content_length': 100}, 'Short confession'),
        ('confession_submitted', {'content_length': 300}, 'Medium confession'),
        ('confession_submitted', {'content_length': 600, 'quality_score': 4}, 'High-quality long confession'),
        ('confession_liked', {'like_count': 5}, 'Few likes'),
        ('confession_liked', {'like_count': 50}, 'Popular post'),
        ('confession_liked', {'like_count': 150}, 'Viral post'),
        ('consecutive_days_bonus', {'consecutive_days': 5}, 'Short streak'),
        ('consecutive_days_bonus', {'consecutive_days': 30}, 'Month streak'),
        ('consecutive_days_bonus', {'consecutive_days': 100}, 'Quarter streak'),
        ('consecutive_days_bonus', {'consecutive_days': 400}, 'Year streak'),
    ]
    
    for activity_type, kwargs, description in test_cases:
        points = EnhancedPointSystem.calculate_points(activity_type, **kwargs)
        print(f"  {description}: {points} points ({activity_type})")

if __name__ == '__main__':
    install_enhanced_achievements()
    test_enhanced_point_system()
    print("\n🎉 Enhanced ranking system is ready!")
