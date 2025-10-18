"""
Test case data models.
"""

from typing import List, Optional

from pydantic import BaseModel, Field

from .story import PriorityLevel, TestCaseType


class TestStep(BaseModel):
    """Represents a single test step."""

    step_number: int = Field(description="Step number in sequence")
    action: str = Field(description="Action to perform")
    expected_result: str = Field(description="Expected result of the action")
    test_data: Optional[str] = Field(default=None, description="Test data to use")


class TestCase(BaseModel):
    """Represents a single test case."""

    id: Optional[str] = Field(default=None, description="Test case ID (from Zephyr)")
    title: str = Field(description="Test case title")
    description: str = Field(description="Detailed description")
    preconditions: Optional[str] = Field(
        default=None, description="Preconditions before test execution"
    )
    steps: List[TestStep] = Field(description="Test steps")
    expected_result: str = Field(description="Overall expected result")
    priority: PriorityLevel = Field(default=PriorityLevel.MEDIUM, description="Test priority")
    test_type: TestCaseType = Field(
        default=TestCaseType.FUNCTIONAL, description="Type of test"
    )
    tags: List[str] = Field(default_factory=list, description="Tags for categorization")
    estimated_time: Optional[int] = Field(
        default=None, description="Estimated execution time in minutes"
    )
    automation_candidate: bool = Field(
        default=True, description="Whether this test is a good candidate for automation"
    )
    risk_level: str = Field(default="medium", description="Risk level if this test fails")
    related_existing_tests: List[str] = Field(
        default_factory=list, description="Related existing test case keys"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "title": "Verify user login with valid credentials",
                "description": "Test that a user can successfully login with valid email and password",
                "preconditions": "User account exists in the system",
                "steps": [
                    {
                        "step_number": 1,
                        "action": "Navigate to login page",
                        "expected_result": "Login form is displayed",
                    },
                    {
                        "step_number": 2,
                        "action": "Enter valid email and password",
                        "expected_result": "Credentials are accepted",
                        "test_data": "email: test@example.com, password: Test123!",
                    },
                ],
                "expected_result": "User is logged in and redirected to dashboard",
                "priority": "high",
                "test_type": "functional",
                "tags": ["authentication", "login", "smoke"],
            }
        }

