"""
Specialized caching for embeddings to avoid recomputing identical vectors.
Uses LRU cache for fast in-memory storage.
"""

import hashlib
from functools import lru_cache
from typing import List, Optional, Tuple

from loguru import logger


class EmbeddingCache:
    """
    LRU cache for storing text embeddings.
    Avoids recomputing embeddings for identical text queries.
    """
    
    def __init__(self, maxsize: int = 1000):
        """
        Initialize embedding cache.
        
        Args:
            maxsize: Maximum number of embeddings to cache
        """
        self.maxsize = maxsize
        self.cache = {}
        self.access_order = []  # Track LRU
        self.hits = 0
        self.misses = 0
    
    def _compute_key(self, text: str) -> str:
        """Compute cache key from text."""
        return hashlib.md5(text.encode('utf-8')).hexdigest()
    
    def get(self, text: str) -> Optional[List[float]]:
        """
        Get cached embedding for text.
        
        Args:
            text: Text to lookup
            
        Returns:
            Embedding vector or None if not cached
        """
        key = self._compute_key(text)
        
        if key in self.cache:
            # Move to end (most recently used)
            self.access_order.remove(key)
            self.access_order.append(key)
            self.hits += 1
            return self.cache[key]
        
        self.misses += 1
        return None
    
    def set(self, text: str, embedding: List[float]):
        """
        Cache an embedding.
        
        Args:
            text: Text that was embedded
            embedding: Embedding vector
        """
        key = self._compute_key(text)
        
        # Evict oldest if at capacity
        if len(self.cache) >= self.maxsize and key not in self.cache:
            oldest_key = self.access_order.pop(0)
            del self.cache[oldest_key]
        
        self.cache[key] = embedding
        
        # Track access order
        if key in self.access_order:
            self.access_order.remove(key)
        self.access_order.append(key)
    
    def get_batch(self, texts: List[str]) -> Tuple[List[Optional[List[float]]], List[str]]:
        """
        Get cached embeddings for multiple texts.
        
        Args:
            texts: List of texts to lookup
            
        Returns:
            Tuple of (embeddings, texts_to_compute)
            - embeddings: List with cached embeddings or None for cache misses
            - texts_to_compute: List of texts that need embedding computation
        """
        embeddings = []
        texts_to_compute = []
        
        for text in texts:
            cached = self.get(text)
            if cached is not None:
                embeddings.append(cached)
            else:
                embeddings.append(None)
                texts_to_compute.append(text)
        
        return embeddings, texts_to_compute
    
    def set_batch(self, texts: List[str], embeddings: List[List[float]]):
        """
        Cache multiple embeddings.
        
        Args:
            texts: List of texts
            embeddings: List of embedding vectors
        """
        for text, embedding in zip(texts, embeddings):
            self.set(text, embedding)
    
    def clear(self):
        """Clear all cached embeddings."""
        self.cache.clear()
        self.access_order.clear()
        self.hits = 0
        self.misses = 0
        logger.info("Embedding cache cleared")
    
    def get_stats(self) -> dict:
        """Get cache statistics."""
        total = self.hits + self.misses
        hit_rate = (self.hits / total * 100) if total > 0 else 0
        
        return {
            'hits': self.hits,
            'misses': self.misses,
            'total_requests': total,
            'hit_rate_percent': round(hit_rate, 2),
            'cache_size': len(self.cache),
            'max_size': self.maxsize
        }
    
    def print_stats(self):
        """Print cache statistics."""
        stats = self.get_stats()
        logger.info(f"Embedding Cache Stats: {stats}")


# Global embedding cache instance
_embedding_cache: Optional[EmbeddingCache] = None


def get_embedding_cache(maxsize: int = 1000) -> EmbeddingCache:
    """
    Get global embedding cache instance (singleton).
    
    Args:
        maxsize: Maximum cache size
        
    Returns:
        EmbeddingCache instance
    """
    global _embedding_cache
    if _embedding_cache is None:
        _embedding_cache = EmbeddingCache(maxsize=maxsize)
    return _embedding_cache

