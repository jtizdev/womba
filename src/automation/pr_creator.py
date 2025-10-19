"""
PR creation for automated test code.
"""

import subprocess
from pathlib import Path
from typing import List, Optional
from loguru import logger

from src.models.test_plan import TestPlan


class PRCreator:
    """Creates pull requests with generated test code."""

    def __init__(self, repo_path: str):
        """
        Args:
            repo_path: Path to the test repository
        """
        self.repo_path = Path(repo_path)
        if not self.repo_path.exists():
            raise ValueError(f"Repository path does not exist: {repo_path}")

    def create_branch(self, branch_name: str) -> bool:
        """
        Create a new git branch.

        Args:
            branch_name: Name of the branch to create

        Returns:
            True if successful, False otherwise
        """
        try:
            # Check if branch already exists
            result = subprocess.run(
                ["git", "rev-parse", "--verify", branch_name],
                cwd=self.repo_path,
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                logger.warning(f"Branch {branch_name} already exists, switching to it")
                subprocess.run(
                    ["git", "checkout", branch_name],
                    cwd=self.repo_path,
                    check=True
                )
            else:
                # Create new branch
                subprocess.run(
                    ["git", "checkout", "-b", branch_name],
                    cwd=self.repo_path,
                    check=True
                )

            logger.info(f"Created/switched to branch: {branch_name}")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to create branch: {e}")
            return False

    def commit_files(self, files: List[str], commit_message: str) -> bool:
        """
        Commit files to the current branch.

        Args:
            files: List of file paths to commit
            commit_message: Commit message

        Returns:
            True if successful, False otherwise
        """
        try:
            # Add files
            subprocess.run(
                ["git", "add"] + files,
                cwd=self.repo_path,
                check=True
            )

            # Commit
            subprocess.run(
                ["git", "commit", "-m", commit_message],
                cwd=self.repo_path,
                check=True
            )

            logger.info(f"Committed {len(files)} files")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to commit files: {e}")
            return False

    def push_branch(self, branch_name: str) -> bool:
        """
        Push branch to remote.

        Args:
            branch_name: Name of the branch to push

        Returns:
            True if successful, False otherwise
        """
        try:
            subprocess.run(
                ["git", "push", "-u", "origin", branch_name],
                cwd=self.repo_path,
                check=True
            )

            logger.info(f"Pushed branch: {branch_name}")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to push branch: {e}")
            return False

    def create_pr(
        self,
        test_plan: TestPlan,
        branch_name: str,
        base_branch: str = "main"
    ) -> Optional[str]:
        """
        Create a pull request using GitHub CLI.

        Args:
            test_plan: Test plan that was implemented
            branch_name: Source branch name
            base_branch: Target branch name (default: main)

        Returns:
            PR URL if successful, None otherwise
        """
        try:
            story_key = test_plan.story.key
            pr_title = f"🤖 AI-Generated Tests for {story_key}"
            pr_body = self._build_pr_description(test_plan)

            result = subprocess.run(
                [
                    "gh", "pr", "create",
                    "--title", pr_title,
                    "--body", pr_body,
                    "--base", base_branch,
                    "--head", branch_name,
                    "--label", "ai-generated",
                    "--label", "tests"
                ],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True
            )

            pr_url = result.stdout.strip()
            logger.info(f"Created PR: {pr_url}")
            return pr_url

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to create PR: {e}")
            logger.error(f"Error output: {e.stderr}")
            return None

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

