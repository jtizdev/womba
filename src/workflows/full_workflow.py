"""
Full end-to-end workflow orchestrator for Womba
Handles: generate → upload → branch → code → commit → PR
"""

import asyncio
from pathlib import Path
from typing import Optional
from loguru import logger

from src.config.user_config import WombaConfig
from src.config.settings import settings
from src.aggregator.story_collector import StoryCollector
from src.ai.context_indexer import ContextIndexer
from src.ai.two_stage_generator import TwoStageGenerator
from src.integrations.zephyr_integration import ZephyrIntegration
from src.automation.code_generator import TestCodeGenerator
from src.automation.pr_creator import PRCreator


async def _run_git_command(cmd: list, cwd: Path, check: bool = True, capture_output: bool = True) -> tuple:
    """
    Run a git command asynchronously.
    
    Args:
        cmd: Command list (e.g., ["git", "status"])
        cwd: Working directory
        check: If True, raise on non-zero exit
        capture_output: If True, capture stdout/stderr
        
    Returns:
        Tuple of (returncode, stdout, stderr)
    """
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE if capture_output else None,
        stderr=asyncio.subprocess.PIPE if capture_output else None
    )
    stdout, stderr = await proc.communicate()
    
    if check and proc.returncode != 0:
        stderr_text = stderr.decode() if stderr else ""
        raise RuntimeError(f"Command {' '.join(cmd)} failed with code {proc.returncode}: {stderr_text}")
    
    return proc.returncode, stdout, stderr


class FullWorkflowOrchestrator:
    """Orchestrates the complete Womba workflow"""
    
    def __init__(self, config: WombaConfig):
        self.config = config
        self.story_key = None
        self.story_data = None
        self.test_plan = None
        self.zephyr_ids = []
        self.generated_files = []
        self.branch_name = None
        self.pr_url = None
        self.folder_path: Optional[str] = None
    
    async def run(self, story_key: str, repo_path: Optional[str] = None) -> dict:
        """
        Run complete end-to-end workflow
        
        Steps:
        1. Generate test plan
        2. Upload to Zephyr
        3. Create feature branch
        4. Generate test code
        5. Compile tests
        6. Commit & push
        7. Create MR/PR
        
        Returns:
            dict: Summary of workflow results
        """
        self.story_key = story_key
        repo_path = repo_path or self.config.repo_path
        
        if not repo_path:
            raise ValueError("Repository path not configured. Use --repo or configure default repo.")
        
        repo_path = Path(repo_path)
        if not repo_path.exists():
            raise ValueError(f"Repository path does not exist: {repo_path}")
        
        logger.info(f"Starting full workflow for {story_key}")
        
        try:
            # Step 1: Generate test plan
            logger.info("Step 1/7: Generating test plan...")
            await self._generate_test_plan()
            
            # Step 2: Upload to Zephyr
            logger.info("Step 2/7: Uploading to Zephyr...")
            await self._upload_to_zephyr()
            
            # Step 3: Create feature branch
            logger.info("Step 3/7: Creating feature branch...")
            await self._create_feature_branch(repo_path)
            
            # Step 4: Generate test code
            logger.info("Step 4/7: Generating test code...")
            await self._generate_test_code(repo_path)
            
            # Step 5: Compile tests (optional validation)
            logger.info("Step 5/7: Validating tests...")
            await self._validate_tests(repo_path)
            
            # Step 6: Commit & push
            logger.info("Step 6/7: Committing and pushing...")
            await self._commit_and_push(repo_path)
            
            # Step 7: Create MR/PR
            logger.info("Step 7/7: Creating merge request...")
            await self._create_pr(repo_path)
            
            # Return summary
            return self._get_summary()
            
        except Exception as e:
            logger.error(f"Workflow failed: {e}")
            raise
    
    async def _generate_test_plan(self):
        """Step 1: Generate test plan"""
        # Collect story context
        collector = StoryCollector()
        self.story_data = await collector.collect_story_context(self.story_key)
        
        # Use two-stage generator (Analysis → Generation)
        logger.info(f"Creating TwoStageGenerator with model: {self.config.ai_model}")
        generator = TwoStageGenerator(
            api_key=self.config.openai_api_key,
            model=self.config.ai_model,
            use_openai=True
        )
        
        self.test_plan = await generator.generate_test_plan(self.story_data)
        
        logger.info(f"Generated {len(self.test_plan.test_cases)} test cases")
        
        if settings.enable_rag and settings.rag_auto_index:
            try:
                project_key = self.story_key.split('-')[0]
                indexer = ContextIndexer()
                await indexer.index_story_context(self.story_data, project_key)
                logger.info(f"Auto-upserted story context for {self.story_key} into RAG")
            except Exception as exc:
                logger.warning(f"Failed to auto-upsert story context: {exc}")
    
    async def _upload_to_zephyr(self, *, force: bool = False):
        """Step 2: Upload test cases to Zephyr"""
        if not force and not self.config.auto_upload:
            logger.info("Auto-upload disabled, skipping Zephyr upload")
            return
        
        zephyr = ZephyrIntegration()
        
        # Extract project key from story key (e.g., PROJ-12345 -> PROJ)
        project_key = self.story_key.split('-')[0]
        
        results = await zephyr.upload_test_plan(
            test_plan=self.test_plan,
            project_key=project_key,
            folder_path=(self.folder_path or (self.test_plan.suggested_folder if getattr(self.test_plan, 'suggested_folder', None) else None))
        )
        
        self.zephyr_ids = [value for value in results.values() if not str(value).startswith('ERROR')]
        logger.info(f"Uploaded {len(results)} test cases to Zephyr (success: {len(self.zephyr_ids)})")
        return results
    
    async def _create_feature_branch(self, repo_path: Path):
        """Step 3: Create feature branch (async)"""
        # Extract feature name from story summary (simplified)
        feature_name = self.story_data.main_story.summary.lower()
        feature_name = feature_name.replace(' ', '-')[:50]
        feature_name = ''.join(c for c in feature_name if c.isalnum() or c == '-')
        
        base_branch_name = f"feature/{self.story_key}-{feature_name}"
        
        # Check if branch already exists
        returncode, _, _ = await _run_git_command(
            ["git", "rev-parse", "--verify", base_branch_name],
            cwd=repo_path,
            check=False
        )
        
        if returncode == 0:
            # Branch exists, add timestamp to make it unique
            import time
            timestamp = int(time.time())
            self.branch_name = f"{base_branch_name}-{timestamp}"
            logger.info(f"Branch {base_branch_name} exists, using {self.branch_name}")
        else:
            self.branch_name = base_branch_name
        
        # Create and checkout branch
        await _run_git_command(
            ["git", "checkout", "-b", self.branch_name],
            cwd=repo_path
        )
        
        logger.info(f"Created branch: {self.branch_name}")
    
    async def _generate_test_code(self, repo_path: Path):
        """Step 4: Generate test code"""
        generator = TestCodeGenerator(
            repo_path=str(repo_path),
            framework="auto",
            ai_tool=self.config.ai_tool
        )
        
        self.generated_files = await generator.generate_code(self.test_plan)
        if self.generated_files is None:
            self.generated_files = []
        logger.info(f"Generated {len(self.generated_files)} test files")
    
    async def _validate_tests(self, repo_path: Path):
        """Step 5: Validate tests compile (framework-specific) - async"""
        # Try to detect and run compilation/validation
        if (repo_path / "pom.xml").exists():
            logger.info("Detected Maven project, running test-compile...")
            try:
                await _run_git_command(
                    ["mvn", "test-compile", "-DskipTests"],
                    cwd=repo_path,
                    check=False
                )
            except Exception as e:
                logger.warning(f"Test compilation check failed: {e}")
        elif (repo_path / "package.json").exists():
            logger.info("Detected Node project, running tsc check...")
            try:
                await _run_git_command(
                    ["npm", "run", "build"],
                    cwd=repo_path,
                    check=False
                )
            except Exception as e:
                logger.warning(f"Build check failed: {e}")
        else:
            logger.info("No specific validation for this project type")
    
    async def _commit_and_push(self, repo_path: Path):
        """Step 6: Commit and push changes (async)"""
        # Add files
        await _run_git_command(
            ["git", "add", "."],
            cwd=repo_path
        )
        
        # Commit
        commit_message = f"""feat({self.story_key}): Add automated tests

- Generated {len(self.test_plan.test_cases)} test cases
- Story: {self.story_data.main_story.summary}
- Test types: {', '.join(set(tc.test_type for tc in self.test_plan.test_cases))}

Generated by Womba AI Test Generator
"""
        
        await _run_git_command(
            ["git", "commit", "-m", commit_message],
            cwd=repo_path
        )
        
        # Push
        await _run_git_command(
            ["git", "push", "-u", "origin", self.branch_name],
            cwd=repo_path
        )
        
        logger.info(f"Committed and pushed to {self.branch_name}")
    
    async def _create_pr(self, repo_path: Path):
        """Step 7: Create pull/merge request (async)"""
        if not self.config.auto_create_pr:
            logger.info("Auto-create PR disabled, skipping")
            return
        
        pr_creator = PRCreator(
            repo_path=repo_path,
            story=self.story_data
        )
        
        self.pr_url = await pr_creator.create_pr_async(
            branch_name=self.branch_name,
            test_plan=self.test_plan
        )
        
        logger.info(f"Created PR: {self.pr_url}")
    
    def _get_summary(self) -> dict:
        """Get workflow summary"""
        return {
            "story_key": self.story_key,
            "story_title": self.story_data.main_story.summary if self.story_data else None,
            "test_cases_generated": len(self.test_plan.test_cases) if self.test_plan else 0,
            "zephyr_test_ids": self.zephyr_ids,
            "generated_files": self.generated_files,
            "branch_name": self.branch_name,
            "pr_url": self.pr_url,
            "status": "success"
        }


async def run_full_workflow(story_key: str, config: WombaConfig, repo_path: Optional[str] = None, folder_path: Optional[str] = None) -> dict:
    """
    Convenience function to run full workflow
    
    Args:
        story_key: Jira story key (e.g., PROJ-12345)
        config: Womba configuration
        repo_path: Override repository path
        folder_path: Optional Zephyr folder path
    
    Returns:
        dict: Workflow summary
    """
    orchestrator = FullWorkflowOrchestrator(config)
    orchestrator.folder_path = folder_path
    return await orchestrator.run(story_key, repo_path)
