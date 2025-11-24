"""
API routes for direct Zephyr Scale uploads.
Uses the existing robust ZephyrIntegration from Womba CLI.
"""

from typing import List, Optional
from pathlib import Path
import re
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from loguru import logger

from src.integrations.zephyr_integration import ZephyrIntegration
from src.models.test_plan import TestPlan

router = APIRouter(prefix="/api/v1/zephyr", tags=["zephyr"])


class UploadTestCasesRequest(BaseModel):
    """Request model for uploading test cases to Zephyr."""
    issue_key: str
    project_key: str
    test_cases: Optional[List[dict]] = None  # If provided, upload only these selected tests
    folder_id: Optional[str] = None
    folder_path: Optional[str] = None  # Support folder paths like "Regression/UI"


class UploadTestCasesResponse(BaseModel):
    """Response model for test case upload."""
    success: bool
    uploaded_count: int
    test_case_ids: List[str]
    zephyr_results: dict


@router.post("/upload", response_model=UploadTestCasesResponse)
async def upload_test_cases(request: UploadTestCasesRequest):
    """
    Upload test cases to Zephyr Scale using the robust Womba CLI upload logic.
    
    This endpoint simply loads the saved test plan and uses the existing
    ZephyrIntegration.upload_test_plan() method which handles:
    - Folder path resolution (finding or creating folders)
    - Proper test case formatting
    - Error handling and retries
    
    Args:
        request: Upload request with issue_key, project_key, and optional folder_path
        
    Returns:
        Upload results with Zephyr test case IDs
    """
    try:
        logger.info(f"Uploading test cases to Zephyr for {request.issue_key}")
        
        # Load saved test plan from file (like CLI upload-plan command)
        # Use absolute path to avoid working directory issues
        # In Docker, working dir is /app, so test_plans is at /app/test_plans
        import os
        app_root = Path(os.getenv("APP_ROOT", "/app"))  # Default to /app for Docker
        plan_path = app_root / "test_plans" / f"test_plan_{request.issue_key}.json"
        
        logger.debug(f"Looking for test plan at: {plan_path.absolute()}")
        if not plan_path.exists():
            raise HTTPException(
                status_code=404, 
                detail=f"Saved test plan not found: {plan_path.absolute()}. Generate a test plan first."
            )
        
        logger.info(f"Loading saved test plan from {plan_path}")
        test_plan = TestPlan.model_validate_json(plan_path.read_text())
        
        # If specific test cases are provided, filter to only those
        if request.test_cases:
            logger.info(f"Selective upload: uploading {len(request.test_cases)} selected test cases")
            logger.info(f"Selected test cases from request: {[tc.get('id', tc.get('title', 'NO_ID_OR_TITLE')) for tc in request.test_cases]}")
            logger.info(f"Test plan has {len(test_plan.test_cases)} test cases")
            logger.info(f"Test plan test case IDs: {[tc.id for tc in test_plan.test_cases]}")
            logger.info(f"Test plan test case titles: {[tc.title for tc in test_plan.test_cases]}")
            
            # Extract selected identifiers from request
            selected_identifiers = set()
            selected_indices = set()
            
            for tc in request.test_cases:
                tc_id = tc.get('id')
                tc_title = tc.get('title')
                
                if tc_id:
                    selected_identifiers.add(tc_id)
                    # Try to extract index from ID format like "TC-PROJ-12345-1" -> index 0
                    # Pattern: TC-{PROJECT}-{ISSUE}-{INDEX}
                    match = re.search(r'-(\d+)$', tc_id)
                    if match:
                        # Convert 1-based index to 0-based
                        index = int(match.group(1)) - 1
                        if 0 <= index < len(test_plan.test_cases):
                            selected_indices.add(index)
                            logger.info(f"Extracted index {index} from ID {tc_id}")
                
                if tc_title:
                    selected_identifiers.add(tc_title)
            
            logger.info(f"Looking for IDs/titles: {selected_identifiers}")
            logger.info(f"Looking for indices: {selected_indices}")
            
            # Match by: 1) ID (exact match), 2) title (exact match), 3) extracted index
            filtered_cases = []
            for idx, tc in enumerate(test_plan.test_cases):
                matched = False
                match_reason = None
                
                # Check ID match (exact)
                if tc.id and tc.id in selected_identifiers:
                    matched = True
                    match_reason = f"ID match: {tc.id}"
                
                # Check title match (exact)
                elif tc.title in selected_identifiers:
                    matched = True
                    match_reason = f"Title match: {tc.title}"
                
                # Check index match
                elif idx in selected_indices:
                    matched = True
                    match_reason = f"Index match: {idx}"
                
                if matched:
                    # Ensure manual test cases have at least one valid step
                    if tc.id and tc.id.startswith('TC-MANUAL-'):
                        # Filter out empty steps and ensure at least one step exists
                        valid_steps = [s for s in tc.steps if s.action and s.action.strip()]
                        if not valid_steps:
                            # Add a default step if all steps are empty
                            from src.models.test_case import TestStep
                            tc.steps = [TestStep(
                                step_number=1,
                                action="Manual test case - steps to be defined",
                                expected_result="Verify expected behavior"
                            )]
                            logger.warning(f"Manual test case {tc.id} had no valid steps, added default step")
                        else:
                            tc.steps = valid_steps
                    
                    filtered_cases.append(tc)
                    logger.info(f"Matched test case {idx}: {tc.title} (id={tc.id}) - {match_reason}")
            
            if len(filtered_cases) != len(request.test_cases):
                logger.warning(
                    f"Mismatch: Requested {len(request.test_cases)} test cases, "
                    f"but only matched {len(filtered_cases)} from saved plan. "
                    f"Requested IDs: {[tc.get('id', 'NO_ID') for tc in request.test_cases]}"
                )
            
            test_plan.test_cases = filtered_cases
            logger.info(f"Filtered to {len(test_plan.test_cases)} matching test cases from saved plan")
        
        # Use the robust Womba CLI upload logic
        zephyr = ZephyrIntegration()
        
        # Support both folder_id and folder_path (folder_path is more flexible)
        effective_folder = request.folder_path or request.folder_id
        if hasattr(test_plan, 'suggested_folder') and test_plan.suggested_folder:
            effective_folder = effective_folder or test_plan.suggested_folder
        
        logger.info(f"Uploading {len(test_plan.test_cases)} test cases to project {request.project_key}")
        if effective_folder:
            logger.info(f"📁 Target folder: {effective_folder}")
        
        # This method handles everything: folder resolution, test case creation, error handling
        zephyr_results = await zephyr.upload_test_plan(
            test_plan=test_plan,
            project_key=request.project_key,
            folder_id=request.folder_id if not effective_folder else None,
            folder_path=effective_folder
        )
        
        # Extract successful uploads
        successful_uploads = [
            test_id for test_id in zephyr_results.values() 
            if not str(test_id).startswith('ERROR')
        ]
        
        logger.info(
            f"✅ Successfully uploaded {len(successful_uploads)}/{len(test_plan.test_cases)} "
            f"test cases to Zephyr"
        )
        
        # Include folder path in response
        zephyr_results_with_folder = dict(zephyr_results) if zephyr_results else {}
        if effective_folder:
            zephyr_results_with_folder['folder_path'] = effective_folder
        
        return UploadTestCasesResponse(
            success=len(successful_uploads) > 0,
            uploaded_count=len(successful_uploads),
            test_case_ids=successful_uploads,
            zephyr_results=zephyr_results_with_folder
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to upload test cases: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

