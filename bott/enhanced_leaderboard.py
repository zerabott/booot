#!/usr/bin/env python3
"""
Enhanced Leaderboard System with Seasonal Competitions and Better Privacy
"""

import sqlite3
import json
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum

DB_PATH = 'confessions.db'

class LeaderboardType(Enum):
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"
    ALL_TIME = "all_time"
    SEASONAL = "seasonal"

class CompetitionStatus(Enum):
    UPCOMING = "upcoming"
    ACTIVE = "active"
    ENDED = "ended"

@dataclass
class Season:
    """Seasonal competition definition"""
    season_id: str
    name: str
    description: str
    start_date: datetime
    end_date: datetime
    theme: str
    special_rewards: Dict[str, Any]
    status: CompetitionStatus

@dataclass
class LeaderboardEntry:
    """Enhanced leaderboard entry with more details"""
    position: int
    anonymous_name: str
    points: int
    rank_emoji: str
    rank_name: str
    special_badges: List[str]
    streak_days: int
    achievements_count: int
    is_current_user: bool = False

class EnhancedAnonymousNames:
    """More sophisticated anonymous name generation"""
    
    ADJECTIVES = [
        # Personality traits
        'Mysterious', 'Silent', 'Thoughtful', 'Wise', 'Clever', 'Brave',
        'Gentle', 'Creative', 'Curious', 'Humble', 'Witty', 'Bold',
        'Peaceful', 'Bright', 'Swift', 'Noble', 'Kind', 'Cheerful',
        'Inspiring', 'Passionate', 'Determined', 'Resilient', 'Graceful',
        
        # Academic themed
        'Studious', 'Brilliant', 'Scholarly', 'Academic', 'Intellectual',
        'Analytical', 'Perceptive', 'Insightful', 'Eloquent', 'Articulate',
        
        # Colors with character
        'Golden', 'Silver', 'Crimson', 'Azure', 'Emerald', 'Violet',
        'Amber', 'Ruby', 'Sapphire', 'Pearl', 'Diamond', 'Crystal',
        
        # Nature inspired
        'Stellar', 'Cosmic', 'Lunar', 'Solar', 'Aurora', 'Storm',
        'Thunder', 'Lightning', 'Ocean', 'Mountain', 'Forest', 'Desert'
    ]
    
    NOUNS = [
        # Student roles
        'Student', 'Scholar', 'Learner', 'Researcher', 'Graduate', 'Academic',
        'Freshman', 'Sophomore', 'Junior', 'Senior', 'Alumnus', 'Pupil',
        
        # Personality archetypes
        'Confessor', 'Dreamer', 'Thinker', 'Writer', 'Observer', 'Listener',
        'Helper', 'Friend', 'Sage', 'Storyteller', 'Guardian', 'Seeker',
        'Wanderer', 'Explorer', 'Creator', 'Mentor', 'Guide', 'Philosopher',
        
        # Academic subjects
        'Mathematician', 'Scientist', 'Historian', 'Linguist', 'Psychologist',
        'Sociologist', 'Economist', 'Philosopher', 'Artist', 'Engineer',
        
        # Abstract concepts
        'Spirit', 'Soul', 'Mind', 'Heart', 'Voice', 'Whisper', 'Echo',
        'Shadow', 'Light', 'Star', 'Moon', 'Sun', 'Flame', 'Wave'
    ]
    
    SPECIAL_NAMES = [
        # For top performers
        'The Legendary One', 'Master of Confessions', 'Community Champion',
        'Ultimate Storyteller', 'Supreme Commentator', 'Elite Contributor',
        'Grandmaster Confessor', 'Platinum Voice', 'Diamond Mind'
    ]
    
    @staticmethod
    def generate_name(user_rank: int = 0, is_special: bool = False, seed: Optional[int] = None) -> str:
        """Generate anonymous name based on rank and special status"""
        if seed:
            random.seed(seed)
        
        if is_special and user_rank <= 3:
            return random.choice(EnhancedAnonymousNames.SPECIAL_NAMES)
        
        # Weight adjectives based on rank
        if user_rank <= 10:  # Top 10 get premium adjectives
            adj_choices = [adj for adj in EnhancedAnonymousNames.ADJECTIVES if adj in [
                'Legendary', 'Brilliant', 'Golden', 'Diamond', 'Stellar', 'Supreme'
            ]] + EnhancedAnonymousNames.ADJECTIVES[:20]
        else:
            adj_choices = EnhancedAnonymousNames.ADJECTIVES
        
        adjective = random.choice(adj_choices)
        noun = random.choice(EnhancedAnonymousNames.NOUNS)
        
        return f"{adjective} {noun}"

class SeasonalCompetitionManager:
    """Manages seasonal competitions and special events"""
    
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.initialize_seasonal_tables()
    
    def initialize_seasonal_tables(self):
        """Create tables for seasonal competitions"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Seasonal competitions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS seasonal_competitions (
                season_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                theme TEXT,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                special_rewards TEXT,
                status TEXT DEFAULT 'upcoming',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Seasonal participation table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS seasonal_participation (
                participation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                season_id TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                points_earned INTEGER DEFAULT 0,
                achievements_earned INTEGER DEFAULT 0,
                rank_achieved INTEGER,
                special_rewards_earned TEXT,
                FOREIGN KEY(season_id) REFERENCES seasonal_competitions(season_id),
                FOREIGN KEY(user_id) REFERENCES users(user_id),
                UNIQUE(season_id, user_id)
            )
        ''')
        
        # Competition rewards table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS competition_rewards (
                reward_id INTEGER PRIMARY KEY AUTOINCREMENT,
                season_id TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                reward_type TEXT NOT NULL,
                reward_description TEXT,
                points_bonus INTEGER DEFAULT 0,
                special_badge TEXT,
                awarded_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(season_id) REFERENCES seasonal_competitions(season_id),
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def create_seasonal_competition(self, name: str, description: str, theme: str,
                                  duration_days: int = 30, special_rewards: Dict = None) -> str:
        """Create a new seasonal competition"""
        season_id = f"season_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        start_date = datetime.now()
        end_date = start_date + timedelta(days=duration_days)
        
        if special_rewards is None:
            special_rewards = {
                "first_place": {"points": 1000, "badge": "🏆 Seasonal Champion"},
                "second_place": {"points": 750, "badge": "🥈 Seasonal Runner-up"},
                "third_place": {"points": 500, "badge": "🥉 Seasonal Third Place"},
                "participation": {"points": 100, "badge": "🎪 Seasonal Participant"}
            }
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO seasonal_competitions
            (season_id, name, description, theme, start_date, end_date, special_rewards, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (season_id, name, description, theme, start_date.isoformat(),
              end_date.isoformat(), json.dumps(special_rewards), 'active'))
        
        conn.commit()
        conn.close()
        
        return season_id
    
    def get_active_seasons(self) -> List[Season]:
        """Get currently active seasonal competitions"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT season_id, name, description, theme, start_date, end_date, special_rewards, status
            FROM seasonal_competitions
            WHERE status = 'active' AND datetime(end_date) > datetime('now')
        ''')
        
        seasons = []
        for row in cursor.fetchall():
            season = Season(
                season_id=row[0],
                name=row[1],
                description=row[2],
                theme=row[4],
                start_date=datetime.fromisoformat(row[4]),
                end_date=datetime.fromisoformat(row[5]),
                special_rewards=json.loads(row[6]),
                status=CompetitionStatus(row[7])
            )
            seasons.append(season)
        
        conn.close()
        return seasons

class EnhancedLeaderboardManager:
    """Advanced leaderboard with seasonal competitions and better privacy"""
    
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.seasonal_manager = SeasonalCompetitionManager(db_path)
        self.name_generator = EnhancedAnonymousNames()
    
    def get_enhanced_leaderboard(self, leaderboard_type: LeaderboardType, 
                               limit: int = 10, user_id: Optional[int] = None) -> List[LeaderboardEntry]:
        """Get enhanced leaderboard with more detailed information"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Build query based on leaderboard type
        if leaderboard_type == LeaderboardType.WEEKLY:
            time_filter = "datetime('now', '-7 days')"
            points_column = "ur.weekly_points"
        elif leaderboard_type == LeaderboardType.MONTHLY:
            time_filter = "datetime('now', '-30 days')"
            points_column = "ur.monthly_points"
        elif leaderboard_type == LeaderboardType.QUARTERLY:
            time_filter = "datetime('now', '-90 days')"
            points_column = "ur.total_points"  # Will filter by date
        elif leaderboard_type == LeaderboardType.YEARLY:
            time_filter = "datetime('now', '-365 days')"
            points_column = "ur.total_points"  # Will filter by date
        else:  # ALL_TIME
            time_filter = None
            points_column = "ur.total_points"
        
        # Base query
        base_query = f'''
            SELECT ur.user_id, {points_column} as points, ur.current_rank_id,
                   rd.rank_name, rd.rank_emoji, ur.consecutive_days,
                   ur.total_achievements, ur.created_at
            FROM user_rankings ur
            JOIN rank_definitions rd ON ur.current_rank_id = rd.rank_id
            WHERE {points_column} > 0
        '''
        
        # Add time filter for quarterly and yearly
        if leaderboard_type in [LeaderboardType.QUARTERLY, LeaderboardType.YEARLY]:
            base_query += f" AND ur.last_activity >= {time_filter}"
        
        base_query += f" ORDER BY {points_column} DESC LIMIT ?"
        
        cursor.execute(base_query, (limit,))
        results = cursor.fetchall()
        
        leaderboard = []
        for i, row in enumerate(results):
            user_db_id, points, rank_id, rank_name, rank_emoji, consecutive_days, achievements, created_at = row
            
            # Generate consistent anonymous name using user_id as seed
            anonymous_name = self.name_generator.generate_name(
                user_rank=i+1, 
                is_special=(i < 3), 
                seed=hash(str(user_db_id) + leaderboard_type.value) % 1000000
            )
            
            # Get special badges
            special_badges = self._get_user_badges(user_db_id, cursor)
            
            entry = LeaderboardEntry(
                position=i+1,
                anonymous_name=anonymous_name,
                points=points,
                rank_emoji=rank_emoji,
                rank_name=rank_name,
                special_badges=special_badges,
                streak_days=consecutive_days,
                achievements_count=achievements,
                is_current_user=(user_db_id == user_id)
            )
            leaderboard.append(entry)
        
        conn.close()
        return leaderboard
    
    def _get_user_badges(self, user_id: int, cursor) -> List[str]:
        """Get special badges for a user"""
        badges = []
        
        # Check for seasonal competition badges
        cursor.execute('''
            SELECT DISTINCT special_badge FROM competition_rewards 
            WHERE user_id = ? AND special_badge IS NOT NULL
        ''', (user_id,))
        
        for badge_row in cursor.fetchall():
            badges.append(badge_row[0])
        
        # Check for special achievements
        cursor.execute('''
            SELECT achievement_name FROM user_achievements 
            WHERE user_id = ? AND is_special = 1
            ORDER BY achieved_at DESC LIMIT 3
        ''', (user_id,))
        
        for achievement_row in cursor.fetchall():
            # Convert achievement name to badge emoji
            achievement_name = achievement_row[0]
            if "Legend" in achievement_name:
                badges.append("🌟")
            elif "Champion" in achievement_name:
                badges.append("🏆")
            elif "Master" in achievement_name:
                badges.append("👑")
            elif "Elite" in achievement_name:
                badges.append("💎")
        
        return badges[:3]  # Limit to 3 badges
    
    def get_seasonal_leaderboard(self, season_id: str, limit: int = 10) -> List[LeaderboardEntry]:
        """Get leaderboard for a specific seasonal competition"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT sp.user_id, sp.points_earned, ur.current_rank_id,
                   rd.rank_name, rd.rank_emoji, sp.achievements_earned
            FROM seasonal_participation sp
            JOIN user_rankings ur ON sp.user_id = ur.user_id
            JOIN rank_definitions rd ON ur.current_rank_id = rd.rank_id
            WHERE sp.season_id = ? AND sp.points_earned > 0
            ORDER BY sp.points_earned DESC
            LIMIT ?
        ''', (season_id, limit))
        
        results = cursor.fetchall()
        leaderboard = []
        
        for i, row in enumerate(results):
            user_db_id, points, rank_id, rank_name, rank_emoji, seasonal_achievements = row
            
            # Generate seasonal anonymous name
            anonymous_name = self.name_generator.generate_name(
                user_rank=i+1, 
                is_special=(i < 3),
                seed=hash(str(user_db_id) + season_id) % 1000000
            )
            
            # Get seasonal badges
            special_badges = self._get_seasonal_badges(user_db_id, season_id, cursor)
            
            entry = LeaderboardEntry(
                position=i+1,
                anonymous_name=anonymous_name,
                points=points,
                rank_emoji=rank_emoji,
                rank_name=rank_name,
                special_badges=special_badges,
                streak_days=0,  # Not relevant for seasonal
                achievements_count=seasonal_achievements
            )
            leaderboard.append(entry)
        
        conn.close()
        return leaderboard
    
    def _get_seasonal_badges(self, user_id: int, season_id: str, cursor) -> List[str]:
        """Get badges earned in a specific season"""
        cursor.execute('''
            SELECT special_badge FROM competition_rewards
            WHERE user_id = ? AND season_id = ? AND special_badge IS NOT NULL
        ''', (user_id, season_id))
        
        return [row[0] for row in cursor.fetchall()]
    
    def get_leaderboard_stats(self, leaderboard_type: LeaderboardType) -> Dict[str, Any]:
        """Get statistics about the leaderboard"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if leaderboard_type == LeaderboardType.WEEKLY:
            points_column = "weekly_points"
        elif leaderboard_type == LeaderboardType.MONTHLY:
            points_column = "monthly_points"
        else:
            points_column = "total_points"
        
        # Get basic stats
        cursor.execute(f'''
            SELECT 
                COUNT(*) as total_participants,
                AVG({points_column}) as average_points,
                MAX({points_column}) as highest_points,
                MIN({points_column}) as lowest_points
            FROM user_rankings
            WHERE {points_column} > 0
        ''')
        
        stats_row = cursor.fetchone()
        
        # Get rank distribution
        cursor.execute(f'''
            SELECT rd.rank_name, COUNT(*) as count
            FROM user_rankings ur
            JOIN rank_definitions rd ON ur.current_rank_id = rd.rank_id
            WHERE ur.{points_column} > 0
            GROUP BY rd.rank_name
            ORDER BY rd.rank_id
        ''')
        
        rank_distribution = dict(cursor.fetchall())
        
        conn.close()
        
        return {
            "total_participants": stats_row[0],
            "average_points": round(stats_row[1] or 0, 2),
            "highest_points": stats_row[2] or 0,
            "lowest_points": stats_row[3] or 0,
            "rank_distribution": rank_distribution,
            "leaderboard_type": leaderboard_type.value
        }

def setup_sample_seasonal_competition():
    """Set up a sample seasonal competition for testing"""
    seasonal_manager = SeasonalCompetitionManager()
    
    # Create a "Back to School" seasonal competition
    season_id = seasonal_manager.create_seasonal_competition(
        name="🎒 Back to School Challenge",
        description="Welcome back, ASTU students! Share your experiences and earn rewards!",
        theme="academic_year_start",
        duration_days=30,
        special_rewards={
            "first_place": {"points": 1500, "badge": "🏆 Academic Champion"},
            "second_place": {"points": 1000, "badge": "🥈 Scholar Runner-up"},
            "third_place": {"points": 750, "badge": "🥉 Distinguished Student"},
            "top_10": {"points": 300, "badge": "📚 Honor Roll"},
            "participation": {"points": 150, "badge": "🎒 Back to School Participant"}
        }
    )
    
    print(f"✅ Created seasonal competition: {season_id}")
    return season_id

def test_enhanced_leaderboard():
    """Test the enhanced leaderboard system"""
    print("=== TESTING ENHANCED LEADERBOARD SYSTEM ===")
    
    leaderboard_manager = EnhancedLeaderboardManager()
    
    # Test different leaderboard types
    for lb_type in [LeaderboardType.WEEKLY, LeaderboardType.MONTHLY, LeaderboardType.ALL_TIME]:
        print(f"\n📊 {lb_type.value.upper()} LEADERBOARD:")
        
        leaderboard = leaderboard_manager.get_enhanced_leaderboard(lb_type, limit=5)
        
        if not leaderboard:
            print("  No participants yet")
            continue
        
        for entry in leaderboard:
            badges_str = " ".join(entry.special_badges) if entry.special_badges else ""
            print(f"  #{entry.position} {entry.rank_emoji} {entry.anonymous_name} - {entry.points:,} points {badges_str}")
            print(f"      {entry.rank_name} | {entry.streak_days} day streak | {entry.achievements_count} achievements")
        
        # Show stats
        stats = leaderboard_manager.get_leaderboard_stats(lb_type)
        print(f"  📈 Stats: {stats['total_participants']} participants, avg {stats['average_points']} points")

if __name__ == '__main__':
    # Setup seasonal competition
    setup_sample_seasonal_competition()
    
    # Test enhanced leaderboard
    test_enhanced_leaderboard()
    
    print("\n🎉 Enhanced leaderboard system is ready!")
