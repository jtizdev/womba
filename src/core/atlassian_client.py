"""
Common Atlassian client base providing unified configuration and HTTP helpers.
"""

from typing import Any, Dict, Optional

import httpx
from loguru import logger

from src.config.settings import settings


class AtlassianClient:
    """Base class for Atlassian services (Jira, Confluence, etc.)."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        email: Optional[str] = None,
        api_token: Optional[str] = None,
    ) -> None:
        self.base_url = (base_url or settings.atlassian_base_url).rstrip("/")
        self.email = email or settings.atlassian_email
        self.api_token = api_token or settings.atlassian_api_token
        self.auth = (self.email, self.api_token)
        logger.info(f"Initialized {self.__class__.__name__} for {self.base_url}")

    async def _get(self, path: str, params: Optional[Dict[str, Any]] = None, timeout: float = 30.0) -> httpx.Response:
        url = f"{self.base_url}{path}"
        async with httpx.AsyncClient() as client:
            response = await client.get(url, auth=self.auth, params=params, timeout=timeout)
        response.raise_for_status()
        return response

    async def _post(self, path: str, json: Optional[Dict[str, Any]] = None, timeout: float = 30.0) -> httpx.Response:
        url = f"{self.base_url}{path}"
        async with httpx.AsyncClient() as client:
            response = await client.post(url, auth=self.auth, json=json, timeout=timeout)
        response.raise_for_status()
        return response


