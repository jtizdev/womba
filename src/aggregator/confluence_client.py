"""
Confluence client for fetching PRDs and technical documentation.
"""

from typing import Dict, List, Optional

import httpx
from loguru import logger

from src.core.atlassian_client import AtlassianClient


class ConfluenceClient(AtlassianClient):
    """Client for interacting with Confluence API."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        email: Optional[str] = None,
        api_token: Optional[str] = None,
    ):
        """
        Initialize Confluence client.

        Args:
            base_url: Atlassian base URL (defaults to settings)
            email: Atlassian user email (defaults to settings)
            api_token: Atlassian API token (defaults to settings)
        """
        super().__init__(base_url=base_url, email=email, api_token=api_token)

    async def get_page(self, page_id: str) -> Dict:
        """
        Fetch a Confluence page by ID.

        Args:
            page_id: Confluence page ID

        Returns:
            Page data including content

        Raises:
            httpx.HTTPError: If the request fails
        """
        logger.info(f"Fetching Confluence page: {page_id}")

        url = f"{self.base_url}/wiki/rest/api/content/{page_id}"
        params = {"expand": "body.storage,version,space"}

        async with httpx.AsyncClient() as client:
            response = await client.get(url, auth=self.auth, params=params, timeout=30.0)
            response.raise_for_status()
            return response.json()

    async def search_pages(self, cql: str, limit: int = 25) -> List[Dict]:
        """
        Search for Confluence pages using CQL.

        Args:
            cql: Confluence Query Language string
            limit: Maximum results

        Returns:
            List of page data

        Raises:
            httpx.HTTPError: If the request fails
        """
        logger.info(f"Searching Confluence with CQL: {cql}")

        url = f"{self.base_url}/wiki/rest/api/content/search"
        params = {"cql": cql, "limit": limit, "expand": "body.storage"}

        async with httpx.AsyncClient() as client:
            response = await client.get(url, auth=self.auth, params=params, timeout=30.0)
            response.raise_for_status()
            data = response.json()

        return data.get("results", [])

    async def find_related_pages(self, story_key: str, labels: List[str] = None) -> List[Dict]:
        """
        Find Confluence pages related to a Jira story.

        Args:
            story_key: Jira issue key
            labels: Additional labels to search for

        Returns:
            List of related pages
        """
        logger.info(f"Finding Confluence pages related to {story_key}")

        pages = []
        
        # Strategy 1: Search for pages containing the story key
        try:
            cql = f'text ~ "{story_key}" AND type = page ORDER BY lastmodified DESC'
            results = await self.search_pages(cql, limit=10)
            pages.extend(results)
            logger.info(f"Found {len(results)} pages mentioning {story_key}")
        except Exception as e:
            logger.debug(f"Story key search failed: {e}")

        # Strategy 2: Search in specific spaces (common PRD/tech design spaces)
        common_spaces = ["PROD", "TECH", "ENG", "DOC", "PLAT"]  # Add your spaces
        for space in common_spaces:
            try:
                cql = f'space = "{space}" AND (text ~ "{story_key}" OR text ~ "POP" OR text ~ "ID alignment") AND type = page ORDER BY lastmodified DESC'
                results = await self.search_pages(cql, limit=5)
                pages.extend(results)
            except Exception as e:
                logger.debug(f"Space {space} search failed: {e}")
                continue
        
        # Strategy 3: Search by labels if provided
        if labels:
            for label in labels[:3]:  # Try first 3 labels
                try:
                    cql = f'label = "{label}" AND type = page ORDER BY lastmodified DESC'
                    results = await self.search_pages(cql, limit=5)
                    pages.extend(results)
                except Exception as e:
                    logger.debug(f"Label {label} search failed: {e}")
                    continue
        
        # Remove duplicates by page ID
        unique_pages = {page['id']: page for page in pages}.values()
        
        logger.info(f"Found {len(unique_pages)} unique related Confluence pages")
        return list(unique_pages)

    def extract_page_content(self, page_data: Dict) -> str:
        """
        Extract plain text content from Confluence page.

        Args:
            page_data: Raw page data from API

        Returns:
            Plain text content
        """
        try:
            storage = page_data.get("body", {}).get("storage", {})
            html_content = storage.get("value", "")

            # Basic HTML stripping (you might want to use BeautifulSoup for better parsing)
            import re

            # Remove HTML tags
            text = re.sub(r"<[^>]+>", " ", html_content)
            # Clean up whitespace
            text = re.sub(r"\s+", " ", text).strip()

            return text
        except Exception as e:
            logger.error(f"Error extracting page content: {e}")
            return ""

    async def get_page_by_title(self, space_key: str, title: str) -> Optional[Dict]:
        """
        Get page by title in a specific space.

        Args:
            space_key: Confluence space key
            title: Page title

        Returns:
            Page data or None if not found
        """
        logger.info(f"Fetching Confluence page: {space_key}/{title}")

        cql = f'space = "{space_key}" AND title ~ "{title}" AND type = page'

        try:
            pages = await self.search_pages(cql, limit=1)
            return pages[0] if pages else None
        except Exception as e:
            logger.error(f"Error fetching page by title: {e}")
            return None

