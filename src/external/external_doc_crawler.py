"""External documentation crawler - ASYNC version using httpx."""

from __future__ import annotations

import asyncio
import json as json_module
import re
from collections import deque
from dataclasses import dataclass
from typing import List, Optional, Set
from urllib.parse import urljoin, urlparse

import httpx
from loguru import logger

try:  # pragma: no cover - optional dependency
    from bs4 import BeautifulSoup  # type: ignore
except ImportError:  # pragma: no cover
    BeautifulSoup = None  # type: ignore


@dataclass
class ExternalDocument:
    """Normalized external documentation entry."""

    url: str
    title: str
    html: str


class ExternalDocCrawler:
    """Async crawler with separate URL discovery and content fetching phases."""

    def __init__(
        self,
        base_url: str,
        max_pages: int = 200,
        delay: float = 0.5,
        max_depth: int = 10,
        user_agent: str = "WombaExternalDocIndexer/1.0",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.max_pages = max_pages
        self.delay = delay
        self.max_depth = max_depth
        self.user_agent = user_agent

        parsed = urlparse(self.base_url)
        self.allowed_netloc = parsed.netloc
        self.base_path = parsed.path.rstrip("/") or "/"

    def is_available(self) -> bool:
        """Check if required dependencies are available."""
        if BeautifulSoup is None:
            logger.warning("External doc crawler unavailable: install beautifulsoup4")
            return False
        return True

    async def discover_urls(self) -> List[str]:
        """
        Phase 1: Crawl from base URL to discover all documentation pages.
        Uses BFS to find all linked pages within the allowed domain.
        Returns list of URLs to fetch.
        """
        if not self.is_available():
            return []

        logger.info(f"🔍 Starting URL discovery from {self.base_url}")
        
        visited: Set[str] = set()
        to_visit: deque = deque([(self.base_url, 0)])  # (url, depth)
        discovered_urls: List[str] = []
        
        async with httpx.AsyncClient(
            headers={"User-Agent": self.user_agent, "Accept": "text/html"},
            timeout=30.0,
            follow_redirects=True
        ) as client:
            while to_visit:
                current_url, depth = to_visit.popleft()
                
                if depth > self.max_depth:
                    continue
                    
                if current_url in visited:
                    continue
                
                if len(discovered_urls) >= self.max_pages:
                    logger.info(f"⚠️  Reached max_pages limit ({self.max_pages}), stopping discovery")
                    break
                    
                visited.add(current_url)
                discovered_urls.append(current_url)
                logger.debug(f"📄 Discovered [{len(discovered_urls)}/{self.max_pages}]: {current_url} (depth={depth})")
                
                # Fetch the page to find more links
                html = await self._fetch(client, current_url)
                if not html:
                    continue
                    
                soup = BeautifulSoup(html, "html.parser")
                links = self._extract_links(soup)
                
                for link in links:
                    # Convert relative URLs to absolute
                    absolute_url = urljoin(current_url, link)
                    normalized_url = self._normalize_url(absolute_url)
                    
                    if normalized_url and normalized_url not in visited:
                        to_visit.append((normalized_url, depth + 1))
                
                # Rate limiting - ASYNC sleep
                if self.delay > 0:
                    await asyncio.sleep(self.delay)
        
        logger.info(f"✅ Discovered {len(discovered_urls)} URLs to fetch")
        return discovered_urls

    async def fetch_content(self, urls: Optional[List[str]] = None) -> List[ExternalDocument]:
        """
        Phase 2: Fetch full content via ASYNC GET requests.
        
        Args:
            urls: List of URLs to fetch. If None, will discover URLs first.
            
        Returns:
            List of ExternalDocument objects with full HTML content.
        """
        if not self.is_available():
            return []

        if urls is None:
            urls = await self.discover_urls()

        if not urls:
            logger.warning("No URLs to fetch content for")
            return []

        documents: List[ExternalDocument] = []
        total = len(urls)

        logger.info(f"🚀 Fetching content for {total} URLs via async GET requests...")

        async with httpx.AsyncClient(
            headers={"User-Agent": self.user_agent, "Accept": "text/html"},
            timeout=30.0,
            follow_redirects=True
        ) as client:
            for i, url in enumerate(urls, 1):
                logger.info(f"📥 [{i}/{total}] GET {url}")
                html = await self._fetch(client, url)
                if not html:
                    logger.warning(f"❌ Failed to fetch content from {url}")
                    continue

                soup = BeautifulSoup(html, "html.parser")
                content_node = self._extract_content_node(soup)
                content_html = content_node.decode() if content_node else html
                
                # Extract JSON examples and append them
                json_examples = self._extract_json_examples(soup)
                if json_examples:
                    content_html += "\n\n=== JSON EXAMPLES ===\n" + "\n\n".join(json_examples)
                    logger.info(f"   Extracted {len(json_examples)} JSON examples")
                
                title = self._extract_title(soup, url)

                documents.append(ExternalDocument(url=url, title=title, html=content_html))
                logger.info(f"✅ [{i}/{total}] Fetched: {title}")

                # Rate limiting - ASYNC sleep
                if self.delay > 0:
                    await asyncio.sleep(self.delay)

        logger.info(f"✅ Content fetching complete: {len(documents)}/{total} pages successfully fetched")
        return documents

    async def crawl(self) -> List[ExternalDocument]:
        """
        Full crawl (discovery + fetching in one pass).
        """
        urls = await self.discover_urls()
        return await self.fetch_content(urls)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _normalize_url(self, url: str) -> Optional[str]:
        """Normalize and validate URL."""
        if not url:
            return None
        parsed = urlparse(url)
        if parsed.netloc != self.allowed_netloc:
            return None
        path = parsed.path or "/"
        
        # Accept URLs that are:
        # 1. Under the base path (e.g., /v1-api/...)
        # 2. OR under /apidocs/ (API documentation)
        # 3. OR under /docs/ (general documentation)
        if not (path.startswith(self.base_path) or 
                path.startswith('/apidocs/') or 
                path.startswith('/docs/')):
            return None
            
        # Remove query params and fragments for canonical form
        normalized = parsed._replace(query="", fragment="").geturl().rstrip("/")
        return normalized

    async def _fetch(self, client: httpx.AsyncClient, url: str) -> Optional[str]:
        """Fetch HTML content via async GET request."""
        try:
            response = await client.get(url)
            if response.status_code == 404:
                logger.debug(f"Page not found (404): {url}")
                return None
            if response.status_code != 200:
                logger.warning(f"External doc crawler HTTP {response.status_code} for {url}")
                return None
            return response.text
        except httpx.TimeoutException:
            logger.warning(f"Timeout fetching {url}")
            return None
        except httpx.RequestError as exc:
            logger.warning(f"External doc crawler failed to fetch {url}: {exc}")
            return None
        except Exception as exc:  # pragma: no cover - network issues
            logger.warning(f"Unexpected error fetching {url}: {exc}")
            return None

    def _extract_links(self, soup) -> Set[str]:
        """Extract all href links from HTML."""
        links: Set[str] = set()
        for tag in soup.find_all("a", href=True):
            href = tag.get("href")
            if not href:
                continue
            # Skip anchors
            if href.startswith("#"):
                continue
            links.add(href)
        return links

    def _extract_title(self, soup, fallback: str) -> str:
        """Extract page title from HTML."""
        if soup.title and soup.title.string:
            return soup.title.string.strip()
        heading = soup.find(["h1", "h2"])
        if heading and heading.get_text(strip=True):
            return heading.get_text(strip=True)
        # Fallback to URL path
        parsed = urlparse(fallback)
        return parsed.path.split("/")[-1] or fallback

    def _extract_content_node(self, soup):
        """Extract main content node from HTML."""
        # Try common documentation wrappers first
        selectors = [
            ("main", {}),
            ("article", {}),
            ("div", {"class": "doc-content"}),
            ("div", {"role": "main"}),
            ("div", {"class": "article-content"}),
            ("div", {"id": "doc_main_content"}),
        ]
        for name, attrs in selectors:
            node = soup.find(name, attrs=attrs)
            if node:
                return node
        # Fallback to body if nothing found
        return soup.body or soup
    
    def _extract_json_examples(self, soup) -> List[str]:
        """Extract JSON code examples from HTML with context."""
        json_examples = []
        
        # Find all code/pre tags that might contain JSON
        code_tags = soup.find_all(['code', 'pre'])
        
        for tag in code_tags:
            text = tag.get_text(strip=False)
            
            # Get context from surrounding text (headers, labels)
            context = ""
            parent = tag.parent
            if parent:
                # Look for nearby headers or labels
                for sibling in parent.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'strong', 'b'], limit=5):
                    sibling_text = sibling.get_text(strip=True).lower()
                    if any(keyword in sibling_text for keyword in ['request', 'body', 'payload', 'example', 'response']):
                        context = sibling.get_text(strip=True)
                        break
            
            # Look for JSON patterns (starts with { or [)
            # Try to find complete JSON objects
            json_pattern = r'(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}|\[[^\[\]]*(?:\[[^\[\]]*\][^\[\]]*)*\])'
            matches = re.finditer(json_pattern, text, re.DOTALL)
            
            for match in matches:
                potential_json = match.group(1)
                # Try to parse to validate it's real JSON
                try:
                    parsed = json_module.loads(potential_json)
                    # Re-format for readability
                    formatted = json_module.dumps(parsed, indent=2)
                    if len(formatted) > 20:  # Skip trivial examples
                        # Add context if available
                        if context:
                            json_examples.append(f"[{context}]\n{formatted}")
                        else:
                            json_examples.append(formatted)
                except (json_module.JSONDecodeError, ValueError):
                    # Not valid JSON, skip
                    continue
        
        return json_examples
