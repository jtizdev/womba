"""
API endpoint tests.
"""

import pytest


class TestAPIEndpoints:
    """Test suite for API endpoints."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_root_endpoint(self, api_client):
        """Test root endpoint returns API information."""
        response = await api_client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Womba API"
        assert "version" in data
        assert data["status"] == "operational"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_health_endpoint(self, api_client):
        """Test health check endpoint."""
        response = await api_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "environment" in data

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_openapi_docs(self, api_client):
        """Test that API documentation is accessible."""
        response = await api_client.get("/docs")
        assert response.status_code == 200

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_story_endpoint_error_handling(self, api_client, mocker):
        """Test error handling when Jira API fails."""
        # Mock Jira client to raise an error
        mock_jira_client = mocker.MagicMock()
        mock_jira_client.get_issue = mocker.AsyncMock(
            side_effect=Exception("Jira API error")
        )

        mocker.patch(
            "src.aggregator.jira_client.JiraClient",
            return_value=mock_jira_client,
        )

        response = await api_client.get("/api/v1/stories/INVALID-123")
        # Should return 404 for non-existent story (fixed from 500)
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_test_plan_generation_without_project_key(self, api_client):
        """Test that generating with Zephyr upload requires project_key."""
        response = await api_client.post(
            "/api/v1/test-plans/generate",
            json={
                "issue_key": "PROJ-123",
                "upload_to_zephyr": True,
                # Missing project_key
            },
        )
        # Should fail because project_key is required when upload_to_zephyr is True
        assert response.status_code == 400

