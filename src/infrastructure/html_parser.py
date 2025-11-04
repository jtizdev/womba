"""
Centralized HTML parsing and text extraction service.
Uses BeautifulSoup4 for robust HTML parsing.
"""

import re
from typing import Optional
from loguru import logger

try:
    from bs4 import BeautifulSoup, Tag  # type: ignore
except ImportError:  # pragma: no cover
    BeautifulSoup = None  # type: ignore
    Tag = None  # type: ignore


class HTMLParser:
    """
    Service for parsing HTML and extracting text content.
    Features:
    - Clean text extraction
    - Tag/script/style removal
    - HTML entity handling
    - Title extraction
    """

    def __init__(self, parser: str = "html.parser"):
        """
        Initialize HTML parser.
        
        Args:
            parser: Parser to use (html.parser, lxml, html5lib)
        """
        if BeautifulSoup is None:
            raise ImportError(
                "BeautifulSoup4 is required for HTML parsing. "
                "Install it with: pip install beautifulsoup4"
            )
        self.parser = parser

    def strip_html_tags(self, html: str) -> str:
        """
        Convert HTML to readable text by removing scripts, styles, and tags.
        
        Args:
            html: HTML content to parse
            
        Returns:
            Clean text content with preserved line breaks
        """
        if not html:
            return ""

        try:
            soup = BeautifulSoup(html, self.parser)
            
            # Remove script, style, nav, header, footer elements
            for tag in soup(["script", "style", "nav", "header", "footer"]):
                tag.decompose()
            
            # Get text with preserved line breaks
            text = soup.get_text("\n")
            
            # Clean up whitespace
            text = re.sub(r"\r", "\n", text)  # Normalize line endings
            text = re.sub(r"\n{3,}", "\n\n", text)  # Collapse multiple newlines
            text = re.sub(r"[ \t]+", " ", text)  # Collapse multiple spaces
            
            return text.strip()
            
        except Exception as e:
            logger.warning(f"BeautifulSoup parsing failed: {e}, using regex fallback")
            return self._strip_html_regex_fallback(html)

    def _strip_html_regex_fallback(self, html: str) -> str:
        """
        Fallback regex-based HTML stripping when BeautifulSoup fails.
        
        Args:
            html: HTML content
            
        Returns:
            Cleaned text
        """
        # Remove scripts and styles
        cleaned = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html)
        
        # Convert common tags to line breaks
        cleaned = re.sub(r"(?i)<br[/\\s]*>", "\n", cleaned)
        cleaned = re.sub(r"(?i)</p>", "\n\n", cleaned)
        
        # Remove all HTML tags
        cleaned = re.sub(r"<[^>]+>", " ", cleaned)
        
        # Decode common HTML entities
        cleaned = re.sub(r"&nbsp;", " ", cleaned)
        cleaned = re.sub(r"&amp;", "&", cleaned)
        cleaned = re.sub(r"&lt;", "<", cleaned)
        cleaned = re.sub(r"&gt;", ">", cleaned)
        cleaned = re.sub(r"&quot;", '"', cleaned)
        
        # Clean up whitespace
        cleaned = re.sub(r"\s+", " ", cleaned)
        
        return cleaned.strip()

    def extract_title(self, html: str, fallback: str = "Untitled") -> str:
        """
        Extract title from HTML.
        
        Args:
            html: HTML content
            fallback: Fallback title if extraction fails
            
        Returns:
            Extracted title or fallback
        """
        if not html:
            return fallback

        try:
            soup = BeautifulSoup(html, self.parser)
            
            # Try <title> tag first
            if soup.title and soup.title.string:
                return soup.title.string.strip()[:200]
            
            # Try <h1> tag as fallback
            h1 = soup.find("h1")
            if h1 and h1.string:
                return h1.string.strip()[:200]
            
            return fallback
            
        except Exception as e:
            logger.debug(f"Title extraction failed: {e}, using regex")
            return self._extract_title_regex(html, fallback)

    def _extract_title_regex(self, html: str, fallback: str) -> str:
        """
        Regex fallback for title extraction.
        
        Args:
            html: HTML content
            fallback: Fallback title
            
        Returns:
            Extracted title or fallback
        """
        match = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        if match:
            title = self.strip_html_tags(match.group(1))
            return title[:200]
        return fallback

    def extract_text_from_element(
        self, html: str, selector: str
    ) -> Optional[str]:
        """
        Extract text from specific element using CSS selector.
        
        Args:
            html: HTML content
            selector: CSS selector (e.g., 'div.content', '#main')
            
        Returns:
            Extracted text or None if not found
        """
        try:
            soup = BeautifulSoup(html, self.parser)
            element = soup.select_one(selector)
            
            if element:
                # Remove scripts and styles within element
                for tag in element(["script", "style"]):
                    tag.decompose()
                    
                text = element.get_text("\n")
                text = re.sub(r"\s+", " ", text)
                return text.strip()
                
            return None
            
        except Exception as e:
            logger.warning(f"Failed to extract element {selector}: {e}")
            return None

    def find_code_blocks(self, html: str) -> list[str]:
        """
        Extract all code blocks from HTML (<pre>, <code> tags).
        
        Args:
            html: HTML content
            
        Returns:
            List of code block contents
        """
        try:
            soup = BeautifulSoup(html, self.parser)
            code_blocks = []
            
            # Find <pre> tags (usually contain code)
            for pre in soup.find_all("pre"):
                code_blocks.append(pre.get_text())
            
            # Find standalone <code> tags (not inside <pre>)
            for code in soup.find_all("code"):
                # Skip if already captured in <pre>
                if not code.find_parent("pre"):
                    code_blocks.append(code.get_text())
            
            return code_blocks
            
        except Exception as e:
            logger.warning(f"Failed to extract code blocks: {e}")
            return []

    def extract_links(self, html: str, base_url: Optional[str] = None) -> list[str]:
        """
        Extract all links from HTML.
        
        Args:
            html: HTML content
            base_url: Base URL for resolving relative links
            
        Returns:
            List of URLs
        """
        try:
            soup = BeautifulSoup(html, self.parser)
            links = []
            
            for link in soup.find_all("a", href=True):
                href = link["href"]
                
                # Skip anchors and javascript links
                if href.startswith("#") or href.startswith("javascript:"):
                    continue
                
                # Handle relative URLs if base_url provided
                if base_url and not href.startswith(("http://", "https://")):
                    from urllib.parse import urljoin
                    href = urljoin(base_url, href)
                
                links.append(href)
            
            return links
            
        except Exception as e:
            logger.warning(f"Failed to extract links: {e}")
            return []

    def clean_whitespace(self, text: str) -> str:
        """
        Clean up excessive whitespace in text.
        
        Args:
            text: Text to clean
            
        Returns:
            Cleaned text
        """
        # Normalize line endings
        text = re.sub(r"\r\n", "\n", text)
        text = re.sub(r"\r", "\n", text)
        
        # Collapse multiple spaces
        text = re.sub(r"[ \t]+", " ", text)
        
        # Collapse multiple newlines (max 2)
        text = re.sub(r"\n{3,}", "\n\n", text)
        
        # Remove leading/trailing whitespace on each line
        lines = [line.strip() for line in text.split("\n")]
        text = "\n".join(lines)
        
        return text.strip()


# Create a default instance for convenience
default_parser = HTMLParser() if BeautifulSoup else None


def strip_html_tags(html: str) -> str:
    """Convenience function for stripping HTML tags."""
    if default_parser:
        return default_parser.strip_html_tags(html)
    # If BeautifulSoup not available, return regex-only fallback
    return HTMLParser()._strip_html_regex_fallback(html)


def extract_title(html: str, fallback: str = "Untitled") -> str:
    """Convenience function for extracting title."""
    if default_parser:
        return default_parser.extract_title(html, fallback)
    return HTMLParser()._extract_title_regex(html, fallback)

