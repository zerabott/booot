"""
Integration layer for ranking system with existing bot functionality
Connects point awards to user actions throughout the bot
"""

import sqlite3
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes
from typing import Optional, Tuple, Dict, Any
import logging

# Import ranking system components
from enhanced_ranking_system import EnhancedPointSystem, EnhancedAchievementSystem, UserRank
from config import DB_PATH, ADMIN_IDS
from utils import escape_markdown_text

logger = logging.getLogger(__name__)

class RankingManager:
    """Main ranking system manager for database operations"""
    
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or DB_PATH
        self.point_system = EnhancedPointSystem()
        self.achievement_system = EnhancedAchievementSystem()
    
    def initialize_user_ranking(self, user_id: int) -> bool:
        """Initialize ranking data for a new user"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR IGNORE INTO user_rankings (
                        user_id, total_points, weekly_points, monthly_points,
                        current_rank_id, rank_progress, total_achievements,
                        highest_rank_achieved, consecutive_days, last_login_date,
                        last_activity, created_at, updated_at
                    ) VALUES (?, 0, 0, 0, 1, 0.0, 0, 1, 0, 
                             CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 
                             CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """, (user_id,))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error initializing user ranking for {user_id}: {e}")
            return False
    
    def award_points(self, user_id: int, activity_type: str, reference_id: Optional[int] = None,
                    reference_type: Optional[str] = None, description: str = "", **kwargs) -> Tuple[bool, int]:
        """Award points to user and update ranking"""
        try:
            # Calculate points
            points = self.point_system.calculate_points(activity_type, **kwargs)
            
            if points == 0:
                return True, 0
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Ensure user ranking exists
                self.initialize_user_ranking(user_id)
                
                # Add point transaction
                cursor.execute("""
                    INSERT INTO point_transactions (
                        user_id, points_change, transaction_type, reference_id,
                        reference_type, description, timestamp
                    ) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (user_id, points, activity_type, reference_id, reference_type, description))
                
                # Update user totals
                cursor.execute("""
                    UPDATE user_rankings 
                    SET total_points = total_points + ?,
                        weekly_points = weekly_points + ?,
                        monthly_points = monthly_points + ?,
                        last_activity = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = ?
                """, (points, points, points, user_id))
                
                # Update rank if needed
                self._update_user_rank(cursor, user_id)
                
                conn.commit()
                return True, points
                
        except Exception as e:
            logger.error(f"Error awarding points to user {user_id}: {e}")
            return False, 0
    
    def get_user_rank(self, user_id: int) -> Optional[UserRank]:
        """Get user's current ranking information"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get user ranking data
                cursor.execute("""
                    SELECT ur.total_points, ur.current_rank_id, ur.consecutive_days,
                           rd.rank_name, rd.rank_emoji, rd.min_points, rd.max_points,
                           rd.special_perks, rd.is_special
                    FROM user_rankings ur
                    JOIN rank_definitions rd ON ur.current_rank_id = rd.rank_id
                    WHERE ur.user_id = ?
                """, (user_id,))
                
                result = cursor.fetchone()
                if not result:
                    return None
                
                total_points, rank_id, consecutive_days, rank_name, rank_emoji, min_points, max_points, special_perks_json, is_special = result
                
                # Parse special perks
                special_perks = {}
                if special_perks_json:
                    try:
                        import json
                        special_perks = json.loads(special_perks_json)
                    except:
                        special_perks = {}
                
                # Calculate points to next rank
                if max_points:
                    points_to_next = max_points - total_points
                    next_rank_points = max_points
                else:
                    points_to_next = 0
                    next_rank_points = total_points
                
                return UserRank(
                    rank_name=rank_name,
                    rank_emoji=rank_emoji,
                    total_points=total_points,
                    points_to_next=max(0, points_to_next),
                    next_rank_points=next_rank_points,
                    is_special_rank=bool(is_special),
                    special_perks=special_perks,
                    rank_level=rank_id,
                    streak_days=consecutive_days or 0
                )
                
        except Exception as e:
            logger.error(f"Error getting user rank for {user_id}: {e}")
            return None
    
    def get_user_achievements(self, user_id: int, limit: int = 20) -> list:
        """Get user's achievements"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT achievement_type, achievement_name, achievement_description,
                           points_awarded, is_special, achieved_at
                    FROM user_achievements
                    WHERE user_id = ?
                    ORDER BY achieved_at DESC
                    LIMIT ?
                """, (user_id, limit))
                
                achievements = []
                for row in cursor.fetchall():
                    achievements.append({
                        'type': row[0],
                        'name': row[1],
                        'description': row[2],
                        'points': row[3],
                        'is_special': bool(row[4]),
                        'date': row[5]
                    })
                
                return achievements
        except Exception as e:
            logger.error(f"Error getting achievements for user {user_id}: {e}")
            return []
    
    def _update_user_rank(self, cursor, user_id: int):
        """Update user's rank based on points"""
        try:
            # Get current points
            cursor.execute("SELECT total_points FROM user_rankings WHERE user_id = ?", (user_id,))
            result = cursor.fetchone()
            if not result:
                return
            
            total_points = result[0]
            
            # Find appropriate rank
            cursor.execute("""
                SELECT rank_id, rank_name, rank_emoji 
                FROM rank_definitions 
                WHERE min_points <= ? AND (max_points IS NULL OR max_points >= ?)
                ORDER BY min_points DESC
                LIMIT 1
            """, (total_points, total_points))
            
            rank_result = cursor.fetchone()
            if rank_result:
                new_rank_id = rank_result[0]
                
                # Update user's rank
                cursor.execute("""
                    UPDATE user_rankings 
                    SET current_rank_id = ?,
                        highest_rank_achieved = CASE 
                            WHEN ? > highest_rank_achieved THEN ?
                            ELSE highest_rank_achieved
                        END
                    WHERE user_id = ?
                """, (new_rank_id, new_rank_id, new_rank_id, user_id))
                
        except Exception as e:
            logger.error(f"Error updating rank for user {user_id}: {e}")

# Global ranking manager instance
ranking_manager = RankingManager()

class RankingIntegration:
    """Integrates ranking system with existing bot features"""
    
    @staticmethod
    async def handle_confession_submitted(user_id: int, post_id: int, category: str, context: ContextTypes.DEFAULT_TYPE):
        """Handle points when confession is submitted"""
        try:
            # Award points using ranking manager
            success, points = ranking_manager.award_points(
                user_id=user_id,
                activity_type='confession_submitted',
                reference_id=post_id,
                reference_type='confession',
                description="Confession submitted",
                content_length=len(category)
            )
            
            if success:
                logger.info(f"Awarded {points} points to user {user_id} for confession submission")
                
                # Check if this is their first confession
                await RankingIntegration.check_first_time_achievements(user_id, 'confession', context)
                
        except Exception as e:
            logger.error(f"Error awarding points for confession submission: {e}")
    
    @staticmethod
    async def handle_confession_approved(user_id: int, post_id: int, admin_id: int, context: ContextTypes.DEFAULT_TYPE):
        """Handle points when confession is approved"""
        try:
            # Award points to user
            success, points = ranking_manager.award_points(
                user_id=user_id,
                activity_type='confession_approved',
                reference_id=post_id,
                reference_type='confession',
                description="Confession approved by admin"
            )
            
            if success:
                logger.info(f"Awarded {points} points to user {user_id} for approved confession")
                
                # Check for rank up and notify user
                await RankingIntegration.check_and_notify_rank_up(user_id, context)
                
                # Daily login bonus (if they haven't been active today)
                await RankingIntegration.award_daily_login_bonus(user_id)
                
        except Exception as e:
            logger.error(f"Error awarding points for confession approval: {e}")
    
    @staticmethod
    async def handle_confession_rejected(user_id: int, post_id: int, admin_id: int):
        """Handle points when confession is rejected"""
        try:
            success, points = ranking_manager.award_points(
                user_id=user_id,
                activity_type='content_rejected',
                reference_id=post_id,
                reference_type='confession',
                description="Confession rejected by admin"
            )
            
            if success:
                logger.info(f"Deducted {abs(points)} points from user {user_id} for rejected confession")
                
        except Exception as e:
            logger.error(f"Error deducting points for confession rejection: {e}")
    
    @staticmethod
    async def handle_comment_posted(user_id: int, post_id: int, comment_id: int, content: str, context: ContextTypes.DEFAULT_TYPE):
        """Handle points when comment is posted"""
        try:
            # Base comment points
            activity_type = 'comment_posted'
            
            # Check if it's a quality comment (longer, thoughtful)
            if len(content) > 100:
                activity_type = 'quality_comment'
            
            success, points = ranking_manager.award_points(
                user_id=user_id,
                activity_type=activity_type,
                reference_id=comment_id,
                reference_type='comment',
                comment_length=len(content),
                description=f"Posted comment on confession {post_id}"
            )
            
            if success:
                logger.info(f"Awarded {points} points to user {user_id} for comment")
                
                # Check if this is their first comment
                await RankingIntegration.check_first_time_achievements(user_id, 'comment', context)
                
                # Check for rank up
                await RankingIntegration.check_and_notify_rank_up(user_id, context)
                
        except Exception as e:
            logger.error(f"Error awarding points for comment: {e}")
    
    @staticmethod
    async def handle_reaction_given(user_id: int, target_id: int, target_type: str, reaction_type: str):
        """Handle points when user gives a reaction"""
        try:
            success, points = ranking_manager.award_points(
                user_id=user_id,
                activity_type='reaction_given',
                reference_id=target_id,
                reference_type=target_type,
                description=f"Gave {reaction_type} reaction to {target_type}"
            )
            
            if success:
                logger.info(f"Awarded {points} points to user {user_id} for reaction")
                
        except Exception as e:
            logger.error(f"Error awarding points for reaction: {e}")
    
    @staticmethod
    async def handle_reaction_received(user_id: int, target_id: int, target_type: str, reaction_type: str, context: ContextTypes.DEFAULT_TYPE):
        """Handle points when user receives a reaction on their content"""
        try:
            activity_type = 'confession_liked' if target_type == 'confession' else 'comment_liked'
            
            success, points = ranking_manager.award_points(
                user_id=user_id,
                activity_type=activity_type,
                reference_id=target_id,
                reference_type=target_type,
                description=f"Received {reaction_type} on {target_type}"
            )
            
            if success:
                logger.info(f"Awarded {points} points to user {user_id} for receiving reaction")
                
                # Check for viral post achievements
                if target_type == 'confession':
                    await RankingIntegration.check_viral_achievements(user_id, target_id, context)
                
        except Exception as e:
            logger.error(f"Error awarding points for received reaction: {e}")
    
    @staticmethod
    async def handle_spam_detected(user_id: int, content_id: int, content_type: str):
        """Handle point deduction for spam"""
        try:
            success, points = ranking_manager.award_points(
                user_id=user_id,
                activity_type='spam_detected',
                reference_id=content_id,
                reference_type=content_type,
                description=f"Spam detected in {content_type}"
            )
            
            if success:
                logger.info(f"Deducted {abs(points)} points from user {user_id} for spam")
                
        except Exception as e:
            logger.error(f"Error deducting points for spam: {e}")
    
    @staticmethod
    async def handle_inappropriate_content(user_id: int, content_id: int, content_type: str):
        """Handle point deduction for inappropriate content"""
        try:
            success, points = ranking_manager.award_points(
                user_id=user_id,
                activity_type='inappropriate_content',
                reference_id=content_id,
                reference_type=content_type,
                description=f"Inappropriate content in {content_type}"
            )
            
            if success:
                logger.info(f"Deducted {abs(points)} points from user {user_id} for inappropriate content")
                
        except Exception as e:
            logger.error(f"Error deducting points for inappropriate content: {e}")
    
    @staticmethod
    async def check_first_time_achievements(user_id: int, activity_type: str, context: ContextTypes.DEFAULT_TYPE):
        """Check and award first-time achievements"""
        try:
            # This will be handled automatically by the achievement system
            # but we can add special notifications here
            pass
            
        except Exception as e:
            logger.error(f"Error checking first-time achievements: {e}")
    
    @staticmethod
    async def check_viral_achievements(user_id: int, post_id: int, context: ContextTypes.DEFAULT_TYPE):
        """Check for viral post achievements based on likes"""
        try:
            import sqlite3
            from config import DB_PATH
            
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                # Get total likes for this post (assuming you have a likes system)
                cursor.execute("""
                    SELECT COUNT(*) FROM reactions 
                    WHERE target_id = ? AND target_type = 'post' AND reaction_type = 'like'
                """, (post_id,))
                
                like_count = cursor.fetchone()[0]
                
                # Check for viral achievements
                if like_count >= 100:
                    success, points = ranking_manager.award_points(
                        user_id=user_id,
                        activity_type='confession_100_likes',
                        reference_id=post_id,
                        reference_type='confession',
                        like_count=like_count,
                        description=f"Confession reached {like_count} likes"
                    )
                    
                    if success:
                        # Notify about viral achievement
                        await notify_achievement_earned(
                            context,
                            user_id,
                            "🔥 Viral Post",
                            f"Your confession got {like_count}+ likes!",
                            points
                        )
                
        except Exception as e:
            logger.error(f"Error checking viral achievements: {e}")
    
    @staticmethod
    async def check_and_notify_rank_up(user_id: int, context: ContextTypes.DEFAULT_TYPE):
        """Check if user ranked up and notify them"""
        try:
            user_rank = ranking_manager.get_user_rank(user_id)
            if not user_rank:
                return
                
            # Check rank history to see if they just ranked up
            import sqlite3
            from config import DB_PATH
            
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT new_rank_id, rd.rank_name, rd.rank_emoji
                    FROM rank_history rh
                    JOIN rank_definitions rd ON rh.new_rank_id = rd.rank_id
                    WHERE rh.user_id = ?
                    ORDER BY rh.created_at DESC
                    LIMIT 1
                """, (user_id,))
                
                result = cursor.fetchone()
                if result:
                    new_rank_id, rank_name, rank_emoji = result
                    if new_rank_id == user_rank.rank_level:
                        # They just ranked up, notify them
                        await notify_rank_up(context, user_id, rank_name, rank_emoji)
                
        except Exception as e:
            logger.error(f"Error checking rank up: {e}")
    
    @staticmethod
    async def award_daily_login_bonus(user_id: int):
        """Award daily login bonus if user hasn't been active today"""
        try:
            success, points = ranking_manager.award_points(
                user_id=user_id,
                activity_type='daily_login',
                description="Daily login bonus"
            )
            
            if success and points > 0:
                logger.info(f"Awarded daily login bonus to user {user_id}")
                
        except Exception as e:
            logger.error(f"Error awarding daily login bonus: {e}")
    
    @staticmethod
    async def handle_admin_action(admin_id: int, action_type: str, target_user_id: Optional[int] = None):
        """Handle admin actions (optional - admins could also earn points)"""
        try:
            if admin_id in ADMIN_IDS and action_type in ['approve_post', 'moderate_content']:
                success, points = ranking_manager.award_points(
                    user_id=admin_id,
                    activity_type='community_contribution',
                    description=f"Admin action: {action_type}"
                )
                
                if success:
                    logger.info(f"Awarded {points} points to admin {admin_id} for {action_type}")
                    
        except Exception as e:
            logger.error(f"Error awarding admin points: {e}")

# Convenience functions for easy integration
async def award_points_for_confession_submission(user_id: int, post_id: int, category: str, context: ContextTypes.DEFAULT_TYPE):
    """Convenience function for confession submission"""
    await RankingIntegration.handle_confession_submitted(user_id, post_id, category, context)

async def award_points_for_confession_approval(user_id: int, post_id: int, admin_id: int, context: ContextTypes.DEFAULT_TYPE):
    """Convenience function for confession approval"""
    await RankingIntegration.handle_confession_approved(user_id, post_id, admin_id, context)

async def award_points_for_comment(user_id: int, post_id: int, comment_id: int, content: str, context: ContextTypes.DEFAULT_TYPE):
    """Convenience function for comment posting"""
    await RankingIntegration.handle_comment_posted(user_id, post_id, comment_id, content, context)

async def award_points_for_reaction_given(user_id: int, target_id: int, target_type: str, reaction_type: str):
    """Convenience function for giving reactions"""
    await RankingIntegration.handle_reaction_given(user_id, target_id, target_type, reaction_type)

async def award_points_for_reaction_received(user_id: int, target_id: int, target_type: str, reaction_type: str, context: ContextTypes.DEFAULT_TYPE):
    """Convenience function for receiving reactions"""
    await RankingIntegration.handle_reaction_received(user_id, target_id, target_type, reaction_type, context)

# Function to add to main menu
async def show_my_rank(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's rank - to be added to main menu"""
    from enhanced_ranking_ui import show_enhanced_ranking_menu
    await show_enhanced_ranking_menu(update, context)

# Notification functions
async def notify_rank_up(context: ContextTypes.DEFAULT_TYPE, user_id: int, rank_name: str, rank_emoji: str):
    """Notify user about rank up"""
    try:
        message = f"🎉 *RANK UP!* 🎉\n\n" \
                 f"Congratulations! You've achieved the rank of:\n" \
                 f"{rank_emoji} **{escape_markdown_text(rank_name)}**\n\n" \
                 f"Keep contributing to climb even higher!"
        
        await context.bot.send_message(
            chat_id=user_id,
            text=message,
            parse_mode="MarkdownV2"
        )
        logger.info(f"Sent rank up notification to user {user_id}: {rank_name}")
    except Exception as e:
        logger.error(f"Error sending rank up notification to user {user_id}: {e}")

async def notify_achievement_earned(context: ContextTypes.DEFAULT_TYPE, user_id: int, 
                                  achievement_name: str, description: str, points: int):
    """Notify user about achievement earned"""
    try:
        message = f"🏆 *ACHIEVEMENT UNLOCKED!* 🏆\n\n" \
                 f"**{escape_markdown_text(achievement_name)}**\n" \
                 f"_{escape_markdown_text(description)}_\n\n" \
                 f"**\+{points}** points earned!"
        
        await context.bot.send_message(
            chat_id=user_id,
            text=message,
            parse_mode="MarkdownV2"
        )
        logger.info(f"Sent achievement notification to user {user_id}: {achievement_name}")
    except Exception as e:
        logger.error(f"Error sending achievement notification to user {user_id}: {e}")
