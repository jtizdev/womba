"""
Unit tests for ZephyrIntegration.
"""

import pytest
from httpx import Response

from src.integrations.zephyr_integration import ZephyrIntegration


@pytest.mark.skip(reason="Zephyr integration tests require external API mock updates")
class TestZephyrIntegration:
    """Test suite for ZephyrIntegration."""

    @pytest.mark.asyncio
    async def test_create_test_case(self, mocker, sample_test_case):
        """Test creating a test case in Zephyr."""
        mock_response = Response(
            201, json={"key": "TEST-1", "id": "12345"}
        )
        mock_post = mocker.patch("httpx.AsyncClient.post", return_value=mock_response)

        integration = ZephyrIntegration(
            api_key="test-key", base_url="https://api.zephyrscale.smartbear.com/v2"
        )

        test_case_key = await integration.create_test_case(
            test_case=sample_test_case,
            project_key="PROJ",
        )

        assert test_case_key == "TEST-1"
        mock_post.assert_called_once()

        # Verify payload structure
        call_args = mock_post.call_args
        payload = call_args.kwargs["json"]
        assert payload["projectKey"] == "PROJ"
        assert payload["name"] == sample_test_case.title
        assert payload["objective"] == sample_test_case.description

    @pytest.mark.asyncio
    async def test_upload_test_plan(self, mocker, sample_test_plan):
        """Test uploading entire test plan to Zephyr."""
        mock_response = Response(201, json={"key": "TEST-1", "id": "12345"})
        mocker.patch("httpx.AsyncClient.post", return_value=mock_response)

        integration = ZephyrIntegration()
        results = await integration.upload_test_plan(
            test_plan=sample_test_plan, project_key="PROJ"
        )

        assert len(results) == len(sample_test_plan.test_cases)
        assert all(not v.startswith("ERROR") for v in results.values())

    @pytest.mark.asyncio
    async def test_link_test_to_issue(self, mocker):
        """Test linking test case to Jira issue."""
        mock_response = Response(200, json={"success": True})
        mock_post = mocker.patch("httpx.AsyncClient.post", return_value=mock_response)

        integration = ZephyrIntegration()
        await integration.link_test_to_issue("TEST-1", "PROJ-123")

        mock_post.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_test_case(self, mocker):
        """Test retrieving a test case from Zephyr."""
        mock_response = Response(
            200,
            json={"key": "TEST-1", "name": "Test case", "projectKey": "PROJ"},
        )
        mock_get = mocker.patch("httpx.AsyncClient.get", return_value=mock_response)

        integration = ZephyrIntegration()
        test_case = await integration.get_test_case("TEST-1")

        assert test_case["key"] == "TEST-1"
        mock_get.assert_called_once()

    def test_map_priority(self):
        """Test priority mapping."""
        integration = ZephyrIntegration()

        assert integration._map_priority("critical") == "High"
        assert integration._map_priority("high") == "High"
        assert integration._map_priority("medium") == "Medium"
        assert integration._map_priority("low") == "Low"
        assert integration._map_priority("unknown") == "Medium"  # Default

    @pytest.mark.asyncio
    async def test_create_test_cycle(self, mocker):
        """Test creating a test cycle."""
        mock_response = Response(201, json={"key": "CYCLE-1", "id": "67890"})
        mock_post = mocker.patch("httpx.AsyncClient.post", return_value=mock_response)

        integration = ZephyrIntegration()
        cycle_key = await integration.create_test_cycle(
            project_key="PROJ", name="Sprint 10 Tests", description="Test cycle for sprint 10"
        )

        assert cycle_key == "CYCLE-1"
        mock_post.assert_called_once()


@pytest.mark.asyncio
async def test_ensure_folder_uses_existing(monkeypatch):
    integration = ZephyrIntegration(api_key="test", base_url="https://api.example.com")

    async def fake_get_structure(project_key):
        return [{
            'id': '10',
            'name': 'Existing',
            'parentId': None,
            'children': []
        }]

    async def fake_create(*args, **kwargs):
        raise AssertionError("Should not create folder when it already exists")

    monkeypatch.setattr(integration, "get_folder_structure", fake_get_structure)
    monkeypatch.setattr(integration, "_create_folder", fake_create)

    folder_id = await integration.ensure_folder('PROJ', 'Existing')
    assert folder_id == '10'


@pytest.mark.asyncio
async def test_ensure_folder_creates_missing(monkeypatch):
    integration = ZephyrIntegration(api_key="test", base_url="https://api.example.com")

    async def fake_get_structure(project_key):
        return [{
            'id': '10',
            'name': 'Existing',
            'parentId': None,
            'children': []
        }]

    created = []

    async def fake_create(project_key, name, parent_id):
        created.append((name, parent_id))
        return '20' if parent_id == '10' else '11'

    monkeypatch.setattr(integration, "get_folder_structure", fake_get_structure)
    monkeypatch.setattr(integration, "_create_folder", fake_create)

    folder_id = await integration.ensure_folder('PROJ', 'Existing/NewChild')
    assert folder_id == '20'
    assert created == [('NewChild', '10')]

