"""
Confluence client for fetching PRDs and technical documentation.
"""

import asyncio
from typing import Dict, List, Optional, Tuple, Any

import httpx
from loguru import logger
from urllib.parse import urlparse, parse_qs, urljoin

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

    def _make_absolute_url(self, url: Optional[str]) -> Optional[str]:
        if not url:
            return None
        if url.startswith("http"):
            return url
        if url.startswith("/"):
            return urljoin(f"{self.base_url}/", url.lstrip("/"))
        return urljoin(f"{self.base_url}/", url)

    async def _fetch_json(
        self,
        client: httpx.AsyncClient,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        max_retries: int = 3,
    ) -> Dict[str, Any]:
        delay = 1.0
        attempt = 0
        absolute_url = self._make_absolute_url(url)

        while True:
            try:
                response = await client.get(
                    absolute_url,
                    auth=self.auth,
                    params=params,
                )

                if response.status_code in {429, 503} and attempt < max_retries:
                    retry_after = response.headers.get("Retry-After")
                    wait_time = float(retry_after) if retry_after else delay
                    logger.warning(
                        f"Confluence rate limit ({response.status_code}). Retrying in {wait_time:.1f}s..."
                    )
                    await asyncio.sleep(wait_time)
                    attempt += 1
                    delay = min(delay * 2, 30)
                    continue

                response.raise_for_status()
                return response.json()

            except httpx.HTTPError as exc:
                if attempt < max_retries:
                    logger.warning(f"Confluence request error '{exc}'. Retrying in {delay:.1f}s...")
                    await asyncio.sleep(delay)
                    attempt += 1
                    delay = min(delay * 2, 30)
                    continue
                logger.error(f"Confluence request failed: {exc}")
                raise

    async def _iter_spaces_v2(
        self,
        client: httpx.AsyncClient,
        limit: int = 250
    ):
        url = f"{self.base_url}/wiki/api/v2/spaces"
        params: Optional[Dict[str, Any]] = {"limit": limit}

        while url:
            data = await self._fetch_json(client, url, params=params)
            for space in data.get("results", []):
                yield space

            next_link = data.get("_links", {}).get("next")
            url = self._make_absolute_url(next_link)
            params = None

    async def _iter_pages_v2(
        self,
        client: httpx.AsyncClient,
        space_id: str,
        limit: int = 250,
        expand: Optional[str] = None
    ):
        url = f"{self.base_url}/wiki/api/v2/spaces/{space_id}/pages"
        params: Optional[Dict[str, Any]] = {"limit": limit}
        if expand:
            params["expand"] = expand

        while url:
            data = await self._fetch_json(client, url, params=params)
            for page in data.get("results", []):
                yield page

            next_link = data.get("_links", {}).get("next")
            url = self._make_absolute_url(next_link)
            params = None

    async def search_all_pages(
        self,
        cql: str,
        limit: int = 250,
        expand: str = "body.storage,space,version"
    ) -> List[Dict]:
        """Fetch ALL pages across spaces using Confluence API v2 (cursor pagination)."""
        logger.info(f"Fetching ALL Confluence pages for CQL: '{cql}' via API v2")

        all_pages: List[Dict[str, Any]] = []
        async with httpx.AsyncClient(timeout=60.0) as client:
            async for space in self._iter_spaces_v2(client, limit=limit):
                space_id = space.get("id")
                space_key = space.get("key") or space.get("name", "")
                logger.info(f"Processing space {space_key} ({space_id})")

                async for page in self._iter_pages_v2(client, space_id, limit=limit, expand=expand):
                    page_copy = dict(page)
                    page_copy.setdefault("space", {"id": space_id, "key": space_key})
                    all_pages.append(page_copy)

        logger.info(f"✅ Fetched {len(all_pages)} Confluence pages via API v2")
        return all_pages

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

    async def search_pages(
        self,
        cql: str,
        limit: int = 50,
        start: int = 0,
        expand: str = "space,version"
    ) -> List[Dict]:
        url = f"{self.base_url}/wiki/rest/api/content/search"
        params = {
            "cql": cql,
            "limit": limit,
            "start": start,
            "expand": expand,
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            data = await self._fetch_json(client, url, params=params)
        return data.get("results", [])

