"""
Advanced analytics system for the confession bot
"""

import sqlite3
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Tuple, Any
from collections import defaultdict, Counter
import json

try:
    import pandas as pd
    import numpy as np
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    pd = None
    np = None

from config import DB_PATH
from logger import get_logger
try:
    from error_handler import handle_database_errors
except ImportError:
    # Fallback decorator if error_handler is not available
    def handle_database_errors(func):
        return func

logger = get_logger('analytics')


class AnalyticsManager:
    """Advanced analytics and insights manager"""
    
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
    
    @handle_database_errors
    def log_user_activity(self, user_id: int, activity_type: str, details: str = ""):
        """Log user activity for analytics"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO user_activity_log (user_id, activity_type, details)
                VALUES (?, ?, ?)
            """, (user_id, activity_type, details))
            conn.commit()
    
    @handle_database_errors
    def update_daily_stats(self, stat_date: date = None):
        """Update daily statistics"""
        if stat_date is None:
            stat_date = date.today()
        
        stat_date_str = stat_date.strftime('%Y-%m-%d')
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Get daily statistics
            stats = {}
            
            # New users today
            cursor.execute("""
                SELECT COUNT(*) FROM users 
                WHERE DATE(join_date) = ?
            """, (stat_date_str,))
            stats['new_users'] = cursor.fetchone()[0]
            
            # Total confessions submitted today
            cursor.execute("""
                SELECT COUNT(*) FROM posts 
                WHERE DATE(timestamp) = ?
            """, (stat_date_str,))
            stats['total_confessions'] = cursor.fetchone()[0]
            
            # Approved confessions today
            cursor.execute("""
                SELECT COUNT(*) FROM posts 
                WHERE DATE(timestamp) = ? AND status = 'approved'
            """, (stat_date_str,))
            stats['approved_confessions'] = cursor.fetchone()[0]
            
            # Rejected confessions today
            cursor.execute("""
                SELECT COUNT(*) FROM posts 
                WHERE DATE(timestamp) = ? AND status = 'rejected'
            """, (stat_date_str,))
            stats['rejected_confessions'] = cursor.fetchone()[0]
            
            # Total comments today
            cursor.execute("""
                SELECT COUNT(*) FROM comments 
                WHERE DATE(timestamp) = ?
            """, (stat_date_str,))
            stats['total_comments'] = cursor.fetchone()[0]
            
            # Active users today (users who submitted or commented)
            cursor.execute("""
                SELECT COUNT(DISTINCT user_id) FROM (
                    SELECT user_id FROM posts WHERE DATE(timestamp) = ?
                    UNION
                    SELECT user_id FROM comments WHERE DATE(timestamp) = ?
                )
            """, (stat_date_str, stat_date_str))
            stats['active_users'] = cursor.fetchone()[0]
            
            # Insert or update daily stats
            cursor.execute("""
                INSERT OR REPLACE INTO daily_stats (
                    stat_date, new_users, total_confessions, approved_confessions,
                    rejected_confessions, total_comments, active_users
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                stat_date_str, stats['new_users'], stats['total_confessions'],
                stats['approved_confessions'], stats['rejected_confessions'],
                stats['total_comments'], stats['active_users']
            ))
            
            conn.commit()
            return stats
    
    @handle_database_errors
    def get_weekly_stats(self, weeks_back: int = 4) -> Dict[str, Any]:
        """Get weekly statistics"""
        end_date = date.today()
        start_date = end_date - timedelta(weeks=weeks_back)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            if not PANDAS_AVAILABLE:
                # Fallback implementation without pandas
                cursor.execute("""
                    SELECT * FROM daily_stats 
                    WHERE stat_date >= ? AND stat_date <= ?
                    ORDER BY stat_date
                """, (start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')))
                
                daily_data = cursor.fetchall()
                if not daily_data:
                    return {'error': 'No data available for the specified period'}
                
                # Manual weekly aggregation
                weekly_data = defaultdict(lambda: {
                    'new_users': 0, 'total_confessions': 0, 'approved_confessions': 0,
                    'rejected_confessions': 0, 'total_comments': 0, 'active_users': []
                })
                
                for row in daily_data:
                    stat_date_str = row[0]
                    stat_date = datetime.strptime(stat_date_str, '%Y-%m-%d').date()
                    year, week, _ = stat_date.isocalendar()
                    week_key = f"{year}-W{week:02d}"
                    
                    weekly_data[week_key]['new_users'] += row[1] or 0
                    weekly_data[week_key]['total_confessions'] += row[2] or 0
                    weekly_data[week_key]['approved_confessions'] += row[3] or 0
                    weekly_data[week_key]['rejected_confessions'] += row[4] or 0
                    weekly_data[week_key]['total_comments'] += row[5] or 0
                    weekly_data[week_key]['active_users'].append(row[6] or 0)
                
                # Calculate averages for active_users
                for week in weekly_data:
                    active_users_list = weekly_data[week]['active_users']
                    weekly_data[week]['active_users'] = sum(active_users_list) / len(active_users_list) if active_users_list else 0
                
                # Calculate trends
                weeks = sorted(weekly_data.keys())
                trends = {}
                if len(weeks) > 1:
                    current = weekly_data[weeks[-1]]
                    previous = weekly_data[weeks[-2]]
                    for key in ['new_users', 'total_confessions', 'approved_confessions', 'rejected_confessions', 'total_comments', 'active_users']:
                        if previous[key] > 0:
                            trends[key] = ((current[key] - previous[key]) / previous[key] * 100)
                        else:
                            trends[key] = 0
                else:
                    trends = {key: 0 for key in ['new_users', 'total_confessions', 'approved_confessions', 'rejected_confessions', 'total_comments', 'active_users']}
                
                # Calculate summary
                all_weeks = list(weekly_data.values())
                summary = {
                    'total_weeks': len(all_weeks),
                    'avg_weekly_confessions': sum(w['total_confessions'] for w in all_weeks) / len(all_weeks) if all_weeks else 0,
                    'avg_weekly_comments': sum(w['total_comments'] for w in all_weeks) / len(all_weeks) if all_weeks else 0,
                    'avg_weekly_new_users': sum(w['new_users'] for w in all_weeks) / len(all_weeks) if all_weeks else 0
                }
                
                return {
                    'weekly_data': dict(weekly_data),
                    'trends': trends,
                    'summary': summary
                }
            
            # Original pandas implementation
            df = pd.read_sql_query("""
                SELECT * FROM daily_stats 
                WHERE stat_date >= ? AND stat_date <= ?
                ORDER BY stat_date
            """, conn, params=(start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')))
            
            if df.empty:
                return {'error': 'No data available for the specified period'}
            
            # Convert stat_date to datetime
            df['stat_date'] = pd.to_datetime(df['stat_date'])
            df['week'] = df['stat_date'].dt.isocalendar().week
            df['year'] = df['stat_date'].dt.year
            df['week_year'] = df['year'].astype(str) + '-W' + df['week'].astype(str).str.zfill(2)
            
            # Group by week
            weekly_stats = df.groupby('week_year').agg({
                'new_users': 'sum',
                'total_confessions': 'sum',
                'approved_confessions': 'sum',
                'rejected_confessions': 'sum',
                'total_comments': 'sum',
                'active_users': 'mean'  # Average daily active users per week
            }).round(2)
            
            # Calculate trends
            trends = {}
            for col in weekly_stats.columns:
                if len(weekly_stats) > 1:
                    current_week = weekly_stats[col].iloc[-1]
                    previous_week = weekly_stats[col].iloc[-2]
                    if previous_week > 0:
                        trends[col] = ((current_week - previous_week) / previous_week * 100)
                    else:
                        trends[col] = 0
                else:
                    trends[col] = 0
            
            return {
                'weekly_data': weekly_stats.to_dict('index'),
                'trends': trends,
                'summary': {
                    'total_weeks': len(weekly_stats),
                    'avg_weekly_confessions': weekly_stats['total_confessions'].mean(),
                    'avg_weekly_comments': weekly_stats['total_comments'].mean(),
                    'avg_weekly_new_users': weekly_stats['new_users'].mean()
                }
            }
    
    @handle_database_errors
    def get_monthly_stats(self, months_back: int = 6) -> Dict[str, Any]:
        """Get monthly statistics"""
        end_date = date.today()
        start_date = end_date - timedelta(days=months_back * 30)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            if not PANDAS_AVAILABLE:
                # Fallback implementation without pandas
                cursor.execute("""
                    SELECT * FROM daily_stats 
                    WHERE stat_date >= ? AND stat_date <= ?
                    ORDER BY stat_date
                """, (start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')))
                
                daily_data = cursor.fetchall()
                if not daily_data:
                    return {'error': 'No data available for the specified period'}
                
                # Manual monthly aggregation
                monthly_data = defaultdict(lambda: {
                    'new_users': 0, 'total_confessions': 0, 'approved_confessions': 0,
                    'rejected_confessions': 0, 'total_comments': 0, 'active_users': []
                })
                
                for row in daily_data:
                    stat_date_str = row[0]
                    stat_date = datetime.strptime(stat_date_str, '%Y-%m-%d').date()
                    month_key = stat_date.strftime('%Y-%m')
                    
                    monthly_data[month_key]['new_users'] += row[1] or 0
                    monthly_data[month_key]['total_confessions'] += row[2] or 0
                    monthly_data[month_key]['approved_confessions'] += row[3] or 0
                    monthly_data[month_key]['rejected_confessions'] += row[4] or 0
                    monthly_data[month_key]['total_comments'] += row[5] or 0
                    monthly_data[month_key]['active_users'].append(row[6] or 0)
                
                # Calculate averages for active_users
                for month in monthly_data:
                    active_users_list = monthly_data[month]['active_users']
                    monthly_data[month]['active_users'] = sum(active_users_list) / len(active_users_list) if active_users_list else 0
                
                # Calculate growth rates
                months = sorted(monthly_data.keys())
                growth_rates = {}
                for key in ['new_users', 'total_confessions', 'approved_confessions', 'rejected_confessions', 'total_comments', 'active_users']:
                    growth_rates[key] = {}
                    for i in range(1, len(months)):
                        current = monthly_data[months[i]][key]
                        previous = monthly_data[months[i-1]][key]
                        if previous > 0:
                            growth_rates[key][months[i]] = ((current - previous) / previous * 100)
                        else:
                            growth_rates[key][months[i]] = 0
                
                # Calculate summary
                all_months = list(monthly_data.values())
                summary = {
                    'total_months': len(all_months),
                    'avg_monthly_confessions': sum(m['total_confessions'] for m in all_months) / len(all_months) if all_months else 0,
                    'avg_monthly_comments': sum(m['total_comments'] for m in all_months) / len(all_months) if all_months else 0,
                    'avg_monthly_new_users': sum(m['new_users'] for m in all_months) / len(all_months) if all_months else 0
                }
                
                return {
                    'monthly_data': dict(monthly_data),
                    'growth_rates': growth_rates,
                    'summary': summary
                }
            
            # Original pandas implementation
            df = pd.read_sql_query("""
                SELECT * FROM daily_stats 
                WHERE stat_date >= ? AND stat_date <= ?
                ORDER BY stat_date
            """, conn, params=(start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')))
            
            if df.empty:
                return {'error': 'No data available for the specified period'}
            
            # Convert stat_date to datetime and extract month-year
            df['stat_date'] = pd.to_datetime(df['stat_date'])
            df['month_year'] = df['stat_date'].dt.to_period('M').astype(str)
            
            # Group by month
            monthly_stats = df.groupby('month_year').agg({
                'new_users': 'sum',
                'total_confessions': 'sum',
                'approved_confessions': 'sum',
                'rejected_confessions': 'sum',
                'total_comments': 'sum',
                'active_users': 'mean'
            }).round(2)
            
            # Calculate growth rates
            growth_rates = {}
            for col in monthly_stats.columns:
                if len(monthly_stats) > 1:
                    pct_change = monthly_stats[col].pct_change().fillna(0) * 100
                    growth_rates[col] = pct_change.to_dict()
                else:
                    growth_rates[col] = {}
            
            return {
                'monthly_data': monthly_stats.to_dict('index'),
                'growth_rates': growth_rates,
                'summary': {
                    'total_months': len(monthly_stats),
                    'avg_monthly_confessions': monthly_stats['total_confessions'].mean(),
                    'avg_monthly_comments': monthly_stats['total_comments'].mean(),
                    'avg_monthly_new_users': monthly_stats['new_users'].mean()
                }
            }
    
    @handle_database_errors
    def get_category_analytics(self, days_back: int = 30) -> Dict[str, Any]:
        """Analyze confession categories popularity and trends"""
        start_date = (date.today() - timedelta(days=days_back)).strftime('%Y-%m-%d')
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Category distribution for approved posts
            cursor.execute("""
                SELECT category, COUNT(*) as count,
                       AVG(COALESCE(likes, 0)) as avg_likes,
                       COUNT(CASE WHEN c.comment_id IS NOT NULL THEN 1 END) as total_comments
                FROM posts p
                LEFT JOIN comments c ON p.post_id = c.post_id
                WHERE p.status = 'approved' AND DATE(p.timestamp) >= ?
                GROUP BY p.category
                ORDER BY count DESC
            """, (start_date,))
            
            categories_data = cursor.fetchall()
            
            if not categories_data:
                return {'error': 'No category data available'}
            
            # Calculate category metrics
            category_stats = {}
            total_posts = sum(row[1] for row in categories_data)
            
            for category, count, avg_likes, total_comments in categories_data:
                category_stats[category] = {
                    'post_count': count,
                    'percentage': (count / total_posts * 100) if total_posts > 0 else 0,
                    'avg_likes': avg_likes or 0,
                    'total_comments': total_comments or 0,
                    'engagement_score': ((avg_likes or 0) + (total_comments or 0)) / max(count, 1)
                }
            
            # Get trending categories (comparing last 7 days vs previous 7 days)
            cursor.execute("""
                SELECT category,
                       SUM(CASE WHEN DATE(timestamp) >= DATE('now', '-7 days') THEN 1 ELSE 0 END) as recent_count,
                       SUM(CASE WHEN DATE(timestamp) >= DATE('now', '-14 days') AND DATE(timestamp) < DATE('now', '-7 days') THEN 1 ELSE 0 END) as previous_count
                FROM posts
                WHERE status = 'approved' AND DATE(timestamp) >= DATE('now', '-14 days')
                GROUP BY category
            """)
            
            trending_data = cursor.fetchall()
            trending_categories = []
            
            for category, recent_count, previous_count in trending_data:
                if previous_count > 0:
                    growth_rate = ((recent_count - previous_count) / previous_count) * 100
                    if growth_rate > 20:  # At least 20% growth
                        trending_categories.append({
                            'category': category,
                            'growth_rate': growth_rate,
                            'recent_count': recent_count,
                            'previous_count': previous_count
                        })
            
            # Sort by growth rate
            trending_categories.sort(key=lambda x: x['growth_rate'], reverse=True)
            
            return {
                'category_stats': category_stats,
                'trending_categories': trending_categories[:5],  # Top 5 trending
                'total_categories': len(category_stats),
                'total_posts_analyzed': total_posts,
                'analysis_period_days': days_back
            }
    
    @handle_database_errors
    def get_user_engagement_metrics(self, days_back: int = 30) -> Dict[str, Any]:
        """Analyze user engagement patterns"""
        start_date = (date.today() - timedelta(days=days_back)).strftime('%Y-%m-%d')
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # User engagement levels
            cursor.execute("""
                SELECT 
                    u.user_id,
                    u.join_date,
                    COUNT(DISTINCT p.post_id) as confession_count,
                    COUNT(DISTINCT c.comment_id) as comment_count,
                    COUNT(DISTINCT r.reaction_id) as reaction_count,
                    MAX(COALESCE(p.timestamp, c.timestamp, r.timestamp)) as last_activity
                FROM users u
                LEFT JOIN posts p ON u.user_id = p.user_id AND DATE(p.timestamp) >= ?
                LEFT JOIN comments c ON u.user_id = c.user_id AND DATE(c.timestamp) >= ?
                LEFT JOIN reactions r ON u.user_id = r.user_id AND DATE(r.timestamp) >= ?
                WHERE DATE(u.join_date) >= ?
                GROUP BY u.user_id
            """, (start_date, start_date, start_date, start_date))
            
            engagement_data = cursor.fetchall()
            
            # Categorize users by engagement level
            engagement_levels = {
                'highly_active': 0,  # 5+ confessions or 20+ comments/reactions
                'moderately_active': 0,  # 2-4 confessions or 5-19 comments/reactions
                'low_active': 0,  # 1 confession or 1-4 comments/reactions
                'inactive': 0  # No activity
            }
            
            user_retention = {'active_users': 0, 'total_users': len(engagement_data)}
            
            for user_data in engagement_data:
                user_id, join_date, confessions, comments, reactions, last_activity = user_data
                total_activity = confessions + comments + reactions
                
                if confessions >= 5 or (comments + reactions) >= 20:
                    engagement_levels['highly_active'] += 1
                elif confessions >= 2 or (comments + reactions) >= 5:
                    engagement_levels['moderately_active'] += 1
                elif total_activity >= 1:
                    engagement_levels['low_active'] += 1
                else:
                    engagement_levels['inactive'] += 1
                
                if last_activity:
                    user_retention['active_users'] += 1
            
            # Calculate retention rate
            retention_rate = (user_retention['active_users'] / max(user_retention['total_users'], 1)) * 100
            
            # Get peak activity hours
            cursor.execute("""
                SELECT strftime('%H', timestamp) as hour, COUNT(*) as activity_count
                FROM (
                    SELECT timestamp FROM posts WHERE DATE(timestamp) >= ?
                    UNION ALL
                    SELECT timestamp FROM comments WHERE DATE(timestamp) >= ?
                    UNION ALL
                    SELECT timestamp FROM reactions WHERE DATE(timestamp) >= ?
                ) 
                GROUP BY hour
                ORDER BY activity_count DESC
            """, (start_date, start_date, start_date))
            
            peak_hours = cursor.fetchall()
            
            return {
                'engagement_levels': engagement_levels,
                'retention_rate': retention_rate,
                'peak_activity_hours': dict(peak_hours[:5]),  # Top 5 hours
                'total_users_analyzed': user_retention['total_users'],
                'active_users': user_retention['active_users'],
                'analysis_period_days': days_back
            }
    
    @handle_database_errors
    def get_content_performance_metrics(self, limit: int = 20) -> Dict[str, Any]:
        """Analyze content performance and quality metrics"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Top performing posts by engagement
            cursor.execute("""
                SELECT 
                    p.post_id,
                    p.category,
                    p.timestamp,
                    COALESCE(p.likes, 0) as likes,
                    COUNT(c.comment_id) as comment_count,
                    COUNT(r.reaction_id) as reaction_count,
                    (COALESCE(p.likes, 0) + COUNT(c.comment_id) * 2 + COUNT(r.reaction_id)) as engagement_score
                FROM posts p
                LEFT JOIN comments c ON p.post_id = c.post_id
                LEFT JOIN reactions r ON r.target_type = 'post' AND r.target_id = p.post_id
                WHERE p.status = 'approved'
                GROUP BY p.post_id
                ORDER BY engagement_score DESC
                LIMIT ?
            """, (limit,))
            
            top_posts = cursor.fetchall()
            
            # Average performance metrics
            cursor.execute("""
                SELECT 
                    AVG(COALESCE(likes, 0)) as avg_likes,
                    AVG(comment_count) as avg_comments,
                    AVG(reaction_count) as avg_reactions
                FROM (
                    SELECT 
                        p.post_id,
                        COALESCE(p.likes, 0) as likes,
                        COUNT(c.comment_id) as comment_count,
                        COUNT(r.reaction_id) as reaction_count
                    FROM posts p
                    LEFT JOIN comments c ON p.post_id = c.post_id
                    LEFT JOIN reactions r ON r.target_type = 'post' AND r.target_id = p.post_id
                    WHERE p.status = 'approved'
                    GROUP BY p.post_id
                )
            """)
            
            avg_metrics = cursor.fetchone()
            
            # Content quality indicators
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_posts,
                    AVG(CASE WHEN sentiment_score > 0.1 THEN 1.0 ELSE 0.0 END) * 100 as positive_sentiment_rate,
                    AVG(CASE WHEN profanity_detected = 1 THEN 1.0 ELSE 0.0 END) * 100 as profanity_rate,
                    AVG(spam_score) * 100 as avg_spam_score
                FROM posts
                WHERE status = 'approved'
            """)
            
            quality_metrics = cursor.fetchone()
            
            # Comment engagement analysis
            cursor.execute("""
                SELECT 
                    AVG(likes) as avg_comment_likes,
                    AVG(dislikes) as avg_comment_dislikes,
                    COUNT(CASE WHEN parent_comment_id IS NOT NULL THEN 1 END) * 100.0 / COUNT(*) as reply_rate
                FROM comments
            """)
            
            comment_metrics = cursor.fetchone()
            
            return {
                'top_performing_posts': [
                    {
                        'post_id': row[0],
                        'category': row[1],
                        'timestamp': row[2],
                        'likes': row[3],
                        'comments': row[4],
                        'reactions': row[5],
                        'engagement_score': row[6]
                    }
                    for row in top_posts
                ],
                'average_metrics': {
                    'avg_likes': avg_metrics[0] or 0,
                    'avg_comments': avg_metrics[1] or 0,
                    'avg_reactions': avg_metrics[2] or 0
                },
                'content_quality': {
                    'total_posts': quality_metrics[0] or 0,
                    'positive_sentiment_rate': quality_metrics[1] or 0,
                    'profanity_rate': quality_metrics[2] or 0,
                    'avg_spam_score': quality_metrics[3] or 0
                },
                'comment_engagement': {
                    'avg_comment_likes': comment_metrics[0] or 0,
                    'avg_comment_dislikes': comment_metrics[1] or 0,
                    'reply_rate': comment_metrics[2] or 0
                }
            }
    
    @handle_database_errors
    def get_admin_performance_metrics(self, days_back: int = 30) -> Dict[str, Any]:
        """Analyze admin performance and moderation statistics"""
        start_date = (date.today() - timedelta(days=days_back)).strftime('%Y-%m-%d')
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Admin approval statistics
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_submissions,
                    COUNT(CASE WHEN status = 'approved' THEN 1 END) as approved_count,
                    COUNT(CASE WHEN status = 'rejected' THEN 1 END) as rejected_count,
                    COUNT(CASE WHEN status = 'pending' OR status IS NULL THEN 1 END) as pending_count,
                    AVG(julianday('now') - julianday(timestamp)) as avg_processing_time_days
                FROM posts
                WHERE DATE(timestamp) >= ?
            """, (start_date,))
            
            moderation_stats = cursor.fetchone()
            
            # Response times analysis
            cursor.execute("""
                SELECT 
                    AVG(julianday('now') - julianday(timestamp)) * 24 as avg_response_time_hours,
                    MIN(julianday('now') - julianday(timestamp)) * 24 as min_response_time_hours,
                    MAX(julianday('now') - julianday(timestamp)) * 24 as max_response_time_hours
                FROM posts
                WHERE status IS NOT NULL AND DATE(timestamp) >= ?
            """, (start_date,))
            
            response_times = cursor.fetchone()
            
            # Admin message handling
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_messages,
                    COUNT(CASE WHEN replied = 1 THEN 1 END) as replied_count,
                    AVG(CASE WHEN replied = 1 THEN julianday(timestamp) - julianday(timestamp) END) as avg_reply_time_days
                FROM admin_messages
                WHERE DATE(timestamp) >= ?
            """, (start_date,))
            
            message_stats = cursor.fetchone()
            
            total_submissions = moderation_stats[0] or 1
            approval_rate = (moderation_stats[1] / total_submissions * 100) if total_submissions > 0 else 0
            rejection_rate = (moderation_stats[2] / total_submissions * 100) if total_submissions > 0 else 0
            
            return {
                'moderation_statistics': {
                    'total_submissions': moderation_stats[0] or 0,
                    'approved': moderation_stats[1] or 0,
                    'rejected': moderation_stats[2] or 0,
                    'pending': moderation_stats[3] or 0,
                    'approval_rate': approval_rate,
                    'rejection_rate': rejection_rate,
                    'avg_processing_time_days': moderation_stats[4] or 0
                },
                'response_times': {
                    'avg_response_hours': response_times[0] or 0,
                    'min_response_hours': response_times[1] or 0,
                    'max_response_hours': response_times[2] or 0
                },
                'message_handling': {
                    'total_messages': message_stats[0] or 0,
                    'replied_count': message_stats[1] or 0,
                    'reply_rate': (message_stats[1] / max(message_stats[0], 1) * 100),
                    'avg_reply_time_days': message_stats[2] or 0
                },
                'analysis_period_days': days_back
            }
    
    def generate_comprehensive_report(self, days_back: int = 30) -> Dict[str, Any]:
        """Generate a comprehensive analytics report"""
        try:
            # Update daily stats first
            self.update_daily_stats()
            
            report = {
                'report_generated_at': datetime.now().isoformat(),
                'analysis_period_days': days_back,
                'weekly_trends': self.get_weekly_stats(),
                'category_analysis': self.get_category_analytics(days_back),
                'user_engagement': self.get_user_engagement_metrics(days_back),
                'content_performance': self.get_content_performance_metrics(),
                'admin_performance': self.get_admin_performance_metrics(days_back)
            }
            
            # Add executive summary
            report['executive_summary'] = self._generate_executive_summary(report)
            
            return report
            
        except Exception as e:
            logger.error(f"Failed to generate comprehensive report: {e}")
            return {'error': str(e)}
    
    def _generate_executive_summary(self, report_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate executive summary from report data"""
        summary = {}
        
        try:
            # Key metrics
            weekly_data = report_data.get('weekly_trends', {})
            if 'summary' in weekly_data:
                summary['avg_weekly_confessions'] = weekly_data['summary'].get('avg_weekly_confessions', 0)
                summary['avg_weekly_comments'] = weekly_data['summary'].get('avg_weekly_comments', 0)
            
            # Top category
            category_data = report_data.get('category_analysis', {})
            if 'category_stats' in category_data:
                top_category = max(
                    category_data['category_stats'].items(),
                    key=lambda x: x[1]['post_count'],
                    default=('Unknown', {'post_count': 0})
                )
                summary['top_category'] = top_category[0]
                summary['top_category_posts'] = top_category[1]['post_count']
            
            # User engagement
            engagement_data = report_data.get('user_engagement', {})
            if 'retention_rate' in engagement_data:
                summary['user_retention_rate'] = engagement_data['retention_rate']
                summary['total_active_users'] = engagement_data.get('active_users', 0)
            
            # Content performance
            content_data = report_data.get('content_performance', {})
            if 'average_metrics' in content_data:
                summary['avg_engagement_per_post'] = (
                    content_data['average_metrics'].get('avg_likes', 0) +
                    content_data['average_metrics'].get('avg_comments', 0) +
                    content_data['average_metrics'].get('avg_reactions', 0)
                )
            
            # Admin performance
            admin_data = report_data.get('admin_performance', {})
            if 'moderation_statistics' in admin_data:
                summary['approval_rate'] = admin_data['moderation_statistics'].get('approval_rate', 0)
                summary['avg_processing_time_hours'] = admin_data['moderation_statistics'].get('avg_processing_time_days', 0) * 24
            
        except Exception as e:
            logger.error(f"Failed to generate executive summary: {e}")
            summary['error'] = 'Failed to generate summary'
        
        return summary


# Global analytics manager
analytics_manager = AnalyticsManager()
