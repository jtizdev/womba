"""
Unit tests for JiraClient.
"""

import pytest
from httpx import AsyncClient, Response
from pytest_mock import MockerFixture

from src.aggregator.jira_client import JiraClient


class TestJiraClient:
    """Test suite for JiraClient."""

    @pytest.mark.asyncio
    async def test_get_issue_success(
        self, mocker: MockerFixture, sample_jira_issue_data
    ):
        """Test successful issue retrieval."""
        # Mock the HTTP client
        mock_response = Response(200, json=sample_jira_issue_data)
        mock_get = mocker.patch(
            "httpx.AsyncClient.get", return_value=mock_response
        )

        client = JiraClient(
            base_url="https://test.atlassian.net",
            email="test@example.com",
            api_token="test-token",
        )

        story = await client.get_issue("PROJ-123")

        assert story.key == "PROJ-123"
        assert story.summary == "Add user authentication feature"
        assert story.issue_type == "Story"
        assert story.status == "In Progress"
        assert story.priority == "High"
        assert "authentication" in story.labels
        assert "Backend" in story.components
        mock_get.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_issue_not_found(self, mocker: MockerFixture):
        """Test issue not found error."""
        mock_response = Response(404, json={"errorMessages": ["Issue not found"]})
        mock_response.request = mocker.MagicMock()
        mocker.patch("httpx.AsyncClient.get", return_value=mock_response)

        client = JiraClient()

        with pytest.raises(Exception):
            await client.get_issue("INVALID-999")

    def test_parse_issue_with_adf_description(self, sample_jira_issue_data):
        """Test parsing issue with Atlassian Document Format description."""
        # Modify data to use ADF format
        sample_jira_issue_data["fields"]["description"] = {
            "type": "doc",
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": "This is ADF formatted text"}],
                }
            ],
        }

        client = JiraClient()
        story = client._parse_issue(sample_jira_issue_data)

        assert "This is ADF formatted text" in story.description

    def test_extract_acceptance_criteria_from_description(self):
        """Test extraction of acceptance criteria from description."""
        fields = {
            "summary": "Test feature",
            "issuetype": {"name": "Story"},
            "status": {"name": "Open"},
            "priority": {"name": "High"},
            "reporter": {"emailAddress": "test@example.com"},
            "created": "2024-01-01T00:00:00.000+0000",
            "updated": "2024-01-01T00:00:00.000+0000",
        }
        description = """
        Feature description here.
        
        Acceptance Criteria
        - Criterion 1
        - Criterion 2
        
        Additional notes.
        """

        client = JiraClient()
        ac = client._extract_acceptance_criteria(fields, description)

        assert ac is not None
        assert "Criterion 1" in ac or "criterion 1" in ac.lower()

    @pytest.mark.asyncio
    async def test_search_issues(self, mocker: MockerFixture, sample_jira_issue_data):
        """Test searching issues with JQL."""
        mock_response = Response(
            200, json={"issues": [sample_jira_issue_data], "total": 1}
        )
        mock_post = mocker.patch("httpx.AsyncClient.post", return_value=mock_response)

        client = JiraClient()
        stories = await client.search_issues("project = PROJ", max_results=10)

        assert len(stories) == 1
        assert stories[0].key == "PROJ-123"
        mock_post.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_linked_issues(
        self, mocker: MockerFixture, sample_jira_issue_data
    ):
        """Test fetching linked issues."""
        # Add linked issue to data
        linked_issue_data = sample_jira_issue_data.copy()
        linked_issue_data["key"] = "PROJ-124"
        
        main_issue_with_links = sample_jira_issue_data.copy()
        main_issue_with_links["fields"]["issuelinks"] = [
            {"inwardIssue": {"key": "PROJ-124"}}
        ]

        mock_get = mocker.patch(
            "httpx.AsyncClient.get",
            side_effect=[
                Response(200, json=main_issue_with_links),
                Response(200, json=linked_issue_data),
            ],
        )

        client = JiraClient()
        linked_stories = await client.get_linked_issues("PROJ-123")

        assert len(linked_stories) == 1
        assert linked_stories[0].key == "PROJ-124"

