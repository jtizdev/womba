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

        # Step 3: Save test plan to RAG
        try:
            from src.ai.context_indexer import ContextIndexer
            indexer = ContextIndexer()
            await indexer.index_test_plan(test_plan, context)
            logger.info(f"Saved test plan to RAG for {request.issue_key}")
        except Exception as e:
            logger.error(f"Failed to save test plan to RAG: {e}")

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
        
        # Track in history (test plan stored in RAG)
        duration = int(time.time() - start_time)
        from .ui import track_test_generation, update_history_test_count
        track_test_generation(
            story_key=request.issue_key,
            test_count=len(test_plan.test_cases),
            status='success',
            duration=duration,
            zephyr_ids=zephyr_ids if zephyr_ids else None,
            test_plan_file=f"rag:{request.issue_key}"  # Reference RAG storage
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
        from .ui import track_test_generation, update_history_test_count
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
    """
    Get the absolute path to a test plan file.
    
    Works in both local and containerized environments:
    - In K8s/Docker: Uses /app/data/test_plans/ (persistent volume)
    - Local development: Uses ./test_plans/ (current working directory)
    """
    # Check if we're in a containerized environment (K8s/Docker)
    # Use /app/data which is mounted as a persistent volume
    if Path("/app/data").exists():
        # Containerized environment - use persistent volume
        app_root = Path("/app/data")
    else:
        # Local development - use current working directory
        app_root = Path.cwd()
    
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
    # Load test plan from RAG
    from src.ai.rag_store import RAGVectorStore
    store = RAGVectorStore()
    test_plan_data = await store.get_test_plan_by_story_key(issue_key)
    
    if not test_plan_data:
        raise HTTPException(
            status_code=404,
            detail=f"Test plan not found for {issue_key}. Generate a test plan first."
        )
    
    logger.info(f"Loading test plan from RAG for {issue_key}")
    test_plan = TestPlan.model_validate_json(test_plan_data['metadata']['test_plan_json'])
    
    return {"test_plan": test_plan}


@router.put("/{issue_key}", response_model=UpdateTestPlanResponse)
async def update_test_plan(issue_key: str, request: UpdateTestPlanRequest):
    """
    Update an existing test plan by replacing test cases.
    
    This endpoint:
    1. Loads the existing test plan from RAG
    2. Updates it with the new test cases (validates and fills in defaults for incomplete test cases)
    3. Saves it back to RAG
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
        # Step 1: Load existing test plan from RAG
        from src.ai.rag_store import RAGVectorStore
        store = RAGVectorStore()
        test_plan_data = await store.get_test_plan_by_story_key(issue_key)
        
        if not test_plan_data:
            raise HTTPException(
                status_code=404,
                detail=f"Test plan not found for {issue_key}. Generate a test plan first."
            )
        
        logger.info(f"Loading existing test plan from RAG for {issue_key}")
        existing_plan = TestPlan.model_validate_json(test_plan_data['metadata']['test_plan_json'])
        
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
        # Support both full replacement and partial updates
        if len(normalized_test_cases) == len(existing_plan.test_cases):
            # Full replacement: all test cases provided (backward compatible)
            logger.info(f"Full update: Replacing all {len(normalized_test_cases)} test cases")
            existing_plan.test_cases = normalized_test_cases
        elif len(normalized_test_cases) < len(existing_plan.test_cases):
            # Fewer test cases sent - likely a deletion, replace entire list
            logger.info(
                f"Deletion detected: Replacing {len(existing_plan.test_cases)} test cases "
                f"with {len(normalized_test_cases)} test cases (deleted {len(existing_plan.test_cases) - len(normalized_test_cases)})"
            )
            existing_plan.test_cases = normalized_test_cases
        else:
            # More test cases sent - partial update: merge updated test cases into existing list
            logger.info(
                f"Partial update: Merging {len(normalized_test_cases)} updated test cases "
                f"into existing {len(existing_plan.test_cases)} test cases"
            )
            
            # Create a map of existing test cases by ID and index
            existing_by_id = {tc.id: idx for idx, tc in enumerate(existing_plan.test_cases) if tc.id}
            existing_by_title = {tc.title: idx for idx, tc in enumerate(existing_plan.test_cases)}
            
            # Update existing test cases that match
            updated_indices = set()
            for updated_tc in normalized_test_cases:
                matched_idx = None
                
                # Try to match by ID first
                if updated_tc.id and updated_tc.id in existing_by_id:
                    matched_idx = existing_by_id[updated_tc.id]
                    logger.debug(f"Matched test case by ID: {updated_tc.id} -> index {matched_idx}")
                
                # Fallback to matching by title
                elif updated_tc.title in existing_by_title:
                    matched_idx = existing_by_title[updated_tc.title]
                    logger.debug(f"Matched test case by title: {updated_tc.title} -> index {matched_idx}")
                
                # Fallback to matching by index if normalized_test_cases is in order
                elif len(normalized_test_cases) <= len(existing_plan.test_cases):
                    # Assume they're in the same order, use the position in normalized list
                    potential_idx = len(updated_indices)
                    if potential_idx < len(existing_plan.test_cases):
                        matched_idx = potential_idx
                        logger.debug(f"Matched test case by position: index {matched_idx}")
                
                if matched_idx is not None:
                    existing_plan.test_cases[matched_idx] = updated_tc
                    updated_indices.add(matched_idx)
                    logger.info(f"Updated test case at index {matched_idx}: {updated_tc.title}")
                else:
                    logger.warning(
                        f"Could not match test case '{updated_tc.title}' (id={updated_tc.id}). "
                        f"Adding as new test case."
                    )
                    existing_plan.test_cases.append(updated_tc)
            
            if len(updated_indices) != len(normalized_test_cases):
                logger.warning(
                    f"Only updated {len(updated_indices)}/{len(normalized_test_cases)} test cases. "
                    f"Some test cases could not be matched."
                )
        
        # Update metadata based on the final test plan (after merge)
        existing_plan.metadata.total_test_cases = len(existing_plan.test_cases)
        existing_plan.metadata.edge_case_count = sum(
            1 for tc in existing_plan.test_cases 
            if tc.test_type.value == "edge_case" or "edge" in (tc.tags or [])
        )
        existing_plan.metadata.integration_test_count = sum(
            1 for tc in existing_plan.test_cases 
            if tc.test_type.value == "integration"
        )
        
        # Step 4: Save updated test plan to RAG
        logger.info(f"Saving updated test plan to RAG for {issue_key}")
        try:
            from src.ai.indexing.document_processor import DocumentProcessor
            from src.ai.indexing.document_indexer import DocumentIndexer
            
            processor = DocumentProcessor()
            doc_text = processor.build_test_plan_document(existing_plan)
            
            # Use DocumentIndexer to save (handles normalization and upsert logic)
            indexer = DocumentIndexer()
            await indexer.index_test_plan(existing_plan, doc_text)
            logger.info(f"✅ Saved updated test plan to RAG with {len(existing_plan.test_cases)} test cases")
            
            # Update history entry with new test count
            from .ui import update_history_test_count
            update_history_test_count(issue_key, len(existing_plan.test_cases))
        except Exception as e:
            logger.error(f"❌ Failed to save test plan to RAG: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to save test plan to RAG: {str(e)}"
            )
        
        # Step 5: Upload to Zephyr if requested
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

