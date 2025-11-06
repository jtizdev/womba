"""
Document fetching service for retrieving documents from external sources.
Single Responsibility: Fetching documents from PlainID, GitLab, web, etc.
"""

import asyncio
from typing import List, Optional
from loguru import logger

from src.config.settings import settings
from src.external.plainid_crawler import PlainIDDocCrawler, PlainIDDocument
from src.external.gitlab_swagger_fetcher import GitLabSwaggerFetcher, SwaggerDocument


class DocumentFetcher:
    """
    Fetches documents from various external sources.
    Features:
    - PlainID documentation crawling and fetching
    - URL discovery
    - Content retrieval
    """

    def __init__(self):
        """Initialize document fetcher."""
        pass

    async def fetch_plainid_docs(self) -> List[PlainIDDocument]:
        """
        Fetch PlainID documentation using configured settings.
        
        Returns:
            List of PlainIDDocument objects
        """
        if not settings.plainid_doc_index_enabled:
            logger.info("External documentation indexing disabled via settings")
            return []

        urls_to_fetch = await self._discover_plainid_urls()
        
        if not urls_to_fetch:
            logger.info("No external documentation URLs to fetch")
            return []

        logger.info(f"Fetching content for {len(urls_to_fetch)} PlainID URLs")
        
        # Create crawler for content fetching
        fetch_crawler = PlainIDDocCrawler(
            base_url=urls_to_fetch[0] if urls_to_fetch else "https://docs.plainid.io",
            max_pages=settings.plainid_doc_max_pages,
            delay=settings.plainid_doc_request_delay,
            max_depth=1  # Only fetch the given URLs, no further crawling
        )
        
        if not fetch_crawler.is_available():
            logger.error("PlainID crawler dependencies not available (requests/beautifulsoup4)")
            return []

        docs = await asyncio.to_thread(fetch_crawler.fetch_content, urls_to_fetch)
        
        if not docs:
            logger.warning("No external documentation content fetched (all requests failed)")
            return []
        
        logger.info(f"Successfully fetched {len(docs)} PlainID documents")
        return docs

    async def _discover_plainid_urls(self) -> List[str]:
        """
        Discover PlainID documentation URLs from configured entry points.
        
        Returns:
            List of URLs to fetch
        """
        configured_urls = settings.plainid_doc_urls or []
        
        if not configured_urls:
            # Try base_url if no configured URLs
            base_url = settings.plainid_doc_base_url
            if base_url:
                configured_urls = [base_url]
            else:
                return []
        
        logger.info(f"Starting crawl from {len(configured_urls)} configured entry points")
        
        all_discovered = set()
        
        for entry_url in configured_urls:
            try:
                temp_crawler = PlainIDDocCrawler(
                    base_url=entry_url,
                    max_pages=settings.plainid_doc_max_pages,
                    delay=settings.plainid_doc_request_delay,
                    max_depth=settings.plainid_doc_max_depth,
                )
                
                if temp_crawler.is_available():
                    logger.info(f"Crawling from: {entry_url}")
                    discovered = await asyncio.to_thread(temp_crawler.discover_urls)
                    all_discovered.update(discovered)
                    logger.info(f"  → Found {len(discovered)} URLs from this entry point")
            except Exception as e:
                logger.warning(f"Failed to crawl from {entry_url}: {e}")
                # Still add the entry URL itself
                all_discovered.add(entry_url)
        
        urls_to_index = list(all_discovered)
        logger.info(f"Total discovered URLs: {len(urls_to_index)}")
        
        return urls_to_index

    async def fetch_gitlab_swagger_docs(self) -> List[SwaggerDocument]:
        """
        Fetch Swagger/OpenAPI documentation from GitLab services.
        
        Returns:
            List of SwaggerDocument objects
        """
        if not settings.gitlab_swagger_enabled:
            logger.info("GitLab Swagger indexing disabled via settings")
            return []
        
        if not settings.gitlab_token:
            logger.warning("GitLab token not configured, skipping Swagger fetch")
            return []
        
        logger.info("Fetching Swagger/OpenAPI docs from GitLab")
        
        try:
            fetcher = GitLabSwaggerFetcher()
            
            if not fetcher.is_available():
                logger.warning("GitLab Swagger fetcher not available")
                return []
            
            # Fetch all swagger docs from the configured group
            docs = await asyncio.to_thread(fetcher.fetch_all)
            
            if not docs:
                logger.warning("No Swagger documentation found in GitLab")
                return []
            
            logger.info(f"Successfully fetched {len(docs)} Swagger documents from GitLab")
            return docs
            
        except Exception as e:
            logger.error(f"Failed to fetch GitLab Swagger docs: {e}")
            return []

