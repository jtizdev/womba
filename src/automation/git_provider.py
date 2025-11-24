"""
Git provider abstraction for PR/MR creation
Supports GitLab and GitHub
"""

import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional
from loguru import logger


class GitProvider(ABC):
    """Base class for git providers"""
    
    def __init__(self, repo_path: Path):
        self.repo_path = repo_path
        self.remote_url = self._get_remote_url()
    
    @abstractmethod
    def create_pr(self, branch_name: str, title: str, description: str, base_branch: str = "master") -> str:
        """Create pull/merge request. Returns URL."""
        pass
    
    def _get_remote_url(self) -> str:
        """Get git remote URL"""
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=self.repo_path,
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    
    @staticmethod
    def detect_provider(repo_path: Path) -> str:
        """Detect git provider from remote URL"""
        try:
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            remote_url = result.stdout.strip().lower()
            
            if "github.com" in remote_url:
                return "github"
            elif "gitlab.com" in remote_url or "gitlab" in remote_url:
                return "gitlab"
            else:
                return "unknown"
        except Exception as e:
            logger.warning(f"Could not detect git provider: {e}")
            return "unknown"


class GitLabProvider(GitProvider):
    """GitLab MR creation"""
    
    def create_pr(self, branch_name: str, title: str, description: str, base_branch: str = "master") -> str:
        """Create GitLab merge request"""
        # Push will show MR URL in output
        result = subprocess.run(
            ["git", "push", "-u", "origin", branch_name],
            cwd=self.repo_path,
            capture_output=True,
            text=True
        )
        
        # Extract MR URL from output
        for line in result.stderr.split('\n'):
            if "merge_requests/new" in line:
                # Extract URL
                if "http" in line:
                    start = line.index("http")
                    url = line[start:].split()[0]
                    return url
        
        # Fallback: construct URL manually
        # Extract project path from remote URL
        # gitlab.com/company/services/automation.git -> company/services/automation
        remote_url = self.remote_url.replace(".git", "")
        if "gitlab.com/" in remote_url:
            project_path = remote_url.split("gitlab.com/")[1]
        elif "gitlab.com:" in remote_url:
            project_path = remote_url.split("gitlab.com:")[1]
        else:
            return f"GitLab MR created for branch {branch_name}"
        
        return f"https://gitlab.com/{project_path}/-/merge_requests/new?merge_request%5Bsource_branch%5D={branch_name}"


class GitHubProvider(GitProvider):
    """GitHub PR creation"""
    
    def create_pr(self, branch_name: str, title: str, description: str, base_branch: str = "master") -> str:
        """Create GitHub pull request using gh CLI"""
        try:
            # Try using GitHub CLI
            result = subprocess.run(
                ["gh", "pr", "create", 
                 "--title", title,
                 "--body", description,
                 "--base", base_branch,
                 "--head", branch_name],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            
            # gh CLI returns PR URL
            pr_url = result.stdout.strip()
            return pr_url
            
        except FileNotFoundError:
            logger.warning("GitHub CLI (gh) not found. Install with: brew install gh")
            # Fallback: construct URL
            return self._create_pr_url_fallback(branch_name, base_branch)
        except subprocess.CalledProcessError as e:
            logger.warning(f"GitHub CLI failed: {e}")
            return self._create_pr_url_fallback(branch_name, base_branch)
    
    def _create_pr_url_fallback(self, branch_name: str, base_branch: str) -> str:
        """Construct GitHub PR URL manually"""
        # Extract owner/repo from remote URL
        # github.com/owner/repo.git -> owner/repo
        remote_url = self.remote_url.replace(".git", "")
        
        if "github.com/" in remote_url:
            repo_path = remote_url.split("github.com/")[1]
        elif "github.com:" in remote_url:
            repo_path = remote_url.split("github.com:")[1]
        else:
            return f"GitHub PR created for branch {branch_name}"
        
        return f"https://github.com/{repo_path}/compare/{base_branch}...{branch_name}?expand=1"


def create_pr_for_repo(
    repo_path: Path,
    branch_name: str,
    title: str,
    description: str,
    base_branch: str = "master",
    provider: Optional[str] = None
) -> str:
    """
    Create PR/MR for repository
    
    Args:
        repo_path: Path to repository
        branch_name: Branch to create PR from
        title: PR title
        description: PR description
        base_branch: Target branch
        provider: Force provider ("github" or "gitlab"), or auto-detect
    
    Returns:
        str: PR/MR URL
    """
    if provider is None:
        provider = GitProvider.detect_provider(repo_path)
    
    if provider == "github":
        git_provider = GitHubProvider(repo_path)
    elif provider == "gitlab":
        git_provider = GitLabProvider(repo_path)
    else:
        logger.warning(f"Unknown git provider: {provider}, using GitLab as default")
        git_provider = GitLabProvider(repo_path)
    
    return git_provider.create_pr(branch_name, title, description, base_branch)

