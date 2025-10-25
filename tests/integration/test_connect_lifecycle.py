"""
Integration tests for Atlassian Connect lifecycle endpoints.
"""

import pytest
import tempfile
import os
from fastapi.testclient import TestClient

from src.api.main import app
from src.storage.installation_store import InstallationStore


class TestConnectLifecycle:
    """Test Atlassian Connect lifecycle endpoints."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    @pytest.fixture
    def temp_store(self):
        """Create temporary installation store."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name
        
        # Override the default store
        from src.api.routes import connect
        original_store = connect.installation_store
        connect.installation_store = InstallationStore(storage_path=temp_path)
        
        yield connect.installation_store
        
        # Restore original
        connect.installation_store = original_store
        
        # Cleanup
        if os.path.exists(temp_path):
            os.remove(temp_path)
    
    @pytest.fixture
    def installation_payload(self):
        """Create sample installation payload."""
        return {
            "key": "com.womba.jira",
            "clientKey": "test-client-abc123",
            "publicKey": "public-key-data",
            "sharedSecret": "shared-secret-xyz789",
            "serverVersion": "8.20.0",
            "pluginsVersion": "1.0.0",
            "baseUrl": "https://test.atlassian.net",
            "productType": "jira",
            "description": "Test Company Jira",
            "eventType": "installed"
        }
    
    def test_installed_endpoint(self, client, temp_store, installation_payload):
        """Test app installation endpoint."""
        response = client.post("/connect/installed", json=installation_payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "installed successfully" in data["message"]
        
        # Verify installation was saved
        installation = temp_store.get_installation(installation_payload["clientKey"])
        assert installation is not None
        assert installation.client_key == installation_payload["clientKey"]
        assert installation.shared_secret == installation_payload["sharedSecret"]
        assert installation.base_url == installation_payload["baseUrl"]
        assert installation.enabled is True
    
    def test_uninstalled_endpoint(self, client, temp_store, installation_payload):
        """Test app uninstallation endpoint."""
        # First install
        client.post("/connect/installed", json=installation_payload)
        
        # Then uninstall
        response = client.post("/connect/uninstalled", json=installation_payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "uninstalled successfully" in data["message"]
        
        # Verify installation was removed
        installation = temp_store.get_installation(installation_payload["clientKey"])
        assert installation is None
    
    def test_uninstalled_nonexistent(self, client, installation_payload):
        """Test uninstalling non-existent installation."""
        response = client.post("/connect/uninstalled", json=installation_payload)
        
        # Should still return success (idempotent)
        assert response.status_code == 200
    
    def test_enabled_endpoint(self, client, temp_store, installation_payload):
        """Test app enabled endpoint."""
        # First install
        client.post("/connect/installed", json=installation_payload)
        
        # Disable it
        temp_store.update_enabled_status(installation_payload["clientKey"], False)
        
        # Enable it
        response = client.post("/connect/enabled", json=installation_payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        
        # Verify enabled status
        installation = temp_store.get_installation(installation_payload["clientKey"])
        assert installation.enabled is True
    
    def test_disabled_endpoint(self, client, temp_store, installation_payload):
        """Test app disabled endpoint."""
        # First install
        client.post("/connect/installed", json=installation_payload)
        
        # Disable it
        response = client.post("/connect/disabled", json=installation_payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        
        # Verify disabled status
        installation = temp_store.get_installation(installation_payload["clientKey"])
        assert installation.enabled is False
    
    def test_multiple_installations(self, client, temp_store):
        """Test multiple Jira instances can install."""
        payload1 = {
            "key": "com.womba.jira",
            "clientKey": "client-1",
            "sharedSecret": "secret-1",
            "serverVersion": "8.20.0",
            "pluginsVersion": "1.0.0",
            "baseUrl": "https://company1.atlassian.net",
            "productType": "jira",
            "description": "Company 1",
            "eventType": "installed"
        }
        
        payload2 = {
            "key": "com.womba.jira",
            "clientKey": "client-2",
            "sharedSecret": "secret-2",
            "serverVersion": "8.20.0",
            "pluginsVersion": "1.0.0",
            "baseUrl": "https://company2.atlassian.net",
            "productType": "jira",
            "description": "Company 2",
            "eventType": "installed"
        }
        
        # Install both
        response1 = client.post("/connect/installed", json=payload1)
        response2 = client.post("/connect/installed", json=payload2)
        
        assert response1.status_code == 200
        assert response2.status_code == 200
        
        # Verify both exist
        inst1 = temp_store.get_installation("client-1")
        inst2 = temp_store.get_installation("client-2")
        
        assert inst1 is not None
        assert inst2 is not None
        assert inst1.client_key != inst2.client_key
    
    def test_reinstallation_updates_secret(self, client, temp_store, installation_payload):
        """Test reinstalling updates the shared secret."""
        # First install
        client.post("/connect/installed", json=installation_payload)
        
        # Modify payload with new secret
        installation_payload["sharedSecret"] = "new-secret-abc"
        
        # Reinstall
        response = client.post("/connect/installed", json=installation_payload)
        
        assert response.status_code == 200
        
        # Verify secret was updated
        installation = temp_store.get_installation(installation_payload["clientKey"])
        assert installation.shared_secret == "new-secret-abc"


class TestConnectDescriptor:
    """Test serving the Atlassian Connect descriptor."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    def test_descriptor_endpoint(self, client):
        """Test /atlassian-connect.json endpoint."""
        response = client.get("/atlassian-connect.json")
        
        assert response.status_code == 200
        descriptor = response.json()
        
        # Verify required fields
        assert descriptor["key"] == "com.womba.jira"
        assert descriptor["name"] == "Womba - AI Test Generator"
        assert "baseUrl" in descriptor
        assert descriptor["authentication"]["type"] == "jwt"
        
        # Verify lifecycle hooks
        assert "lifecycle" in descriptor
        assert descriptor["lifecycle"]["installed"] == "/connect/installed"
        assert descriptor["lifecycle"]["uninstalled"] == "/connect/uninstalled"
        
        # Verify modules
        assert "modules" in descriptor
        assert "jiraIssueGlances" in descriptor["modules"]
        assert "webPanels" in descriptor["modules"]
        assert "generalPages" in descriptor["modules"]
        assert "adminPages" in descriptor["modules"]
    
    def test_descriptor_baseurl_override(self, client, monkeypatch):
        """Test baseUrl can be overridden with environment variable."""
        monkeypatch.setenv("WOMBA_BASE_URL", "https://custom.example.com")
        
        response = client.get("/atlassian-connect.json")
        
        assert response.status_code == 200
        descriptor = response.json()
        assert descriptor["baseUrl"] == "https://custom.example.com"

