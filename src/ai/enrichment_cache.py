"""
Enrichment cache for storing preprocessed story context.
Caches EnrichedStory objects to avoid reprocessing unchanged stories.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from loguru import logger

from src.models.enriched_story import EnrichedStory
from src.config.settings import settings


class EnrichmentCache:
    """
    File-based cache for enriched stories.
    
    Cache key format: {story_key}_{story_updated_timestamp}.json
    Invalidation: If source story updated or cache > TTL days old
    """
    
    def __init__(self, cache_dir: Optional[str] = None):
        """
        Initialize enrichment cache.
        
        Args:
            cache_dir: Directory for cache storage (defaults to settings)
        """
        self.cache_dir = Path(cache_dir or settings.enrichment_cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl_days = settings.enrichment_cache_ttl_days
        logger.debug(f"Enrichment cache initialized at {self.cache_dir} (TTL: {self.ttl_days} days)")
    
    def _get_cache_path(self, story_key: str, story_updated: Optional[datetime] = None) -> Path:
        """
        Get cache file path for a story.
        
        Args:
            story_key: Story key (e.g., PLAT-123)
            story_updated: Optional story update timestamp for versioning
            
        Returns:
            Path to cache file
        """
        if story_updated:
            timestamp_str = story_updated.strftime("%Y%m%d_%H%M%S")
            filename = f"{story_key}_{timestamp_str}.json"
        else:
            # When retrieving, look for any version of this story
            filename = f"{story_key}_*.json"
        
        return self.cache_dir / filename
    
    def get_cached(self, story_key: str, story_updated: Optional[datetime] = None) -> Optional[EnrichedStory]:
        """
        Retrieve cached enriched story if available and valid.
        
        Args:
            story_key: Story key
            story_updated: Optional story update timestamp for validation
            
        Returns:
            EnrichedStory if cached and valid, None otherwise
        """
        try:
            # Find the most recent cache file for this story
            cache_files = list(self.cache_dir.glob(f"{story_key}_*.json"))
            
            if not cache_files:
                logger.debug(f"No cache found for {story_key}")
                return None
            
            # Sort by modification time, most recent first
            cache_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            cache_path = cache_files[0]
            
            # Check TTL
            cache_age = datetime.utcnow() - datetime.fromtimestamp(cache_path.stat().st_mtime)
            if cache_age > timedelta(days=self.ttl_days):
                logger.info(f"Cache expired for {story_key} (age: {cache_age.days} days)")
                return None
            
            # Load and validate
            with open(cache_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            enriched = EnrichedStory(**data)
            
            # If story was updated after cache, invalidate
            if story_updated and enriched.enrichment_timestamp < story_updated:
                logger.info(f"Cache invalidated for {story_key} (story updated after cache)")
                return None
            
            # Debug: Log cache hit details
            logger.debug(f"Cache HIT for {story_key}:")
            logger.debug(f"  - Cached at: {enriched.enrichment_timestamp}")
            logger.debug(f"  - Age: {cache_age.days} days")
            logger.debug(f"  - Source stories: {', '.join(enriched.source_story_ids)}")
            logger.debug(f"  - APIs: {len(enriched.api_specifications)}")
            logger.debug(f"  - ACs: {len(enriched.acceptance_criteria)}")
            
            logger.info(f"Using cached enrichment for {story_key} (age: {cache_age.days}d)")
            return enriched
            
        except Exception as e:
            logger.warning(f"Failed to load cache for {story_key}: {e}")
            return None
    
    def save_cached(self, enriched: EnrichedStory, story_updated: Optional[datetime] = None) -> None:
        """
        Save enriched story to cache.
        
        Args:
            enriched: EnrichedStory to cache
            story_updated: Optional story update timestamp for versioning
        """
        try:
            # Clear old cache files for this story
            self.clear_cache(enriched.story_key)
            
            # Save new cache
            cache_path = self._get_cache_path(enriched.story_key, story_updated or enriched.enrichment_timestamp)
            
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(enriched.dict(), f, indent=2, default=str)
            
            logger.debug(f"Saved enrichment cache for {enriched.story_key}:")
            logger.debug(f"  - Path: {cache_path}")
            logger.debug(f"  - Size: {cache_path.stat().st_size / 1024:.1f} KB")
            logger.info(f"Cached enrichment for {enriched.story_key} at {cache_path}")
            
        except Exception as e:
            logger.error(f"Failed to save cache for {enriched.story_key}: {e}")
    
    def clear_cache(self, story_key: Optional[str] = None) -> int:
        """
        Clear cache for specific story or all stories.
        
        Args:
            story_key: Optional story key to clear (if None, clears all)
            
        Returns:
            Number of cache files deleted
        """
        try:
            if story_key:
                cache_files = list(self.cache_dir.glob(f"{story_key}_*.json"))
            else:
                cache_files = list(self.cache_dir.glob("*.json"))
            
            count = 0
            for cache_file in cache_files:
                cache_file.unlink()
                count += 1
            
            if count > 0:
                logger.info(f"Cleared {count} cache file(s)" + (f" for {story_key}" if story_key else ""))
            
            return count
            
        except Exception as e:
            logger.error(f"Failed to clear cache: {e}")
            return 0
    
    def get_cache_stats(self) -> dict:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache stats
        """
        try:
            cache_files = list(self.cache_dir.glob("*.json"))
            total_size = sum(f.stat().st_size for f in cache_files)
            
            return {
                "total_files": len(cache_files),
                "total_size_kb": total_size // 1024,
                "cache_dir": str(self.cache_dir),
                "ttl_days": self.ttl_days
            }
        except Exception as e:
            logger.error(f"Failed to get cache stats: {e}")
            return {}

