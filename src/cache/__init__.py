"""
Caching module for Womba.
Provides intelligent caching for Jira, Confluence, RAG, and embeddings.
"""

from .cache_manager import CacheManager, get_cache, cached
from .embedding_cache import EmbeddingCache, get_embedding_cache

__all__ = [
    'CacheManager',
    'get_cache',
    'cached',
    'EmbeddingCache',
    'get_embedding_cache',
]

