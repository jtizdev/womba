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


class UISpec(BaseModel):
    """UI navigation and access specification."""
    
    feature_name: str = Field(description="Name of the UI feature")
    navigation_path: str = Field(description="Full navigation path (e.g., 'Authorization Workspace → Applications → Policies tab')")
    access_method: str = Field(description="How to access (e.g., 'Click tab', 'Select from menu')")
    ui_elements: List[str] = Field(default_factory=list, description="Key UI elements (buttons, tabs, fields)")
    source: str = Field(description="Where this info came from (story, RAG, inference)")


class APIContext(BaseModel):
    """
    API and UI context for prompt construction (separate from EnrichedStory).
    
    Built using a fallback flow:
    1. Extract from story text directly
    2. Fall back to Swagger RAG collection if incomplete
    3. Fall back to GitLab MCP if Swagger has nothing
    """
    
    api_specifications: List[APISpec] = Field(
        default_factory=list,
        description="API endpoints extracted via fallback flow (story → swagger → MCP)"
    )
    ui_specifications: List[UISpec] = Field(
        default_factory=list,
        description="UI navigation patterns extracted via fallback flow"
    )
    extraction_flow: str = Field(
        default="story→swagger→mcp",
        description="Which sources were used (e.g., 'story', 'story+swagger', 'story+swagger+mcp')"
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
    Enriched story with Jira-native context.
    
    This preprocessed story focuses on original Jira content, providing:
    - Compressed narrative explaining the feature
    - Complete acceptance criteria from all linked stories
    - Risk areas and integration points
    - Related story context and Confluence references
    - Functional points derived from story
    
    NOTE: API and UI specifications are NOT included here.
    They are built separately during prompt construction via APIContext
    using a fallback flow: story → swagger RAG → GitLab MCP.
    """
    
    story_key: str = Field(description="Primary story key (e.g., PLAT-123)")
    feature_narrative: str = Field(description="2-3 paragraph synthesis explaining what/why")
    acceptance_criteria: List[str] = Field(
        default_factory=list,
        description="All acceptance criteria from story + linked stories"
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

