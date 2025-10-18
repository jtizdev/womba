"""
API routes for test plan generation and management.
"""

from typing import Optional

from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel

from src.aggregator.story_collector import StoryCollector
from src.ai.test_plan_generator import TestPlanGenerator
from src.integrations.zephyr_integration import ZephyrIntegration
from src.models.test_plan import TestPlan

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

        # Step 3: Upload to Zephyr if requested
        zephyr_results = None
        if request.upload_to_zephyr:
            if not request.project_key:
                raise HTTPException(
                    status_code=400,
                    detail="project_key is required when upload_to_zephyr is True",
                )

            logger.info("Step 3: Uploading test plan to Zephyr...")
            zephyr = ZephyrIntegration()
            zephyr_results = await zephyr.upload_test_plan(
                test_plan=test_plan,
                project_key=request.project_key,
                folder_id=request.folder_id,
            )
            logger.info("Successfully uploaded test plan to Zephyr")

        return GenerateTestPlanResponse(
            test_plan=test_plan, zephyr_results=zephyr_results
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate test plan for {request.issue_key}: {e}")
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

