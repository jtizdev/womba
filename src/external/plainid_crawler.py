"""PlainID documentation crawler PRIORITIZING DIRECT GET REQUEST FOR CONTENT FETCHING."""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from typing import List, Optional, Set
from urllib.parse import urljoin, urlparse

from loguru import logger

try:  # pragma: no cover - optional dependency
    import requests
except ImportError:  # pragma: no cover
    requests = None

try:  # pragma: no cover - optional dependency
    from bs4 import BeautifulSoup  # type: ignore
except ImportError:  # pragma: no cover
    BeautifulSoup = None  # type: ignore


@dataclass
class PlainIDDocument:
    """Normalized PlainID documentation entry."""

    url: str
    title: str
    html: str


class PlainIDDocCrawler:
    """Efficient crawler with separate URL discovery and content fetching phases."""

    def __init__(
        self,
        base_url: str,
        max_pages: int = 200,
        delay: float = 0.5,
        max_depth: int = 10,
        user_agent: str = "WombaPlainIDIndexer/1.0",
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
        if requests is None or BeautifulSoup is None:
            logger.warning("PlainID crawler unavailable: install requests and beautifulsoup4")
            return False
        return True

    def discover_urls(self) -> List[str]:
        """
        Phase 1: Lightweight URL discovery via link-following crawl.
        Only parses HTML to extract links, doesn't store full content.
        Returns list of discovered URLs.
        """
        if not self.is_available():
            return []

        queue: deque[tuple[str, int]] = deque([(self.base_url, 0)])  # (url, depth)
        visited: Set[str] = set()
        discovered_urls: List[str] = []

        logger.info(f"Starting URL discovery from {self.base_url}")

        while queue and len(discovered_urls) < self.max_pages:
            current_url, depth = queue.popleft()
            normalized = self._normalize_url(current_url)
            
            if not normalized or normalized in visited:
                continue
                
            if depth > self.max_depth:
                logger.debug(f"Skipping {normalized} - exceeded max depth {self.max_depth}")
                continue
                
            visited.add(normalized)
            discovered_urls.append(normalized)

            # Fetch HTML just to extract links (minimal processing)
            html = self._fetch(normalized)
            if not html:
                continue

            # Quick parse just for links
            soup = BeautifulSoup(html, "html.parser")
            for href in self._extract_links(soup):
                candidate = self._normalize_url(urljoin(normalized, href))
                if candidate and candidate not in visited:
                    queue.append((candidate, depth + 1))

            if self.delay > 0:
                time.sleep(self.delay)

            if len(discovered_urls) % 10 == 0:
                logger.info(f"Discovered {len(discovered_urls)} URLs so far...")

        logger.info(f"URL discovery complete: found {len(discovered_urls)} URLs")
        return discovered_urls

    def fetch_content(self, urls: Optional[List[str]] = None) -> List[PlainIDDocument]:
        """
        Phase 2: Fetch full content for discovered URLs via direct GET requests.
        
        Args:
            urls: List of URLs to fetch. If None, will discover URLs first.
            
        Returns:
            List of PlainIDDocument objects with full HTML content.
        """
        if not self.is_available():
            return []

        if urls is None:
            urls = self.discover_urls()

        if not urls:
            logger.warning("No URLs to fetch content for")
            return []

        documents: List[PlainIDDocument] = []
        total = len(urls)

        logger.info(f"Fetching content for {total} URLs...")

        for i, url in enumerate(urls, 1):
            html = self._fetch(url)
            if not html:
                logger.warning(f"Failed to fetch content from {url}")
                continue

            soup = BeautifulSoup(html, "html.parser")
            content_node = self._extract_content_node(soup)
            content_html = content_node.decode() if content_node else html
            title = self._extract_title(soup, url)

            documents.append(PlainIDDocument(url=url, title=title, html=content_html))

            if self.delay > 0:
                time.sleep(self.delay)

            if i % 10 == 0:
                logger.info(f"Fetched {i}/{total} pages ({len(documents)} successful)")

        logger.info(f"Content fetching complete: {len(documents)}/{total} pages successfully fetched")
        return documents

    def crawl(self) -> List[PlainIDDocument]:
        """
        Legacy method: Full crawl (discovery + fetching in one pass).
        Kept for backward compatibility but uses new two-phase approach internally.
        """
        urls = self.discover_urls()
        return self.fetch_content(urls)

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
        # Filter to only /apidocs/ paths for API documentation
        if "/apidocs/" not in path and path != self.base_path and path != self.base_path + "/":
            return None
        # Remove query params and fragments for canonical form
        normalized = parsed._replace(query="", fragment="").geturl().rstrip("/")
        return normalized

    def _fetch(self, url: str) -> Optional[str]:
        """Fetch HTML content via direct GET request."""
        try:
            response = requests.get(
                url,
                headers={"User-Agent": self.user_agent, "Accept": "text/html"},
                timeout=30,
            )
            if response.status_code == 404:
                logger.debug(f"Page not found (404): {url}")
                return None
            if response.status_code != 200:
                logger.warning(f"PlainID crawler HTTP {response.status_code} for {url}")
                return None
            response.encoding = response.encoding or "utf-8"
            return response.text
        except requests.exceptions.Timeout:
            logger.warning(f"Timeout fetching {url}")
            return None
        except requests.exceptions.RequestException as exc:
            logger.warning(f"PlainID crawler failed to fetch {url}: {exc}")
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
