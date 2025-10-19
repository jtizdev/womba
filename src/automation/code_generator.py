"""
Automated test code generation from test plans.
Uses AI code generation tools (cursor-cli, aider) to analyze repo and generate matching code.
"""

import json
import subprocess
from pathlib import Path
from typing import Dict, List, Optional
from loguru import logger

from src.models.test_plan import TestPlan
from src.models.test_case import TestCase
from .framework_detector import FrameworkDetector
from .pr_creator import PRCreator


class TestCodeGenerator:
    """Generates executable test code from test plans."""

    def __init__(
        self,
        repo_path: str,
        framework: str = "auto",
        ai_tool: str = "aider"  # or "cursor-cli"
    ):
        """
        Args:
            repo_path: Path to customer's test repository
            framework: Test framework (auto, playwright, cypress, rest-assured, junit)
            ai_tool: AI code generation tool to use
        """
        self.repo_path = Path(repo_path)
        self.framework = framework
        self.ai_tool = ai_tool

        if not self.repo_path.exists():
            raise ValueError(f"Repository path does not exist: {repo_path}")

        self.detector = FrameworkDetector(repo_path)
        self.pr_creator = PRCreator(repo_path)

    async def analyze_repo(self) -> Dict[str, any]:
        """
        Analyze repo to detect:
        - Test framework used
        - File naming patterns
        - Code structure
        - Import patterns

        Returns:
            Dictionary with repository analysis
        """
        logger.info("Analyzing repository structure and patterns...")

        # Detect framework if auto
        if self.framework == "auto":
            self.framework = self.detector.detect_framework()
            logger.info(f"Auto-detected framework: {self.framework}")

        # Analyze patterns
        patterns = self.detector.analyze_patterns()

        analysis = {
            "framework": self.framework,
            "naming_pattern": patterns["naming_pattern"],
            "directory_structure": patterns["directory_structure"],
            "import_patterns": patterns["import_patterns"][:10],  # Top 10
            "test_structure": patterns["test_structure"]
        }

        logger.info(f"Repository analysis complete: {analysis['framework']} framework detected")
        return analysis

    async def generate_code(
        self,
        test_plan: TestPlan,
        target_branch: str = None,
        create_pr: bool = True
    ) -> Optional[str]:
        """
        Generate test code matching repo patterns and optionally create PR.

        Args:
            test_plan: Test plan with test cases to implement
            target_branch: Branch name (default: feature/ai-tests-{story_key})
            create_pr: Whether to create a PR automatically

        Returns:
            PR URL if create_pr=True, otherwise branch name
        """
        story_key = test_plan.story.key
        if not target_branch:
            target_branch = f"feature/ai-tests-{story_key.lower()}"

        logger.info(f"Generating test code for {len(test_plan.test_cases)} test cases")

        # Step 1: Analyze repo
        repo_analysis = await self.analyze_repo()

        # Step 2: Generate prompt for AI tool
        prompt = self._build_generation_prompt(test_plan, repo_analysis)

        # Step 3: Use AI tool to generate code
        generated_files = await self._generate_with_ai_tool(prompt, test_plan)

        if not generated_files:
            logger.error("Failed to generate test files")
            return None

        # Step 4: Create branch and commit
        if not self.pr_creator.create_branch(target_branch):
            logger.error("Failed to create branch")
            return None

        commit_message = self._build_commit_message(test_plan)
        if not self.pr_creator.commit_files(generated_files, commit_message):
            logger.error("Failed to commit files")
            return None

        # Step 5: Push branch
        if not self.pr_creator.push_branch(target_branch):
            logger.error("Failed to push branch")
            return None

        # Step 6: Create PR if requested
        if create_pr:
            pr_url = self.pr_creator.create_pr(
                test_plan=test_plan,
                branch_name=target_branch
            )
            return pr_url
        else:
            return target_branch

    def _build_generation_prompt(
        self,
        test_plan: TestPlan,
        repo_analysis: Dict[str, any]
    ) -> str:
        """Build detailed prompt for AI code generation tool."""
        story = test_plan.story
        test_cases = test_plan.test_cases

        prompt = f"""# Task: Generate Automated Test Files

## Context
You are an expert test automation engineer. You need to generate executable test files based on the following test plan.

## Story Information
- **Key**: {story.key}
- **Summary**: {story.summary}
- **Description**: {story.description[:500]}...

## Repository Analysis
- **Framework**: {repo_analysis['framework']}
- **File naming pattern**: {repo_analysis['naming_pattern']}
- **Test directories**: {', '.join(repo_analysis['directory_structure'].get('test_directories', ['tests/']))}
- **Common imports**:
```
{chr(10).join(repo_analysis['import_patterns'][:5])}
```

## Test Cases to Implement

{self._format_test_cases_for_prompt(test_cases)}

## Requirements

1. **Match existing patterns**: Analyze existing test files in the repository and match their structure, naming, and style.
2. **Framework-specific**: Use {repo_analysis['framework']} best practices and conventions.
3. **File organization**: Place tests in appropriate directories based on test type.
4. **Test data**: Use realistic test data as specified in the test cases.
5. **Assertions**: Write clear, specific assertions that validate expected behavior.
6. **Error handling**: Include appropriate error handling and timeout configurations.
7. **Documentation**: Add comments explaining complex test logic.
8. **Independence**: Each test should be independent and not rely on execution order.

## Naming Convention
Follow the pattern: `{repo_analysis['naming_pattern']}` (e.g., `feature_name{repo_analysis['naming_pattern']}`)

## Output
Generate complete, executable test files that implement ALL test cases above.
Each file should be production-ready and follow repository conventions.
"""

        return prompt

    def _format_test_cases_for_prompt(self, test_cases: List[TestCase]) -> str:
        """Format test cases for the AI prompt."""
        formatted = []

        for i, tc in enumerate(test_cases, 1):
            formatted.append(f"""
### Test Case {i}: {tc.title}

**Description**: {tc.description}

**Type**: {tc.test_type}  
**Priority**: {tc.priority}  
**Preconditions**: {tc.preconditions or 'None'}

**Steps**:
""")
            for step in tc.steps:
                formatted.append(f"{step.step_number}. {step.action}")
                formatted.append(f"   **Expected**: {step.expected_result}")
                if step.test_data:
                    formatted.append(f"   **Test Data**: {step.test_data}")
                formatted.append("")

            formatted.append(f"**Expected Result**: {tc.expected_result}\n")

        return "\n".join(formatted)

    async def _generate_with_ai_tool(
        self,
        prompt: str,
        test_plan: TestPlan
    ) -> List[str]:
        """
        Use AI tool (aider or cursor-cli) to generate code.

        Args:
            prompt: Generation prompt
            test_plan: Test plan for context

        Returns:
            List of generated file paths
        """
        logger.info(f"Using {self.ai_tool} to generate test code...")

        if self.ai_tool == "aider":
            return await self._generate_with_aider(prompt)
        elif self.ai_tool == "cursor-cli":
            return await self._generate_with_cursor(prompt)
        else:
            logger.error(f"Unsupported AI tool: {self.ai_tool}")
            return []

    async def _generate_with_aider(self, prompt: str) -> List[str]:
        """
        Generate code using aider in customer's repo.
        Aider will analyze the repo and generate code matching their patterns.
        """
        try:
            # Save prompt to temp file in customer's repo
            prompt_file = self.repo_path / ".womba_prompt.txt"
            prompt_file.write_text(prompt)

            logger.info("Running aider to generate test code in customer's repo...")
            logger.info(f"Repo: {self.repo_path}")

            # Run aider in customer's repo - it will analyze their patterns automatically
            # Try python3 -m aider first, fallback to aider command
            aider_cmd = ["python3", "-m", "aider"]
            try:
                subprocess.run(["aider", "--version"], capture_output=True, check=True)
                aider_cmd = ["aider"]
            except (FileNotFoundError, subprocess.CalledProcessError):
                pass  # Use python3 -m aider
            
            result = subprocess.run(
                aider_cmd + [
                    "--yes",  # Auto-accept changes
                    "--no-git",  # We'll handle git ourselves
                    "--message-file", str(prompt_file)
                ],
                cwd=self.repo_path,  # Run in CUSTOMER'S repo
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )

            # Clean up prompt file
            if prompt_file.exists():
                prompt_file.unlink()

            if result.returncode != 0:
                logger.error(f"Aider failed: {result.stderr}")
                return []

            # Extract generated files from aider output
            # Aider outputs "Added: filename" or "Modified: filename"
            generated_files = []
            for line in result.stdout.split('\n'):
                if "Added:" in line or "Modified:" in line:
                    file_path = line.split(":", 1)[1].strip()
                    generated_files.append(file_path)

            logger.info(f"✅ Aider generated {len(generated_files)} test files")
            return generated_files

        except subprocess.TimeoutExpired:
            logger.error("Aider timed out after 5 minutes")
            return []
        except FileNotFoundError:
            logger.error("Aider not found. Install with: pip install aider-chat")
            return []
        except Exception as e:
            logger.error(f"Aider execution failed: {e}")
            return []

    async def _generate_with_cursor(self, prompt: str) -> List[str]:
        """
        Generate code using cursor-cli in customer's repo.
        Cursor will analyze the repo structure and generate matching code.
        """
        try:
            # Save prompt to temp file in customer's repo
            prompt_file = self.repo_path / ".womba_prompt.txt"
            prompt_file.write_text(prompt)

            logger.info("Running cursor-cli to generate test code in customer's repo...")
            logger.info(f"Repo: {self.repo_path}")

            # Run cursor-cli with composer/agent mode to generate code
            # The CLI will analyze the repo and generate code matching their patterns
            result = subprocess.run(
                [
                    "cursor",  # cursor-cli command
                    "--command", prompt,
                    "--path", str(self.repo_path),
                    "--no-interactive"  # Don't wait for user input
                ],
                cwd=self.repo_path,  # Run in CUSTOMER'S repo
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )

            # Clean up
            if prompt_file.exists():
                prompt_file.unlink()

            if result.returncode != 0:
                logger.error(f"cursor-cli failed: {result.stderr}")
                logger.info("Note: cursor-cli syntax may vary. Consider using 'aider' instead.")
                return []

            # Parse output to find generated files
            # Look for file creation messages in output
            generated_files = []
            for line in result.stdout.split('\n'):
                if "Created:" in line or "Modified:" in line or "Added:" in line:
                    file_path = line.split(":", 1)[1].strip()
                    generated_files.append(file_path)

            # If no files detected, try to find all modified files in git
            if not generated_files:
                git_result = subprocess.run(
                    ["git", "status", "--porcelain"],
                    cwd=self.repo_path,
                    capture_output=True,
                    text=True
                )
                for line in git_result.stdout.split('\n'):
                    if line.strip():
                        # Format: " M file.txt" or "?? file.txt"
                        file_path = line[3:].strip()
                        if file_path and 'test' in file_path.lower():
                            generated_files.append(file_path)

            logger.info(f"✅ Cursor generated {len(generated_files)} test files")
            return generated_files

        except subprocess.TimeoutExpired:
            logger.error("cursor-cli timed out after 5 minutes")
            return []
        except FileNotFoundError:
            logger.error("cursor command not found. Using aider as fallback...")
            return await self._generate_with_aider(prompt)
        except Exception as e:
            logger.error(f"cursor-cli execution failed: {e}")
            return []

    def _build_commit_message(self, test_plan: TestPlan) -> str:
        """Build commit message for generated tests."""
        story_key = test_plan.story.key
        test_count = len(test_plan.test_cases)

        message = f"""feat: Add AI-generated tests for {story_key}

Generated {test_count} test cases covering:
{test_plan.summary}

Test Types:
"""
        # Count test types
        test_types = {}
        for tc in test_plan.test_cases:
            test_types[tc.test_type] = test_types.get(tc.test_type, 0) + 1

        for test_type, count in test_types.items():
            message += f"- {count} {test_type} tests\n"

        message += f"\nGenerated by: Womba AI\nAI Model: {test_plan.metadata.ai_model}"

        return message

