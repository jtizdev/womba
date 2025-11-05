"""
Integration test for end-to-end story to test plan generation.
"""

import pytest

from src.aggregator.story_collector import StoryCollector
from src.ai.test_plan_generator import TestPlanGenerator


class TestJiraToTestPlan:
    """Integration tests for Jira story to test plan workflow."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_full_workflow_story_to_testplan(
        self, mocker, sample_jira_story, mock_anthropic_client
    ):
        """
        Test the complete workflow from Jira story to generated test plan.
        
        This integration test verifies:
        1. Story context collection from Jira
        2. AI test plan generation
        3. Test plan structure and completeness
        """
        # Mock Jira client
        mock_jira_client = mocker.MagicMock()
        mock_jira_client.get_issue_with_subtasks = mocker.AsyncMock(return_value=(sample_jira_story, []))
        mock_jira_client.get_issue = mocker.AsyncMock(return_value=sample_jira_story)
        mock_jira_client.get_linked_issues = mocker.AsyncMock(return_value=[])
        mock_jira_client.search_issues = mocker.Mock(return_value=([], 0))

        # Mock Anthropic client
        mocker.patch(
            "anthropic.Anthropic",
            return_value=mock_anthropic_client,
        )

        # Step 1: Collect story context
        collector = StoryCollector(jira_client=mock_jira_client)
        context = await collector.collect_story_context("PROJ-123")

        assert context.main_story.key == "PROJ-123"
        assert context["full_context_text"] is not None

        # Step 2: Generate test plan
        generator = TestPlanGenerator(api_key="test-key")
        test_plan = await generator.generate_test_plan(context)

        # Verify test plan structure
        assert test_plan.story.key == "PROJ-123"
        assert len(test_plan.test_cases) > 0
        assert test_plan.summary is not None
        assert test_plan.metadata.total_test_cases == len(test_plan.test_cases)

        # Verify test cases have proper structure
        for test_case in test_plan.test_cases:
            assert test_case.title is not None
            assert test_case.description is not None
            assert test_case.expected_result is not None
            assert test_case.priority in ["critical", "high", "medium", "low"]
            assert len(test_case.steps) > 0

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_context_aggregation_with_linked_issues(
        self, mocker, sample_jira_story
    ):
        """Test that linked issues are properly aggregated into context."""
        linked_story = sample_jira_story.model_copy()
        linked_story.key = "PROJ-124"
        linked_story.summary = "OAuth2 implementation"

        mock_jira_client = mocker.MagicMock()
        mock_jira_client.get_issue_with_subtasks = mocker.AsyncMock(return_value=(sample_jira_story, []))
        mock_jira_client.get_issue = mocker.AsyncMock(return_value=sample_jira_story)
        mock_jira_client.get_linked_issues = mocker.AsyncMock(
            return_value=[linked_story]
        )
        mock_jira_client.search_issues = mocker.Mock(return_value=([], 0))

        collector = StoryCollector(jira_client=mock_jira_client)
        context = await collector.collect_story_context("PROJ-123")

        assert len(context["linked_stories"]) == 1
        assert context["linked_stories"][0].key == "PROJ-124"
        # Verify linked story is in context text
        assert "PROJ-124" in context["full_context_text"]

