"""
Unit tests for fix version extraction and folder suggestion functionality.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from src.aggregator.jira_client import JiraClient
from src.models.story import JiraStory


class TestFixVersionExtraction:
    """Test suite for fix version extraction from Jira issues."""

    def test_parse_issue_extracts_fix_versions(self):
        """Test that _parse_issue correctly extracts fixVersions."""
        issue_data = {
            "key": "PLAT-12345",
            "fields": {
                "summary": "Test story",
                "description": "Test description",
                "issuetype": {"name": "Story"},
                "status": {"name": "In Progress"},
                "priority": {"name": "High"},
                "reporter": {"emailAddress": "test@example.com"},
                "created": "2024-01-01T00:00:00.000+0000",
                "updated": "2024-01-02T00:00:00.000+0000",
                "labels": [],
                "components": [],
                "attachment": [],
                "issuelinks": [],
                "fixVersions": [
                    {"name": "Platform MNG - Dec-7th (5.2550.X)"},
                    {"name": "Platform MNG - Dec-14th (5.2551.X)"}
                ]
            }
        }

        client = JiraClient()
        story = client._parse_issue(issue_data)

        assert story.fix_versions is not None
        assert len(story.fix_versions) == 2
        assert "Platform MNG - Dec-7th (5.2550.X)" in story.fix_versions
        assert "Platform MNG - Dec-14th (5.2551.X)" in story.fix_versions

    def test_parse_issue_empty_fix_versions(self):
        """Test that _parse_issue handles empty fixVersions."""
        issue_data = {
            "key": "PLAT-12345",
            "fields": {
                "summary": "Test story",
                "description": "Test description",
                "issuetype": {"name": "Story"},
                "status": {"name": "In Progress"},
                "priority": {"name": "High"},
                "reporter": {"emailAddress": "test@example.com"},
                "created": "2024-01-01T00:00:00.000+0000",
                "updated": "2024-01-02T00:00:00.000+0000",
                "labels": [],
                "components": [],
                "attachment": [],
                "issuelinks": [],
                "fixVersions": []
            }
        }

        client = JiraClient()
        story = client._parse_issue(issue_data)

        assert story.fix_versions is not None
        assert len(story.fix_versions) == 0

    def test_parse_issue_missing_fix_versions(self):
        """Test that _parse_issue handles missing fixVersions field."""
        issue_data = {
            "key": "PLAT-12345",
            "fields": {
                "summary": "Test story",
                "description": "Test description",
                "issuetype": {"name": "Story"},
                "status": {"name": "In Progress"},
                "priority": {"name": "High"},
                "reporter": {"emailAddress": "test@example.com"},
                "created": "2024-01-01T00:00:00.000+0000",
                "updated": "2024-01-02T00:00:00.000+0000",
                "labels": [],
                "components": [],
                "attachment": [],
                "issuelinks": []
                # No fixVersions field
            }
        }

        client = JiraClient()
        story = client._parse_issue(issue_data)

        assert story.fix_versions is not None
        assert len(story.fix_versions) == 0

    def test_parse_sdk_issue_extracts_fix_versions(self):
        """Test that _parse_sdk_issue correctly extracts fixVersions from SDK Issue object."""
        # Create a mock SDK Issue object
        mock_issue = MagicMock()
        mock_issue.key = "PLAT-12345"
        mock_issue.fields.summary = "Test story"
        mock_issue.fields.description = None
        mock_issue.fields.issuetype.name = "Story"
        mock_issue.fields.status.name = "In Progress"
        mock_issue.fields.priority.name = "High"
        mock_issue.fields.assignee = None
        mock_issue.fields.reporter.displayName = "Test User"
        mock_issue.fields.created = "2024-01-01T00:00:00.000+0000"
        mock_issue.fields.updated = "2024-01-02T00:00:00.000+0000"
        mock_issue.fields.labels = []
        mock_issue.fields.components = []
        mock_issue.fields.attachment = []
        mock_issue.fields.issuelinks = []
        
        # Mock fix versions
        mock_version1 = MagicMock()
        mock_version1.name = "Platform MNG - Dec-7th (5.2550.X)"
        mock_version2 = MagicMock()
        mock_version2.name = "Platform MNG - Dec-14th (5.2551.X)"
        mock_issue.fields.fixVersions = [mock_version1, mock_version2]
        
        # Mock renderedFields
        mock_issue.renderedFields = MagicMock()
        mock_issue.renderedFields.description = None

        client = JiraClient()
        story = client._parse_sdk_issue(mock_issue)

        assert story.fix_versions is not None
        assert len(story.fix_versions) == 2
        assert "Platform MNG - Dec-7th (5.2550.X)" in story.fix_versions
        assert "Platform MNG - Dec-14th (5.2551.X)" in story.fix_versions

    def test_parse_sdk_issue_empty_fix_versions(self):
        """Test that _parse_sdk_issue handles empty fixVersions."""
        mock_issue = MagicMock()
        mock_issue.key = "PLAT-12345"
        mock_issue.fields.summary = "Test story"
        mock_issue.fields.description = None
        mock_issue.fields.issuetype.name = "Story"
        mock_issue.fields.status.name = "In Progress"
        mock_issue.fields.priority.name = "High"
        mock_issue.fields.assignee = None
        mock_issue.fields.reporter.displayName = "Test User"
        mock_issue.fields.created = "2024-01-01T00:00:00.000+0000"
        mock_issue.fields.updated = "2024-01-02T00:00:00.000+0000"
        mock_issue.fields.labels = []
        mock_issue.fields.components = []
        mock_issue.fields.attachment = []
        mock_issue.fields.issuelinks = []
        mock_issue.fields.fixVersions = []
        mock_issue.renderedFields = MagicMock()
        mock_issue.renderedFields.description = None

        client = JiraClient()
        story = client._parse_sdk_issue(mock_issue)

        assert story.fix_versions is not None
        assert len(story.fix_versions) == 0


class TestSuggestFolderEndpoint:
    """Test suite for the suggest-folder API endpoint."""

    def _create_mock_completion(self, content: str):
        """Helper to create a mock OpenAI completion response."""
        mock_message = MagicMock()
        mock_message.content = content
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_completion = MagicMock()
        mock_completion.choices = [mock_choice]
        return mock_completion

    @pytest.mark.asyncio
    async def test_suggest_folder_with_matching_folder(self):
        """Test folder suggestion when a matching folder exists."""
        from src.api.routes.zephyr import suggest_folder, SuggestFolderRequest
        
        # Mock ZephyrIntegration.get_folders
        mock_folders = [
            {"id": "1", "name": "Nov-16th - 2025", "parentId": None, "path": "Nov-16th - 2025"},
            {"id": "2", "name": "Dec-7th - 2025", "parentId": None, "path": "Dec-7th - 2025"},
            {"id": "3", "name": "Dec-14th - 2025", "parentId": None, "path": "Dec-14th - 2025"},
        ]
        
        # Mock AI response
        mock_ai_response = '{"folder_path": "Dec-7th - 2025", "confidence": "high", "reason": "Matched Dec-7th date pattern"}'
        mock_completion = self._create_mock_completion(mock_ai_response)
        
        with patch('src.integrations.zephyr_integration.ZephyrIntegration.get_folders', new_callable=AsyncMock) as mock_get_folders, \
             patch('src.ai.generation.ai_client_factory.AIClientFactory.create_openai_client') as mock_create_client:
            
            mock_get_folders.return_value = mock_folders
            
            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = mock_completion
            mock_create_client.return_value = (mock_client, "gpt-4o-mini")
            
            request = SuggestFolderRequest(
                project_key="PLAT",
                fix_version="Platform MNG - Dec-7th (5.2550.X)",
                folder_type="TEST_CYCLE"
            )
            
            response = await suggest_folder(request)
            
            assert response.suggested_folder_path == "Dec-7th - 2025"
            assert response.suggested_folder_id == "2"
            assert response.confidence == "high"
            assert len(response.available_folders) == 3

    @pytest.mark.asyncio
    async def test_suggest_folder_no_folders_available(self):
        """Test folder suggestion when no folders exist."""
        from src.api.routes.zephyr import suggest_folder, SuggestFolderRequest
        
        with patch('src.integrations.zephyr_integration.ZephyrIntegration.get_folders', new_callable=AsyncMock) as mock_get_folders:
            mock_get_folders.return_value = []
            
            request = SuggestFolderRequest(
                project_key="PLAT",
                fix_version="Platform MNG - Dec-7th (5.2550.X)",
                folder_type="TEST_CYCLE"
            )
            
            response = await suggest_folder(request)
            
            assert response.suggested_folder_path is None
            assert response.suggested_folder_id is None
            assert response.confidence == "low"
            assert "No folders available" in response.reason

    @pytest.mark.asyncio
    async def test_suggest_folder_ai_returns_null(self):
        """Test folder suggestion when AI returns null folder."""
        from src.api.routes.zephyr import suggest_folder, SuggestFolderRequest
        
        mock_folders = [
            {"id": "1", "name": "Old Folder", "parentId": None, "path": "Old Folder"},
        ]
        
        # AI couldn't find a match
        mock_ai_response = '{"folder_path": null, "confidence": "low", "reason": "No matching date pattern found"}'
        mock_completion = self._create_mock_completion(mock_ai_response)
        
        with patch('src.integrations.zephyr_integration.ZephyrIntegration.get_folders', new_callable=AsyncMock) as mock_get_folders, \
             patch('src.ai.generation.ai_client_factory.AIClientFactory.create_openai_client') as mock_create_client:
            
            mock_get_folders.return_value = mock_folders
            
            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = mock_completion
            mock_create_client.return_value = (mock_client, "gpt-4o-mini")
            
            request = SuggestFolderRequest(
                project_key="PLAT",
                fix_version="Platform MNG - Dec-7th (5.2550.X)",
                folder_type="TEST_CYCLE"
            )
            
            response = await suggest_folder(request)
            
            assert response.suggested_folder_path is None
            assert response.confidence == "low"

    @pytest.mark.asyncio
    async def test_suggest_folder_ai_response_with_markdown(self):
        """Test folder suggestion handles AI response wrapped in markdown code blocks."""
        from src.api.routes.zephyr import suggest_folder, SuggestFolderRequest
        
        mock_folders = [
            {"id": "1", "name": "Dec-7th - 2025", "parentId": None, "path": "Dec-7th - 2025"},
        ]
        
        # AI response wrapped in markdown (common issue)
        mock_ai_response = '''```json
{"folder_path": "Dec-7th - 2025", "confidence": "high", "reason": "Matched date"}
```'''
        mock_completion = self._create_mock_completion(mock_ai_response)
        
        with patch('src.integrations.zephyr_integration.ZephyrIntegration.get_folders', new_callable=AsyncMock) as mock_get_folders, \
             patch('src.ai.generation.ai_client_factory.AIClientFactory.create_openai_client') as mock_create_client:
            
            mock_get_folders.return_value = mock_folders
            
            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = mock_completion
            mock_create_client.return_value = (mock_client, "gpt-4o-mini")
            
            request = SuggestFolderRequest(
                project_key="PLAT",
                fix_version="Platform MNG - Dec-7th (5.2550.X)",
                folder_type="TEST_CYCLE"
            )
            
            response = await suggest_folder(request)
            
            assert response.suggested_folder_path == "Dec-7th - 2025"
            assert response.confidence == "high"


class TestJiraStoryModel:
    """Test suite for JiraStory model with fix_versions field."""

    def test_jira_story_with_fix_versions(self):
        """Test creating JiraStory with fix_versions."""
        story = JiraStory(
            key="PLAT-12345",
            summary="Test story",
            issue_type="Story",
            status="In Progress",
            priority="High",
            reporter="test@example.com",
            created=datetime.now(),
            updated=datetime.now(),
            fix_versions=["Platform MNG - Dec-7th (5.2550.X)"]
        )

        assert story.fix_versions is not None
        assert len(story.fix_versions) == 1
        assert "Platform MNG - Dec-7th (5.2550.X)" in story.fix_versions

    def test_jira_story_default_fix_versions(self):
        """Test JiraStory defaults to empty fix_versions list."""
        story = JiraStory(
            key="PLAT-12345",
            summary="Test story",
            issue_type="Story",
            status="In Progress",
            priority="High",
            reporter="test@example.com",
            created=datetime.now(),
            updated=datetime.now()
        )

        assert story.fix_versions is not None
        assert len(story.fix_versions) == 0

    def test_jira_story_serialization_with_fix_versions(self):
        """Test JiraStory serialization includes fix_versions."""
        story = JiraStory(
            key="PLAT-12345",
            summary="Test story",
            issue_type="Story",
            status="In Progress",
            priority="High",
            reporter="test@example.com",
            created=datetime.now(),
            updated=datetime.now(),
            fix_versions=["Platform MNG - Dec-7th (5.2550.X)", "Platform MNG - Dec-14th (5.2551.X)"]
        )

        story_dict = story.model_dump()
        
        assert "fix_versions" in story_dict
        assert len(story_dict["fix_versions"]) == 2

