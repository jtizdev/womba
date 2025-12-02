"""
PR creation for automated test code.
"""

import asyncio
from pathlib import Path
from typing import List, Optional
from loguru import logger

from src.models.test_plan import TestPlan
from src.models.story import JiraStory
from src.automation.git_provider import create_pr_for_repo, create_pr_for_repo_async


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
    
    if check and proc.returncode != 0:
        stderr_text = stderr.decode() if stderr else ""
        raise RuntimeError(f"Command {' '.join(cmd)} failed: {stderr_text}")
    
    return proc.returncode, stdout, stderr


class PRCreator:
    """Creates pull requests with generated test code."""

    def __init__(self, repo_path: str, story: Optional[JiraStory] = None):
        """
        Args:
            repo_path: Path to the test repository
            story: Jira story (optional, for better PR descriptions)
        """
        self.repo_path = Path(repo_path)
        self.story = story
        if not self.repo_path.exists():
            raise ValueError(f"Repository path does not exist: {repo_path}")

    async def create_branch_async(self, branch_name: str) -> bool:
        """
        Create a new git branch (async).

        Args:
            branch_name: Name of the branch to create

        Returns:
            True if successful, False otherwise
        """
        try:
            # Check if branch already exists
            returncode, _, _ = await _run_git_command(
                ["git", "rev-parse", "--verify", branch_name],
                cwd=self.repo_path,
                check=False
            )

            if returncode == 0:
                logger.warning(f"Branch {branch_name} already exists, switching to it")
                await _run_git_command(
                    ["git", "checkout", branch_name],
                    cwd=self.repo_path
                )
            else:
                # Create new branch
                await _run_git_command(
                    ["git", "checkout", "-b", branch_name],
                    cwd=self.repo_path
                )

            logger.info(f"Created/switched to branch: {branch_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to create branch: {e}")
            return False

    async def commit_files_async(self, files: List[str], commit_message: str) -> bool:
        """
        Commit files to the current branch (async).

        Args:
            files: List of file paths to commit
            commit_message: Commit message

        Returns:
            True if successful, False otherwise
        """
        try:
            # Add files
            await _run_git_command(
                ["git", "add"] + files,
                cwd=self.repo_path
            )

            # Commit
            await _run_git_command(
                ["git", "commit", "-m", commit_message],
                cwd=self.repo_path
            )

            logger.info(f"Committed {len(files)} files")
            return True

        except Exception as e:
            logger.error(f"Failed to commit files: {e}")
            return False

    async def push_branch_async(self, branch_name: str) -> bool:
        """
        Push branch to remote (async).

        Args:
            branch_name: Name of the branch to push

        Returns:
            True if successful, False otherwise
        """
        try:
            await _run_git_command(
                ["git", "push", "-u", "origin", branch_name],
                cwd=self.repo_path
            )

            logger.info(f"Pushed branch: {branch_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to push branch: {e}")
            return False

    async def create_pr_async(
        self,
        test_plan: TestPlan,
        branch_name: str,
        base_branch: str = "main"
    ) -> Optional[str]:
        """
        Create a pull request using GitHub CLI (async).

        Args:
            test_plan: Test plan that was implemented
            branch_name: Source branch name
            base_branch: Target branch name (default: main)

        Returns:
            PR URL if successful, None otherwise
        """
        try:
            story_key = test_plan.story.key if test_plan.story else "Unknown"
            pr_title = f"feat({story_key}): Add AI-generated test cases"
            pr_body = self._build_pr_description(test_plan)

            # Use new git provider abstraction (async)
            pr_url = await create_pr_for_repo_async(
                repo_path=self.repo_path,
                branch_name=branch_name,
                title=pr_title,
                description=pr_body,
                base_branch=base_branch
            )

            logger.info(f"Created PR: {pr_url}")
            return pr_url

        except Exception as e:
            logger.error(f"Failed to create PR: {e}")
            return None

    # Sync wrappers for backward compatibility
    def create_branch(self, branch_name: str) -> bool:
        """Sync wrapper for create_branch_async."""
        return asyncio.get_event_loop().run_until_complete(
            self.create_branch_async(branch_name)
        )

    def commit_files(self, files: List[str], commit_message: str) -> bool:
        """Sync wrapper for commit_files_async."""
        return asyncio.get_event_loop().run_until_complete(
            self.commit_files_async(files, commit_message)
        )

    def push_branch(self, branch_name: str) -> bool:
        """Sync wrapper for push_branch_async."""
        return asyncio.get_event_loop().run_until_complete(
            self.push_branch_async(branch_name)
        )

    def create_pr(
        self,
        test_plan: TestPlan,
        branch_name: str,
        base_branch: str = "main"
    ) -> Optional[str]:
        """Sync wrapper for create_pr_async."""
        return asyncio.get_event_loop().run_until_complete(
            self.create_pr_async(test_plan, branch_name, base_branch)
        )

    def _build_pr_description(self, test_plan: TestPlan) -> str:
        """Build detailed PR description."""
        story = test_plan.story
        test_cases = test_plan.test_cases

        # Count test types
        test_types = {}
        for tc in test_cases:
            test_types[tc.test_type] = test_types.get(tc.test_type, 0) + 1

        test_types_summary = ", ".join([f"{count} {type}" for type, count in test_types.items()])

        description = f"""## 🤖 AI-Generated Test Cases

**Jira Story**: [{story.key}]({story.key}) - {story.summary}

**Test Coverage**: {len(test_cases)} test cases ({test_types_summary})

### 📋 Test Cases Generated:

"""

        for i, tc in enumerate(test_cases, 1):
            description += f"{i}. **{tc.title}**\n"
            description += f"   - Type: {tc.test_type}\n"
            description += f"   - Priority: {tc.priority}\n"
            description += f"   - Steps: {len(tc.steps)}\n"
            description += f"   - Automation candidate: {'✅' if tc.automation_candidate else '❌'}\n\n"

        description += f"""
### 📊 Summary

{test_plan.summary}

### ✅ Review Checklist

- [ ] Tests follow repository patterns and conventions
- [ ] Test data is realistic and meaningful
- [ ] Assertions are clear and specific
- [ ] Tests are independent and can run in any order
- [ ] Error messages are helpful for debugging
- [ ] Tests are properly documented

### 🤖 Generated by Womba AI

This PR was automatically generated by Womba AI based on the Jira story requirements, PRD, and technical design documents.

**Quality Score**: {test_plan.metadata.confidence_score * 100 if test_plan.metadata.confidence_score else 'N/A'}/100

**AI Model**: {test_plan.metadata.ai_model}
"""

        return description
