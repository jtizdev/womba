"""
MCP Context Provider for passing structured context to AI.

This provides better, more structured context to the AI model via MCP protocol.
"""

import json
from typing import Dict, List, Optional
from loguru import logger

try:
    from mcp.server import Server
    from mcp.types import Resource, TextContent
    MCP_AVAILABLE = True
except ImportError:
    logger.warning("MCP not installed. Install with: pip install mcp")
    MCP_AVAILABLE = False
    Resource = Dict  # Fallback type
    TextContent = Dict


class WombaMCPProvider:
    """
    Provides Jira/Confluence/Zephyr context to AI via MCP.
    
    Benefits:
    - Structured, validated context
    - Better prompts
    - Easier debugging
    - AI can read resources directly
    """
    
    def __init__(self):
        self.enabled = MCP_AVAILABLE
        if not self.enabled:
            logger.warning("MCP disabled - package not available")
    
    async def get_story_resource(
        self, 
        story_key: str, 
        context: Dict
    ) -> Optional[Resource]:
        """
        Convert story context to MCP Resource.
        
        Args:
            story_key: Jira story key
            context: Story context dictionary
            
        Returns:
            MCP Resource object (or dict if MCP not available)
        """
        if not self.enabled:
            return None
        
        # Format context as structured JSON
        formatted_context = self._format_context(context)
        
        resource = {
            "uri": f"womba://story/{story_key}",
            "name": f"Jira Story {story_key}",
            "description": context.main_story.summary if hasattr(context, 'main_story') else story_key,
            "mimeType": "application/json",
            "text": json.dumps(formatted_context, indent=2)
        }
        
        logger.debug(f"Created MCP resource for {story_key}")
        return resource
    
    def _format_context(self, context: Dict) -> Dict:
        """
        Format context into clean JSON structure for MCP.
        
        Args:
            context: Raw story context
            
        Returns:
            Formatted context dictionary
        """
        formatted = {
            "story": {
                "key": context.main_story.key if hasattr(context, 'main_story') else "UNKNOWN",
                "summary": context.main_story.summary if hasattr(context, 'main_story') else "",
                "description": context.main_story.description if hasattr(context, 'main_story') else "",
                "type": context.main_story.story_type if hasattr(context, 'main_story') else "",
                "status": context.main_story.status if hasattr(context, 'main_story') else "",
                "priority": context.main_story.priority if hasattr(context, 'main_story') else ""
            },
            "subtasks": [
                {
                    "key": st.key,
                    "summary": st.summary,
                    "status": st.status
                }
                for st in context.get('subtasks', [])
            ],
            "confluence_docs": [
                {
                    "id": doc.get('id'),
                    "title": doc.get('title'),
                    "excerpt": doc.get('excerpt', '')[:200]  # First 200 chars
                }
                for doc in context.get('confluence_docs', [])
            ],
            "comments_count": len(context.get('story_comments', [])),
            "linked_issues_count": len(context.get('linked_stories', []))
        }
        
        return formatted
    
    async def get_existing_tests_resource(
        self, 
        existing_tests: List[Dict]
    ) -> Optional[Resource]:
        """
        Convert existing Zephyr tests to MCP Resource.
        
        Args:
            existing_tests: List of existing test dictionaries
            
        Returns:
            MCP Resource with existing tests
        """
        if not self.enabled or not existing_tests:
            return None
        
        # Limit to most relevant tests
        formatted_tests = [
            {
                "key": test.get('key', ''),
                "name": test.get('name', ''),
                "objective": test.get('objective', '')[:150]  # Truncate long descriptions
            }
            for test in existing_tests[:20]  # Top 20 most relevant
        ]
        
        resource = {
            "uri": "womba://existing-tests",
            "name": "Existing Test Cases",
            "description": f"{len(existing_tests)} existing tests in Zephyr",
            "mimeType": "application/json",
            "text": json.dumps(formatted_tests, indent=2)
        }
        
        return resource
    
    async def get_folder_structure_resource(
        self,
        folder_structure: List[Dict]
    ) -> Optional[Resource]:
        """
        Convert Zephyr folder structure to MCP Resource.
        
        Args:
            folder_structure: Zephyr folder hierarchy
            
        Returns:
            MCP Resource with folder structure
        """
        if not self.enabled or not folder_structure:
            return None
        
        # Simplify folder structure
        simplified = [
            {
                "name": folder.get('name', ''),
                "id": folder.get('id', ''),
                "subfolders": [
                    sf.get('name', '') 
                    for sf in folder.get('folders', [])[:5]
                ]
            }
            for folder in folder_structure[:15]  # Top 15 folders
        ]
        
        resource = {
            "uri": "womba://folders",
            "name": "Zephyr Folder Structure",
            "description": "Available test folders for organization",
            "mimeType": "application/json",
            "text": json.dumps(simplified, indent=2)
        }
        
        return resource
    
    async def get_all_resources(
        self,
        story_key: str,
        context: Dict,
        existing_tests: List[Dict],
        folder_structure: List[Dict]
    ) -> List[Optional[Resource]]:
        """
        Get all MCP resources for AI consumption.
        
        Args:
            story_key: Jira story key
            context: Story context
            existing_tests: Existing test cases
            folder_structure: Zephyr folders
            
        Returns:
            List of MCP resources
        """
        if not self.enabled:
            logger.debug("MCP disabled, returning empty resources")
            return []
        
        resources = []
        
        # Story resource
        story_resource = await self.get_story_resource(story_key, context)
        if story_resource:
            resources.append(story_resource)
        
        # Existing tests resource
        tests_resource = await self.get_existing_tests_resource(existing_tests)
        if tests_resource:
            resources.append(tests_resource)
        
        # Folder structure resource
        folders_resource = await self.get_folder_structure_resource(folder_structure)
        if folders_resource:
            resources.append(folders_resource)
        
        logger.info(f"Created {len(resources)} MCP resources")
        return resources

