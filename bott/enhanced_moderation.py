"""
Enhanced content moderation system for the confession bot
"""

import sqlite3
import re
import json
import requests
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
import hashlib

try:
    from textblob import TextBlob
    TEXTBLOB_AVAILABLE = True
except ImportError:
    TEXTBLOB_AVAILABLE = False

from config import DB_PATH
from logger import get_logger
from error_handler import handle_database_errors

logger = get_logger('enhanced_moderation')


class ProfanityFilter:
    """Advanced profanity filtering system"""
    
    def __init__(self):
        # Common profanity words - this is a basic list, you should expand it
        self.profanity_words = {
            'mild': ['damn', 'hell', 'crap', 'stupid'],
            'moderate': ['ass', 'bitch', 'bastard', 'piss'],
            'severe': ['fuck', 'shit', 'motherfucker', 'asshole']
        }
        
        # Leetspeak and common substitutions
        self.substitutions = {
            '@': 'a', '3': 'e', '1': 'i', '0': 'o', '5': 's',
            '$': 's', '7': 't', '4': 'a', '!': 'i'
        }
        
        # Patterns for detecting masked profanity
        self.patterns = [
            r'f+[\*\-\_\s]*u+[\*\-\_\s]*c+[\*\-\_\s]*k',  # f*u*c*k variations
            r's+[\*\-\_\s]*h+[\*\-\_\s]*i+[\*\-\_\s]*t',  # s*h*i*t variations
            r'b+[\*\-\_\s]*i+[\*\-\_\s]*t+[\*\-\_\s]*c+[\*\-\_\s]*h',  # b*i*t*c*h variations
        ]
    
    def normalize_text(self, text: str) -> str:
        """Normalize text by removing special characters and applying substitutions"""
        text = text.lower()
        
        # Apply leetspeak substitutions
        for char, replacement in self.substitutions.items():
            text = text.replace(char, replacement)
        
        # Remove non-alphanumeric characters except spaces
        text = re.sub(r'[^a-z0-9\s]', '', text)
        
        return text
    
    def check_profanity(self, text: str) -> Dict[str, Any]:
        """Check text for profanity and return detailed results"""
        normalized_text = self.normalize_text(text)
        
        result = {
            'has_profanity': False,
            'severity_level': 'clean',
            'detected_words': [],
            'confidence': 0.0,
            'masked_profanity': False
        }
        
        # Check for exact word matches
        words = normalized_text.split()
        for word in words:
            for severity, word_list in self.profanity_words.items():
                if word in word_list:
                    result['has_profanity'] = True
                    result['detected_words'].append(word)
                    if severity == 'severe':
                        result['severity_level'] = 'severe'
                        result['confidence'] = 0.9
                    elif severity == 'moderate' and result['severity_level'] != 'severe':
                        result['severity_level'] = 'moderate'
                        result['confidence'] = 0.7
                    elif result['severity_level'] == 'clean':
                        result['severity_level'] = 'mild'
                        result['confidence'] = 0.5
        
        # Check for masked profanity patterns
        for pattern in self.patterns:
            if re.search(pattern, normalized_text):
                result['has_profanity'] = True
                result['masked_profanity'] = True
                result['severity_level'] = 'moderate'
                result['confidence'] = max(result['confidence'], 0.6)
        
        return result


class SentimentAnalyzer:
    """Sentiment analysis for posts and comments"""
    
    def __init__(self):
        self.textblob_available = TEXTBLOB_AVAILABLE
    
    def analyze_sentiment(self, text: str) -> Dict[str, Any]:
        """Analyze sentiment of text"""
        result = {
            'sentiment_score': 0.0,
            'sentiment_label': 'neutral',
            'confidence': 0.0,
            'subjectivity': 0.0
        }
        
        if not self.textblob_available:
            # Fallback: simple keyword-based sentiment analysis
            positive_words = ['good', 'great', 'awesome', 'happy', 'love', 'excellent', 'amazing', 'wonderful', 'fantastic']
            negative_words = ['bad', 'terrible', 'awful', 'hate', 'horrible', 'disgusting', 'worst', 'stupid', 'annoying']
            
            text_lower = text.lower()
            positive_count = sum(1 for word in positive_words if word in text_lower)
            negative_count = sum(1 for word in negative_words if word in text_lower)
            
            total_sentiment_words = positive_count + negative_count
            if total_sentiment_words > 0:
                sentiment_score = (positive_count - negative_count) / total_sentiment_words
                result['sentiment_score'] = sentiment_score
                result['confidence'] = min(total_sentiment_words / 5.0, 1.0)  # Max confidence with 5+ sentiment words
                
                if sentiment_score > 0.1:
                    result['sentiment_label'] = 'positive'
                elif sentiment_score < -0.1:
                    result['sentiment_label'] = 'negative'
                else:
                    result['sentiment_label'] = 'neutral'
        else:
            # Use TextBlob for more accurate sentiment analysis
            try:
                blob = TextBlob(text)
                sentiment_score = blob.sentiment.polarity
                subjectivity = blob.sentiment.subjectivity
                
                result['sentiment_score'] = sentiment_score
                result['subjectivity'] = subjectivity
                result['confidence'] = abs(sentiment_score)
                
                if sentiment_score > 0.1:
                    result['sentiment_label'] = 'positive'
                elif sentiment_score < -0.1:
                    result['sentiment_label'] = 'negative'
                else:
                    result['sentiment_label'] = 'neutral'
                    
            except Exception as e:
                logger.warning(f"TextBlob sentiment analysis failed: {e}")
        
        return result


class SpamDetector:
    """Detect spam and low-quality content"""
    
    def __init__(self):
        self.spam_indicators = [
            r'https?://[^\s]+',  # URLs
            r'\b\d{10,}\b',  # Long numbers (phone numbers)
            r'(buy|sell|cheap|discount|offer|deal)',  # Commercial terms
            r'(\$\d+|\d+\$)',  # Price mentions
        ]
        
        # Common spam phrases
        self.spam_phrases = [
            'click here', 'buy now', 'limited time', 'special offer',
            'make money', 'work from home', 'guaranteed', 'risk free'
        ]
    
    def calculate_spam_score(self, text: str) -> Dict[str, Any]:
        """Calculate spam probability for text"""
        text_lower = text.lower()
        spam_score = 0.0
        indicators_found = []
        
        # Check for URL patterns
        if re.search(self.spam_indicators[0], text):
            spam_score += 0.3
            indicators_found.append('contains_url')
        
        # Check for phone numbers
        if re.search(self.spam_indicators[1], text):
            spam_score += 0.2
            indicators_found.append('contains_phone')
        
        # Check for commercial terms
        if re.search(self.spam_indicators[2], text_lower):
            spam_score += 0.2
            indicators_found.append('commercial_terms')
        
        # Check for price mentions
        if re.search(self.spam_indicators[3], text):
            spam_score += 0.2
            indicators_found.append('price_mentions')
        
        # Check for spam phrases
        spam_phrase_count = 0
        for phrase in self.spam_phrases:
            if phrase in text_lower:
                spam_phrase_count += 1
                indicators_found.append(f'spam_phrase_{phrase.replace(" ", "_")}')
        
        spam_score += min(spam_phrase_count * 0.1, 0.3)
        
        # Check for excessive repetition
        words = text.split()
        if len(words) > 5:
            unique_words = set(words)
            repetition_ratio = 1 - (len(unique_words) / len(words))
            if repetition_ratio > 0.5:
                spam_score += 0.2
                indicators_found.append('excessive_repetition')
        
        # Check for excessive caps
        if len(text) > 10:
            caps_ratio = sum(1 for c in text if c.isupper()) / len(text)
            if caps_ratio > 0.5:
                spam_score += 0.1
                indicators_found.append('excessive_caps')
        
        # Normalize score to 0-1 range
        spam_score = min(spam_score, 1.0)
        
        return {
            'spam_score': spam_score,
            'is_spam': spam_score > 0.5,
            'indicators_found': indicators_found,
            'confidence': spam_score
        }


class ContentModerationSystem:
    """Comprehensive content moderation system"""
    
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.profanity_filter = ProfanityFilter()
        self.sentiment_analyzer = SentimentAnalyzer()
        self.spam_detector = SpamDetector()
        
        # Auto-moderation thresholds
        self.auto_reject_thresholds = {
            'profanity_severe': True,
            'spam_score': 0.8,
            'excessive_profanity': 3  # Number of profane words
        }
        
        self.auto_flag_thresholds = {
            'profanity_moderate': True,
            'spam_score': 0.5,
            'negative_sentiment': -0.7
        }
    
    @handle_database_errors
    def moderate_content(self, content: str, content_type: str = 'post', user_id: int = None) -> Dict[str, Any]:
        """Perform comprehensive content moderation"""
        
        # Run all moderation checks
        profanity_result = self.profanity_filter.check_profanity(content)
        sentiment_result = self.sentiment_analyzer.analyze_sentiment(content)
        spam_result = self.spam_detector.calculate_spam_score(content)
        
        # Determine moderation action
        moderation_action = self._determine_action(profanity_result, sentiment_result, spam_result)
        
        # Log moderation result
        moderation_result = {
            'content_type': content_type,
            'user_id': user_id,
            'profanity': profanity_result,
            'sentiment': sentiment_result,
            'spam': spam_result,
            'action': moderation_action,
            'timestamp': datetime.now().isoformat()
        }
        
        # Store moderation log
        self._log_moderation_result(moderation_result)
        
        return moderation_result
    
    def _determine_action(self, profanity_result: Dict, sentiment_result: Dict, spam_result: Dict) -> Dict[str, Any]:
        """Determine what action to take based on moderation results"""
        
        action = {
            'type': 'approve',  # approve, flag, reject
            'reason': [],
            'confidence': 0.0,
            'requires_manual_review': False
        }
        
        # Check for auto-reject conditions
        if profanity_result['severity_level'] == 'severe':
            action['type'] = 'reject'
            action['reason'].append('severe_profanity')
            action['confidence'] = 0.9
        
        elif spam_result['spam_score'] >= self.auto_reject_thresholds['spam_score']:
            action['type'] = 'reject'
            action['reason'].append('high_spam_score')
            action['confidence'] = spam_result['confidence']
        
        elif len(profanity_result['detected_words']) >= self.auto_reject_thresholds['excessive_profanity']:
            action['type'] = 'reject'
            action['reason'].append('excessive_profanity')
            action['confidence'] = 0.8
        
        # Check for auto-flag conditions
        elif profanity_result['severity_level'] == 'moderate':
            action['type'] = 'flag'
            action['reason'].append('moderate_profanity')
            action['requires_manual_review'] = True
            action['confidence'] = profanity_result['confidence']
        
        elif spam_result['spam_score'] >= self.auto_flag_thresholds['spam_score']:
            action['type'] = 'flag'
            action['reason'].append('potential_spam')
            action['requires_manual_review'] = True
            action['confidence'] = spam_result['confidence']
        
        elif sentiment_result['sentiment_score'] <= self.auto_flag_thresholds['negative_sentiment']:
            action['type'] = 'flag'
            action['reason'].append('highly_negative_sentiment')
            action['requires_manual_review'] = True
            action['confidence'] = sentiment_result['confidence']
        
        # Check for mild issues that might need attention
        elif profanity_result['severity_level'] == 'mild' or spam_result['spam_score'] > 0.2:
            action['requires_manual_review'] = True
            action['confidence'] = max(profanity_result['confidence'], spam_result['confidence'])
        
        return action
    
    @handle_database_errors
    def _log_moderation_result(self, result: Dict[str, Any]):
        """Log moderation results to database"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Create moderation_results table if it doesn't exist
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS moderation_results (
                    result_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content_type TEXT NOT NULL,
                    user_id INTEGER,
                    profanity_detected INTEGER DEFAULT 0,
                    profanity_severity TEXT DEFAULT 'clean',
                    sentiment_score REAL DEFAULT 0.0,
                    sentiment_label TEXT DEFAULT 'neutral',
                    spam_score REAL DEFAULT 0.0,
                    moderation_action TEXT NOT NULL,
                    action_reason TEXT,
                    confidence REAL DEFAULT 0.0,
                    requires_manual_review INTEGER DEFAULT 0,
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                    full_result TEXT
                )
            """)
            
            cursor.execute("""
                INSERT INTO moderation_results (
                    content_type, user_id, profanity_detected, profanity_severity,
                    sentiment_score, sentiment_label, spam_score, moderation_action,
                    action_reason, confidence, requires_manual_review, full_result
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                result['content_type'],
                result['user_id'],
                1 if result['profanity']['has_profanity'] else 0,
                result['profanity']['severity_level'],
                result['sentiment']['sentiment_score'],
                result['sentiment']['sentiment_label'],
                result['spam']['spam_score'],
                result['action']['type'],
                ', '.join(result['action']['reason']),
                result['action']['confidence'],
                1 if result['action']['requires_manual_review'] else 0,
                json.dumps(result)
            ))
            
            conn.commit()
    
    @handle_database_errors
    def get_moderation_stats(self, days_back: int = 30) -> Dict[str, Any]:
        """Get moderation statistics"""
        start_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Check if moderation_results table exists
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='moderation_results'
            """)
            
            if not cursor.fetchone():
                return {'error': 'No moderation data available'}
            
            # Overall moderation stats
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_moderated,
                    COUNT(CASE WHEN moderation_action = 'approve' THEN 1 END) as approved,
                    COUNT(CASE WHEN moderation_action = 'flag' THEN 1 END) as flagged,
                    COUNT(CASE WHEN moderation_action = 'reject' THEN 1 END) as rejected,
                    AVG(confidence) as avg_confidence,
                    COUNT(CASE WHEN profanity_detected = 1 THEN 1 END) as profanity_detected,
                    AVG(spam_score) as avg_spam_score,
                    COUNT(CASE WHEN requires_manual_review = 1 THEN 1 END) as needs_review
                FROM moderation_results
                WHERE DATE(timestamp) >= ?
            """, (start_date,))
            
            stats = cursor.fetchone()
            
            if not stats or stats[0] == 0:
                return {'error': 'No moderation data for the specified period'}
            
            # Profanity severity distribution
            cursor.execute("""
                SELECT profanity_severity, COUNT(*) as count
                FROM moderation_results
                WHERE DATE(timestamp) >= ? AND profanity_detected = 1
                GROUP BY profanity_severity
            """, (start_date,))
            
            profanity_severity = dict(cursor.fetchall())
            
            # Sentiment distribution
            cursor.execute("""
                SELECT sentiment_label, COUNT(*) as count, AVG(sentiment_score) as avg_score
                FROM moderation_results
                WHERE DATE(timestamp) >= ?
                GROUP BY sentiment_label
            """, (start_date,))
            
            sentiment_distribution = {
                row[0]: {'count': row[1], 'avg_score': row[2]}
                for row in cursor.fetchall()
            }
            
            return {
                'overview': {
                    'total_moderated': stats[0],
                    'approved': stats[1],
                    'flagged': stats[2],
                    'rejected': stats[3],
                    'avg_confidence': round(stats[4] or 0, 3),
                    'profanity_detected': stats[5],
                    'avg_spam_score': round(stats[6] or 0, 3),
                    'needs_manual_review': stats[7],
                },
                'profanity_severity': profanity_severity,
                'sentiment_distribution': sentiment_distribution,
                'analysis_period_days': days_back
            }
    
    @handle_database_errors
    def update_moderation_thresholds(self, new_thresholds: Dict[str, Any]):
        """Update auto-moderation thresholds"""
        if 'auto_reject' in new_thresholds:
            self.auto_reject_thresholds.update(new_thresholds['auto_reject'])
        
        if 'auto_flag' in new_thresholds:
            self.auto_flag_thresholds.update(new_thresholds['auto_flag'])
        
        logger.info("Moderation thresholds updated")
    
    def get_current_thresholds(self) -> Dict[str, Any]:
        """Get current moderation thresholds"""
        return {
            'auto_reject': self.auto_reject_thresholds,
            'auto_flag': self.auto_flag_thresholds
        }


# Global moderation system
moderation_system = ContentModerationSystem()


def moderate_post_content(content: str, user_id: int) -> Dict[str, Any]:
    """Helper function to moderate post content"""
    return moderation_system.moderate_content(content, 'post', user_id)


def moderate_comment_content(content: str, user_id: int) -> Dict[str, Any]:
    """Helper function to moderate comment content"""
    return moderation_system.moderate_content(content, 'comment', user_id)
