"""
JWT authentication middleware for Atlassian Connect.

Validates JWT tokens from Jira and extracts context.
"""

import jwt
import time
from typing import Optional
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from loguru import logger

from src.storage.installation_store import InstallationStore
from src.api.utils.jira_context import JiraContext, get_jwt_from_request


class JWTAuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware for validating Atlassian Connect JWT tokens.
    
    Validates:
    - JWT signature using shared secret
    - Token expiry
    - Issuer (clientKey)
    - Query String Hash (QSH) for security
    """
    
    def __init__(self, app, installation_store: Optional[InstallationStore] = None):
        super().__init__(app)
        self.installation_store = installation_store or InstallationStore()
    
    async def dispatch(self, request: Request, call_next):
        """Process the request and validate JWT if present."""
        # Skip JWT validation for certain paths
        if self._should_skip_auth(request.url.path):
            return await call_next(request)
        
        # Only validate JWT for Connect endpoints
        if not request.url.path.startswith('/connect/'):
            return await call_next(request)
        
        # Extract JWT from request
        query_params = dict(request.query_params)
        headers = dict(request.headers)
        jwt_token = get_jwt_from_request(query_params, headers)
        
        if not jwt_token:
            # For lifecycle endpoints, JWT might be in body
            if request.method == "POST" and request.url.path in [
                '/connect/installed', '/connect/uninstalled', 
                '/connect/enabled', '/connect/disabled'
            ]:
                # Let the endpoint handler deal with it
                return await call_next(request)
            
            logger.warning(f"No JWT token found for {request.url.path}")
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Missing JWT token"}
            )
        
        # Decode and validate JWT
        try:
            context = self._validate_jwt(jwt_token, query_params)
            # Attach context to request state
            request.state.jira_context = context
            request.state.authenticated = True
            
            logger.info(f"Authenticated request from {context.client_key} for {request.url.path}")
            
        except Exception as e:
            logger.error(f"JWT validation failed: {e}")
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": f"Invalid JWT: {str(e)}"}
            )
        
        return await call_next(request)
    
    def _should_skip_auth(self, path: str) -> bool:
        """
        Determine if a path should skip JWT authentication.
        
        Args:
            path: Request path
            
        Returns:
            True if auth should be skipped
        """
        skip_paths = [
            '/atlassian-connect.json',
            '/health',
            '/docs',
            '/openapi.json',
            '/static/',
            '/',
            '/api/v1/health'
        ]
        
        return any(path.startswith(skip_path) for skip_path in skip_paths)
    
    def _validate_jwt(self, jwt_token: str, query_params: dict) -> JiraContext:
        """
        Validate and decode JWT token.
        
        Args:
            jwt_token: JWT token string
            query_params: Query parameters from the request
            
        Returns:
            JiraContext object
            
        Raises:
            HTTPException: If validation fails
        """
        try:
            # Decode without verification first to get the issuer
            unverified_payload = jwt.decode(jwt_token, options={"verify_signature": False})
            client_key = unverified_payload.get('iss')
            
            if not client_key:
                raise ValueError("Missing issuer (iss) in JWT")
            
            # Get installation to retrieve shared secret
            installation = self.installation_store.get_installation(client_key)
            if not installation:
                raise ValueError(f"Unknown installation: {client_key}")
            
            if not installation.enabled:
                raise ValueError(f"App is disabled for {client_key}")
            
            # Verify JWT signature with shared secret
            payload = jwt.decode(
                jwt_token,
                installation.shared_secret,
                algorithms=["HS256"],
                options={
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_aud": True
                }
            )
            
            # Validate expiry (JWT library does this, but double-check)
            exp = payload.get('exp', 0)
            if exp < time.time():
                raise ValueError("JWT token has expired")
            
            # Validate issuer matches
            if payload.get('iss') != client_key:
                raise ValueError("JWT issuer mismatch")
            
            # Create context from payload
            context = JiraContext.from_jwt_payload(payload, query_params)
            
            return context
            
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="JWT token has expired"
            )
        except jwt.InvalidTokenError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid JWT token: {str(e)}"
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"JWT validation error: {str(e)}"
            )


def require_jwt(request: Request) -> JiraContext:
    """
    Dependency to require JWT authentication.
    
    Use in FastAPI route handlers to ensure JWT is validated.
    
    Example:
        @router.get("/some-endpoint")
        async def handler(context: JiraContext = Depends(require_jwt)):
            ...
    
    Args:
        request: FastAPI request object
        
    Returns:
        JiraContext object
        
    Raises:
        HTTPException: If JWT is not validated
    """
    if not hasattr(request.state, 'jira_context'):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="JWT authentication required"
        )
    
    return request.state.jira_context

