"""
API routes for direct Zephyr Scale uploads.
Uses the existing robust ZephyrIntegration from Womba CLI.
"""

from typing import List, Optional, Any
from pathlib import Path
import re
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from loguru import logger

from src.integrations.zephyr_integration import ZephyrIntegration
from src.models.test_plan import TestPlan

router = APIRouter(prefix="/api/v1/zephyr", tags=["zephyr"])


# ============================================================================
# Folder Endpoints
# ============================================================================

class ZephyrFolder(BaseModel):
    """Zephyr folder model."""
    id: str
    name: str
    parentId: Optional[str] = None
    path: str


class FoldersResponse(BaseModel):
    """Response model for folder list."""
    folders: List[ZephyrFolder]
    folder_type: str
    project_key: str


@router.get("/folders", response_model=FoldersResponse)
async def get_folders(
    project_key: str = Query(..., description="Jira project key"),
    folder_type: str = Query("TEST_CASE", description="Folder type: TEST_CASE or TEST_CYCLE")
):
    """
    Get folders from Zephyr Scale for a project.
    
    Args:
        project_key: Jira project key (e.g., "PLAT")
        folder_type: Either "TEST_CASE" or "TEST_CYCLE"
        
    Returns:
        List of folders with their full paths
    """
    try:
        logger.info(f"Fetching {folder_type} folders for project {project_key}")
        
        if folder_type not in ["TEST_CASE", "TEST_CYCLE"]:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid folder_type: {folder_type}. Must be TEST_CASE or TEST_CYCLE"
            )
        
        zephyr = ZephyrIntegration()
        folders = await zephyr.get_folders(project_key, folder_type)
        
        logger.info(f"Found {len(folders)} {folder_type} folders")
        
        return FoldersResponse(
            folders=[ZephyrFolder(**f) for f in folders],
            folder_type=folder_type,
            project_key=project_key
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch folders: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Suggest Folder Endpoint (AI-based)
# ============================================================================

class SuggestFolderRequest(BaseModel):
    """Request model for folder suggestion."""
    project_key: str = Field(..., description="Jira project key (e.g., PLAT)")
    fix_version: str = Field(..., description="Fix version from Jira story (e.g., 'Platform MNG - Dec-7th (5.2550.X)')")
    folder_type: str = Field("TEST_CYCLE", description="Folder type: TEST_CASE or TEST_CYCLE")


class SuggestFolderResponse(BaseModel):
    """Response model for folder suggestion."""
    suggested_folder_id: Optional[str] = None
    suggested_folder_path: Optional[str] = None
    confidence: str = "high"  # high, medium, low
    reason: str = ""
    available_folders: List[ZephyrFolder] = []


@router.post("/suggest-folder", response_model=SuggestFolderResponse)
async def suggest_folder(request: SuggestFolderRequest):
    """
    Use AI to suggest the best folder for a test cycle based on the story's fix version.
    
    This endpoint:
    1. Fetches available folders from Zephyr
    2. Uses AI to match the fix version to the most appropriate folder
    
    Args:
        request: Request with project_key and fix_version
        
    Returns:
        Suggested folder with confidence level and reasoning
    """
    try:
        logger.info(f"🤖 Suggesting folder for fix version: {request.fix_version}")
        
        # Fetch available folders
        zephyr = ZephyrIntegration()
        folders = await zephyr.get_folders(request.project_key, request.folder_type)
        
        if not folders:
            return SuggestFolderResponse(
                suggested_folder_id=None,
                suggested_folder_path=None,
                confidence="low",
                reason="No folders available in Zephyr",
                available_folders=[]
            )
        
        folder_paths = [f['path'] for f in folders]
        
        # Use AI to find the best match
        from src.ai.generation.ai_client_factory import AIClientFactory
        client, model = AIClientFactory.create_openai_client()
        
        prompt = f"""Given the Jira fix version and available Zephyr test cycle folders, suggest the best folder to place test cycles for this version.

Fix Version: {request.fix_version}

Available Folders:
{chr(10).join(f"- {path}" for path in folder_paths)}

Instructions:
1. Look for date patterns in both the fix version and folder names (e.g., "Dec-7th", "Nov-16th", dates like "5.2550.X")
2. Match based on release timing - if the fix version is for Dec 7th, look for the closest preceding release folder
3. Consider version numbers like "5.2550.X" which indicate release sequences
4. If no good match is found, suggest the most recent/relevant folder

Respond with ONLY a JSON object (no markdown, no code blocks):
{{"folder_path": "exact folder path from the list", "confidence": "high|medium|low", "reason": "brief explanation"}}

If you cannot find a good match, set folder_path to null and confidence to "low"."""

        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=200
        )
        response = completion.choices[0].message.content
        
        # Parse AI response
        import json
        try:
            # Clean the response - remove markdown code blocks if present
            response_text = response.strip()
            if response_text.startswith("```"):
                # Remove markdown code block
                lines = response_text.split("\n")
                response_text = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
            
            ai_result = json.loads(response_text)
            suggested_path = ai_result.get("folder_path")
            confidence = ai_result.get("confidence", "medium")
            reason = ai_result.get("reason", "AI-based suggestion")
            
            # Find the folder ID for the suggested path
            suggested_id = None
            if suggested_path:
                for f in folders:
                    if f['path'] == suggested_path:
                        suggested_id = f['id']
                        break
            
            logger.info(f"✅ AI suggested folder: {suggested_path} (confidence: {confidence})")
            
            return SuggestFolderResponse(
                suggested_folder_id=suggested_id,
                suggested_folder_path=suggested_path,
                confidence=confidence,
                reason=reason,
                available_folders=[ZephyrFolder(**f) for f in folders]
            )
            
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse AI response: {e}. Response: {response}")
            # Fallback to the last folder (most recently created)
            last_folder = folders[-1] if folders else None
            return SuggestFolderResponse(
                suggested_folder_id=last_folder['id'] if last_folder else None,
                suggested_folder_path=last_folder['path'] if last_folder else None,
                confidence="low",
                reason="Could not parse AI response, using most recent folder",
                available_folders=[ZephyrFolder(**f) for f in folders]
            )
        
    except Exception as e:
        logger.error(f"Failed to suggest folder: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Upload to Cycle Endpoint
# ============================================================================

class UploadToCycleRequest(BaseModel):
    """Request model for uploading test cases to a test cycle."""
    issue_key: str = Field(..., description="Jira issue key (e.g., PLAT-12345)")
    project_key: str = Field(..., description="Jira project key (e.g., PLAT)")
    cycle_name: str = Field(..., description="Name for the test cycle")
    test_case_folder_path: Optional[str] = Field(None, description="(Deprecated) Folder path for test cases - use TEST_CASE folders")
    cycle_folder_path: Optional[str] = Field(None, description="(Deprecated) Folder path - use cycle_folder_id instead")
    cycle_folder_id: Optional[str] = Field(None, description="Folder ID for the test cycle (preferred - avoids duplicate name issues)")
    test_cases: Optional[List[dict]] = Field(None, description="Specific test cases to upload")


class UploadToCycleResponse(BaseModel):
    """Response model for upload to cycle."""
    success: bool
    cycle_key: Optional[str] = None
    cycle_name: str
    test_case_count: int
    test_case_ids: List[str]
    execution_count: int
    linked_to_story: bool
    story_key: Optional[str] = None
    errors: List[str] = []
    test_case_results: dict = {}


@router.post("/upload-to-cycle", response_model=UploadToCycleResponse)
async def upload_to_cycle(request: UploadToCycleRequest):
    """
    Upload test cases to Zephyr Scale and add them to a new test cycle.
    
    This endpoint:
    1. Creates test cases in the specified folder
    2. Creates a new test cycle
    3. Adds all test cases to the cycle
    4. Links the cycle to the story (not individual tests)
    
    Args:
        request: Upload request with cycle name, folder paths, and test cases
        
    Returns:
        Upload results with cycle key and test case IDs
    """
    try:
        logger.info(f"📦 Upload to cycle request for {request.issue_key}")
        logger.info(f"   Cycle name: {request.cycle_name}")
        if request.test_case_folder_path:
            logger.info(f"   Test case folder (TEST_CASE type): {request.test_case_folder_path}")
        if request.cycle_folder_path:
            logger.info(f"   Cycle folder (TEST_CYCLE type): {request.cycle_folder_path}")
        
        # Load saved test plan from RAG
        from src.ai.rag_store import RAGVectorStore
        store = RAGVectorStore()
        test_plan_data = await store.get_test_plan_by_story_key(request.issue_key)
        
        if not test_plan_data:
            raise HTTPException(
                status_code=404, 
                detail=f"Test plan not found for {request.issue_key}. Generate a test plan first."
            )
        
        logger.info(f"Loading saved test plan from RAG for {request.issue_key}")
        test_plan = TestPlan.model_validate_json(test_plan_data['metadata']['test_plan_json'])
        
        # If specific test cases are provided, filter to only those
        if request.test_cases:
            logger.info(f"Selective upload: {len(request.test_cases)} selected test cases")
            
            selected_identifiers = set()
            selected_indices = set()
            
            for tc in request.test_cases:
                tc_id = tc.get('id')
                tc_title = tc.get('title')
                
                if tc_id:
                    selected_identifiers.add(tc_id)
                    match = re.search(r'-(\d+)$', tc_id)
                    if match:
                        index = int(match.group(1)) - 1
                        if 0 <= index < len(test_plan.test_cases):
                            selected_indices.add(index)
                
                if tc_title:
                    selected_identifiers.add(tc_title)
            
            filtered_cases = []
            for idx, tc in enumerate(test_plan.test_cases):
                if (tc.id and tc.id in selected_identifiers) or \
                   tc.title in selected_identifiers or \
                   idx in selected_indices:
                    # Ensure manual test cases have valid steps
                    if tc.id and tc.id.startswith('TC-MANUAL-'):
                        valid_steps = [s for s in tc.steps if s.action and s.action.strip()]
                        if not valid_steps:
                            from src.models.test_case import TestStep
                            tc.steps = [TestStep(
                                step_number=1,
                                action="Manual test case - steps to be defined",
                                expected_result="Verify expected behavior"
                            )]
                        else:
                            tc.steps = valid_steps
                    filtered_cases.append(tc)
            
            test_plan.test_cases = filtered_cases
            logger.info(f"Filtered to {len(test_plan.test_cases)} matching test cases")
        
        if not test_plan.test_cases:
            raise HTTPException(
                status_code=400,
                detail="No test cases to upload"
            )
        
        # Use the new upload_to_cycle method
        zephyr = ZephyrIntegration()
        result = await zephyr.upload_to_cycle(
            test_plan=test_plan,
            project_key=request.project_key,
            cycle_name=request.cycle_name,
            test_case_folder_path=request.test_case_folder_path,
            cycle_folder_id=request.cycle_folder_id,  # Preferred: use ID directly
            cycle_folder_path=request.cycle_folder_path,  # Fallback: resolve by path
            story_key=request.issue_key
        )
        
        return UploadToCycleResponse(
            success=result['cycle_key'] is not None and len(result['test_case_keys']) > 0,
            cycle_key=result['cycle_key'],
            cycle_name=result['cycle_name'],
            test_case_count=len(result['test_case_keys']),
            test_case_ids=result['test_case_keys'],
            execution_count=len(result['executions']),
            linked_to_story=result['linked_to_story'],
            story_key=result['story_key'],
            errors=result['errors'],
            test_case_results=result['test_case_results']
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to upload to cycle: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Original Upload Endpoint (for backwards compatibility)
# ============================================================================


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
        
        # Load saved test plan from RAG
        from src.ai.rag_store import RAGVectorStore
        store = RAGVectorStore()
        test_plan_data = await store.get_test_plan_by_story_key(request.issue_key)
        
        if not test_plan_data:
            raise HTTPException(
                status_code=404, 
                detail=f"Test plan not found for {request.issue_key}. Generate a test plan first."
            )
        
        logger.info(f"Loading saved test plan from RAG for {request.issue_key}")
        test_plan = TestPlan.model_validate_json(test_plan_data['metadata']['test_plan_json'])
        
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

