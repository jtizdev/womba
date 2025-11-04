"""
Unit tests for StoryCollector.
"""

import pytest

from src.aggregator.story_collector import StoryCollector


class TestStoryCollector:
    """Test suite for StoryCollector."""

    @pytest.mark.skip(reason="Requires mock fixes for SDK integration")
    @pytest.mark.asyncio
    async def test_collect_story_context(self, mocker, sample_jira_story):
        """Test collecting comprehensive story context."""
        # Mock JiraClient
        mock_jira_client = mocker.MagicMock()
        mock_jira_client.get_issue = mocker.AsyncMock(return_value=sample_jira_story)
        mock_jira_client.get_linked_issues = mocker.AsyncMock(return_value=[])
        mock_jira_client.search_issues = mocker.AsyncMock(return_value=[])

        collector = StoryCollector(jira_client=mock_jira_client)
        context = await collector.collect_story_context("PROJ-123")

        assert context.main_story.key == "PROJ-123"
        assert "linked_stories" in context
        assert "related_bugs" in context
        assert "context_graph" in context
        assert "full_context_text" in context

    @pytest.mark.skip(reason="Requires mock fixes for SDK integration")
    @pytest.mark.asyncio
    async def test_fetch_related_bugs(self, mocker, sample_jira_story):
        """Test fetching related bugs based on components and labels."""
        bug_story = sample_jira_story.model_copy()
        bug_story.key = "PROJ-200"
        bug_story.issue_type = "Bug"

        mock_jira_client = mocker.MagicMock()
        mock_jira_client.search_issues = mocker.AsyncMock(return_value=[bug_story])

        collector = StoryCollector(jira_client=mock_jira_client)
        bugs = await collector._fetch_related_bugs(sample_jira_story)

        assert len(bugs) == 1
        assert bugs[0].key == "PROJ-200"
        assert bugs[0].issue_type == "Bug"

    def test_build_context_graph(self, sample_jira_story):
        """Test building context graph from stories."""
        linked_story = sample_jira_story.model_copy()
        linked_story.key = "PROJ-124"

        bug_story = sample_jira_story.model_copy()
        bug_story.key = "PROJ-200"
        bug_story.issue_type = "Bug"

        collector = StoryCollector()
        graph = collector._build_context_graph(
            sample_jira_story, [linked_story], [bug_story]
        )

        assert graph["main"] == "PROJ-123"
        assert "PROJ-200" in graph["fixed_by"]
        assert "Backend" in graph["components"]
        assert "authentication" in graph["labels"]

    def test_build_full_context_text(self, sample_jira_story):
        """Test building full context text for AI."""
        from src.aggregator.story_collector import StoryContext

        context = StoryContext(sample_jira_story)
        context["linked_stories"] = []
        context["related_bugs"] = []

        collector = StoryCollector()
        text = collector._build_full_context_text(context)

        assert "=== MAIN STORY ===" in text
        assert "PROJ-123" in text
        assert "Add user authentication feature" in text
        assert "Backend" in text
        assert "authentication" in text

