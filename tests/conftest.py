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
            "coverage_analysis": "Covers all authentication scenarios including happy path, edge cases, and error handling",
            "risk_assessment": "High risk feature requiring thorough testing",
            "test_cases": [
                {
                    "title": "Verify user login with valid credentials",
                    "description": "Test successful login with valid email and password via POST /api/auth/login endpoint",
                    "preconditions": "User account exists in the system",
                    "steps": [
                        {"step_number": 1, "action": "Navigate to login page", "expected_result": "Login form displayed"},
                        {"step_number": 2, "action": "Enter valid email and password", "expected_result": "Credentials accepted"},
                        {"step_number": 3, "action": "Click login button", "expected_result": "User redirected to dashboard"}
                    ],
                    "expected_result": "User logged in successfully and sees dashboard",
                    "priority": "high",
                    "test_type": "functional",
                    "tags": ["authentication", "login", "happy-path"],
                    "automation_candidate": true,
                    "risk_level": "high"
                },
                {
                    "title": "Verify Google OAuth login",
                    "description": "Test successful login using Google OAuth via GET /api/auth/google endpoint",
                    "preconditions": "User has Google account",
                    "steps": [
                        {"step_number": 1, "action": "Click 'Login with Google' button", "expected_result": "Redirected to Google"},
                        {"step_number": 2, "action": "Enter Google credentials", "expected_result": "Google authenticates user"},
                        {"step_number": 3, "action": "Approve OAuth consent", "expected_result": "Redirected back to app"}
                    ],
                    "expected_result": "User logged in via Google OAuth",
                    "priority": "high",
                    "test_type": "functional",
                    "tags": ["authentication", "oauth", "google"],
                    "automation_candidate": true,
                    "risk_level": "high"
                },
                {
                    "title": "Verify login fails with invalid password",
                    "description": "Test that login fails with wrong password at POST /api/auth/login endpoint",
                    "preconditions": "User account exists",
                    "steps": [
                        {"step_number": 1, "action": "Navigate to login page", "expected_result": "Login form displayed"},
                        {"step_number": 2, "action": "Enter valid email and invalid password", "expected_result": "Credentials rejected"},
                        {"step_number": 3, "action": "Click login button", "expected_result": "Error message shown"}
                    ],
                    "expected_result": "Login fails with appropriate error message",
                    "priority": "high",
                    "test_type": "negative",
                    "tags": ["authentication", "security", "error-handling"],
                    "automation_candidate": true,
                    "risk_level": "high"
                },
                {
                    "title": "Verify failed login attempts are logged",
                    "description": "Test that failed login attempts are recorded in logs via custom logging policy",
                    "preconditions": "User account exists and logging is enabled",
                    "steps": [
                        {"step_number": 1, "action": "Attempt login with wrong password", "expected_result": "Login fails"},
                        {"step_number": 2, "action": "Check system logs", "expected_result": "Failed attempt logged with timestamp and IP"}
                    ],
                    "expected_result": "Failed login attempt is logged with details",
                    "priority": "medium",
                    "test_type": "security",
                    "tags": ["authentication", "security", "logging"],
                    "automation_candidate": true,
                    "risk_level": "medium"
                },
                {
                    "title": "Verify account lockout after multiple failed attempts",
                    "description": "Test that account is locked after 5 failed login attempts per custom security policy",
                    "preconditions": "User account exists",
                    "steps": [
                        {"step_number": 1, "action": "Attempt login with wrong password 5 times", "expected_result": "Each attempt fails"},
                        {"step_number": 2, "action": "Attempt 6th login with correct password", "expected_result": "Account locked message shown"}
                    ],
                    "expected_result": "Account is locked and user cannot login",
                    "priority": "high",
                    "test_type": "security",
                    "tags": ["authentication", "security", "brute-force"],
                    "automation_candidate": true,
                    "risk_level": "high"
                },
                {
                    "title": "Verify session timeout after inactivity",
                    "description": "Test that user session expires after 30 minutes of inactivity",
                    "preconditions": "User is logged in",
                    "steps": [
                        {"step_number": 1, "action": "Login successfully", "expected_result": "User logged in"},
                        {"step_number": 2, "action": "Wait 30 minutes without activity", "expected_result": "Session expires"},
                        {"step_number": 3, "action": "Try to access protected page", "expected_result": "Redirected to login"}
                    ],
                    "expected_result": "Session expires and user must re-login",
                    "priority": "medium",
                    "test_type": "security",
                    "tags": ["authentication", "session", "timeout"],
                    "automation_candidate": true,
                    "risk_level": "medium"
                },
                {
                    "title": "Verify password reset flow",
                    "description": "Test that users can reset forgotten passwords",
                    "preconditions": "User account exists with valid email",
                    "steps": [
                        {"step_number": 1, "action": "Click 'Forgot Password' link", "expected_result": "Password reset form shown"},
                        {"step_number": 2, "action": "Enter email address", "expected_result": "Reset email sent"},
                        {"step_number": 3, "action": "Click reset link in email", "expected_result": "New password form shown"},
                        {"step_number": 4, "action": "Enter and confirm new password", "expected_result": "Password updated"}
                    ],
                    "expected_result": "User can login with new password",
                    "priority": "high",
                    "test_type": "functional",
                    "tags": ["authentication", "password-reset"],
                    "automation_candidate": true,
                    "risk_level": "medium"
                }
            ],
            "estimated_execution_time": 45,
            "dependencies": ["OAuth2 provider", "Email service"]
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
    from httpx import ASGITransport

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest.fixture
def mock_integration_env(monkeypatch, sample_jira_story, mock_anthropic_client):
    """
    Mock environment for integration tests that make real API calls.
    Patches Jira and Anthropic clients to avoid real API calls.
    """
    from unittest.mock import Mock, AsyncMock
    from datetime import datetime
    from src.models.story import JiraStory
    
    # Create a subtask
    subtask = JiraStory(
        key="PROJ-124",
        summary="Implement OAuth2 integration",
        description="Technical task for OAuth2",
        issue_type="Task",
        status="In Progress",
        priority="High",
        reporter="dev@example.com",
        created=datetime(2024, 1, 2, 10, 0, 0),
        updated=datetime(2024, 1, 3, 15, 30, 0),
    )
    
    # Mock Jira Client
    mock_jira = Mock()
    mock_jira.get_issue_with_subtasks = AsyncMock(return_value=(sample_jira_story, [subtask]))
    mock_jira.get_issue = AsyncMock(return_value=sample_jira_story)
    mock_jira.get_linked_issues = AsyncMock(return_value=[])
    mock_jira.search_issues = Mock(return_value=([], 0))
    
    # Mock Confluence Client - mock all methods that make API calls
    mock_confluence = Mock()
    mock_confluence.search_all_pages = AsyncMock(return_value=[])
    mock_confluence.search_pages = AsyncMock(return_value=[])
    mock_confluence.find_related_pages = AsyncMock(return_value=[])
    mock_confluence._fetch_json = AsyncMock(return_value={'results': []})
    
    # Mock OpenAI Client
    mock_openai = Mock()
    mock_openai_response = Mock()
    mock_openai_response.choices = [
        Mock(message=Mock(content=mock_anthropic_client.messages.create().content[0].text))
    ]
    mock_openai.chat.completions.create = Mock(return_value=mock_openai_response)
    
    # Patch the client classes to return our mocks
    monkeypatch.setattr("src.aggregator.jira_client.JiraClient", lambda: mock_jira)
    monkeypatch.setattr("src.aggregator.story_collector.JiraClient", lambda: mock_jira)
    monkeypatch.setattr("src.aggregator.confluence_client.ConfluenceClient", lambda: mock_confluence)
    monkeypatch.setattr("src.aggregator.story_collector.ConfluenceClient", lambda: mock_confluence)
    monkeypatch.setattr("anthropic.Anthropic", lambda api_key=None: mock_anthropic_client)
    monkeypatch.setattr("openai.OpenAI", lambda api_key=None: mock_openai)
    
    return {
        "jira": mock_jira,
        "confluence": mock_confluence,
        "anthropic": mock_anthropic_client,
        "openai": mock_openai
    }

