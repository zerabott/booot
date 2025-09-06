"""
Performance optimizations for the confession bot
"""

import sqlite3
import threading
import time
import asyncio
from typing import Dict, Any, Optional, Callable, List, Tuple
from functools import wraps, lru_cache
from datetime import datetime, timedelta
import json
import psutil
import gc
from contextlib import contextmanager

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

from config import (
    DB_PATH, REDIS_HOST, REDIS_PORT, REDIS_DB, REDIS_URL
)
from logger import get_logger

logger = get_logger('performance')


class DatabaseConnectionPool:
    """Database connection pool for better performance"""
    
    def __init__(self, database_path: str, pool_size: int = 10, timeout: float = 30.0):
        self.database_path = database_path
        self.pool_size = pool_size
        self.timeout = timeout
        self._pool = []
        self._used_connections = set()
        self._lock = threading.RLock()
        self._create_initial_connections()
    
    def _create_initial_connections(self):
        """Create initial connections in the pool"""
        with self._lock:
            for _ in range(self.pool_size):
                conn = self._create_connection()
                if conn:
                    self._pool.append(conn)
    
    def _create_connection(self) -> Optional[sqlite3.Connection]:
        """Create a new database connection"""
        try:
            conn = sqlite3.connect(
                self.database_path,
                timeout=self.timeout,
                check_same_thread=False,
                isolation_level=None  # Autocommit mode for better performance
            )
            
            # Enable WAL mode for better concurrent access
            conn.execute("PRAGMA journal_mode=WAL")
            
            # Optimize SQLite settings
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA cache_size=10000")  # 10MB cache
            conn.execute("PRAGMA temp_store=MEMORY")
            conn.execute("PRAGMA mmap_size=268435456")  # 256MB memory-mapped I/O
            
            return conn
        except Exception as e:
            logger.error(f"Failed to create database connection: {e}")
            return None
    
    @contextmanager
    def get_connection(self):
        """Get a connection from the pool"""
        conn = None
        try:
            with self._lock:
                if self._pool:
                    conn = self._pool.pop()
                    self._used_connections.add(conn)
                else:
                    # Create new connection if pool is empty
                    conn = self._create_connection()
                    if conn:
                        self._used_connections.add(conn)
            
            if not conn:
                raise Exception("Could not get database connection")
            
            yield conn
            
        finally:
            if conn:
                try:
                    # Reset connection state
                    conn.rollback()
                    
                    with self._lock:
                        self._used_connections.discard(conn)
                        if len(self._pool) < self.pool_size:
                            self._pool.append(conn)
                        else:
                            conn.close()
                            
                except Exception as e:
                    logger.error(f"Error returning connection to pool: {e}")
                    try:
                        conn.close()
                    except:
                        pass
    
    def close_all_connections(self):
        """Close all connections in the pool"""
        with self._lock:
            # Close pooled connections
            for conn in self._pool:
                try:
                    conn.close()
                except:
                    pass
            self._pool.clear()
            
            # Close used connections
            for conn in list(self._used_connections):
                try:
                    conn.close()
                except:
                    pass
            self._used_connections.clear()


class CacheManager:
    """Cache manager with Redis and in-memory fallback"""
    
    def __init__(self):
        self.redis_client = None
        self.in_memory_cache = {}
        self.cache_stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'deletes': 0
        }
        
        self._initialize_redis()
    
    def _initialize_redis(self):
        """Initialize Redis connection"""
        if not REDIS_AVAILABLE:
            logger.info("Redis not available, using in-memory cache")
            return
        
        try:
            self.redis_client = redis.from_url(
                REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True
            )
            
            # Test connection
            self.redis_client.ping()
            logger.info("Redis cache initialized successfully")
            
        except Exception as e:
            logger.warning(f"Redis initialization failed, using in-memory cache: {e}")
            self.redis_client = None
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        try:
            if self.redis_client:
                value = self.redis_client.get(f"confession_bot:{key}")
                if value is not None:
                    self.cache_stats['hits'] += 1
                    return json.loads(value)
                else:
                    self.cache_stats['misses'] += 1
                    return None
            else:
                # In-memory fallback
                if key in self.in_memory_cache:
                    entry = self.in_memory_cache[key]
                    if entry['expires'] > time.time():
                        self.cache_stats['hits'] += 1
                        return entry['value']
                    else:
                        del self.in_memory_cache[key]
                
                self.cache_stats['misses'] += 1
                return None
                
        except Exception as e:
            logger.error(f"Cache get error: {e}")
            self.cache_stats['misses'] += 1
            return None
    
    def set(self, key: str, value: Any, expire: int = 3600):
        """Set value in cache with expiration"""
        try:
            if self.redis_client:
                self.redis_client.setex(
                    f"confession_bot:{key}",
                    expire,
                    json.dumps(value, default=str)
                )
            else:
                # In-memory fallback
                self.in_memory_cache[key] = {
                    'value': value,
                    'expires': time.time() + expire
                }
                
                # Clean up expired entries if cache gets too large
                if len(self.in_memory_cache) > 1000:
                    self._cleanup_expired()
            
            self.cache_stats['sets'] += 1
            
        except Exception as e:
            logger.error(f"Cache set error: {e}")
    
    def delete(self, key: str):
        """Delete key from cache"""
        try:
            if self.redis_client:
                self.redis_client.delete(f"confession_bot:{key}")
            else:
                self.in_memory_cache.pop(key, None)
            
            self.cache_stats['deletes'] += 1
            
        except Exception as e:
            logger.error(f"Cache delete error: {e}")
    
    def delete_pattern(self, pattern: str):
        """Delete keys matching pattern"""
        try:
            if self.redis_client:
                keys = self.redis_client.keys(f"confession_bot:{pattern}")
                if keys:
                    self.redis_client.delete(*keys)
                    self.cache_stats['deletes'] += len(keys)
            else:
                # In-memory fallback - simple pattern matching
                import fnmatch
                keys_to_delete = [
                    key for key in self.in_memory_cache.keys()
                    if fnmatch.fnmatch(key, pattern)
                ]
                for key in keys_to_delete:
                    del self.in_memory_cache[key]
                    self.cache_stats['deletes'] += 1
                    
        except Exception as e:
            logger.error(f"Cache pattern delete error: {e}")
    
    def _cleanup_expired(self):
        """Clean up expired entries from in-memory cache"""
        current_time = time.time()
        expired_keys = [
            key for key, entry in self.in_memory_cache.items()
            if entry['expires'] <= current_time
        ]
        
        for key in expired_keys:
            del self.in_memory_cache[key]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total_ops = sum(self.cache_stats.values())
        hit_rate = (self.cache_stats['hits'] / max(self.cache_stats['hits'] + self.cache_stats['misses'], 1)) * 100
        
        stats = {
            **self.cache_stats,
            'hit_rate_percent': round(hit_rate, 2),
            'total_operations': total_ops,
            'cache_type': 'redis' if self.redis_client else 'in_memory',
            'in_memory_size': len(self.in_memory_cache) if not self.redis_client else 0
        }
        
        if self.redis_client:
            try:
                info = self.redis_client.info('memory')
                stats['redis_memory_usage'] = info.get('used_memory_human', 'Unknown')
            except:
                pass
        
        return stats


class QueryOptimizer:
    """Query optimization and caching layer"""
    
    def __init__(self, cache_manager: CacheManager):
        self.cache = cache_manager
        self.query_stats = {}
    
    def cached_query(self, cache_key: str, expire: int = 3600, 
                    invalidate_patterns: List[str] = None):
        """Decorator for caching database queries"""
        def decorator(func: Callable):
            @wraps(func)
            def wrapper(*args, **kwargs):
                # Generate cache key with arguments
                full_cache_key = f"{cache_key}_{hash(str(args) + str(sorted(kwargs.items())))}"
                
                # Try to get from cache first
                cached_result = self.cache.get(full_cache_key)
                if cached_result is not None:
                    return cached_result
                
                # Execute query and cache result
                start_time = time.time()
                result = func(*args, **kwargs)
                execution_time = time.time() - start_time
                
                # Track query performance
                query_name = func.__name__
                if query_name not in self.query_stats:
                    self.query_stats[query_name] = {
                        'total_calls': 0,
                        'total_time': 0,
                        'avg_time': 0,
                        'cache_hits': 0,
                        'cache_misses': 0
                    }
                
                self.query_stats[query_name]['total_calls'] += 1
                self.query_stats[query_name]['total_time'] += execution_time
                self.query_stats[query_name]['avg_time'] = (
                    self.query_stats[query_name]['total_time'] / 
                    self.query_stats[query_name]['total_calls']
                )
                self.query_stats[query_name]['cache_misses'] += 1
                
                # Cache the result
                self.cache.set(full_cache_key, result, expire)
                
                return result
            
            return wrapper
        return decorator
    
    def invalidate_cache_patterns(self, patterns: List[str]):
        """Invalidate cache entries matching patterns"""
        for pattern in patterns:
            self.cache.delete_pattern(pattern)
    
    def get_query_stats(self) -> Dict[str, Any]:
        """Get query performance statistics"""
        return self.query_stats


class PerformanceMonitor:
    """Monitor system and application performance"""
    
    def __init__(self):
        self.start_time = time.time()
        self.performance_data = {
            'request_count': 0,
            'total_response_time': 0,
            'peak_memory_usage': 0,
            'database_operations': 0,
            'cache_operations': 0
        }
    
    def record_request(self, response_time: float):
        """Record a request and its response time"""
        self.performance_data['request_count'] += 1
        self.performance_data['total_response_time'] += response_time
    
    def record_database_operation(self):
        """Record a database operation"""
        self.performance_data['database_operations'] += 1
    
    def record_cache_operation(self):
        """Record a cache operation"""
        self.performance_data['cache_operations'] += 1
    
    def get_system_metrics(self) -> Dict[str, Any]:
        """Get current system metrics"""
        try:
            # Memory usage
            memory = psutil.virtual_memory()
            process = psutil.Process()
            process_memory = process.memory_info()
            
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Disk usage
            disk = psutil.disk_usage('/')
            
            # Update peak memory usage
            current_memory = process_memory.rss
            if current_memory > self.performance_data['peak_memory_usage']:
                self.performance_data['peak_memory_usage'] = current_memory
            
            uptime = time.time() - self.start_time
            avg_response_time = (
                self.performance_data['total_response_time'] / 
                max(self.performance_data['request_count'], 1)
            )
            
            return {
                'uptime_seconds': int(uptime),
                'uptime_human': str(timedelta(seconds=int(uptime))),
                'system': {
                    'cpu_percent': cpu_percent,
                    'memory_total': memory.total,
                    'memory_used': memory.used,
                    'memory_percent': memory.percent,
                    'disk_total': disk.total,
                    'disk_used': disk.used,
                    'disk_percent': (disk.used / disk.total) * 100
                },
                'process': {
                    'memory_rss': process_memory.rss,
                    'memory_vms': process_memory.vms,
                    'memory_percent': process.memory_percent(),
                    'threads': process.num_threads(),
                    'peak_memory': self.performance_data['peak_memory_usage']
                },
                'application': {
                    'total_requests': self.performance_data['request_count'],
                    'avg_response_time': avg_response_time,
                    'database_operations': self.performance_data['database_operations'],
                    'cache_operations': self.performance_data['cache_operations']
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting system metrics: {e}")
            return {'error': str(e)}
    
    def performance_decorator(self, func: Callable):
        """Decorator to monitor function performance"""
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)
                return result
            finally:
                response_time = time.time() - start_time
                self.record_request(response_time)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                response_time = time.time() - start_time
                self.record_request(response_time)
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper


class DatabaseOptimizer:
    """Database optimization utilities"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
    
    def create_performance_indexes(self):
        """Create indexes for better query performance"""
        indexes = [
            # Posts table indexes
            "CREATE INDEX IF NOT EXISTS idx_posts_user_approved ON posts(user_id, approved)",
            "CREATE INDEX IF NOT EXISTS idx_posts_category_approved ON posts(category, approved)",
            "CREATE INDEX IF NOT EXISTS idx_posts_timestamp_approved ON posts(timestamp DESC, approved)",
            "CREATE INDEX IF NOT EXISTS idx_posts_flagged ON posts(flagged) WHERE flagged = 1",
            "CREATE INDEX IF NOT EXISTS idx_posts_sentiment ON posts(sentiment_score)",
            
            # Comments table indexes
            "CREATE INDEX IF NOT EXISTS idx_comments_post_timestamp ON comments(post_id, timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_comments_user_timestamp ON comments(user_id, timestamp DESC)",
            "CREATE INDEX IF NOT EXISTS idx_comments_parent_timestamp ON comments(parent_comment_id, timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_comments_likes_desc ON comments(likes DESC)",
            
            # Reactions table indexes
            "CREATE INDEX IF NOT EXISTS idx_reactions_user_target ON reactions(user_id, target_type, target_id)",
            "CREATE INDEX IF NOT EXISTS idx_reactions_target_type ON reactions(target_type, target_id, reaction_type)",
            "CREATE INDEX IF NOT EXISTS idx_reactions_timestamp ON reactions(timestamp DESC)",
            
            # Users table indexes
            "CREATE INDEX IF NOT EXISTS idx_users_join_date ON users(join_date DESC)",
            "CREATE INDEX IF NOT EXISTS idx_users_blocked ON users(blocked)",
            "CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)",
            
            # Admin messages indexes
            "CREATE INDEX IF NOT EXISTS idx_admin_messages_user_replied ON admin_messages(user_id, replied)",
            "CREATE INDEX IF NOT EXISTS idx_admin_messages_timestamp ON admin_messages(timestamp DESC)",
            
            # Reports table indexes
            "CREATE INDEX IF NOT EXISTS idx_reports_target ON reports(target_type, target_id)",
            "CREATE INDEX IF NOT EXISTS idx_reports_timestamp ON reports(timestamp DESC)",
            
            # User activity log indexes
            "CREATE INDEX IF NOT EXISTS idx_activity_user_type ON user_activity_log(user_id, activity_type)",
            "CREATE INDEX IF NOT EXISTS idx_activity_timestamp ON user_activity_log(timestamp DESC)",
            
            # Daily stats indexes
            "CREATE INDEX IF NOT EXISTS idx_daily_stats_date ON daily_stats(stat_date DESC)",
            
            # Notifications indexes
            "CREATE INDEX IF NOT EXISTS idx_notifications_user_read ON notifications(user_id, read)",
            "CREATE INDEX IF NOT EXISTS idx_notifications_timestamp ON notifications(created_at DESC)",
            
            # Moderation log indexes
            "CREATE INDEX IF NOT EXISTS idx_moderation_target ON moderation_log(target_type, target_id)",
            "CREATE INDEX IF NOT EXISTS idx_moderation_moderator ON moderation_log(moderator_id, timestamp DESC)"
        ]
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                for index_sql in indexes:
                    try:
                        cursor.execute(index_sql)
                        logger.debug(f"Created index: {index_sql}")
                    except sqlite3.OperationalError as e:
                        if "already exists" not in str(e):
                            logger.warning(f"Failed to create index: {e}")
                
                conn.commit()
                logger.info("Performance indexes created successfully")
                
        except Exception as e:
            logger.error(f"Failed to create performance indexes: {e}")
    
    def analyze_database(self) -> Dict[str, Any]:
        """Analyze database performance"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get database size
                cursor.execute("SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()")
                db_size = cursor.fetchone()[0]
                
                # Get table sizes
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]
                
                table_stats = {}
                total_rows = 0
                
                for table in tables:
                    try:
                        cursor.execute(f"SELECT COUNT(*) FROM {table}")
                        row_count = cursor.fetchone()[0]
                        total_rows += row_count
                        table_stats[table] = {
                            'row_count': row_count
                        }
                    except sqlite3.OperationalError:
                        continue
                
                # Get index information
                cursor.execute("""
                    SELECT name, sql FROM sqlite_master 
                    WHERE type='index' AND name NOT LIKE 'sqlite_%'
                """)
                indexes = cursor.fetchall()
                
                return {
                    'database_size_bytes': db_size,
                    'database_size_mb': round(db_size / (1024 * 1024), 2),
                    'total_rows': total_rows,
                    'table_count': len(tables),
                    'index_count': len(indexes),
                    'table_stats': table_stats,
                    'indexes': [{'name': idx[0], 'sql': idx[1]} for idx in indexes]
                }
                
        except Exception as e:
            logger.error(f"Database analysis failed: {e}")
            return {'error': str(e)}
    
    def vacuum_database(self):
        """Vacuum database to reclaim space and optimize"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("VACUUM")
                conn.execute("ANALYZE")
                logger.info("Database vacuumed and analyzed successfully")
        except Exception as e:
            logger.error(f"Database vacuum failed: {e}")


class MemoryManager:
    """Memory management utilities"""
    
    @staticmethod
    def cleanup_memory():
        """Force garbage collection and memory cleanup"""
        try:
            # Force garbage collection
            collected = gc.collect()
            
            # Get memory info before and after
            process = psutil.Process()
            memory_info = process.memory_info()
            
            logger.info(f"Garbage collection freed {collected} objects")
            logger.info(f"Current memory usage: {memory_info.rss / (1024*1024):.2f} MB")
            
            return {
                'objects_collected': collected,
                'memory_rss_mb': round(memory_info.rss / (1024*1024), 2),
                'memory_vms_mb': round(memory_info.vms / (1024*1024), 2)
            }
            
        except Exception as e:
            logger.error(f"Memory cleanup failed: {e}")
            return {'error': str(e)}
    
    @staticmethod
    def get_memory_usage() -> Dict[str, float]:
        """Get current memory usage statistics"""
        try:
            process = psutil.Process()
            memory_info = process.memory_info()
            
            return {
                'rss_mb': round(memory_info.rss / (1024*1024), 2),
                'vms_mb': round(memory_info.vms / (1024*1024), 2),
                'percent': round(process.memory_percent(), 2)
            }
        except Exception as e:
            logger.error(f"Failed to get memory usage: {e}")
            return {'error': str(e)}


# Global instances
db_pool = DatabaseConnectionPool(DB_PATH)
cache_manager = CacheManager()
query_optimizer = QueryOptimizer(cache_manager)
performance_monitor = PerformanceMonitor()
db_optimizer = DatabaseOptimizer(DB_PATH)


def initialize_performance_optimizations():
    """Initialize all performance optimizations"""
    try:
        logger.info("Initializing performance optimizations...")
        
        # Create performance indexes
        db_optimizer.create_performance_indexes()
        
        # Log initial system state
        metrics = performance_monitor.get_system_metrics()
        logger.info(f"Initial memory usage: {metrics['process']['memory_rss'] / (1024*1024):.2f} MB")
        
        logger.info("Performance optimizations initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize performance optimizations: {e}")


async def periodic_maintenance():
    """Run periodic maintenance tasks"""
    while True:
        try:
            await asyncio.sleep(3600)  # Run every hour
            
            # Cleanup memory
            MemoryManager.cleanup_memory()
            
            # Clean up expired cache entries
            if not cache_manager.redis_client:
                cache_manager._cleanup_expired()
            
            # Log performance metrics
            metrics = performance_monitor.get_system_metrics()
            logger.info(f"Hourly metrics - Memory: {metrics['process']['memory_rss'] / (1024*1024):.2f} MB, "
                       f"Requests: {metrics['application']['total_requests']}, "
                       f"Avg Response: {metrics['application']['avg_response_time']:.3f}s")
            
        except Exception as e:
            logger.error(f"Periodic maintenance error: {e}")


# Performance decorators for common use cases
def cached_db_query(cache_key: str, expire: int = 3600):
    """Decorator for caching database queries"""
    return query_optimizer.cached_query(cache_key, expire)


def monitor_performance(func: Callable):
    """Decorator to monitor function performance"""
    return performance_monitor.performance_decorator(func)


def with_db_connection(func: Callable):
    """Decorator to provide database connection from pool"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        with db_pool.get_connection() as conn:
            return func(conn, *args, **kwargs)
    return wrapper


# Utility functions
def get_performance_report() -> Dict[str, Any]:
    """Get comprehensive performance report"""
    return {
        'system_metrics': performance_monitor.get_system_metrics(),
        'cache_stats': cache_manager.get_stats(),
        'query_stats': query_optimizer.get_query_stats(),
        'database_analysis': db_optimizer.analyze_database(),
        'memory_usage': MemoryManager.get_memory_usage()
    }
