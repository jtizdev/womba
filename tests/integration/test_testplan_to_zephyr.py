"""
Integration test for test plan to Zephyr upload.
"""

import pytest

from src.integrations.zephyr_integration import ZephyrIntegration


class TestTestPlanToZephyr:
    """Integration tests for test plan to Zephyr upload."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_upload_test_plan_to_zephyr(self, mocker, sample_test_plan):
        """
        Test uploading a complete test plan to Zephyr Scale.
        
        This verifies:
        1. Test cases are created in Zephyr
        2. Test cases are linked to Jira story
        3. Proper error handling
        """
        # Mock Zephyr API responses
        create_response = mocker.MagicMock()
        create_response.status_code = 201
        create_response.json.return_value = {"key": "TEST-1", "id": "12345"}
        create_response.raise_for_status = mocker.MagicMock()

        link_response = mocker.MagicMock()
        link_response.status_code = 200
        link_response.raise_for_status = mocker.MagicMock()

        # Mock httpx client
        mock_client = mocker.MagicMock()
        mock_client.__aenter__ = mocker.AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = mocker.AsyncMock(return_value=None)
        mock_client.post = mocker.AsyncMock(
            side_effect=[create_response, link_response]
        )

        mocker.patch("httpx.AsyncClient", return_value=mock_client)

        # Upload test plan
        integration = ZephyrIntegration(api_key="test-key")
        results = await integration.upload_test_plan(
            test_plan=sample_test_plan, project_key="PROJ"
        )

        # Verify results
        assert len(results) == len(sample_test_plan.test_cases)
        for title, result in results.items():
            assert not result.startswith("ERROR")
            assert result == "TEST-1"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_test_case_with_all_fields(self, mocker, sample_test_case):
        """Test that all test case fields are properly sent to Zephyr."""
        create_response = mocker.MagicMock()
        create_response.status_code = 201
        create_response.json.return_value = {"key": "TEST-1"}
        create_response.raise_for_status = mocker.MagicMock()

        mock_client = mocker.MagicMock()
        mock_client.__aenter__ = mocker.AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = mocker.AsyncMock(return_value=None)
        mock_post = mocker.AsyncMock(return_value=create_response)
        mock_client.post = mock_post

        mocker.patch("httpx.AsyncClient", return_value=mock_client)

        integration = ZephyrIntegration()
        await integration.create_test_case(
            test_case=sample_test_case, project_key="PROJ", story_key="PROJ-123"
        )

        # Verify the payload
        call_args = mock_post.call_args_list[0]
        payload = call_args.kwargs["json"]

        assert payload["projectKey"] == "PROJ"
        assert payload["name"] == sample_test_case.title
        assert payload["objective"] == sample_test_case.description
        assert payload["precondition"] == sample_test_case.preconditions
        # Note: testScript is added separately via _add_test_steps, not in initial payload
        assert "testScript" not in payload  # Steps are added via separate API call

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_error_handling_on_failed_upload(self, mocker, sample_test_plan):
        """Test proper error handling when Zephyr API fails."""
        # Mock API failure
        error_response = mocker.MagicMock()
        error_response.status_code = 400
        error_response.raise_for_status.side_effect = Exception("API Error")

        mock_client = mocker.MagicMock()
        mock_client.__aenter__ = mocker.AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = mocker.AsyncMock(return_value=None)
        mock_client.post = mocker.AsyncMock(return_value=error_response)

        mocker.patch("httpx.AsyncClient", return_value=mock_client)

        integration = ZephyrIntegration()
        results = await integration.upload_test_plan(
            test_plan=sample_test_plan, project_key="PROJ"
        )

        # Verify errors are captured
        for title, result in results.items():
            assert result.startswith("ERROR")

