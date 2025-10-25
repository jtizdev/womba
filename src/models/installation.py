"""
Models for Atlassian Connect installation data.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class Installation(BaseModel):
    """
    Represents an installation of the Womba app in a Jira instance.
    
    This stores the necessary credentials and metadata for JWT authentication
    and communication with a specific Jira Cloud instance.
    """
    
    client_key: str = Field(
        ...,
        description="Unique identifier for the Jira instance"
    )
    
    shared_secret: str = Field(
        ...,
        description="Shared secret for JWT signature verification"
    )
    
    base_url: str = Field(
        ...,
        description="Base URL of the Jira instance (e.g., https://example.atlassian.net)"
    )
    
    product_type: str = Field(
        default="jira",
        description="Product type (jira, confluence, etc.)"
    )
    
    description: Optional[str] = Field(
        default=None,
        description="Human-readable description of the instance"
    )
    
    installed_at: datetime = Field(
        default_factory=datetime.now,
        description="Timestamp when the app was installed"
    )
    
    enabled: bool = Field(
        default=True,
        description="Whether the app is currently enabled for this instance"
    )
    
    public_key: Optional[str] = Field(
        default=None,
        description="Public key for additional security (optional)"
    )
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

