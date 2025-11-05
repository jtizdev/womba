"""
End-to-end test for complete user workflow.
"""

import pytest


class TestFullWorkflow:
    """End-to-end tests for complete user workflows."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_complete_workflow_with_api(
        self, api_client, mocker, sample_jira_story, mock_anthropic_client
    ):
        """
        Test the complete workflow through API endpoints:
        1. Fetch story from Jira
        2. Generate test plan with AI
        3. Verify test plan structure
        
        This is the primary user workflow for the application.
        """
        # Mock external dependencies
        mock_jira_client = mocker.MagicMock()
        mock_jira_client.get_issue_with_subtasks = mocker.AsyncMock(return_value=(sample_jira_story, []))
        mock_jira_client.get_issue = mocker.AsyncMock(return_value=sample_jira_story)
        mock_jira_client.get_linked_issues = mocker.AsyncMock(return_value=[])
        mock_jira_client.search_issues = mocker.Mock(return_value=([], 0))

        mocker.patch(
            "src.aggregator.jira_client.JiraClient",
            return_value=mock_jira_client,
        )
        mocker.patch(
            "src.aggregator.story_collector.JiraClient",
            return_value=mock_jira_client,
        )
        mocker.patch(
            "anthropic.Anthropic",
            return_value=mock_anthropic_client,
        )

        # Step 1: Fetch story
        response = await api_client.get("/api/v1/stories/PROJ-123")
        assert response.status_code == 200
        story_data = response.json()
        assert story_data["key"] == "PROJ-123"

        # Step 2: Generate test plan (without Zephyr upload)
        response = await api_client.post(
            "/api/v1/test-plans/generate",
            json={
                "issue_key": "PROJ-123",
                "upload_to_zephyr": False,
            },
        )
        assert response.status_code == 200
        test_plan_data = response.json()

        # Verify test plan structure
        assert "test_plan" in test_plan_data
        test_plan = test_plan_data["test_plan"]
        assert test_plan["story"]["key"] == "PROJ-123"
        assert len(test_plan["test_cases"]) > 0
        assert test_plan["metadata"]["total_test_cases"] > 0
        assert test_plan["summary"] is not None

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_workflow_with_zephyr_upload(
        self, api_client, mocker, sample_jira_story, mock_anthropic_client
    ):
        """
        Test workflow with Zephyr upload enabled.
        """
        # Mock dependencies
        mock_jira_client = mocker.MagicMock()
        mock_jira_client.get_issue_with_subtasks = mocker.AsyncMock(return_value=(sample_jira_story, []))
        mock_jira_client.get_issue = mocker.AsyncMock(return_value=sample_jira_story)
        mock_jira_client.get_linked_issues = mocker.AsyncMock(return_value=[])
        mock_jira_client.search_issues = mocker.Mock(return_value=([], 0))

        # Mock Zephyr responses
        zephyr_response = mocker.MagicMock()
        zephyr_response.status_code = 201
        zephyr_response.json.return_value = {"key": "TEST-1"}
        zephyr_response.raise_for_status = mocker.MagicMock()

        mock_http_client = mocker.MagicMock()
        mock_http_client.__aenter__ = mocker.AsyncMock(return_value=mock_http_client)
        mock_http_client.__aexit__ = mocker.AsyncMock()
        mock_http_client.post = mocker.AsyncMock(return_value=zephyr_response)

        mocker.patch(
            "src.aggregator.jira_client.JiraClient", return_value=mock_jira_client
        )
        mocker.patch(
            "src.aggregator.story_collector.JiraClient", return_value=mock_jira_client
        )
        mocker.patch(
            "anthropic.Anthropic", return_value=mock_anthropic_client
        )
        mocker.patch("httpx.AsyncClient", return_value=mock_http_client)

        # Generate test plan with Zephyr upload
        response = await api_client.post(
            "/api/v1/test-plans/generate",
            json={
                "issue_key": "PROJ-123",
                "upload_to_zephyr": True,
                "project_key": "PROJ",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "test_plan" in data
        assert "zephyr_results" in data
        assert data["zephyr_results"] is not None

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_api_health_check(self, api_client):
        """Test API health check endpoint."""
        response = await api_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_story_context_endpoint(
        self, api_client, mocker, sample_jira_story
    ):
        """Test fetching comprehensive story context."""
        mock_jira_client = mocker.MagicMock()
        mock_jira_client.get_issue_with_subtasks = mocker.AsyncMock(return_value=(sample_jira_story, []))
        mock_jira_client.get_issue = mocker.AsyncMock(return_value=sample_jira_story)
        mock_jira_client.get_linked_issues = mocker.AsyncMock(return_value=[])
        mock_jira_client.search_issues = mocker.Mock(return_value=([], 0))

        mocker.patch(
            "src.aggregator.story_collector.JiraClient", return_value=mock_jira_client
        )

        response = await api_client.get("/api/v1/stories/PROJ-123/context")
        assert response.status_code == 200
        context = response.json()

        assert "main_story" in context
        assert "linked_stories" in context
        assert "related_bugs" in context
        assert "context_graph" in context
        assert context["main_story"]["key"] == "PROJ-123"

