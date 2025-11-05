"""
User configuration management for Womba CLI
"""

from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path


@dataclass
class WombaConfig:
    """User configuration for Womba CLI"""
    
    # Repository settings
    repo_path: Optional[str] = None  # Deprecated: use automation_repo_path
    automation_repo_path: Optional[str] = None  # Path to automation test repository
    git_provider: str = "auto"  # "gitlab", "github", or "auto"
    git_remote_url: Optional[str] = None
    default_branch: str = "master"
    
    # Atlassian settings (unified for Jira and Confluence)
    atlassian_url: str = ""
    atlassian_email: str = ""
    atlassian_api_token: str = ""
    
    # Zephyr settings
    zephyr_api_token: str = ""
    project_key: str = ""
    
    # AI settings
    openai_api_key: str = ""
    ai_model: str = "gpt-4o"
    
    # Womba API settings
    womba_api_url: str = "https://womba.onrender.com"
    womba_api_key: str = ""
    
    # Preferences
    auto_upload: bool = False
    auto_create_pr: bool = True
    ai_tool: str = "aider"  # "aider" or "cursor"
    
    # RAG settings
    enable_rag: bool = True  # Enable RAG by default
    rag_auto_index: bool = True  # Auto-index new test plans
    
    def is_complete(self) -> bool:
        """Check if all required fields are set"""
        required_fields = [
            self.atlassian_url,
            self.atlassian_api_token,
            self.zephyr_api_token,
            self.openai_api_key,
        ]
        return all(required_fields)
    
    def get_missing_fields(self) -> list[str]:
        """Get list of missing required fields"""
        missing = []
        if not self.atlassian_url:
            missing.append("atlassian_url")
        if not self.atlassian_api_token:
            missing.append("atlassian_api_token")
        if not self.zephyr_api_token:
            missing.append("zephyr_api_token")
        if not self.openai_api_key:
            missing.append("openai_api_key")
        return missing
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization"""
        return {
            "repo_path": self.repo_path,
            "automation_repo_path": self.automation_repo_path,
            "git_provider": self.git_provider,
            "git_remote_url": self.git_remote_url,
            "default_branch": self.default_branch,
            "atlassian_url": self.atlassian_url,
            "atlassian_email": self.atlassian_email,
            "atlassian_api_token": self.atlassian_api_token,
            "zephyr_api_token": self.zephyr_api_token,
            "project_key": self.project_key,
            "openai_api_key": self.openai_api_key,
            "anthropic_api_key": self.anthropic_api_key,
            "ai_model": self.ai_model,
            "womba_api_url": self.womba_api_url,
            "womba_api_key": self.womba_api_key,
            "auto_upload": self.auto_upload,
            "auto_create_pr": self.auto_create_pr,
            "ai_tool": self.ai_tool,
            "enable_rag": self.enable_rag,
            "rag_auto_index": self.rag_auto_index,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "WombaConfig":
        """Create from dictionary"""
        return cls(**data)

