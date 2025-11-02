"""
Data models for the application.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class PriorityLevel(str, Enum):
    """Test case priority levels."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TestCaseType(str, Enum):
    """Types of test cases."""

    FUNCTIONAL = "functional"
    INTEGRATION = "integration"
    UI = "ui"
    API = "api"
    PERFORMANCE = "performance"
    SECURITY = "security"
    EDGE_CASE = "edge_case"
    NEGATIVE = "negative"
    REGRESSION = "regression"


class JiraStory(BaseModel):
    """Represents a Jira story/issue."""

    key: str = Field(description="Jira issue key (e.g., PROJ-123)")
    summary: str = Field(description="Issue summary")
    description: Optional[str] = Field(default=None, description="Issue description")
    issue_type: str = Field(description="Issue type (Story, Bug, Task, etc.)")
    status: str = Field(description="Current status")
    priority: str = Field(description="Priority")
    assignee: Optional[str] = Field(default=None, description="Assignee email")
    reporter: str = Field(description="Reporter email")
    created: datetime = Field(description="Creation timestamp")
    updated: datetime = Field(description="Last update timestamp")
    labels: List[str] = Field(default_factory=list, description="Labels")
    components: List[str] = Field(default_factory=list, description="Components")
    acceptance_criteria: Optional[str] = Field(
        default=None, description="Acceptance criteria"
    )
    linked_issues: List[str] = Field(
        default_factory=list, description="Linked issue keys"
    )
    attachments: List[str] = Field(
        default_factory=list, description="Attachment URLs"
    )
    custom_fields: Dict[str, Any] = Field(
        default_factory=dict, description="Custom fields"
    )

    class Config:
        # Allow arbitrary types and convert them to strings during serialization
        arbitrary_types_allowed = True
        json_encoders = {
            object: lambda v: str(v) if not isinstance(v, (dict, list, str, int, float, bool, type(None))) else v
        }
        json_schema_extra = {
            "example": {
                "key": "PROJ-123",
                "summary": "Add user authentication feature",
                "description": "Implement OAuth2 authentication...",
                "issue_type": "Story",
                "status": "In Progress",
                "priority": "High",
                "created": "2024-01-01T00:00:00Z",
                "updated": "2024-01-02T00:00:00Z",
            }
        }

