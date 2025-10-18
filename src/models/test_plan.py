"""
Test plan data models.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from .story import JiraStory
from .test_case import TestCase


class TestPlanMetadata(BaseModel):
    """Metadata about the test plan generation."""

    generated_at: datetime = Field(default_factory=datetime.utcnow, description="Generation timestamp")
    ai_model: str = Field(description="AI model used for generation")
    source_story_key: str = Field(description="Source Jira story key")
    total_test_cases: int = Field(description="Total number of test cases generated")
    edge_case_count: int = Field(default=0, description="Number of edge case tests")
    integration_test_count: int = Field(default=0, description="Number of integration tests")
    confidence_score: Optional[float] = Field(
        default=None, description="AI confidence score (0-1)"
    )


class TestPlan(BaseModel):
    """Represents a complete test plan for a story."""

    story: JiraStory = Field(description="The source Jira story")
    test_cases: List[TestCase] = Field(description="List of test cases")
    metadata: TestPlanMetadata = Field(description="Test plan metadata")
    summary: str = Field(description="Executive summary of the test plan")
    coverage_analysis: Optional[str] = Field(
        default=None, description="Analysis of test coverage"
    )
    risk_assessment: Optional[str] = Field(
        default=None, description="Risk assessment for the feature"
    )
    regression_risks: Optional[str] = Field(
        default=None, description="Specific regression risks identified"
    )
    side_effects: Optional[str] = Field(
        default=None, description="Potential side effects on other features"
    )
    dependencies: List[str] = Field(
        default_factory=list, description="External dependencies or prerequisites"
    )
    estimated_execution_time: Optional[int] = Field(
        default=None, description="Total estimated execution time in minutes"
    )
    suggested_folder: Optional[str] = Field(
        default=None, description="Suggested folder path in test repository"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "summary": "Comprehensive test plan for user authentication feature covering happy paths, edge cases, security scenarios, and error handling.",
                "test_cases": [],
                "metadata": {
                    "ai_model": "claude-3-5-sonnet-20241022",
                    "source_story_key": "PROJ-123",
                    "total_test_cases": 15,
                    "edge_case_count": 5,
                    "integration_test_count": 3,
                },
            }
        }

