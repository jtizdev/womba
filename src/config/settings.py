"""
Configuration settings for the application.
Loads environment variables and provides type-safe configuration.
"""

from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )

    # API Configuration
    api_host: str = Field(default="0.0.0.0", description="API host")
    api_port: int = Field(default=8000, description="API port")
    environment: str = Field(default="development", description="Environment (development/production)")
    secret_key: str = Field(description="Secret key for signing tokens")
    log_level: str = Field(default="INFO", description="Logging level")

    # AI Provider Keys
    anthropic_api_key: Optional[str] = Field(default=None, description="Anthropic (Claude) API key (optional)")
    openai_api_key: Optional[str] = Field(default=None, description="OpenAI API key (optional)")

    # Atlassian Configuration
    jira_base_url: str = Field(description="Jira base URL")
    jira_email: str = Field(description="Jira user email")
    jira_api_token: str = Field(description="Jira API token")
    confluence_api_token: Optional[str] = Field(default=None, description="Confluence API token")

    # Zephyr Configuration
    zephyr_api_token: str = Field(description="Zephyr Scale API token")
    zephyr_base_url: str = Field(
        default="https://api.zephyrscale.smartbear.com/v2",
        description="Zephyr Scale base URL",
    )

    # Repository Access
    github_token: Optional[str] = Field(default=None, description="GitHub personal access token (optional)")
    gitlab_token: Optional[str] = Field(default=None, description="GitLab token (optional)")
    bitbucket_token: Optional[str] = Field(default=None, description="Bitbucket token (optional)")

    # Figma (Optional)
    figma_api_token: Optional[str] = Field(default=None, description="Figma API token (optional)")
    
    # API Documentation (Optional, customer-specific)
    api_docs_url: Optional[str] = Field(
        default=None, 
        description="Customer's API documentation URL (e.g., https://docs.company.com/api)"
    )
    api_docs_type: Optional[str] = Field(
        default="auto", 
        description="API doc format: 'openapi', 'postman', 'readme', or 'auto'"
    )

    # Database
    database_url: str = Field(
        default="sqlite:///./womba.db", description="Database connection URL"
    )

    # Feature Flags
    enable_mcp_server: bool = Field(default=True, description="Enable MCP server")
    enable_code_generation: bool = Field(default=True, description="Enable code generation")
    enable_figma_integration: bool = Field(
        default=False, description="Enable Figma integration"
    )

    # Rate Limiting
    max_requests_per_minute: int = Field(default=60, description="Max API requests per minute")

    # AI Model Configuration
    default_ai_model: str = Field(
        default="claude-3-5-sonnet-20241022", description="Default AI model to use"
    )
    temperature: float = Field(default=0.8, description="AI temperature for generation (higher = more creative)")
    max_tokens: int = Field(default=10000, description="Max tokens for AI responses")


# Global settings instance
settings = Settings()

