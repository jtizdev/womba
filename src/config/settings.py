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
    environment: str = Field(default="production", description="Environment (development/production)")
    secret_key: str = Field(default="change-me-in-production", description="Secret key for signing tokens")
    log_level: str = Field(default="INFO", description="Logging level")

    # AI Provider Keys
    anthropic_api_key: Optional[str] = Field(default=None, description="Anthropic (Claude) API key (optional)")
    openai_api_key: Optional[str] = Field(default=None, description="OpenAI API key (optional)")

    # Atlassian Configuration (unified URL for both Jira and Confluence)
    atlassian_base_url: str = Field(default="https://example.atlassian.net", description="Atlassian base URL (used for both Jira and Confluence)")
    atlassian_email: str = Field(default="user@example.com", description="Atlassian user email")
    atlassian_api_token: str = Field(default="", description="Atlassian API token")

    # Zephyr Configuration
    zephyr_api_token: str = Field(default="", description="Zephyr Scale API token")
    zephyr_base_url: str = Field(
        default="https://api.zephyrscale.smartbear.com/v2",
        description="Zephyr Scale base URL",
    )

    # Repository Access
    github_token: Optional[str] = Field(default=None, description="GitHub personal access token (optional)")
    gitlab_token: Optional[str] = Field(default=None, description="GitLab personal access token (optional)")
    gitlab_base_url: str = Field(default="https://gitlab.com", description="GitLab base URL")
    gitlab_group_path: str = Field(default="plainid/srv", description="GitLab group path for service repositories")
    gitlab_swagger_enabled: bool = Field(default=True, description="Enable GitLab Swagger indexing")
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
    ai_model: str = Field(
        default="gpt-4o-2024-08-06", 
        description="AI model for test generation (gpt-4o-2024-08-06 supports JSON schema + 16K output tokens)"
    )
    temperature: float = Field(default=0.8, description="AI temperature for generation (higher = more creative)")
    max_tokens: int = Field(default=10000, description="Max tokens for AI responses (gpt-4o-2024-08-06 supports up to 16384)")
    
    # RAG Configuration
    enable_rag: bool = Field(default=True, description="Enable RAG for context retrieval")
    rag_collection_path: str = Field(default="./data/chroma", description="ChromaDB storage path")
    embedding_model: str = Field(default="text-embedding-3-small", description="OpenAI embedding model")
    # RAG Top-K Configuration (adjust based on your data quality and token budget)
    # Note: These are starting defaults. Monitor similarity scores and adjust based on:
    # - Average similarity scores (aim for >0.6)
    # - Token budget (more results = more tokens)
    # - Quality of generated tests (too many irrelevant results hurts quality)
    rag_top_k_tests: int = Field(
        default=8, 
        description="Similar test plans to retrieve (increased for better style learning)"
    )
    rag_top_k_docs: int = Field(
        default=20, 
        description="Similar Confluence docs to retrieve (2x increase - docs are valuable context)"
    )
    rag_top_k_stories: int = Field(
        default=15, 
        description="Similar Jira stories to retrieve (50% increase for more domain context)"
    )
    rag_top_k_existing: int = Field(
        default=40, 
        description="Similar existing Zephyr tests to retrieve (2x increase for better duplicate detection)"
    )
    rag_top_k_swagger: int = Field(
        default=10,
        description="Similar Swagger/OpenAPI docs to retrieve (2x increase for complete API coverage)"
    )
    rag_auto_index: bool = Field(default=True, description="Automatically index after test generation")
    rag_min_similarity: float = Field(default=0.5, description="Minimum similarity threshold (0.0-1.0) to filter low-quality results")
    rag_refresh_hours: Optional[float] = Field(default=None, description="Minimum hours between automatic full RAG refresh runs")

    # PlainID External Documentation Indexing
    plainid_doc_index_enabled: bool = Field(default=True, description="Enable PlainID documentation indexing")
    plainid_doc_base_url: Optional[str] = Field(default=None, description="Base URL for PlainID Developer Portal (optional)")
    plainid_doc_urls: Optional[list] = Field(
        default=[
            "https://docs.plainid.io/apidocs/authorization-apis",
            "https://docs.plainid.io/apidocs/policy-management-apis",
            "https://docs.plainid.io/apidocs/authentication-mgmt-apis"
        ],
        description="List of PlainID API documentation entry points to crawl from"
    )
    plainid_doc_max_pages: int = Field(default=200, description="Maximum pages to crawl from PlainID docs")
    plainid_doc_max_depth: int = Field(default=5, description="Maximum crawl depth for PlainID docs")
    plainid_doc_request_delay: float = Field(default=0.3, description="Delay between requests (seconds)")
    plainid_doc_project_key: str = Field(default="PLAT", description="Project key for PlainID docs")

    # Story Enrichment Configuration
    enable_story_enrichment: bool = Field(default=True, description="Enable story preprocessing/enrichment pipeline")
    enrichment_max_hops: int = Field(default=2, description="Maximum hops for recursive story link following (0=none, 1=direct, 2=2-level)")
    enrichment_cache_ttl_days: int = Field(default=7, description="Cache TTL in days - invalidate if story updated or cache older than this")
    enrichment_max_apis: int = Field(default=5, description="Maximum number of API endpoints to extract from Swagger")
    enrichment_cache_dir: str = Field(default="./data/enrichment_cache", description="Directory for enrichment cache storage")


# Global settings instance
settings = Settings()

