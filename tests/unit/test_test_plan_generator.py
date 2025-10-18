"""
Unit tests for TestPlanGenerator.
"""

import json

import pytest

from src.ai.test_plan_generator import TestPlanGenerator
from src.aggregator.story_collector import StoryContext


class TestTestPlanGenerator:
    """Test suite for TestPlanGenerator."""

    @pytest.mark.asyncio
    async def test_generate_test_plan(self, mocker, sample_jira_story, mock_anthropic_client):
        """Test generating a test plan with AI."""
        # Mock the Anthropic client
        mocker.patch(
            "src.ai.test_plan_generator.Anthropic",
            return_value=mock_anthropic_client,
        )

        context = StoryContext(sample_jira_story)
        context["full_context_text"] = "Test context"

        generator = TestPlanGenerator(api_key="test-key")
        test_plan = await generator.generate_test_plan(context)

        assert test_plan.story.key == "PROJ-123"
        assert len(test_plan.test_cases) > 0
        assert test_plan.metadata.source_story_key == "PROJ-123"
        assert test_plan.metadata.ai_model is not None
        assert test_plan.summary is not None

    def test_parse_ai_response_valid_json(self):
        """Test parsing valid JSON response from AI."""
        response_text = """
        Here's the test plan:
        
        {
            "summary": "Test summary",
            "test_cases": [],
            "estimated_execution_time": 30,
            "dependencies": []
        }
        """

        generator = TestPlanGenerator(api_key="test-key")
        data = generator._parse_ai_response(response_text)

        assert data["summary"] == "Test summary"
        assert "test_cases" in data

    def test_parse_ai_response_invalid_json(self):
        """Test error handling for invalid JSON."""
        response_text = "This is not JSON"

        generator = TestPlanGenerator(api_key="test-key")

        with pytest.raises(ValueError, match="No JSON found"):
            generator._parse_ai_response(response_text)

    def test_build_test_plan(self, sample_jira_story):
        """Test building TestPlan object from parsed data."""
        test_plan_data = {
            "summary": "Comprehensive test plan",
            "coverage_analysis": "Covers all scenarios",
            "risk_assessment": "Medium risk",
            "test_cases": [
                {
                    "title": "Test case 1",
                    "description": "Description",
                    "preconditions": "Precondition",
                    "steps": [
                        {
                            "step_number": 1,
                            "action": "Action 1",
                            "expected_result": "Result 1",
                        }
                    ],
                    "expected_result": "Overall result",
                    "priority": "high",
                    "test_type": "functional",
                    "tags": ["tag1"],
                    "automation_candidate": True,
                    "risk_level": "medium",
                }
            ],
            "estimated_execution_time": 30,
            "dependencies": ["Dep 1"],
        }

        generator = TestPlanGenerator(api_key="test-key")
        test_plan = generator._build_test_plan(
            sample_jira_story, test_plan_data, "claude-3-5-sonnet-20241022"
        )

        assert test_plan.story.key == "PROJ-123"
        assert len(test_plan.test_cases) == 1
        assert test_plan.test_cases[0].title == "Test case 1"
        assert len(test_plan.test_cases[0].steps) == 1
        assert test_plan.metadata.total_test_cases == 1

    def test_count_test_types(self, sample_jira_story):
        """Test counting different test types."""
        test_plan_data = {
            "summary": "Test plan",
            "test_cases": [
                {
                    "title": "Edge case test",
                    "description": "Desc",
                    "steps": [],
                    "expected_result": "Result",
                    "priority": "medium",
                    "test_type": "edge_case",
                    "tags": [],
                    "automation_candidate": True,
                    "risk_level": "low",
                },
                {
                    "title": "Integration test",
                    "description": "Desc",
                    "steps": [],
                    "expected_result": "Result",
                    "priority": "high",
                    "test_type": "integration",
                    "tags": [],
                    "automation_candidate": True,
                    "risk_level": "high",
                },
            ],
            "estimated_execution_time": 20,
            "dependencies": [],
        }

        generator = TestPlanGenerator(api_key="test-key")
        test_plan = generator._build_test_plan(
            sample_jira_story, test_plan_data, "test-model"
        )

        assert test_plan.metadata.edge_case_count == 1
        assert test_plan.metadata.integration_test_count == 1

