"""
Unit tests for JWT authentication middleware.
"""

import pytest
import jwt
import time
from datetime import datetime, timedelta

from src.api.middleware.jwt_auth import JWTAuthMiddleware, require_jwt
from src.storage.installation_store import InstallationStore
from src.models.installation import Installation
from fastapi import FastAPI, Request, HTTPException
from fastapi.testclient import TestClient
import tempfile


class TestJWTAuthMiddleware:
    """Test JWT authentication middleware."""
    
    @pytest.fixture
    def temp_store(self):
        """Create temporary installation store."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name
        
        store = InstallationStore(storage_path=temp_path)
        yield store
        
        # Cleanup
        import os
        if os.path.exists(temp_path):
            os.remove(temp_path)
    
    @pytest.fixture
    def test_app(self, temp_store):
        """Create test FastAPI app with JWT middleware."""
        app = FastAPI()
        
        # Add JWT middleware
        app.add_middleware(JWTAuthMiddleware, installation_store=temp_store)
        
        # Test endpoint
        @app.get("/connect/test")
        async def test_endpoint(request: Request):
            if hasattr(request.state, 'jira_context'):
                return {"authenticated": True, "client_key": request.state.jira_context.client_key}
            return {"authenticated": False}
        
        @app.get("/public")
        async def public_endpoint():
            return {"public": True}
        
        return app
    
    @pytest.fixture
    def test_installation(self, temp_store):
        """Create test installation."""
        installation = Installation(
            client_key="test-client-123",
            shared_secret="test-secret-key",
            base_url="https://test.atlassian.net",
            enabled=True
        )
        temp_store.save_installation(installation)
        return installation
    
    def create_jwt_token(self, client_key: str, shared_secret: str, expired: bool = False) -> str:
        """Helper to create JWT token."""
        exp_time = int(time.time()) - 3600 if expired else int(time.time()) + 3600
        
        payload = {
            "iss": client_key,
            "aud": ["https://test.atlassian.net"],
            "exp": exp_time,
            "iat": int(time.time()),
            "context": {
                "user": {
                    "accountId": "test-user-123"
                }
            }
        }
        
        return jwt.encode(payload, shared_secret, algorithm="HS256")
    
    def test_public_endpoint_no_jwt(self, test_app):
        """Test that public endpoints don't require JWT."""
        client = TestClient(test_app)
        response = client.get("/public")
        
        assert response.status_code == 200
        assert response.json() == {"public": True}
    
    def test_connect_endpoint_valid_jwt(self, test_app, test_installation):
        """Test Connect endpoint with valid JWT."""
        client = TestClient(test_app)
        
        # Create valid JWT
        token = self.create_jwt_token(
            test_installation.client_key,
            test_installation.shared_secret
        )
        
        # Make request with JWT in query
        response = client.get(f"/connect/test?jwt={token}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["authenticated"] is True
        assert data["client_key"] == test_installation.client_key
    
    def test_connect_endpoint_missing_jwt(self, test_app):
        """Test Connect endpoint without JWT."""
        client = TestClient(test_app)
        response = client.get("/connect/test")
        
        assert response.status_code == 401
        assert "Missing JWT token" in response.json()["detail"]
    
    def test_connect_endpoint_invalid_jwt(self, test_app, test_installation):
        """Test Connect endpoint with invalid JWT."""
        client = TestClient(test_app)
        
        # Create JWT with wrong secret
        token = self.create_jwt_token(
            test_installation.client_key,
            "wrong-secret"
        )
        
        response = client.get(f"/connect/test?jwt={token}")
        
        assert response.status_code == 401
        assert "Invalid JWT" in response.json()["detail"]
    
    def test_connect_endpoint_expired_jwt(self, test_app, test_installation):
        """Test Connect endpoint with expired JWT."""
        client = TestClient(test_app)
        
        # Create expired JWT
        token = self.create_jwt_token(
            test_installation.client_key,
            test_installation.shared_secret,
            expired=True
        )
        
        response = client.get(f"/connect/test?jwt={token}")
        
        assert response.status_code == 401
        assert "expired" in response.json()["detail"].lower()
    
    def test_connect_endpoint_unknown_installation(self, test_app):
        """Test Connect endpoint with JWT from unknown client."""
        client = TestClient(test_app)
        
        # Create JWT for non-existent client
        token = self.create_jwt_token("unknown-client", "some-secret")
        
        response = client.get(f"/connect/test?jwt={token}")
        
        assert response.status_code == 401
        assert "Unknown installation" in response.json()["detail"]
    
    def test_connect_endpoint_disabled_installation(self, test_app, temp_store):
        """Test Connect endpoint with disabled installation."""
        client = TestClient(test_app)
        
        # Create disabled installation
        installation = Installation(
            client_key="disabled-client",
            shared_secret="secret",
            base_url="https://test.atlassian.net",
            enabled=False
        )
        temp_store.save_installation(installation)
        
        token = self.create_jwt_token("disabled-client", "secret")
        response = client.get(f"/connect/test?jwt={token}")
        
        assert response.status_code == 401
        assert "disabled" in response.json()["detail"].lower()
    
    def test_jwt_in_authorization_header(self, test_app, test_installation):
        """Test JWT in Authorization header."""
        client = TestClient(test_app)
        
        token = self.create_jwt_token(
            test_installation.client_key,
            test_installation.shared_secret
        )
        
        # Send JWT in header
        response = client.get(
            "/connect/test",
            headers={"Authorization": f"JWT {token}"}
        )
        
        assert response.status_code == 200
        assert response.json()["authenticated"] is True


class TestRequireJWT:
    """Test require_jwt dependency."""
    
    def test_require_jwt_with_context(self):
        """Test require_jwt when context exists."""
        from src.api.utils.jira_context import JiraContext
        
        # Create mock request with context
        class MockRequest:
            class State:
                jira_context = JiraContext(
                    client_key="test-client",
                    base_url="https://test.atlassian.net"
                )
            state = State()
        
        request = MockRequest()
        context = require_jwt(request)
        
        assert context.client_key == "test-client"
    
    def test_require_jwt_without_context(self):
        """Test require_jwt when context missing."""
        # Create mock request without context
        class MockRequest:
            class State:
                pass
            state = State()
        
        request = MockRequest()
        
        with pytest.raises(HTTPException) as exc_info:
            require_jwt(request)
        
        assert exc_info.value.status_code == 401
        assert "JWT authentication required" in str(exc_info.value.detail)

