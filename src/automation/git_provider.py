"""
Git provider abstraction for PR/MR creation
Supports GitLab and GitHub - ASYNC version
"""

import asyncio
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional
from loguru import logger


async def _run_git_command(cmd: list, cwd: Path, check: bool = True) -> tuple:
    """
    Run a git command asynchronously.
    
    Returns:
        Tuple of (returncode, stdout, stderr)
    """
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()
    
    stdout_text = stdout.decode() if stdout else ""
    stderr_text = stderr.decode() if stderr else ""
    
    if check and proc.returncode != 0:
        raise RuntimeError(f"Command {' '.join(cmd)} failed: {stderr_text}")
    
    return proc.returncode, stdout_text, stderr_text


class GitProvider(ABC):
    """Base class for git providers"""
    
    def __init__(self, repo_path: Path, remote_url: str = ""):
        self.repo_path = repo_path
        self.remote_url = remote_url
    
    @abstractmethod
    async def create_pr_async(self, branch_name: str, title: str, description: str, base_branch: str = "master") -> str:
        """Create pull/merge request. Returns URL."""
        pass
    
    @staticmethod
    async def get_remote_url_async(repo_path: Path) -> str:
        """Get git remote URL (async)"""
        _, stdout, _ = await _run_git_command(
            ["git", "remote", "get-url", "origin"],
            cwd=repo_path
        )
        return stdout.strip()
    
    @staticmethod
    async def detect_provider_async(repo_path: Path) -> str:
        """Detect git provider from remote URL (async)"""
        try:
            _, stdout, _ = await _run_git_command(
                ["git", "remote", "get-url", "origin"],
                cwd=repo_path
            )
            remote_url = stdout.strip().lower()
            
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
    
    async def create_pr_async(self, branch_name: str, title: str, description: str, base_branch: str = "master") -> str:
        """Create GitLab merge request (async)"""
        # Push will show MR URL in output
        _, _, stderr = await _run_git_command(
            ["git", "push", "-u", "origin", branch_name],
            cwd=self.repo_path,
            check=False
        )
        
        # Extract MR URL from output
        for line in stderr.split('\n'):
            if "merge_requests/new" in line:
                # Extract URL
                if "http" in line:
                    start = line.index("http")
                    url = line[start:].split()[0]
                    return url
        
        # Fallback: construct URL manually
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
    
    async def create_pr_async(self, branch_name: str, title: str, description: str, base_branch: str = "master") -> str:
        """Create GitHub pull request using gh CLI (async)"""
        try:
            # Try using GitHub CLI
            _, stdout, _ = await _run_git_command(
                ["gh", "pr", "create", 
                 "--title", title,
                 "--body", description,
                 "--base", base_branch,
                 "--head", branch_name],
                cwd=self.repo_path
            )
            
            # gh CLI returns PR URL
            pr_url = stdout.strip()
            return pr_url
            
        except FileNotFoundError:
            logger.warning("GitHub CLI (gh) not found. Install with: brew install gh")
            # Fallback: construct URL
            return self._create_pr_url_fallback(branch_name, base_branch)
        except Exception as e:
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


async def create_pr_for_repo_async(
    repo_path: Path,
    branch_name: str,
    title: str,
    description: str,
    base_branch: str = "master",
    provider: Optional[str] = None
) -> str:
    """
    Create PR/MR for repository (async)
    
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
        provider = await GitProvider.detect_provider_async(repo_path)
    
    # Get remote URL
    remote_url = await GitProvider.get_remote_url_async(repo_path)
    
    if provider == "github":
        git_provider = GitHubProvider(repo_path, remote_url)
    elif provider == "gitlab":
        git_provider = GitLabProvider(repo_path, remote_url)
    else:
        logger.warning(f"Unknown git provider: {provider}, using GitLab as default")
        git_provider = GitLabProvider(repo_path, remote_url)
    
    return await git_provider.create_pr_async(branch_name, title, description, base_branch)


# Sync wrapper for backward compatibility
def create_pr_for_repo(
    repo_path: Path,
    branch_name: str,
    title: str,
    description: str,
    base_branch: str = "master",
    provider: Optional[str] = None
) -> str:
    """Sync wrapper for create_pr_for_repo_async."""
    return asyncio.get_event_loop().run_until_complete(
        create_pr_for_repo_async(repo_path, branch_name, title, description, base_branch, provider)
    )
