"""
API routes for direct Zephyr Scale uploads.
Uses the existing robust ZephyrIntegration from Womba CLI.
"""

from typing import List, Optional
from pathlib import Path
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
        plan_path = Path(f"test_plans/test_plan_{request.issue_key}.json")
        if not plan_path.exists():
            raise HTTPException(
                status_code=404, 
                detail=f"Saved test plan not found: {plan_path}. Generate a test plan first."
            )
        
        logger.info(f"Loading saved test plan from {plan_path}")
        test_plan = TestPlan.model_validate_json(plan_path.read_text())
        
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

