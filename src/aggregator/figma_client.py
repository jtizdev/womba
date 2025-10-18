"""
Figma client for extracting UI design information.
"""

import httpx
from typing import List, Dict, Optional
from loguru import logger

from src.config.settings import settings


class FigmaClient:
    """
    Client for interacting with Figma API to extract UI design information.
    """

    def __init__(self, access_token: Optional[str] = None):
        self.access_token = access_token or settings.figma_access_token
        self.headers = {"X-Figma-Token": self.access_token} if self.access_token else {}

    async def get_file_info(self, file_key: str) -> Optional[Dict]:
        """
        Get Figma file information including frames, components, and screens.
        
        Args:
            file_key: Figma file key (from URL)
            
        Returns:
            File information with UI elements
        """
        if not self.access_token:
            logger.warning("Figma access token not configured, skipping Figma integration")
            return None
        
        url = f"https://api.figma.com/v1/files/{file_key}"
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, headers=self.headers)
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.warning(f"Failed to fetch Figma file {file_key}: {e}")
            return None

    async def extract_ui_elements_from_file(self, file_key: str) -> List[Dict]:
        """
        Extract UI elements (buttons, forms, screens) from Figma file.
        
        Args:
            file_key: Figma file key
            
        Returns:
            List of UI elements with names, types, and context
        """
        file_info = await self.get_file_info(file_key)
        if not file_info:
            return []
        
        ui_elements = []
        
        # Parse document structure
        document = file_info.get('document', {})
        self._extract_elements_recursive(document, ui_elements)
        
        logger.info(f"Extracted {len(ui_elements)} UI elements from Figma")
        return ui_elements

    def _extract_elements_recursive(self, node: Dict, elements: List[Dict], parent_name: str = ""):
        """
        Recursively extract UI elements from Figma node tree.
        
        Args:
            node: Figma node
            elements: List to append elements to
            parent_name: Parent screen/frame name for context
        """
        if not isinstance(node, dict):
            return
        
        node_type = node.get('type', '')
        node_name = node.get('name', '')
        
        # Capture screens/frames
        if node_type in ['FRAME', 'COMPONENT']:
            parent_name = node_name
            elements.append({
                'type': 'screen' if node_type == 'FRAME' else 'component',
                'name': node_name,
                'parent': parent_name
            })
        
        # Capture interactive elements
        elif node_type in ['INSTANCE', 'RECTANGLE', 'TEXT']:
            # Look for button-like elements
            if any(keyword in node_name.lower() for keyword in ['button', 'btn', 'cta', 'submit', 'save', 'cancel', 'delete']):
                elements.append({
                    'type': 'button',
                    'name': node_name,
                    'parent': parent_name
                })
            # Look for input fields
            elif any(keyword in node_name.lower() for keyword in ['input', 'field', 'textbox', 'search', 'filter']):
                elements.append({
                    'type': 'input',
                    'name': node_name,
                    'parent': parent_name
                })
            # Look for tabs/navigation
            elif any(keyword in node_name.lower() for keyword in ['tab', 'nav', 'menu', 'link']):
                elements.append({
                    'type': 'navigation',
                    'name': node_name,
                    'parent': parent_name
                })
        
        # Recurse into children
        for child in node.get('children', []):
            self._extract_elements_recursive(child, elements, parent_name)

    async def find_figma_links_in_text(self, text: str) -> List[str]:
        """
        Extract Figma file keys from text (URLs).
        
        Args:
            text: Text that may contain Figma URLs
            
        Returns:
            List of Figma file keys
        """
        import re
        
        # Match Figma URLs: https://www.figma.com/file/FILE_KEY/...
        pattern = r'https://(?:www\.)?figma\.com/file/([a-zA-Z0-9]+)'
        matches = re.findall(pattern, text)
        
        return list(set(matches))  # Remove duplicates

