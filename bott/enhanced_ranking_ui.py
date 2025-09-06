#!/usr/bin/env python3
"""
Enhanced Ranking UI with Better Progress Visualization and User Experience
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
from typing import List, Dict, Optional
import math
from datetime import datetime, timedelta

from enhanced_ranking_system import EnhancedPointSystem, EnhancedAchievementSystem
from enhanced_leaderboard import EnhancedLeaderboardManager, LeaderboardType
from enhanced_ranking_system import UserRank
from ranking_integration import ranking_manager
from utils import escape_markdown_text
from logger import get_logger

logger = get_logger('enhanced_ranking_ui')

class EnhancedRankingUI:
    """Enhanced UI components with better visualizations"""
    
    @staticmethod
    def create_advanced_progress_bar(current: int, maximum: int, length: int = 15) -> str:
        """Create an advanced progress bar with different styles"""
        if maximum == 0:
            return "🔥" * length + " MAX LEVEL"
        
        progress = min(current / maximum, 1.0)
        filled = int(progress * length)
        empty = length - filled
        
        # Different styles based on progress
        if progress >= 0.9:
            fill_char = "🔥"  # Almost complete
        elif progress >= 0.7:
            fill_char = "⭐"  # Good progress
        elif progress >= 0.5:
            fill_char = "💫"  # Halfway
        elif progress >= 0.3:
            fill_char = "✨"  # Some progress
        else:
            fill_char = "🌟"  # Starting
        
        empty_char = "▫️"
        
        bar = fill_char * filled + empty_char * empty
        percentage = f"{int(progress * 100)}%"
        
        return f"{bar} {percentage}"
    
    @staticmethod
    def create_streak_visualization(streak_days: int) -> str:
        """Create visual representation of streak"""
        if streak_days == 0:
            return "📅 No streak yet - start your journey!"
        elif streak_days < 7:
            return f"🔥 {streak_days} day streak - keep it up!"
        elif streak_days < 30:
            return f"⚡ {streak_days} day streak - you're on fire!"
        elif streak_days < 90:
            return f"🚀 {streak_days} day streak - amazing dedication!"
        elif streak_days < 365:
            return f"👑 {streak_days} day streak - you're a legend!"
        else:
            return f"🌟 {streak_days} day streak - ULTIMATE DEVOTEE!"
    
    @staticmethod
    def format_enhanced_rank_display(user_rank: UserRank, user_id: int) -> str:
        """Enhanced rank display with more visual elements"""
        # Calculate progress to next rank
        if user_rank.points_to_next > 0:
            current_progress = user_rank.total_points - (user_rank.next_rank_points - user_rank.points_to_next)
            progress_bar = EnhancedRankingUI.create_advanced_progress_bar(
                current_progress, user_rank.points_to_next, 12
            )
            next_rank_text = f"Next: {user_rank.points_to_next:,} points to go"
        else:
            progress_bar = "🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥 MAXED!"
            next_rank_text = "🎉 Maximum rank achieved!"
        
        # Get streak visualization
        from db import get_db
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT consecutive_days FROM user_rankings WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        streak_days = result[0] if result else 0
        conn.close()
        
        streak_viz = EnhancedRankingUI.create_streak_visualization(streak_days)
        
        # Special rank indicator
        rank_indicator = "⭐ SPECIAL RANK" if user_rank.is_special_rank else "📊 Standard Rank"
        
        rank_text = f"""
🏆 *YOUR RANKING STATUS*

{escape_markdown_text(user_rank.rank_emoji)} **{escape_markdown_text(user_rank.rank_name)}** {escape_markdown_text('(' + rank_indicator + ')')}
💎 **{user_rank.total_points:,} Total Points**

📈 *Progress to Next Rank*
{progress_bar}
{escape_markdown_text(next_rank_text)}

{escape_markdown_text(streak_viz)}

🎯 **{user_rank.total_points:,}** total points earned
🏅 **{ranking_manager.get_user_achievements(user_id).__len__()}** achievements unlocked
"""
        
        # Add special perks if any
        if user_rank.special_perks:
            perks_text = "\n🎁 *SPECIAL PERKS UNLOCKED:*\n"
            perk_emojis = {
                "daily_confessions": "📝",
                "priority_review": "⚡",
                "comment_highlight": "✨",
                "featured_chance": "🌟",
                "exclusive_categories": "🔓",
                "custom_emoji": "😎",
                "legend_badge": "👑",
                "unlimited_daily": "♾️",
                "all_perks": "🌈"
            }
            
            for perk, value in user_rank.special_perks.items():
                emoji = perk_emojis.get(perk, "🎁")
                if perk == "daily_confessions":
                    perks_text += f"{emoji} Daily confessions: **{value}**\n"
                elif perk == "featured_chance":
                    perks_text += f"{emoji} Featured post chance: **{int(value*100)}%**\n"
                elif perk in ["priority_review", "comment_highlight", "legend_badge", "unlimited_daily", "all_perks"]:
                    perk_name = perk.replace('_', ' ').title()
                    perks_text += f"{emoji} **{escape_markdown_text(perk_name)}**\n"
            
            rank_text += perks_text
        
        return rank_text
    
    @staticmethod
    def create_enhanced_ranking_keyboard(user_id: int) -> InlineKeyboardMarkup:
        """Create enhanced keyboard with more options"""
        keyboard = [
            [
                InlineKeyboardButton("🎯 My Achievements", callback_data="enhanced_achievements"),
                InlineKeyboardButton("📊 Detailed Stats", callback_data="enhanced_stats")
            ],
            [
                InlineKeyboardButton("🏆 Leaderboards", callback_data="enhanced_leaderboard"),
                InlineKeyboardButton("🔥 My Progress", callback_data="enhanced_progress")
            ],
            [
                InlineKeyboardButton("🎪 Seasonal Events", callback_data="seasonal_competitions"),
                InlineKeyboardButton("🎁 Point Guide", callback_data="enhanced_point_guide")
            ],
            [
                InlineKeyboardButton("📈 Analytics", callback_data="ranking_analytics"),
                InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def create_leaderboard_selection_keyboard() -> InlineKeyboardMarkup:
        """Enhanced leaderboard selection with more options"""
        keyboard = [
            [
                InlineKeyboardButton("📅 This Week", callback_data="leaderboard_weekly"),
                InlineKeyboardButton("📆 This Month", callback_data="leaderboard_monthly")
            ],
            [
                InlineKeyboardButton("🗓️ This Quarter", callback_data="leaderboard_quarterly"),
                InlineKeyboardButton("📅 This Year", callback_data="leaderboard_yearly")
            ],
            [
                InlineKeyboardButton("⭐ All Time Champions", callback_data="leaderboard_alltime"),
                InlineKeyboardButton("🎪 Seasonal Events", callback_data="leaderboard_seasonal")
            ],
            [
                InlineKeyboardButton("📊 Leaderboard Stats", callback_data="leaderboard_stats"),
                InlineKeyboardButton("🔙 Back", callback_data="enhanced_rank_menu")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def format_enhanced_leaderboard(leaderboard_data: List, leaderboard_type: str, stats: Dict = None) -> str:
        """Format enhanced leaderboard with better visualization"""
        if not leaderboard_data:
            return f"""
🏆 *{leaderboard_type.title()} Leaderboard*

🎯 No participants yet\\. Be the first to earn your place\\!

💡 *Tips to get on the leaderboard:*
• Submit quality confessions
• Engage with comments
• Maintain daily streaks
• Earn achievements
"""
        
        # Title with stats
        header = f"🏆 *{leaderboard_type.title()} Leaderboard*\n\n"
        if stats:
            header += f"👥 **{stats.get('total_participants', 0)}** active participants\n"
            header += f"📊 Average: **{stats.get('average_points', 0):,}** points\n"
            header += f"🎯 Highest: **{stats.get('highest_points', 0):,}** points\n\n"
        
        leaderboard_text = header
        
        # Position emojis with more variety
        position_emojis = {
            1: "🥇", 2: "🥈", 3: "🥉", 4: "🏅", 5: "🏅",
            6: "⭐", 7: "⭐", 8: "⭐", 9: "💫", 10: "💫"
        }
        
        for entry in leaderboard_data:
            position = entry.position if hasattr(entry, 'position') else entry.get('position', 0)
            name = entry.anonymous_name if hasattr(entry, 'anonymous_name') else entry.get('anonymous_name', 'Unknown')
            points = entry.points if hasattr(entry, 'points') else entry.get('points', 0)
            rank_emoji = entry.rank_emoji if hasattr(entry, 'rank_emoji') else entry.get('rank_emoji', '🎯')
            rank_name = entry.rank_name if hasattr(entry, 'rank_name') else entry.get('rank_name', 'Student')
            
            pos_emoji = position_emojis.get(position, f"{position}\\.")
            
            # Add badges if available
            badges_str = ""
            if hasattr(entry, 'special_badges') and entry.special_badges:
                badges_str = " " + " ".join(entry.special_badges[:2])  # Show max 2 badges
            
            # Add streak indicator
            streak_str = ""
            if hasattr(entry, 'streak_days') and entry.streak_days > 0:
                if entry.streak_days >= 30:
                    streak_str = " 🔥"
                elif entry.streak_days >= 7:
                    streak_str = " ⚡"
            
            leaderboard_text += (
                f"{pos_emoji} {escape_markdown_text(rank_emoji)} "
                f"**{escape_markdown_text(name)}**{badges_str}{streak_str}\\n"
                f"     {escape_markdown_text(rank_name)} • **{points:,}** points\\n\\n"
            )
        
        leaderboard_text += "🚀 *Keep climbing the ranks\\!*"
        return leaderboard_text
    
    @staticmethod
    def format_enhanced_achievements(achievements: List[Dict], user_achievements_count: int) -> str:
        """Enhanced achievements display with categories and progress"""
        if not achievements:
            return """
🎯 *YOUR ACHIEVEMENTS*

🌟 No achievements unlocked yet\\!

💡 *Start earning achievements by:*
• Posting your first confession
• Making your first comment  
• Building daily streaks
• Getting likes on your content
• Participating in community events

🎁 Each achievement rewards you with bonus points\\!
"""
        
        # Group achievements by category
        categories = {}
        for achievement in achievements:
            category = achievement.get('category', 'General')
            if category not in categories:
                categories[category] = []
            categories[category].append(achievement)
        
        achievements_text = f"""
🎯 *YOUR ACHIEVEMENTS* \\({len(achievements)} earned\\)

"""
        
        # Category emojis
        category_emojis = {
            'milestone': '🎯', 'content': '📝', 'engagement': '💬',
            'popularity': '🔥', 'streak': '⚡', 'quality': '💎',
            'community': '🤝', 'seasonal': '🎪', 'secret': '🔮',
            'time': '⏰', 'points': '💰', 'meta': '🏅'
        }
        
        for category, cat_achievements in categories.items():
            emoji = category_emojis.get(category.lower(), '🏆')
            achievements_text += f"{emoji} *{category.title()}*\\n"
            
            for achievement in cat_achievements[:3]:  # Show max 3 per category
                special_mark = "⭐" if achievement.get('is_special') else "🏆"
                date_str = achievement['date'][:10] if achievement.get('date') else "Recent"
                
                achievements_text += (
                    f"   {special_mark} *{escape_markdown_text(achievement['name'])}*\\n"
                    f"      _{escape_markdown_text(achievement['description'])}_\\n"
                    f"      \\+{achievement['points']} pts • {escape_markdown_text(date_str)}\\n\\n"
                )
            
            if len(cat_achievements) > 3:
                achievements_text += f"   \\.\\.\\.and {len(cat_achievements) - 3} more in this category\\n\\n"
        
        # Achievement progress
        total_possible = len(EnhancedAchievementSystem().get_all_achievements())
        progress = (len(achievements) / total_possible) * 100
        achievements_text += f"📊 *Progress:* {len(achievements)}/{total_possible} \\({progress:.1f}%\\) unlocked"
        
        return achievements_text
    
    @staticmethod
    def format_enhanced_point_guide() -> str:
        """Enhanced point earning guide with better organization"""
        return """
🎁 *COMPLETE POINT EARNING GUIDE*

*🏆 CONFESSION ACTIVITIES*
📝 Submit confession: **\\+15** points
✅ Confession approved: **\\+35** points  
🔥 Confession featured: **\\+75** points
👍 Each like received: **\\+3** points \\(bonus for viral\\)
🌟 Trending post: **\\+125** points
💯 100\\+ likes: **\\+150** points bonus

*💬 ENGAGEMENT ACTIVITIES*  
💭 Post comment: **\\+8** points
👍 Comment liked: **\\+2** points
💎 Quality comment: **\\+30** points
🎯 Helpful comment: **\\+25** points
🔥 Viral comment: **\\+50** points bonus

*⚡ STREAK & DAILY BONUSES*
📅 Daily login: **\\+5** points
🔥 Consecutive days \\(3\\+\\): **\\+10\\+** points/day
📅 Week streak: **\\+50** points
📆 Month streak: **\\+200** points  
🏆 Quarter streak: **\\+500** points
👑 Year streak: **\\+1000** points

*🎁 SPECIAL BONUSES*
🎯 First confession: **\\+75** points
💬 First comment: **\\+30** points
🏅 Achievement earned: **\\+25** points
🎪 Seasonal participation: **\\+75** points
💎 High quality content: **\\+40** points

*🎉 TIME BONUSES*
🌙 Night owl \\(10PM\\-6AM\\): **\\+5%** bonus
🎉 Weekend posting: **\\+10%** bonus
🎄 Holiday events: **\\+10\\-25** bonus

*🚫 POINT PENALTIES*
❌ Content rejected: **\\-3** points
⚠️ Spam detected: **\\-10** points
🚨 Inappropriate content: **\\-20** points

*💡 PRO TIPS*
• Longer, thoughtful content earns more
• Consistent daily activity builds streaks
• Quality over quantity always wins
• Engage positively with others
• Participate in seasonal events
• Help build the community

🚀 *The more you contribute, the faster you climb\\!*
"""

async def show_enhanced_ranking_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show enhanced ranking menu with better UI"""
    user_id = update.effective_user.id
    user_rank = ranking_manager.get_user_rank(user_id)
    
    if not user_rank:
        ranking_manager.initialize_user_ranking(user_id)
        user_rank = ranking_manager.get_user_rank(user_id)
    
    if not user_rank:
        await update.message.reply_text("❗ Error loading ranking information. Please try again.")
        return
    
    rank_display = EnhancedRankingUI.format_enhanced_rank_display(user_rank, user_id)
    keyboard = EnhancedRankingUI.create_enhanced_ranking_keyboard(user_id)
    
    if update.callback_query:
        try:
            await update.callback_query.edit_message_text(
                rank_display,
                parse_mode="MarkdownV2",
                reply_markup=keyboard
            )
        except Exception as e:
            logger.error(f"Error editing enhanced ranking message: {e}")
            await update.callback_query.answer("Error updating display. Please try again.")
    else:
        await update.message.reply_text(
            rank_display,
            parse_mode="MarkdownV2",
            reply_markup=keyboard
        )

async def show_enhanced_leaderboard_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show enhanced leaderboard selection"""
    keyboard = EnhancedRankingUI.create_leaderboard_selection_keyboard()
    
    text = """
🏆 *COMMUNITY LEADERBOARDS*

Choose your preferred timeframe to see the top contributors:

📅 **This Week:** Current weekly champions
📆 **This Month:** Monthly top performers  
🗓️ **This Quarter:** 90\\-day elite members
📅 **This Year:** Annual ranking leaders
⭐ **All Time:** Legendary hall of fame
🎪 **Seasonal:** Special event competitions

🔒 *Privacy Protected:* All names are anonymized
🏅 *Fair Competition:* Multiple categories available
"""
    
    if update.callback_query:
        await update.callback_query.edit_message_text(
            text,
            parse_mode="MarkdownV2",
            reply_markup=keyboard
        )
    else:
        await update.message.reply_text(
            text,
            parse_mode="MarkdownV2",
            reply_markup=keyboard
        )

async def show_enhanced_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE, leaderboard_type: str):
    """Show enhanced leaderboard for specific timeframe"""
    leaderboard_manager = EnhancedLeaderboardManager()
    
    # Map string to enum
    type_mapping = {
        'weekly': LeaderboardType.WEEKLY,
        'monthly': LeaderboardType.MONTHLY,  
        'quarterly': LeaderboardType.QUARTERLY,
        'yearly': LeaderboardType.YEARLY,
        'alltime': LeaderboardType.ALL_TIME
    }
    
    lb_type = type_mapping.get(leaderboard_type, LeaderboardType.ALL_TIME)
    leaderboard = leaderboard_manager.get_enhanced_leaderboard(lb_type, limit=10, user_id=update.effective_user.id)
    stats = leaderboard_manager.get_leaderboard_stats(lb_type)
    
    leaderboard_text = EnhancedRankingUI.format_enhanced_leaderboard(leaderboard, leaderboard_type, stats)
    
    keyboard = [
        [
            InlineKeyboardButton("📅 Weekly", callback_data="enhanced_leaderboard_weekly"),
            InlineKeyboardButton("📆 Monthly", callback_data="enhanced_leaderboard_monthly"),
        ],
        [
            InlineKeyboardButton("🗓️ Quarterly", callback_data="enhanced_leaderboard_quarterly"),
            InlineKeyboardButton("📅 Yearly", callback_data="enhanced_leaderboard_yearly")
        ],
        [
            InlineKeyboardButton("⭐ All Time", callback_data="enhanced_leaderboard_alltime"),
            InlineKeyboardButton("🔙 Back", callback_data="enhanced_leaderboard")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.edit_message_text(
            leaderboard_text,
            parse_mode="MarkdownV2",
            reply_markup=reply_markup
        )

async def show_enhanced_achievements(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show enhanced achievements display"""
    user_id = update.effective_user.id
    achievements = ranking_manager.get_user_achievements(user_id, limit=50)  # Get more for categorization
    
    # Get total achievement count
    user_rank = ranking_manager.get_user_rank(user_id)
    achievement_count = user_rank.total_points if user_rank else 0
    
    achievements_text = EnhancedRankingUI.format_enhanced_achievements(achievements, achievement_count)
    
    keyboard = [
        [
            InlineKeyboardButton("🎯 Achievement Guide", callback_data="achievement_guide"),
            InlineKeyboardButton("🏆 Missing Achievements", callback_data="missing_achievements")
        ],
        [
            InlineKeyboardButton("📊 My Progress", callback_data="enhanced_progress"),
            InlineKeyboardButton("🔙 Back", callback_data="enhanced_rank_menu")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.edit_message_text(
            achievements_text,
            parse_mode="MarkdownV2",
            reply_markup=reply_markup
        )

async def show_enhanced_point_guide(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show enhanced point earning guide"""
    guide_text = EnhancedRankingUI.format_enhanced_point_guide()
    
    keyboard = [
        [
            InlineKeyboardButton("🎯 My Achievements", callback_data="enhanced_achievements"),
            InlineKeyboardButton("📊 My Stats", callback_data="enhanced_stats")
        ],
        [
            InlineKeyboardButton("🏆 Leaderboard", callback_data="enhanced_leaderboard"),
            InlineKeyboardButton("🔙 Back", callback_data="enhanced_rank_menu")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.edit_message_text(
            guide_text,
            parse_mode="MarkdownV2",
            reply_markup=reply_markup
        )

# Enhanced callback handlers
async def enhanced_ranking_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle enhanced ranking system callbacks"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == "enhanced_rank_menu":
        await show_enhanced_ranking_menu(update, context)
    elif data == "enhanced_achievements":
        await show_enhanced_achievements(update, context)
    elif data == "enhanced_leaderboard":
        await show_enhanced_leaderboard_menu(update, context)
    elif data.startswith("enhanced_leaderboard_"):
        lb_type = data.replace("enhanced_leaderboard_", "")
        await show_enhanced_leaderboard(update, context, lb_type)
    elif data == "enhanced_point_guide":
        await show_enhanced_point_guide(update, context)
    elif data == "enhanced_stats":
        # Could implement detailed stats view
        await query.answer("🚧 Detailed stats coming soon!")
    elif data == "enhanced_progress":
        # Could implement progress tracking
        await query.answer("🚧 Progress tracking coming soon!")
    elif data == "seasonal_competitions":
        # Could implement seasonal competitions view
        await query.answer("🚧 Seasonal events coming soon!")
    elif data == "ranking_analytics":
        # Could implement analytics view
        await query.answer("🚧 Analytics dashboard coming soon!")
    else:
        await query.answer("Unknown enhanced ranking option.")
