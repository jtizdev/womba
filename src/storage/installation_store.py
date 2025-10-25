"""
Storage for Atlassian Connect installation data.

Stores installation credentials (clientKey, sharedSecret) for each Jira instance.
Uses JSON file storage for simplicity (can be upgraded to database for production).
"""

import json
import os
from pathlib import Path
from typing import Dict, Optional
from loguru import logger

from src.models.installation import Installation


class InstallationStore:
    """
    Manages storage and retrieval of Atlassian Connect installation data.
    
    Each Jira instance that installs the app gets an entry with:
    - client_key: Unique identifier
    - shared_secret: For JWT signing
    - base_url: Jira instance URL
    """
    
    def __init__(self, storage_path: Optional[str] = None):
        """
        Initialize the installation store.
        
        Args:
            storage_path: Path to JSON storage file. Defaults to ./data/installations.json
        """
        if storage_path is None:
            # Default to data directory in project root
            data_dir = Path(__file__).parent.parent.parent / "data"
            data_dir.mkdir(exist_ok=True)
            storage_path = str(data_dir / "installations.json")
        
        self.storage_path = storage_path
        self._ensure_storage_exists()
    
    def _ensure_storage_exists(self):
        """Ensure the storage file exists."""
        if not os.path.exists(self.storage_path):
            self._save_data({})
            logger.info(f"Created installations storage at {self.storage_path}")
    
    def _load_data(self) -> Dict[str, dict]:
        """Load all installations from storage."""
        try:
            with open(self.storage_path, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError) as e:
            logger.warning(f"Failed to load installations: {e}. Returning empty dict.")
            return {}
    
    def _save_data(self, data: Dict[str, dict]):
        """Save all installations to storage."""
        try:
            with open(self.storage_path, 'w') as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save installations: {e}")
            raise
    
    def save_installation(self, installation: Installation) -> bool:
        """
        Save or update an installation.
        
        Args:
            installation: Installation object to save
            
        Returns:
            True if successful
        """
        try:
            data = self._load_data()
            data[installation.client_key] = installation.model_dump(mode='json')
            self._save_data(data)
            logger.info(f"Saved installation for {installation.client_key}")
            return True
        except Exception as e:
            logger.error(f"Failed to save installation {installation.client_key}: {e}")
            return False
    
    def get_installation(self, client_key: str) -> Optional[Installation]:
        """
        Retrieve an installation by client key.
        
        Args:
            client_key: Unique Jira instance identifier
            
        Returns:
            Installation object or None if not found
        """
        try:
            data = self._load_data()
            if client_key in data:
                return Installation(**data[client_key])
            return None
        except Exception as e:
            logger.error(f"Failed to get installation {client_key}: {e}")
            return None
    
    def delete_installation(self, client_key: str) -> bool:
        """
        Delete an installation.
        
        Args:
            client_key: Unique Jira instance identifier
            
        Returns:
            True if successful
        """
        try:
            data = self._load_data()
            if client_key in data:
                del data[client_key]
                self._save_data(data)
                logger.info(f"Deleted installation for {client_key}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to delete installation {client_key}: {e}")
            return False
    
    def list_installations(self) -> list[Installation]:
        """
        List all installations.
        
        Returns:
            List of Installation objects
        """
        try:
            data = self._load_data()
            return [Installation(**inst_data) for inst_data in data.values()]
        except Exception as e:
            logger.error(f"Failed to list installations: {e}")
            return []
    
    def update_enabled_status(self, client_key: str, enabled: bool) -> bool:
        """
        Update the enabled status of an installation.
        
        Args:
            client_key: Unique Jira instance identifier
            enabled: Whether the app is enabled
            
        Returns:
            True if successful
        """
        try:
            installation = self.get_installation(client_key)
            if installation:
                installation.enabled = enabled
                return self.save_installation(installation)
            return False
        except Exception as e:
            logger.error(f"Failed to update enabled status for {client_key}: {e}")
            return False

