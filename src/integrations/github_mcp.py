"""Utility helpers for integrating MCP with GitHub repositories."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Any, Dict, Optional

from loguru import logger

from src.config.settings import settings

try:
    import requests
except ImportError:  # pragma: no cover - optional dependency
    requests = None


class GitHubMCPError(Exception):
    """Raised when the GitHub MCP connector encounters an unrecoverable error."""


@dataclass
class GitHubFile:
    """Simple container for GitHub file content."""

    path: str
    content: str
    sha: Optional[str] = None
    encoding: Optional[str] = None
    download_url: Optional[str] = None


class GitHubMCPConnector:
    """Minimal helper for routing MCP file requests through the GitHub REST API."""

    api_base = "https://api.github.com"

    def __init__(
        self,
        token: Optional[str] = None,
    ) -> None:
        self.token = token or settings.github_token
        if requests is None:
            logger.warning("requests package not installed; GitHub MCP connector is disabled")

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------
    def is_available(self) -> bool:
        """Return True if connector can make authenticated GitHub requests."""

        available = requests is not None and bool(self.token)
        if not available:
            logger.debug("GitHub MCP connector unavailable: token missing or requests not installed")
        return available

    def fetch_file(
        self,
        owner: str,
        repo: str,
        path: str,
        ref: str = "main",
    ) -> GitHubFile:
        """Fetch a single file from GitHub and decode its content."""

        if not self.is_available():
            raise GitHubMCPError("GitHub MCP connector is not available")

        url = f"{self.api_base}/repos/{owner}/{repo}/contents/{path}"
        headers = self._build_headers()
        params = {"ref": ref}

        response = requests.get(url, headers=headers, params=params, timeout=30)
        if response.status_code != 200:
            raise GitHubMCPError(f"GitHub API error {response.status_code}: {response.text}")

        payload = response.json()
        content = payload.get("content", "")
        encoding = payload.get("encoding", "utf-8")
        if encoding == "base64":
            decoded = base64.b64decode(content).decode("utf-8", errors="ignore")
        else:
            decoded = content

        return GitHubFile(
            path=payload.get("path", path),
            content=decoded,
            sha=payload.get("sha"),
            encoding=encoding,
            download_url=payload.get("download_url"),
        )

    def list_tree(
        self,
        owner: str,
        repo: str,
        ref: str = "main",
        recursive: bool = True,
    ) -> Dict[str, Any]:
        """Return the repository tree for use with MCP file browsing."""

        if not self.is_available():
            raise GitHubMCPError("GitHub MCP connector is not available")

        url = f"{self.api_base}/repos/{owner}/{repo}/git/trees/{ref}"
        if recursive:
            url += "?recursive=1"
        headers = self._build_headers()

        response = requests.get(url, headers=headers, timeout=30)
        if response.status_code != 200:
            raise GitHubMCPError(f"GitHub API error {response.status_code}: {response.text}")

        return response.json()

    def create_mcp_tool_spec(self, owner: str, repo: str, ref: str = "main") -> Dict[str, Any]:
        """Generate a minimal MCP tool specification for GitHub file retrieval."""

        spec = {
            "name": "github_file_fetch",
            "description": f"Fetch file contents from {owner}/{repo}@{ref}",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path within the repository to fetch",
                    },
                },
                "required": ["path"],
            },
        }
        logger.debug("Generated MCP tool spec: %s", json.dumps(spec))
        return spec

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _build_headers(self) -> Dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "Womba-MCP-GitHub/1.0",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers


