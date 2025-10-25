"""
Unit tests for Installation storage.
"""

import pytest
import tempfile
import os
from datetime import datetime

from src.models.installation import Installation
from src.storage.installation_store import InstallationStore


class TestInstallationStore:
    """Test installation storage operations."""
    
    @pytest.fixture
    def temp_storage(self):
        """Create temporary storage for testing."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name
        
        yield temp_path
        
        # Cleanup
        if os.path.exists(temp_path):
            os.remove(temp_path)
    
    @pytest.fixture
    def store(self, temp_storage):
        """Create InstallationStore with temp storage."""
        return InstallationStore(storage_path=temp_storage)
    
    @pytest.fixture
    def sample_installation(self):
        """Create sample installation."""
        return Installation(
            client_key="test-client-123",
            shared_secret="super-secret-key",
            base_url="https://test.atlassian.net",
            product_type="jira",
            description="Test Instance",
            enabled=True
        )
    
    def test_save_installation(self, store, sample_installation):
        """Test saving an installation."""
        success = store.save_installation(sample_installation)
        
        assert success is True
        
        # Verify it was saved
        retrieved = store.get_installation(sample_installation.client_key)
        assert retrieved is not None
        assert retrieved.client_key == sample_installation.client_key
        assert retrieved.shared_secret == sample_installation.shared_secret
    
    def test_get_installation_not_found(self, store):
        """Test getting non-existent installation."""
        installation = store.get_installation("non-existent")
        assert installation is None
    
    def test_delete_installation(self, store, sample_installation):
        """Test deleting an installation."""
        # Save first
        store.save_installation(sample_installation)
        
        # Delete
        success = store.delete_installation(sample_installation.client_key)
        assert success is True
        
        # Verify it's gone
        retrieved = store.get_installation(sample_installation.client_key)
        assert retrieved is None
    
    def test_delete_nonexistent_installation(self, store):
        """Test deleting non-existent installation."""
        success = store.delete_installation("non-existent")
        assert success is False
    
    def test_list_installations(self, store):
        """Test listing all installations."""
        # Create multiple installations
        inst1 = Installation(
            client_key="client-1",
            shared_secret="secret-1",
            base_url="https://test1.atlassian.net"
        )
        inst2 = Installation(
            client_key="client-2",
            shared_secret="secret-2",
            base_url="https://test2.atlassian.net"
        )
        
        store.save_installation(inst1)
        store.save_installation(inst2)
        
        installations = store.list_installations()
        assert len(installations) == 2
        assert any(i.client_key == "client-1" for i in installations)
        assert any(i.client_key == "client-2" for i in installations)
    
    def test_update_enabled_status(self, store, sample_installation):
        """Test updating enabled status."""
        # Save installation
        store.save_installation(sample_installation)
        
        # Disable it
        success = store.update_enabled_status(sample_installation.client_key, False)
        assert success is True
        
        # Verify status changed
        retrieved = store.get_installation(sample_installation.client_key)
        assert retrieved.enabled is False
        
        # Enable it again
        success = store.update_enabled_status(sample_installation.client_key, True)
        assert success is True
        
        retrieved = store.get_installation(sample_installation.client_key)
        assert retrieved.enabled is True
    
    def test_update_enabled_status_nonexistent(self, store):
        """Test updating status of non-existent installation."""
        success = store.update_enabled_status("non-existent", True)
        assert success is False
    
    def test_installation_persistence(self, temp_storage, sample_installation):
        """Test that installations persist across store instances."""
        # Save with first store
        store1 = InstallationStore(storage_path=temp_storage)
        store1.save_installation(sample_installation)
        
        # Load with second store
        store2 = InstallationStore(storage_path=temp_storage)
        retrieved = store2.get_installation(sample_installation.client_key)
        
        assert retrieved is not None
        assert retrieved.client_key == sample_installation.client_key
        assert retrieved.shared_secret == sample_installation.shared_secret

