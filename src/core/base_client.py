"""
Base client classes for API integrations.
"""

from abc import ABC, abstractmethod
from typing import Optional, Generic, TypeVar
import httpx
from loguru import logger

T = TypeVar('T')


class BaseAPIClient(ABC, Generic[T]):
    """
    Base class for all API clients with connection pooling and context management.
    """
    
    def __init__(self, base_url: str):
        self.base_url = base_url
        self._client: Optional[httpx.AsyncClient] = None
    
    async def __aenter__(self):
        """Initialize connection pool on context enter."""
        self._client = httpx.AsyncClient(
            timeout=30.0,
            limits=httpx.Limits(
                max_keepalive_connections=20,
                max_connections=100
            )
        )
        logger.debug(f"Initialized connection pool for {self.__class__.__name__}")
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close connection pool on context exit."""
        if self._client:
            await self._client.aclose()
            logger.debug(f"Closed connection pool for {self.__class__.__name__}")
    
    @abstractmethod
    async def validate_connection(self) -> bool:
        """
        Validate that the API connection works.
        
        Returns:
            True if connection is valid, False otherwise
        """
        pass
    
    @property
    def client(self) -> httpx.AsyncClient:
        """Get the HTTP client instance."""
        if self._client is None:
            raise RuntimeError(
                f"{self.__class__.__name__} must be used as async context manager"
            )
        return self._client

