"""
Enriched story model for preprocessed story context.
Contains synthesized narrative, extracted APIs, and risk analysis.
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class APISpec(BaseModel):
    """API endpoint specification extracted from Swagger docs or GitLab MCP."""
    
    endpoint_path: str = Field(description="Full endpoint path (e.g., /api/v1/policies)")
    http_methods: List[str] = Field(description="HTTP methods mentioned (GET, POST, etc.)")
    request_schema: Optional[str] = Field(default=None, description="Request body schema (JSON)")
    response_schema: Optional[str] = Field(default=None, description="Response schema (JSON)")
    parameters: Optional[List[str]] = Field(default_factory=list, description="Path/query parameters")
    authentication: Optional[str] = Field(default=None, description="Auth requirements")
    service_name: Optional[str] = Field(default=None, description="Source service name")
    
    # Enhanced fields for complete API documentation (from GitLab MCP)
    request_example: Optional[str] = Field(
        default=None,
        description="Example JSON request body for test steps (e.g., '{\"applicationId\": \"app-123\"}')"
    )
    response_example: Optional[str] = Field(
        default=None,
        description="Example JSON response body for test steps (e.g., '{\"policies\": [...]}')"
    )
    dto_definitions: Optional[dict] = Field(
        default=None,
        description="DTO field definitions with types and descriptions (e.g., {'applicationId': {'type': 'string', 'required': true}})"
    )


class ConfluenceDocRef(BaseModel):
    """Reference to a PRD/Confluence document relevant to the story with structured extraction."""

    title: Optional[str] = Field(default=None, description="Confluence page title")
    url: str = Field(description="Confluence page URL")
    summary: Optional[str] = Field(default=None, description="Short excerpt/summary from the page")
    headings: List[str] = Field(default_factory=list, description="Top-level headings extracted from the document")
    functional_requirements: List[str] = Field(default_factory=list, description="Bulleted functional requirements")
    use_cases: List[str] = Field(default_factory=list, description="Bulleted use cases / scenarios")
    acceptance_criteria: List[str] = Field(default_factory=list, description="Acceptance criteria listed in the PRD")
    non_functional: List[str] = Field(default_factory=list, description="Non-functional requirements")
    notes: List[str] = Field(default_factory=list, description="Other important notes or questions")
    qa_summary: Optional[str] = Field(default=None, description="Concise QA-focused summary of the document")


class EnrichedStory(BaseModel):
    """
    Enriched story with synthesized narrative and extracted context.
    
    This preprocessed story replaces raw dumps in prompts, providing:
    - Compressed narrative explaining the feature
    - Complete acceptance criteria from all linked stories
    - Relevant API specifications extracted from Swagger
    - Risk areas and integration points
    - Related story context
    """
    
    story_key: str = Field(description="Primary story key (e.g., PLAT-123)")
    feature_narrative: str = Field(description="2-3 paragraph synthesis explaining what/why")
    acceptance_criteria: List[str] = Field(
        default_factory=list,
        description="All acceptance criteria from story + linked stories"
    )
    api_specifications: List[APISpec] = Field(
        default_factory=list,
        description="Relevant API endpoints with schemas"
    )
    related_stories: List[str] = Field(
        default_factory=list,
        description="Related story keys with 1-line summaries"
    )
    risk_areas: List[str] = Field(
        default_factory=list,
        description="Integration points, PlainID components, failure scenarios"
    )
    enrichment_timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="When enrichment was performed"
    )
    source_story_ids: List[str] = Field(
        default_factory=list,
        description="All story IDs analyzed during enrichment"
    )
    plainid_components: List[str] = Field(
        default_factory=list,
        description="PlainID components involved (PAP, PDP, POPs, etc.)"
    )
    confluence_docs: List[ConfluenceDocRef] = Field(
        default_factory=list,
        description="PRD/Confluence documents relevant to the story"
    )
    functional_points: List[str] = Field(
        default_factory=list,
        description="Key functional behaviors derived from story and PRD"
    )
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

