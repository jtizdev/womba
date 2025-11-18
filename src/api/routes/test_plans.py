"""
API routes for test plan generation and management.
"""

from typing import Optional, List
from pathlib import Path
import json
import os

from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel, Field

from src.aggregator.story_collector import StoryCollector
from src.ai.test_plan_generator import TestPlanGenerator
from src.integrations.zephyr_integration import ZephyrIntegration
from src.models.test_plan import TestPlan
from src.models.test_case import TestCase

router = APIRouter()


class GenerateTestPlanRequest(BaseModel):
    """Request model for test plan generation."""

    issue_key: str
    upload_to_zephyr: bool = False
    project_key: Optional[str] = None
    folder_id: Optional[str] = None


class GenerateTestPlanResponse(BaseModel):
    """Response model for test plan generation."""

    test_plan: TestPlan
    zephyr_results: Optional[dict] = None


@router.post("/generate", response_model=GenerateTestPlanResponse)
async def generate_test_plan(request: GenerateTestPlanRequest):
    """
    Generate a comprehensive test plan for a Jira story.

    This is the main endpoint that:
    1. Collects story context from Jira and related sources
    2. Uses AI to generate comprehensive test cases
    3. Optionally uploads to Zephyr Scale

    Args:
        request: Test plan generation request

    Returns:
        Generated test plan with optional Zephyr upload results
    """
    logger.info(f"API: Generating test plan for {request.issue_key}")
    
    # Validate request early (before any expensive operations)
    if request.upload_to_zephyr and not request.project_key:
        raise HTTPException(
            status_code=400,
            detail="project_key is required when upload_to_zephyr is True",
        )
    
    import time
    start_time = time.time()

    try:
        # Step 1: Collect story context
        logger.info("Step 1: Collecting story context...")
        collector = StoryCollector()
        context = await collector.collect_story_context(request.issue_key)

        # Step 2: Generate test plan with AI
        logger.info("Step 2: Generating test plan with AI...")
        generator = TestPlanGenerator()
        test_plan = await generator.generate_test_plan(context)

        logger.info(
            f"Generated {len(test_plan.test_cases)} test cases for {request.issue_key}"
        )

        # Step 3: Save test plan to JSON file for history
        test_plan_file = None
        try:
            from pathlib import Path
            import json
            test_plans_dir = Path("test_plans")
            test_plans_dir.mkdir(exist_ok=True)
            test_plan_file = test_plans_dir / f"test_plan_{request.issue_key}.json"
            
            with open(test_plan_file, 'w') as f:
                json.dump(test_plan.dict(), f, indent=2, default=str)
            logger.info(f"Saved test plan to {test_plan_file}")
        except Exception as e:
            logger.error(f"Failed to save test plan to file: {e}")

        # Step 4: Upload to Zephyr if requested
        zephyr_results = None
        zephyr_ids = []
        if request.upload_to_zephyr:

            logger.info("Step 4: Uploading test plan to Zephyr...")
            zephyr = ZephyrIntegration()
            zephyr_results = await zephyr.upload_test_plan(
                test_plan=test_plan,
                project_key=request.project_key,
                folder_id=request.folder_id,
            )
            logger.info("Successfully uploaded test plan to Zephyr")
            
            # Extract Zephyr IDs from results
            if zephyr_results and 'test_case_ids' in zephyr_results:
                zephyr_ids = zephyr_results['test_case_ids']
        
        # Track in history with test plan file path
        duration = int(time.time() - start_time)
        from .ui import track_test_generation
        track_test_generation(
            story_key=request.issue_key,
            test_count=len(test_plan.test_cases),
            status='success',
            duration=duration,
            zephyr_ids=zephyr_ids if zephyr_ids else None,
            test_plan_file=str(test_plan_file) if test_plan_file else None
        )

        return GenerateTestPlanResponse(
            test_plan=test_plan, zephyr_results=zephyr_results
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate test plan for {request.issue_key}: {e}")
        
        # Track failure
        duration = int(time.time() - start_time)
        from .ui import track_test_generation
        track_test_generation(
            story_key=request.issue_key,
            test_count=0,
            status='failed',
            duration=duration
        )
        
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{issue_key}/generate")
async def generate_test_plan_simple(
    issue_key: str, upload_to_zephyr: bool = False, project_key: Optional[str] = None
):
    """
    Simplified endpoint for test plan generation.

    Args:
        issue_key: Jira issue key
        upload_to_zephyr: Whether to upload to Zephyr
        project_key: Project key for Zephyr upload

    Returns:
        Generated test plan
    """
    request = GenerateTestPlanRequest(
        issue_key=issue_key,
        upload_to_zephyr=upload_to_zephyr,
        project_key=project_key,
    )
    return await generate_test_plan(request)


class UpdateTestPlanRequest(BaseModel):
    """Request model for updating an existing test plan."""
    # Accept List[dict] to handle partial/incomplete test cases from UI
    test_cases: List[dict] = Field(description="Updated list of test cases (can be partial/incomplete from UI)")
    upload_to_zephyr: bool = Field(default=False, description="Whether to upload to Zephyr after update")
    project_key: Optional[str] = Field(default=None, description="Project key for Zephyr upload")
    folder_id: Optional[str] = Field(default=None, description="Folder ID for Zephyr")
    folder_path: Optional[str] = Field(default=None, description="Folder path for Zephyr")


class UpdateTestPlanResponse(BaseModel):
    """Response model for test plan update."""
    test_plan: TestPlan
    zephyr_results: Optional[dict] = None
    message: str


def _get_test_plan_path(issue_key: str) -> Path:
    """Get the absolute path to a test plan file."""
    app_root = Path(os.getenv("APP_ROOT", "/app"))
    return app_root / "test_plans" / f"test_plan_{issue_key}.json"


@router.get("/{issue_key}")
async def get_test_plan(issue_key: str):
    """
    Get an existing test plan by issue key.
    
    Args:
        issue_key: Jira issue key
        
    Returns:
        Test plan if found
        
    Raises:
        HTTPException: 404 if test plan not found
    """
    plan_path = _get_test_plan_path(issue_key)
    
    if not plan_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Test plan not found for {issue_key}. Generate a test plan first."
        )
    
    logger.info(f"Loading test plan from {plan_path}")
    test_plan = TestPlan.model_validate_json(plan_path.read_text())
    
    return {"test_plan": test_plan}


@router.put("/{issue_key}", response_model=UpdateTestPlanResponse)
async def update_test_plan(issue_key: str, request: UpdateTestPlanRequest):
    """
    Update an existing test plan by replacing test cases.
    
    This endpoint:
    1. Loads the existing test plan from file
    2. Updates it with the new test cases (validates and fills in defaults for incomplete test cases)
    3. Saves it back to file
    4. Optionally uploads to Zephyr
    
    Args:
        issue_key: Jira issue key
        request: Update request with new test cases
        
    Returns:
        Updated test plan with optional Zephyr upload results
    """
    logger.info(f"API: Updating test plan for {issue_key}")
    
    # Validate request
    if request.upload_to_zephyr and not request.project_key:
        raise HTTPException(
            status_code=400,
            detail="project_key is required when upload_to_zephyr is True",
        )
    
    try:
        # Step 1: Load existing test plan
        plan_path = _get_test_plan_path(issue_key)
        
        if not plan_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Test plan not found for {issue_key}. Generate a test plan first."
            )
        
        logger.info(f"Loading existing test plan from {plan_path}")
        existing_plan = TestPlan.model_validate_json(plan_path.read_text())
        
        # Step 2: Validate and normalize test cases (handle incomplete data from UI)
        logger.info(f"Validating and normalizing {len(request.test_cases)} test cases")
        normalized_test_cases = []
        
        for idx, tc_data in enumerate(request.test_cases):
            try:
                # If it's already a TestCase object, use it
                if isinstance(tc_data, TestCase):
                    tc = tc_data
                else:
                    # Convert dict to TestCase, filling in defaults for missing fields
                    tc_dict = tc_data if isinstance(tc_data, dict) else tc_data.dict()
                    
                    # Fill in required fields with defaults if missing
                    if not tc_dict.get("description"):
                        tc_dict["description"] = tc_dict.get("title", f"Test case {idx + 1}")
                    
                    if not tc_dict.get("expected_result"):
                        tc_dict["expected_result"] = "Test should pass"
                    
                    # Ensure steps is a list (even if empty)
                    if "steps" not in tc_dict or not tc_dict["steps"]:
                        tc_dict["steps"] = []
                    
                    # Convert steps to TestStep objects if they're dicts
                    if tc_dict["steps"]:
                        from src.models.test_case import TestStep
                        normalized_steps = []
                        for step_idx, step in enumerate(tc_dict["steps"]):
                            if isinstance(step, dict):
                                # Fill in missing step fields
                                if "step_number" not in step:
                                    step["step_number"] = step_idx + 1
                                if "action" not in step:
                                    step["action"] = "Perform test action"
                                if "expected_result" not in step:
                                    step["expected_result"] = "Action completes successfully"
                                normalized_steps.append(TestStep(**step))
                            else:
                                normalized_steps.append(step)
                        tc_dict["steps"] = normalized_steps
                    
                    # Set defaults for optional fields
                    if "priority" not in tc_dict:
                        tc_dict["priority"] = "medium"
                    if "test_type" not in tc_dict:
                        tc_dict["test_type"] = "functional"
                    if "tags" not in tc_dict:
                        tc_dict["tags"] = []
                    if "automation_candidate" not in tc_dict:
                        tc_dict["automation_candidate"] = True
                    if "risk_level" not in tc_dict:
                        tc_dict["risk_level"] = "medium"
                    
                    # Create TestCase with normalized data
                    tc = TestCase(**tc_dict)
                
                normalized_test_cases.append(tc)
                logger.debug(f"Normalized test case {idx + 1}: {tc.title}")
                
            except Exception as e:
                logger.error(f"Failed to normalize test case {idx + 1}: {e}", exc_info=True)
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid test case at index {idx}: {str(e)}"
                )
        
        # Step 3: Update test plan with normalized test cases
        logger.info(f"Updating test plan with {len(normalized_test_cases)} validated test cases")
        existing_plan.test_cases = normalized_test_cases
        
        # Update metadata
        existing_plan.metadata.total_test_cases = len(normalized_test_cases)
        existing_plan.metadata.edge_case_count = sum(
            1 for tc in normalized_test_cases 
            if tc.test_type.value == "edge_case" or "edge" in (tc.tags or [])
        )
        existing_plan.metadata.integration_test_count = sum(
            1 for tc in normalized_test_cases 
            if tc.test_type.value == "integration"
        )
        
        # Step 4: Save updated test plan to file IMMEDIATELY
        logger.info(f"Saving updated test plan to {plan_path}")
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(plan_path, 'w') as f:
                json.dump(existing_plan.dict(), f, indent=2, default=str)
            logger.info(f"✅ Saved updated test plan to {plan_path} with {len(normalized_test_cases)} test cases")
            
            # Verify it was saved
            if plan_path.exists():
                logger.info(f"✅ Verified: Test plan file exists at {plan_path}")
            else:
                logger.error(f"❌ ERROR: Test plan file was not saved to {plan_path}")
                raise Exception("Failed to save test plan file")
        except Exception as e:
            logger.error(f"❌ Failed to save test plan: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to save test plan: {str(e)}"
            )
        
        # Step 4: Upload to Zephyr if requested
        zephyr_results = None
        zephyr_ids = []
        if request.upload_to_zephyr:
            logger.info("Uploading updated test plan to Zephyr...")
            zephyr = ZephyrIntegration()
            
            # Use folder_path if provided, otherwise folder_id
            effective_folder = request.folder_path or request.folder_id
            if hasattr(existing_plan, 'suggested_folder') and existing_plan.suggested_folder:
                effective_folder = effective_folder or existing_plan.suggested_folder
            
            zephyr_results = await zephyr.upload_test_plan(
                test_plan=existing_plan,
                project_key=request.project_key,
                folder_id=request.folder_id if not effective_folder else None,
                folder_path=effective_folder
            )
            logger.info("✅ Successfully uploaded updated test plan to Zephyr")
            
            # Extract Zephyr IDs from results
            if zephyr_results:
                zephyr_ids = [
                    test_id for test_id in zephyr_results.values() 
                    if not str(test_id).startswith('ERROR')
                ]
        
        message = f"Test plan updated successfully with {len(normalized_test_cases)} test cases"
        if request.upload_to_zephyr:
            message += f" and uploaded {len(zephyr_ids)} test cases to Zephyr"
        
        return UpdateTestPlanResponse(
            test_plan=existing_plan,
            zephyr_results=zephyr_results,
            message=message
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update test plan for {issue_key}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

