"""
Centralized HTTP client with retry logic and error handling.
Uses httpx (modern async HTTP client) and tenacity (retry library).
"""

from typing import Optional, Dict, Any
from loguru import logger
import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)


class HTTPClient:
    """
    Unified HTTP client for all external requests.
    Features:
    - Automatic retry with exponential backoff
    - Configurable timeouts
    - User agent management
    - Error handling and logging
    """

    def __init__(
        self,
        timeout: float = 30.0,
        max_retries: int = 3,
        user_agent: str = "Womba/1.0",
        verify_ssl: bool = True,
    ):
        """
        Initialize HTTP client.
        
        Args:
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
            user_agent: User agent string for requests
            verify_ssl: Whether to verify SSL certificates
        """
        self.timeout = timeout
        self.max_retries = max_retries
        self.user_agent = user_agent
        self.verify_ssl = verify_ssl

        # Create httpx client with default headers
        self.client = httpx.Client(
            timeout=timeout,
            verify=verify_ssl,
            headers={"User-Agent": user_agent},
            follow_redirects=True,
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
        before_sleep=before_sleep_log(logger, logger.level("WARNING").no),
        reraise=True,
    )
    def get(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> httpx.Response:
        """
        Perform GET request with automatic retry.
        
        Args:
            url: URL to fetch
            headers: Additional headers (merged with default user agent)
            params: Query parameters
            
        Returns:
            httpx.Response object
            
        Raises:
            httpx.HTTPError: On HTTP errors
            httpx.TimeoutException: On timeout (after retries)
            httpx.NetworkError: On network errors (after retries)
        """
        logger.debug(f"GET {url}")
        
        # Merge custom headers with defaults
        merged_headers = {"User-Agent": self.user_agent}
        if headers:
            merged_headers.update(headers)

        try:
            response = self.client.get(url, headers=merged_headers, params=params)
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as e:
            logger.warning(f"HTTP {e.response.status_code} error for {url}: {e}")
            raise
        except httpx.TimeoutException:
            logger.error(f"Request timed out after {self.timeout}s: {url}")
            raise
        except httpx.NetworkError as e:
            logger.error(f"Network error for {url}: {e}")
            raise

    def get_text(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        encoding: Optional[str] = None,
    ) -> Optional[str]:
        """
        Fetch URL and return text content.
        
        Args:
            url: URL to fetch
            headers: Additional headers
            params: Query parameters
            encoding: Character encoding (auto-detected if None)
            
        Returns:
            Text content or None on error
        """
        try:
            response = self.get(url, headers=headers, params=params)
            
            # Use specified encoding or auto-detect
            if encoding:
                response.encoding = encoding
            
            return response.text
        except Exception as e:
            logger.warning(f"Failed to fetch {url}: {e}")
            return None

    def get_json(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch URL and return JSON content.
        
        Args:
            url: URL to fetch
            headers: Additional headers
            params: Query parameters
            
        Returns:
            Parsed JSON dict or None on error
        """
        try:
            response = self.get(url, headers=headers, params=params)
            return response.json()
        except Exception as e:
            logger.warning(f"Failed to fetch JSON from {url}: {e}")
            return None

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
        before_sleep=before_sleep_log(logger, logger.level("WARNING").no),
        reraise=True,
    )
    def post(
        self,
        url: str,
        json: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> httpx.Response:
        """
        Perform POST request with automatic retry.
        
        Args:
            url: URL to post to
            json: JSON payload
            data: Form data payload
            headers: Additional headers
            
        Returns:
            httpx.Response object
            
        Raises:
            httpx.HTTPError: On HTTP errors
        """
        logger.debug(f"POST {url}")
        
        # Merge custom headers with defaults
        merged_headers = {"User-Agent": self.user_agent}
        if headers:
            merged_headers.update(headers)

        try:
            response = self.client.post(
                url, json=json, data=data, headers=merged_headers
            )
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as e:
            logger.warning(f"HTTP {e.response.status_code} error for {url}: {e}")
            raise

    def close(self):
        """Close the HTTP client and release resources."""
        self.client.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - close client."""
        self.close()


class AsyncHTTPClient:
    """
    Async version of HTTP client for concurrent requests.
    """

    def __init__(
        self,
        timeout: float = 30.0,
        max_retries: int = 3,
        user_agent: str = "Womba/1.0",
        verify_ssl: bool = True,
    ):
        """
        Initialize async HTTP client.
        
        Args:
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
            user_agent: User agent string for requests
            verify_ssl: Whether to verify SSL certificates
        """
        self.timeout = timeout
        self.max_retries = max_retries
        self.user_agent = user_agent
        self.verify_ssl = verify_ssl

        # Create async httpx client
        self.client = httpx.AsyncClient(
            timeout=timeout,
            verify=verify_ssl,
            headers={"User-Agent": user_agent},
            follow_redirects=True,
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
        before_sleep=before_sleep_log(logger, logger.level("WARNING").no),
        reraise=True,
    )
    async def get(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> httpx.Response:
        """
        Perform async GET request with automatic retry.
        
        Args:
            url: URL to fetch
            headers: Additional headers
            params: Query parameters
            
        Returns:
            httpx.Response object
        """
        logger.debug(f"GET {url}")
        
        merged_headers = {"User-Agent": self.user_agent}
        if headers:
            merged_headers.update(headers)

        try:
            response = await self.client.get(
                url, headers=merged_headers, params=params
            )
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as e:
            logger.warning(f"HTTP {e.response.status_code} error for {url}: {e}")
            raise

    async def get_text(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        encoding: Optional[str] = None,
    ) -> Optional[str]:
        """
        Fetch URL and return text content (async).
        
        Args:
            url: URL to fetch
            headers: Additional headers
            params: Query parameters
            encoding: Character encoding (auto-detected if None)
            
        Returns:
            Text content or None on error
        """
        try:
            response = await self.get(url, headers=headers, params=params)
            if encoding:
                response.encoding = encoding
            return response.text
        except Exception as e:
            logger.warning(f"Failed to fetch {url}: {e}")
            return None

    async def close(self):
        """Close the HTTP client and release resources."""
        await self.client.aclose()

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - close client."""
        await self.close()

