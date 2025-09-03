"""
Intelligent caching system for oaDeviceAPI.

This module provides a flexible caching layer with TTL support,
cache invalidation, and performance monitoring for service health data.
"""

import asyncio
import time
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Callable, TypeVar, Generic, Union
from datetime import datetime, timezone, timedelta
from functools import wraps
from threading import RLock

from .config_schema import AppConfig
from .exceptions import SystemError, ErrorSeverity

T = TypeVar('T')
logger = logging.getLogger(__name__)


class CacheEntry(Generic[T]):
    """Represents a cached entry with metadata."""
    
    def __init__(
        self,
        value: T,
        ttl: int,
        created_at: Optional[datetime] = None
    ):
        self.value = value
        self.ttl = ttl
        self.created_at = created_at or datetime.now(timezone.utc)
        self.access_count = 0
        self.last_accessed = self.created_at
    
    def is_expired(self) -> bool:
        """Check if the cache entry has expired."""
        if self.ttl <= 0:  # TTL of 0 or negative means no expiration
            return False
        
        expiry_time = self.created_at + timedelta(seconds=self.ttl)
        return datetime.now(timezone.utc) > expiry_time
    
    def access(self) -> T:
        """Access the cached value and update metadata."""
        self.access_count += 1
        self.last_accessed = datetime.now(timezone.utc)
        return self.value
    
    def age_seconds(self) -> float:
        """Get the age of the cache entry in seconds."""
        return (datetime.now(timezone.utc) - self.created_at).total_seconds()


class CacheBackend(ABC, Generic[T]):
    """Abstract base class for cache backends."""
    
    @abstractmethod
    async def get(self, key: str) -> Optional[CacheEntry[T]]:
        """Get a value from the cache."""
        pass
    
    @abstractmethod
    async def set(self, key: str, entry: CacheEntry[T]) -> None:
        """Set a value in the cache."""
        pass
    
    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete a value from the cache."""
        pass
    
    @abstractmethod
    async def clear(self) -> None:
        """Clear all values from the cache."""
        pass
    
    @abstractmethod
    async def keys(self) -> list[str]:
        """Get all keys in the cache."""
        pass
    
    @abstractmethod
    def size(self) -> int:
        """Get the current size of the cache."""
        pass


class MemoryCacheBackend(CacheBackend[T]):
    """In-memory cache backend with LRU eviction."""
    
    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self._cache: Dict[str, CacheEntry[T]] = {}
        self._lock = RLock()
    
    async def get(self, key: str) -> Optional[CacheEntry[T]]:
        """Get a value from the memory cache."""
        with self._lock:
            entry = self._cache.get(key)
            if entry and not entry.is_expired():
                return entry
            elif entry and entry.is_expired():
                # Remove expired entry
                del self._cache[key]
            return None
    
    async def set(self, key: str, entry: CacheEntry[T]) -> None:
        """Set a value in the memory cache."""
        with self._lock:
            # Evict if at capacity
            if len(self._cache) >= self.max_size and key not in self._cache:
                self._evict_lru()
            
            self._cache[key] = entry
    
    async def delete(self, key: str) -> bool:
        """Delete a value from the memory cache."""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False
    
    async def clear(self) -> None:
        """Clear all values from the memory cache."""
        with self._lock:
            self._cache.clear()
    
    async def keys(self) -> list[str]:
        """Get all keys in the memory cache."""
        with self._lock:
            return list(self._cache.keys())
    
    def size(self) -> int:
        """Get the current size of the memory cache."""
        return len(self._cache)
    
    def _evict_lru(self) -> None:
        """Evict the least recently used entry."""
        if not self._cache:
            return
        
        # Find the entry with the oldest access time
        lru_key = min(
            self._cache.keys(),
            key=lambda k: self._cache[k].last_accessed
        )
        del self._cache[lru_key]
        
        logger.debug(f"Evicted LRU cache entry: {lru_key}")


class CacheManager:
    """
    High-level cache manager with intelligent caching strategies.
    
    Provides decorated caching, cache warming, and performance monitoring.
    """
    
    def __init__(self, config: AppConfig):
        self.config = config
        self.backend = MemoryCacheBackend[Any](max_size=config.cache.max_cache_size)
        self._stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'deletes': 0,
            'evictions': 0
        }
        logger.info(f"Cache manager initialized with max size: {config.cache.max_cache_size}")
    
    async def get(
        self,
        key: str,
        default: Optional[T] = None
    ) -> Optional[T]:
        """Get a value from the cache."""
        try:
            entry = await self.backend.get(key)
            if entry:
                self._stats['hits'] += 1
                logger.debug(f"Cache hit: {key} (age: {entry.age_seconds():.1f}s)")
                return entry.access()
            else:
                self._stats['misses'] += 1
                logger.debug(f"Cache miss: {key}")
                return default
        except Exception as exc:
            logger.error(f"Cache get error for key {key}: {exc}")
            return default
    
    async def set(
        self,
        key: str,
        value: T,
        ttl: Optional[int] = None
    ) -> None:
        """Set a value in the cache."""
        try:
            cache_ttl = ttl or self.config.cache.default_ttl
            entry = CacheEntry(value, cache_ttl)
            await self.backend.set(key, entry)
            self._stats['sets'] += 1
            logger.debug(f"Cache set: {key} (TTL: {cache_ttl}s)")
        except Exception as exc:
            logger.error(f"Cache set error for key {key}: {exc}")
    
    async def delete(self, key: str) -> bool:
        """Delete a value from the cache."""
        try:
            result = await self.backend.delete(key)
            if result:
                self._stats['deletes'] += 1
                logger.debug(f"Cache delete: {key}")
            return result
        except Exception as exc:
            logger.error(f"Cache delete error for key {key}: {exc}")
            return False
    
    async def clear(self) -> None:
        """Clear all cached values."""
        try:
            await self.backend.clear()
            logger.info("Cache cleared")
        except Exception as exc:
            logger.error(f"Cache clear error: {exc}")
    
    def cache_with_ttl(
        self,
        key_func: Optional[Callable[..., str]] = None,
        ttl: Optional[int] = None,
        cache_type: str = "default"
    ):
        """
        Decorator for caching function results with TTL.
        
        Args:
            key_func: Function to generate cache key from function args
            ttl: Time-to-live for cached result
            cache_type: Type of cache for specialized TTL lookup
        """
        def decorator(func: Callable[..., T]) -> Callable[..., T]:
            
            if asyncio.iscoroutinefunction(func):
                @wraps(func)
                async def async_wrapper(*args, **kwargs) -> T:
                    # Generate cache key
                    if key_func:
                        cache_key = key_func(*args, **kwargs)
                    else:
                        cache_key = self._generate_default_key(func.__name__, *args, **kwargs)
                    
                    # Check cache
                    cached_result = await self.get(cache_key)
                    if cached_result is not None:
                        return cached_result
                    
                    # Execute function and cache result
                    start_time = time.perf_counter()
                    try:
                        result = await func(*args, **kwargs)
                        execution_time = (time.perf_counter() - start_time) * 1000
                        
                        # Determine TTL
                        cache_ttl = ttl or self.config.get_cache_ttl(cache_type)
                        
                        # Cache the result
                        await self.set(cache_key, result, cache_ttl)
                        
                        logger.debug(
                            f"Function cached: {func.__name__} ({execution_time:.2f}ms)",
                            extra={
                                "function": func.__name__,
                                "cache_key": cache_key,
                                "ttl": cache_ttl,
                                "execution_time_ms": execution_time
                            }
                        )
                        
                        return result
                        
                    except Exception as exc:
                        execution_time = (time.perf_counter() - start_time) * 1000
                        logger.warning(
                            f"Function failed, not cached: {func.__name__} ({execution_time:.2f}ms)",
                            extra={
                                "function": func.__name__,
                                "error": str(exc),
                                "execution_time_ms": execution_time
                            }
                        )
                        raise
                
                return async_wrapper
            else:
                @wraps(func)
                def sync_wrapper(*args, **kwargs) -> T:
                    # For sync functions, we'll need to run the async cache operations
                    # This is a simplified implementation
                    import inspect
                    
                    # Generate cache key
                    if key_func:
                        cache_key = key_func(*args, **kwargs)
                    else:
                        cache_key = self._generate_default_key(func.__name__, *args, **kwargs)
                    
                    # This is a simplified sync implementation
                    # In a real scenario, you'd want to use asyncio.run or similar
                    try:
                        loop = asyncio.get_event_loop()
                    except RuntimeError:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                    
                    # Check cache (simplified)
                    cached_result = loop.run_until_complete(self.get(cache_key))
                    if cached_result is not None:
                        return cached_result
                    
                    # Execute function and cache result
                    start_time = time.perf_counter()
                    try:
                        result = func(*args, **kwargs)
                        execution_time = (time.perf_counter() - start_time) * 1000
                        
                        # Cache the result
                        cache_ttl = ttl or self.config.get_cache_ttl(cache_type)
                        loop.run_until_complete(self.set(cache_key, result, cache_ttl))
                        
                        return result
                        
                    except Exception as exc:
                        logger.warning(f"Function failed, not cached: {func.__name__}")
                        raise
                
                return sync_wrapper
        
        return decorator
    
    def _generate_default_key(self, func_name: str, *args, **kwargs) -> str:
        """Generate a default cache key from function name and arguments."""
        import hashlib
        
        # Create a string representation of arguments
        arg_str = f"{func_name}:{args}:{sorted(kwargs.items())}"
        
        # Hash it to create a consistent key
        return hashlib.md5(arg_str.encode()).hexdigest()
    
    async def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate all cache entries matching a pattern."""
        import fnmatch
        
        try:
            keys = await self.backend.keys()
            matching_keys = [key for key in keys if fnmatch.fnmatch(key, pattern)]
            
            count = 0
            for key in matching_keys:
                if await self.delete(key):
                    count += 1
            
            if count > 0:
                logger.info(f"Invalidated {count} cache entries matching pattern: {pattern}")
            
            return count
        except Exception as exc:
            logger.error(f"Pattern invalidation error for {pattern}: {exc}")
            return 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_requests = self._stats['hits'] + self._stats['misses']
        hit_rate = (self._stats['hits'] / total_requests * 100) if total_requests > 0 else 0
        
        return {
            'hits': self._stats['hits'],
            'misses': self._stats['misses'],
            'hit_rate_percent': round(hit_rate, 2),
            'sets': self._stats['sets'],
            'deletes': self._stats['deletes'],
            'evictions': self._stats['evictions'],
            'current_size': self.backend.size(),
            'max_size': self.config.cache.max_cache_size,
            'enabled': self.config.cache.enable_caching
        }
    
    async def warm_cache(
        self,
        warm_functions: list[Callable],
        warm_args: Optional[list] = None
    ) -> None:
        """Warm the cache by pre-executing specified functions."""
        logger.info(f"Starting cache warming for {len(warm_functions)} functions")
        
        for i, func in enumerate(warm_functions):
            try:
                args = warm_args[i] if warm_args and i < len(warm_args) else ()
                
                if asyncio.iscoroutinefunction(func):
                    await func(*args)
                else:
                    func(*args)
                    
                logger.debug(f"Cache warmed for function: {func.__name__}")
            except Exception as exc:
                logger.warning(f"Cache warming failed for {func.__name__}: {exc}")
        
        logger.info("Cache warming completed")


# Global cache manager instance
_cache_manager: Optional[CacheManager] = None


def get_cache_manager() -> Optional[CacheManager]:
    """Get the global cache manager instance."""
    return _cache_manager


def setup_cache(config: AppConfig) -> CacheManager:
    """Set up global cache manager."""
    global _cache_manager
    
    if config.cache.enable_caching:
        _cache_manager = CacheManager(config)
        logger.info("Cache manager initialized")
    else:
        logger.info("Caching disabled by configuration")
        _cache_manager = None
    
    return _cache_manager


def cached(
    key: Optional[str] = None,
    ttl: Optional[int] = None,
    cache_type: str = "default"
):
    """
    Convenient decorator for caching function results.
    
    Usage:
        @cached(ttl=60, cache_type="health_metrics")
        async def get_health_data():
            return expensive_operation()
    """
    def decorator(func):
        cache_manager = get_cache_manager()
        if cache_manager and cache_manager.config.cache.enable_caching:
            return cache_manager.cache_with_ttl(
                key_func=lambda *args, **kwargs: key or func.__name__,
                ttl=ttl,
                cache_type=cache_type
            )(func)
        else:
            # Return function unchanged if caching is disabled
            return func
    
    return decorator