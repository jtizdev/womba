"""
Utilities for extracting and validating Jira context from Connect requests.
"""

from typing import Optional
from urllib.parse import urlparse, parse_qs
from loguru import logger


class JiraContext:
    """
    Represents the context from a Jira Connect request.
    
    Context is passed via query parameters when Jira loads iframe modules.
    """
    
    def __init__(
        self,
        client_key: str,
        base_url: str,
        user_key: Optional[str] = None,
        user_account_id: Optional[str] = None,
        issue_key: Optional[str] = None,
        project_key: Optional[str] = None,
        project_id: Optional[str] = None
    ):
        self.client_key = client_key
        self.base_url = base_url
        self.user_key = user_key
        self.user_account_id = user_account_id
        self.issue_key = issue_key
        self.project_key = project_key
        self.project_id = project_id
    
    @classmethod
    def from_jwt_payload(cls, payload: dict, query_params: Optional[dict] = None) -> "JiraContext":
        """
        Create JiraContext from decoded JWT payload and query parameters.
        
        Args:
            payload: Decoded JWT payload
            query_params: Additional query parameters from the request
            
        Returns:
            JiraContext object
        """
        # Extract from JWT
        client_key = payload.get('iss', '')
        base_url = payload.get('aud', [''])[0] if isinstance(payload.get('aud'), list) else payload.get('aud', '')
        
        # User context
        user_context = payload.get('context', {}).get('user', {})
        user_key = user_context.get('userKey')
        user_account_id = user_context.get('accountId')
        
        # Additional context from query params
        issue_key = None
        project_key = None
        project_id = None
        
        if query_params:
            issue_key = query_params.get('issueKey')
            project_key = query_params.get('projectKey')
            project_id = query_params.get('projectId')
        
        return cls(
            client_key=client_key,
            base_url=base_url,
            user_key=user_key,
            user_account_id=user_account_id,
            issue_key=issue_key,
            project_key=project_key,
            project_id=project_id
        )
    
    def __repr__(self) -> str:
        return f"JiraContext(client_key={self.client_key}, issue_key={self.issue_key}, project_key={self.project_key})"


def extract_query_params(url: str) -> dict:
    """
    Extract query parameters from a URL.
    
    Args:
        url: Full URL or query string
        
    Returns:
        Dictionary of query parameters (single values, not lists)
    """
    if '?' in url:
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
    else:
        params = parse_qs(url)
    
    # Convert lists to single values
    return {k: v[0] if v else None for k, v in params.items()}


def get_jwt_from_request(query_params: dict, headers: dict) -> Optional[str]:
    """
    Extract JWT token from request query parameters or headers.
    
    Args:
        query_params: Query parameters from the request
        headers: Headers from the request
        
    Returns:
        JWT token string or None
    """
    # Try query parameter first (most common for iframe modules)
    jwt_token = query_params.get('jwt')
    
    # Try Authorization header
    if not jwt_token:
        auth_header = headers.get('authorization', headers.get('Authorization', ''))
        if auth_header.startswith('JWT '):
            jwt_token = auth_header[4:]
        elif auth_header.startswith('Bearer '):
            jwt_token = auth_header[7:]
    
    return jwt_token

