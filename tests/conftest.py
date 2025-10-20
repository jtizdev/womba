"""
Pytest configuration and fixtures.
"""

import os
from typing import AsyncGenerator, Dict
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient

# Set test environment
os.environ["ENVIRONMENT"] = "test"
os.environ["ANTHROPIC_API_KEY"] = "test-key"
os.environ["ATLASSIAN_BASE_URL"] = "https://test.atlassian.net"
os.environ["ATLASSIAN_EMAIL"] = "test@example.com"
os.environ["ATLASSIAN_API_TOKEN"] = "test-token"
os.environ["ZEPHYR_API_KEY"] = "test-zephyr-key"
os.environ["GITHUB_TOKEN"] = "test-github-token"
os.environ["SECRET_KEY"] = "test-secret-key"


@pytest.fixture
def sample_jira_issue_data() -> Dict:
    """Sample Jira issue data for testing."""
    return {
        "key": "PROJ-123",
        "fields": {
            "summary": "Add user authentication feature",
            "description": "Implement OAuth2 authentication for users.\n\nAcceptance Criteria:\n- Users can login with Google\n- Users can login with email/password\n- Failed login attempts are logged",
            "issuetype": {"name": "Story"},
            "status": {"name": "In Progress"},
            "priority": {"name": "High"},
            "assignee": {"emailAddress": "developer@example.com"},
            "reporter": {"emailAddress": "pm@example.com"},
            "created": "2024-01-01T10:00:00.000+0000",
            "updated": "2024-01-05T15:30:00.000+0000",
            "labels": ["authentication", "security"],
            "components": [{"name": "Backend"}, {"name": "Auth Service"}],
            "attachment": [],
            "issuelinks": [],
        },
    }


@pytest.fixture
def sample_jira_story():
    """Sample JiraStory object for testing."""
    from datetime import datetime

    from src.models.story import JiraStory

    return JiraStory(
        key="PROJ-123",
        summary="Add user authentication feature",
        description="Implement OAuth2 authentication for users.",
        issue_type="Story",
        status="In Progress",
        priority="High",
        assignee="developer@example.com",
        reporter="pm@example.com",
        created=datetime(2024, 1, 1, 10, 0, 0),
        updated=datetime(2024, 1, 5, 15, 30, 0),
        labels=["authentication", "security"],
        components=["Backend", "Auth Service"],
        acceptance_criteria="- Users can login with Google\n- Users can login with email/password\n- Failed login attempts are logged",
        linked_issues=[],
        attachments=[],
        custom_fields={},
    )


@pytest.fixture
def sample_test_case():
    """Sample TestCase object for testing."""
    from src.models.test_case import TestCase, TestStep

    return TestCase(
        title="Verify user login with valid credentials",
        description="Test that a user can successfully login with valid email and password",
        preconditions="User account exists in the system",
        steps=[
            TestStep(
                step_number=1,
                action="Navigate to login page",
                expected_result="Login form is displayed",
            ),
            TestStep(
                step_number=2,
                action="Enter valid email and password",
                expected_result="User is logged in",
                test_data="email: test@example.com, password: Test123!",
            ),
        ],
        expected_result="User is logged in and redirected to dashboard",
        priority="high",
        test_type="functional",
        tags=["authentication", "login"],
        automation_candidate=True,
        risk_level="high",
    )


@pytest.fixture
def sample_test_plan(sample_jira_story, sample_test_case):
    """Sample TestPlan object for testing."""
    from datetime import datetime

    from src.models.test_plan import TestPlan, TestPlanMetadata

    metadata = TestPlanMetadata(
        generated_at=datetime(2024, 1, 10, 12, 0, 0),
        ai_model="claude-3-5-sonnet-20241022",
        source_story_key="PROJ-123",
        total_test_cases=1,
        edge_case_count=0,
        integration_test_count=0,
        confidence_score=0.9,
    )

    return TestPlan(
        story=sample_jira_story,
        test_cases=[sample_test_case],
        metadata=metadata,
        summary="Comprehensive test plan for user authentication",
        coverage_analysis="Covers happy path login scenarios",
        risk_assessment="High risk if authentication fails",
        dependencies=["OAuth2 provider", "User database"],
        estimated_execution_time=15,
    )


@pytest.fixture
def mock_jira_client(sample_jira_issue_data):
    """Mock JiraClient for testing."""
    from src.aggregator.jira_client import JiraClient

    client = MagicMock(spec=JiraClient)
    client.get_issue = AsyncMock(return_value=sample_jira_issue_data)
    client.get_linked_issues = AsyncMock(return_value=[])
    client.search_issues = AsyncMock(return_value=[])
    return client


@pytest.fixture
def mock_anthropic_client():
    """Mock Anthropic client for testing."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = [
        MagicMock(
            text="""
        {
            "summary": "Comprehensive test plan for authentication feature",
            "coverage_analysis": "Covers all authentication scenarios",
            "risk_assessment": "High risk feature requiring thorough testing",
            "test_cases": [
                {
                    "title": "Verify user login with valid credentials",
                    "description": "Test successful login with valid credentials",
                    "preconditions": "User account exists",
                    "steps": [
                        {
                            "step_number": 1,
                            "action": "Navigate to login page",
                            "expected_result": "Login form displayed"
                        }
                    ],
                    "expected_result": "User logged in successfully",
                    "priority": "high",
                    "test_type": "functional",
                    "tags": ["authentication", "login"],
                    "automation_candidate": true,
                    "risk_level": "high"
                }
            ],
            "estimated_execution_time": 30,
            "dependencies": ["OAuth2 provider"]
        }
        """
        )
    ]
    mock_client.messages.create = MagicMock(return_value=mock_response)
    return mock_client


@pytest.fixture
async def api_client() -> AsyncGenerator[AsyncClient, None]:
    """Test client for FastAPI app."""
    from src.api.main import app

    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

