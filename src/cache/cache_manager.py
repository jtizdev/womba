"""
Intelligent caching layer for Womba.
Caches Jira issues, Confluence pages, and RAG embeddings to improve performance.
"""

import hashlib
import json
import time
from typing import Any, Callable, Dict, Optional
from functools import wraps

from loguru import logger


class CacheManager:
    """
    Memory-based caching manager with TTL support.
    Can be extended to use Redis for distributed caching.
    """
    
    def __init__(self, use_redis: bool = False, redis_url: Optional[str] = None):
        """
        Initialize cache manager.
        
        Args:
            use_redis: Use Redis for caching (default: False, uses memory)
            redis_url: Redis connection URL (default: redis://localhost:6379)
        """
        self.use_redis = use_redis
        self.memory_cache: Dict[str, Dict[str, Any]] = {}
        self.cache_hits = 0
        self.cache_misses = 0
        
        if use_redis:
            try:
                import redis
                self.redis_client = redis.from_url(redis_url or "redis://localhost:6379")
                logger.info("Connected to Redis cache")
            except ImportError:
                logger.warning("Redis not installed, falling back to memory cache")
                self.use_redis = False
                self.redis_client = None
            except Exception as e:
                logger.warning(f"Failed to connect to Redis: {e}, using memory cache")
                self.use_redis = False
                self.redis_client = None
        else:
            self.redis_client = None
            logger.info("Using in-memory cache")
    
    def _generate_key(self, prefix: str, *args, **kwargs) -> str:
        """
        Generate cache key from function arguments.
        
        Args:
            prefix: Cache key prefix (e.g., 'jira', 'confluence')
            *args: Positional arguments
            **kwargs: Keyword arguments
            
        Returns:
            Cache key string
        """
        # Create deterministic key from arguments
        key_data = f"{prefix}:{args}:{sorted(kwargs.items())}"
        key_hash = hashlib.md5(key_data.encode()).hexdigest()
        return f"{prefix}:{key_hash}"
    
    def _is_expired(self, cached_data: Dict) -> bool:
        """Check if cached data is expired."""
        if 'expires_at' not in cached_data:
            return True
        return time.time() > cached_data['expires_at']
    
    def _get_from_memory(self, key: str) -> Optional[Any]:
        """Get data from memory cache."""
        if key in self.memory_cache:
            cached = self.memory_cache[key]
            if not self._is_expired(cached):
                self.cache_hits += 1
                return cached['value']
            else:
                # Remove expired entry
                del self.memory_cache[key]
        self.cache_misses += 1
        return None
    
    def _set_to_memory(self, key: str, value: Any, ttl: int):
        """Set data in memory cache."""
        self.memory_cache[key] = {
            'value': value,
            'expires_at': time.time() + ttl,
            'created_at': time.time()
        }
    
    def _get_from_redis(self, key: str) -> Optional[Any]:
        """Get data from Redis cache."""
        try:
            cached = self.redis_client.get(key)
            if cached:
                self.cache_hits += 1
                return json.loads(cached)
            self.cache_misses += 1
            return None
        except Exception as e:
            logger.warning(f"Redis get error: {e}")
            return None
    
    def _set_to_redis(self, key: str, value: Any, ttl: int):
        """Set data in Redis cache."""
        try:
            self.redis_client.setex(
                key,
                ttl,
                json.dumps(value, default=str)  # default=str handles datetime, etc.
            )
        except Exception as e:
            logger.warning(f"Redis set error: {e}")
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found/expired
        """
        if self.use_redis:
            return self._get_from_redis(key)
        return self._get_from_memory(key)
    
    def set(self, key: str, value: Any, ttl: int = 300):
        """
        Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (default: 300 = 5 minutes)
        """
        if self.use_redis:
            self._set_to_redis(key, value, ttl)
        else:
            self._set_to_memory(key, value, ttl)
    
    async def get_or_fetch(
        self,
        key: str,
        fetch_func: Callable,
        ttl: int = 300
    ) -> Any:
        """
        Get value from cache or fetch it using the provided function.
        
        Args:
            key: Cache key
            fetch_func: Async function to call if cache miss
            ttl: Time to live in seconds
            
        Returns:
            Cached or fetched value
        """
        # Check cache first
        cached = self.get(key)
        if cached is not None:
            logger.debug(f"Cache HIT: {key}")
            return cached
        
        # Cache miss - fetch the data
        logger.debug(f"Cache MISS: {key}")
        result = await fetch_func()
        
        # Cache the result
        if result is not None:
            self.set(key, result, ttl)
        
        return result
    
    def clear(self):
        """Clear all cached data."""
        if self.use_redis:
            try:
                self.redis_client.flushdb()
                logger.info("Redis cache cleared")
            except Exception as e:
                logger.error(f"Failed to clear Redis cache: {e}")
        else:
            self.memory_cache.clear()
            logger.info("Memory cache cleared")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache stats
        """
        total_requests = self.cache_hits + self.cache_misses
        hit_rate = (self.cache_hits / total_requests * 100) if total_requests > 0 else 0
        
        stats = {
            'cache_hits': self.cache_hits,
            'cache_misses': self.cache_misses,
            'total_requests': total_requests,
            'hit_rate_percent': round(hit_rate, 2),
            'cache_type': 'redis' if self.use_redis else 'memory',
            'cache_size': len(self.memory_cache) if not self.use_redis else 'N/A'
        }
        
        return stats
    
    def print_stats(self):
        """Print cache statistics to console."""
        stats = self.get_stats()
        logger.info(f"Cache Stats: {stats}")


# Global cache instance (singleton pattern)
_cache_instance: Optional[CacheManager] = None


def get_cache() -> CacheManager:
    """
    Get global cache instance (singleton).
    
    Returns:
        CacheManager instance
    """
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = CacheManager()
    return _cache_instance


def cached(prefix: str, ttl: int = 300):
    """
    Decorator for caching async function results.
    
    Usage:
        @cached('jira', ttl=300)
        async def get_issue(issue_key):
            return await fetch_from_jira(issue_key)
    
    Args:
        prefix: Cache key prefix
        ttl: Time to live in seconds
        
    Returns:
        Decorated function
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache = get_cache()
            
            # Generate cache key
            key = cache._generate_key(prefix, *args, **kwargs)
            
            # Try to get from cache
            cached_result = cache.get(key)
            if cached_result is not None:
                logger.debug(f"Cache HIT: {func.__name__}({args}, {kwargs})")
                return cached_result
            
            # Cache miss - call function
            logger.debug(f"Cache MISS: {func.__name__}({args}, {kwargs})")
            result = await func(*args, **kwargs)
            
            # Cache the result
            if result is not None:
                cache.set(key, result, ttl)
            
            return result
        
        return wrapper
    return decorator

