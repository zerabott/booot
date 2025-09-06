"""
Advanced content moderation system for the confession bot
"""

import re
import string
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from datetime import datetime
import sqlite3
import asyncio

try:
    from textblob import TextBlob
    from langdetect import detect, LangDetectError
    import nltk
    from profanity_check import predict, predict_prob
    ADVANCED_NLP_AVAILABLE = True
except ImportError:
    ADVANCED_NLP_AVAILABLE = False

from config import (
    PROFANITY_WORDS, SPAM_WORDS, SENTIMENT_THRESHOLDS, 
    ENABLE_SENTIMENT_ANALYSIS, ENABLE_PROFANITY_FILTER, DB_PATH
)
from logger import get_logger
from error_handler import handle_database_errors

logger = get_logger('content_moderation')


@dataclass
class ModerationResult:
    """Result of content moderation analysis"""
    is_safe: bool
    confidence_score: float
    flags: List[str]
    sentiment_score: float
    sentiment_label: str
    spam_score: float
    profanity_detected: bool
    language: str
    recommendations: List[str]


class ContentModerator:
    """Advanced content moderation system"""
    
    def __init__(self):
        self.spam_patterns = self._compile_spam_patterns()
        self.profanity_patterns = self._compile_profanity_patterns()
        self._initialize_nltk()
        
    def _initialize_nltk(self):
        """Initialize NLTK resources"""
        if ADVANCED_NLP_AVAILABLE:
            try:
                nltk.download('vader_lexicon', quiet=True)
                nltk.download('punkt', quiet=True)
                nltk.download('stopwords', quiet=True)
                from nltk.sentiment import SentimentIntensityAnalyzer
                self.sentiment_analyzer = SentimentIntensityAnalyzer()
            except Exception as e:
                logger.warning(f"Could not initialize NLTK: {e}")
                self.sentiment_analyzer = None
        else:
            self.sentiment_analyzer = None
    
    def _compile_spam_patterns(self) -> List[re.Pattern]:
        """Compile regex patterns for spam detection"""
        patterns = []
        
        # Basic spam patterns
        spam_indicators = [
            r'\b(free|win|winner|prize|lottery|inheritance)\b',
            r'\b(click here|buy now|act now|limited time)\b',
            r'\b(earn money|make money|quick cash)\b',
            r'\b(congratulations|selected|chosen)\b',
            r'\b(urgent|confidential|immediate)\b',
            r'\$\d+|\d+\$',  # Money amounts
            r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b',  # Credit card patterns
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',  # Email addresses
            r'\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b',  # Phone numbers
            r'https?://\S+|www\.\S+',  # URLs
        ]
        
        for pattern in spam_indicators:
            try:
                patterns.append(re.compile(pattern, re.IGNORECASE))
            except re.error as e:
                logger.warning(f"Invalid regex pattern: {pattern} - {e}")
        
        return patterns
    
    def _compile_profanity_patterns(self) -> List[re.Pattern]:
        """Compile regex patterns for profanity detection"""
        patterns = []
        
        for word in PROFANITY_WORDS:
            # Create variations with common character substitutions
            variations = [
                word,
                word.replace('o', '0'),
                word.replace('i', '1'),
                word.replace('e', '3'),
                word.replace('a', '@'),
                word.replace('s', '$'),
            ]
            
            for variation in variations:
                # Match word boundaries and account for spacing/punctuation
                pattern = r'\b' + re.escape(variation) + r'\b'
                try:
                    patterns.append(re.compile(pattern, re.IGNORECASE))
                except re.error:
                    continue
        
        return patterns
    
    def detect_language(self, text: str) -> str:
        """Detect the language of the text"""
        if not text or len(text.strip()) < 10:
            return 'unknown'
        
        try:
            if ADVANCED_NLP_AVAILABLE:
                return detect(text)
            else:
                # Simple heuristic: if it contains mostly ASCII, assume English
                ascii_chars = sum(1 for c in text if ord(c) < 128)
                if ascii_chars / len(text) > 0.8:
                    return 'en'
                return 'unknown'
        except (LangDetectError, Exception):
            return 'unknown'
    
    def analyze_sentiment(self, text: str) -> Tuple[float, str]:
        """Analyze sentiment of the text"""
        if not ENABLE_SENTIMENT_ANALYSIS or not text:
            return 0.0, 'neutral'
        
        try:
            if ADVANCED_NLP_AVAILABLE and self.sentiment_analyzer:
                # Use NLTK VADER sentiment analyzer
                scores = self.sentiment_analyzer.polarity_scores(text)
                compound_score = scores['compound']
                
                # Classify based on compound score
                if compound_score >= SENTIMENT_THRESHOLDS['positive']:
                    label = 'very_positive'
                elif compound_score >= SENTIMENT_THRESHOLDS['neutral']:
                    label = 'positive'
                elif compound_score <= SENTIMENT_THRESHOLDS['very_negative']:
                    label = 'very_negative'
                elif compound_score <= SENTIMENT_THRESHOLDS['negative']:
                    label = 'negative'
                else:
                    label = 'neutral'
                
                return compound_score, label
            
            elif ADVANCED_NLP_AVAILABLE:
                # Use TextBlob as fallback
                blob = TextBlob(text)
                polarity = blob.sentiment.polarity
                
                if polarity > 0.5:
                    label = 'very_positive'
                elif polarity > 0.1:
                    label = 'positive'
                elif polarity < -0.5:
                    label = 'very_negative'
                elif polarity < -0.1:
                    label = 'negative'
                else:
                    label = 'neutral'
                
                return polarity, label
            
            else:
                # Basic keyword-based sentiment analysis
                positive_words = ['good', 'great', 'excellent', 'amazing', 'love', 'happy', 'wonderful']
                negative_words = ['bad', 'terrible', 'awful', 'hate', 'sad', 'horrible', 'disgusting']
                
                text_lower = text.lower()
                positive_count = sum(1 for word in positive_words if word in text_lower)
                negative_count = sum(1 for word in negative_words if word in text_lower)
                
                total_words = len(text.split())
                if total_words == 0:
                    return 0.0, 'neutral'
                
                score = (positive_count - negative_count) / total_words
                
                if score > 0.1:
                    label = 'positive'
                elif score < -0.1:
                    label = 'negative'
                else:
                    label = 'neutral'
                
                return score, label
        
        except Exception as e:
            logger.error(f"Sentiment analysis failed: {e}")
            return 0.0, 'neutral'
    
    def detect_profanity(self, text: str) -> Tuple[bool, float]:
        """Detect profanity in text"""
        if not ENABLE_PROFANITY_FILTER or not text:
            return False, 0.0
        
        try:
            # Use profanity-check library if available
            if ADVANCED_NLP_AVAILABLE:
                try:
                    is_profane = predict([text])[0] == 1
                    confidence = predict_prob([text])[0]
                    
                    if is_profane:
                        return True, confidence
                except Exception:
                    pass
            
            # Fallback to pattern matching
            text_clean = re.sub(r'[^a-zA-Z0-9\s]', '', text.lower())
            
            profanity_count = 0
            for pattern in self.profanity_patterns:
                matches = pattern.findall(text_clean)
                profanity_count += len(matches)
            
            if profanity_count > 0:
                # Calculate confidence based on frequency
                words = text_clean.split()
                confidence = min(profanity_count / max(len(words), 1) * 2, 1.0)
                return True, confidence
            
            return False, 0.0
        
        except Exception as e:
            logger.error(f"Profanity detection failed: {e}")
            return False, 0.0
    
    def calculate_spam_score(self, text: str) -> float:
        """Calculate spam score for text"""
        if not text:
            return 0.0
        
        try:
            spam_indicators = 0
            text_length = len(text.split())
            
            # Check against spam patterns
            for pattern in self.spam_patterns:
                matches = pattern.findall(text)
                spam_indicators += len(matches)
            
            # Additional spam indicators
            indicators = [
                len(re.findall(r'[!]{2,}', text)),  # Multiple exclamation marks
                len(re.findall(r'[?]{2,}', text)),  # Multiple question marks
                len(re.findall(r'[A-Z]{3,}', text)),  # Excessive caps
                len(re.findall(r'\d+', text)) * 0.5,  # Numbers (moderate weight)
                text.count('$') * 2,  # Dollar signs
                text.count('%') * 1.5,  # Percentage signs
            ]
            
            spam_indicators += sum(indicators)
            
            # Check for excessive repetition
            words = text.lower().split()
            unique_words = set(words)
            if len(words) > 0:
                repetition_ratio = 1 - (len(unique_words) / len(words))
                spam_indicators += repetition_ratio * 3
            
            # Normalize score
            if text_length > 0:
                spam_score = min(spam_indicators / text_length, 1.0)
            else:
                spam_score = 0.0
            
            return spam_score
        
        except Exception as e:
            logger.error(f"Spam score calculation failed: {e}")
            return 0.0
    
    def check_length_limits(self, text: str, max_length: int) -> Tuple[bool, str]:
        """Check if text meets length requirements"""
        if not text or len(text.strip()) < 10:
            return False, "Content too short (minimum 10 characters)"
        
        if len(text) > max_length:
            return False, f"Content too long (maximum {max_length} characters)"
        
        return True, ""
    
    def check_content_quality(self, text: str) -> Tuple[bool, List[str]]:
        """Check overall content quality"""
        issues = []
        
        if not text or not text.strip():
            return False, ["Empty content"]
        
        # Check for excessive whitespace
        if len(text) - len(text.strip()) > len(text) * 0.3:
            issues.append("Excessive whitespace")
        
        # Check for excessive repetition
        words = text.lower().split()
        if len(words) > 5:
            unique_words = set(words)
            repetition_ratio = 1 - (len(unique_words) / len(words))
            if repetition_ratio > 0.7:
                issues.append("Excessive repetition")
        
        # Check for coherent sentences
        sentences = re.split(r'[.!?]+', text)
        valid_sentences = [s.strip() for s in sentences if len(s.strip().split()) >= 3]
        
        if len(valid_sentences) == 0 and len(words) > 10:
            issues.append("No coherent sentences detected")
        
        # Check for excessive punctuation
        punct_count = sum(1 for c in text if c in string.punctuation)
        if punct_count > len(text) * 0.3:
            issues.append("Excessive punctuation")
        
        return len(issues) == 0, issues
    
    def moderate_content(self, text: str, content_type: str = "confession", max_length: int = 4000) -> ModerationResult:
        """Comprehensive content moderation"""
        flags = []
        recommendations = []
        
        # Basic validation
        length_ok, length_error = self.check_length_limits(text, max_length)
        if not length_ok:
            flags.append("length_violation")
            recommendations.append(length_error)
        
        # Quality check
        quality_ok, quality_issues = self.check_content_quality(text)
        if not quality_ok:
            flags.extend([f"quality_{issue.lower().replace(' ', '_')}" for issue in quality_issues])
            recommendations.extend(quality_issues)
        
        # Language detection
        language = self.detect_language(text)
        
        # Sentiment analysis
        sentiment_score, sentiment_label = self.analyze_sentiment(text)
        
        # Profanity detection
        profanity_detected, profanity_confidence = self.detect_profanity(text)
        if profanity_detected:
            flags.append("profanity_detected")
            recommendations.append(f"Profanity detected (confidence: {profanity_confidence:.2f})")
        
        # Spam detection
        spam_score = self.calculate_spam_score(text)
        if spam_score > 0.5:
            flags.append("high_spam_score")
            recommendations.append(f"High spam score: {spam_score:.2f}")
        elif spam_score > 0.3:
            flags.append("moderate_spam_score")
            recommendations.append(f"Moderate spam score: {spam_score:.2f}")
        
        # Very negative content warning
        if sentiment_score < SENTIMENT_THRESHOLDS['very_negative']:
            flags.append("very_negative_content")
            recommendations.append("Content has very negative sentiment - may need review")
        
        # Calculate overall safety score
        safety_factors = [
            1.0 if length_ok else 0.0,
            1.0 if quality_ok else 0.3,
            1.0 if not profanity_detected else (1.0 - profanity_confidence),
            1.0 if spam_score < 0.3 else (1.0 - spam_score),
            1.0 if sentiment_score > SENTIMENT_THRESHOLDS['very_negative'] else 0.5
        ]
        
        confidence_score = sum(safety_factors) / len(safety_factors)
        is_safe = confidence_score > 0.7 and len([f for f in flags if f in ['profanity_detected', 'high_spam_score', 'length_violation']]) == 0
        
        return ModerationResult(
            is_safe=is_safe,
            confidence_score=confidence_score,
            flags=flags,
            sentiment_score=sentiment_score,
            sentiment_label=sentiment_label,
            spam_score=spam_score,
            profanity_detected=profanity_detected,
            language=language,
            recommendations=recommendations
        )
    
    @handle_database_errors
    def log_moderation_result(self, content_id: int, content_type: str, moderator_id: int, result: ModerationResult, action: str, reason: str = ""):
        """Log moderation result to database"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            # Update content with moderation results
            if content_type == "post":
                cursor.execute("""
                    UPDATE posts SET 
                        sentiment_score = ?, sentiment_label = ?,
                        profanity_detected = ?, spam_score = ?
                    WHERE post_id = ?
                """, (result.sentiment_score, result.sentiment_label, 
                      1 if result.profanity_detected else 0, result.spam_score, content_id))
            
            elif content_type == "comment":
                cursor.execute("""
                    UPDATE comments SET 
                        sentiment_score = ?, sentiment_label = ?,
                        profanity_detected = ?, spam_score = ?
                    WHERE comment_id = ?
                """, (result.sentiment_score, result.sentiment_label, 
                      1 if result.profanity_detected else 0, result.spam_score, content_id))
            
            # Log moderation action
            cursor.execute("""
                INSERT INTO moderation_log (
                    moderator_id, target_type, target_id, action, reason
                ) VALUES (?, ?, ?, ?, ?)
            """, (moderator_id, content_type, content_id, action, reason))
            
            conn.commit()


class AutoModerator:
    """Automated moderation system"""
    
    def __init__(self):
        self.moderator = ContentModerator()
    
    def should_auto_approve(self, result: ModerationResult) -> bool:
        """Determine if content should be auto-approved"""
        if not result.is_safe:
            return False
        
        # High confidence, no serious flags
        serious_flags = ['profanity_detected', 'high_spam_score', 'very_negative_content', 'length_violation']
        has_serious_flags = any(flag in result.flags for flag in serious_flags)
        
        return result.confidence_score > 0.85 and not has_serious_flags
    
    def should_auto_reject(self, result: ModerationResult) -> bool:
        """Determine if content should be auto-rejected"""
        critical_flags = ['profanity_detected', 'high_spam_score', 'length_violation']
        has_critical_flags = any(flag in result.flags for flag in critical_flags)
        
        return (
            has_critical_flags or 
            result.confidence_score < 0.3 or
            result.spam_score > 0.8 or
            len(result.flags) >= 4
        )
    
    def get_moderation_priority(self, result: ModerationResult) -> str:
        """Get moderation priority level"""
        if self.should_auto_reject(result):
            return "high"  # Needs immediate attention
        elif result.profanity_detected or result.spam_score > 0.5:
            return "high"
        elif result.sentiment_score < SENTIMENT_THRESHOLDS['very_negative']:
            return "medium"  # Potential mental health concern
        elif not result.is_safe or result.confidence_score < 0.6:
            return "medium"
        else:
            return "low"


# Global instances
content_moderator = ContentModerator()
auto_moderator = AutoModerator()


def moderate_confession(text: str, max_length: int = 4000) -> ModerationResult:
    """Moderate a confession submission"""
    return content_moderator.moderate_content(text, "confession", max_length)


def moderate_comment(text: str, max_length: int = 500) -> ModerationResult:
    """Moderate a comment submission"""
    return content_moderator.moderate_content(text, "comment", max_length)


def get_auto_moderation_decision(result: ModerationResult) -> Tuple[str, str]:
    """Get automated moderation decision"""
    if auto_moderator.should_auto_approve(result):
        return "approve", "Auto-approved: High quality content with no issues detected"
    elif auto_moderator.should_auto_reject(result):
        reasons = ", ".join(result.recommendations[:3])  # Top 3 reasons
        return "reject", f"Auto-rejected: {reasons}"
    else:
        priority = auto_moderator.get_moderation_priority(result)
        return "review", f"Manual review required (Priority: {priority})"
