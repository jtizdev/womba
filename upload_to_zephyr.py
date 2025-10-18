#!/usr/bin/env python3
"""
Upload generated test plan to Zephyr Scale.

Usage:
    python3 upload_to_zephyr.py PLAT-11907
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Dict, Any

from loguru import logger
from src.config.settings import settings
from src.integrations.zephyr_integration import ZephyrIntegration
from src.models.test_case import TestCase


async def find_or_create_folder(zephyr: ZephyrIntegration, project_key: str, folder_path: str) -> str:
    """
    Find or create a folder in Zephyr based on path like "Parent/Child".
    
    Args:
        zephyr: ZephyrIntegration instance
        project_key: Jira project key
        folder_path: Folder path (e.g., "Orchestration WS/POP ID Alignment")
        
    Returns:
        Folder ID
    """
    logger.info(f"Looking for folder: {folder_path}")
    
    # Get current folder structure
    folders = await zephyr.get_folder_structure(project_key)
    
    # Parse folder path
    parts = folder_path.split('/')
    parent_name = parts[0].strip()
    child_name = parts[1].strip() if len(parts) > 1 else None
    
    # Find parent folder
    parent_folder = None
    for folder in folders:
        if folder['name'] == parent_name:
            parent_folder = folder
            break
    
    if not parent_folder:
        logger.error(f"❌ Parent folder '{parent_name}' not found in Zephyr!")
        logger.info("Available folders:")
        for f in folders:
            logger.info(f"  - {f['name']} (ID: {f['id']})")
        raise ValueError(f"Parent folder '{parent_name}' not found")
    
    logger.info(f"✅ Found parent folder: {parent_name} (ID: {parent_folder['id']})")
    
    # If no child specified, return parent
    if not child_name:
        return parent_folder['id']
    
    # Check if child folder exists
    if 'folders' in parent_folder and parent_folder['folders']:
        for child in parent_folder['folders']:
            if child['name'] == child_name:
                logger.info(f"✅ Found child folder: {child_name} (ID: {child['id']})")
                return child['id']
    
    # Child doesn't exist, create it
    logger.info(f"Creating child folder: {child_name} under {parent_name}")
    
    try:
        # Create folder using Zephyr API
        async with zephyr._get_client() as client:
            response = await client.post(
                f"{zephyr.base_url}/folders",
                json={
                    "projectKey": project_key,
                    "name": child_name,
                    "parentId": parent_folder['id'],
                    "type": "TEST_CASE"
                }
            )
            response.raise_for_status()
            new_folder = response.json()
            logger.info(f"✅ Created folder: {child_name} (ID: {new_folder['id']})")
            return new_folder['id']
    except Exception as e:
        logger.error(f"❌ Failed to create folder: {e}")
        logger.warning(f"⚠️  Using parent folder instead: {parent_name}")
        return parent_folder['id']


async def upload_test_case(
    zephyr: ZephyrIntegration,
    test_case: Dict[str, Any],
    project_key: str,
    folder_id: str,
    story_key: str,
    dry_run: bool = False
) -> str:
    """
    Upload a single test case to Zephyr.
    
    Args:
        zephyr: ZephyrIntegration instance
        test_case: Test case dict from JSON
        project_key: Jira project key
        folder_id: Zephyr folder ID
        story_key: Jira story key to link
        dry_run: If True, only print what would be uploaded
        
    Returns:
        Test case key (or "DRY-RUN" if dry_run=True)
    """
    title = test_case['title']
    
    if dry_run:
        logger.info(f"[DRY RUN] Would create: {title}")
        return "DRY-RUN"
    
    logger.info(f"Creating test case: {title}")
    
    # Convert dict to TestCase model
    from src.models.test_case import TestCase, TestStep
    from src.models.story import TestCaseType, PriorityLevel
    
    tc = TestCase(
        title=test_case['title'],
        description=test_case['description'],
        preconditions=test_case.get('preconditions'),
        steps=[
            TestStep(
                step_number=s['step_number'],
                action=s['action'],
                expected_result=s['expected_result'],
                test_data=s.get('test_data')
            )
            for s in test_case.get('steps', [])
        ],
        expected_result=test_case.get('expected_result'),
        priority=PriorityLevel(test_case['priority']),
        test_type=TestCaseType(test_case['test_type']),
        tags=test_case.get('tags', []),
        automation_candidate=test_case.get('automation_candidate', False),
        estimated_time=test_case.get('estimated_time'),
        risk_level=test_case.get('risk_level', 'medium')
    )
    
    try:
        test_key = await zephyr.create_test_case(
            test_case=tc,
            project_key=project_key,
            folder_id=folder_id,
            story_key=story_key
        )
        
        logger.info(f"✅ Created: {test_key}")
        logger.info(f"   URL: https://plainid.atlassian.net/projects/{project_key}/testCase/{test_key}")
        
        return test_key
    except Exception as e:
        logger.error(f"❌ Failed to create test case: {e}")
        raise


async def main():
    """Main upload function."""
    if len(sys.argv) < 2:
        print("Usage: python3 upload_to_zephyr.py PLAT-11907 [--dry-run]")
        sys.exit(1)
    
    story_key = sys.argv[1]
    dry_run = "--dry-run" in sys.argv
    
    # Load test plan
    test_plan_file = f"test_plan_{story_key}_enhanced.json"
    if not Path(test_plan_file).exists():
        logger.error(f"❌ Test plan not found: {test_plan_file}")
        sys.exit(1)
    
    with open(test_plan_file) as f:
        test_plan = json.load(f)
    
    logger.info("=" * 80)
    logger.info(f"📤 Uploading Test Plan to Zephyr")
    logger.info("=" * 80)
    logger.info(f"Story: {story_key}")
    logger.info(f"Test cases: {len(test_plan['test_cases'])}")
    logger.info(f"Suggested folder: {test_plan.get('suggested_folder', 'N/A')}")
    logger.info(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    logger.info("")
    
    # Extract project key
    project_key = story_key.split('-')[0]
    
    # Initialize Zephyr client
    zephyr = ZephyrIntegration()
    
    # Find or create folder (with default fallback)
    folder_id = None
    suggested_folder = test_plan.get('suggested_folder') or 'General/Automated Tests'
    if suggested_folder:
        try:
            folder_id = await find_or_create_folder(
                zephyr,
                project_key,
                suggested_folder
            )
        except Exception as e:
            logger.warning(f"⚠️  Could not find/create folder: {e}")
            logger.warning("⚠️  Will upload to project root")
    
    # Upload each test case
    created_tests = []
    failed_tests = []
    
    for i, test_case in enumerate(test_plan['test_cases'], 1):
        logger.info(f"\n[{i}/{len(test_plan['test_cases'])}] Uploading test...")
        
        try:
            test_key = await upload_test_case(
                zephyr=zephyr,
                test_case=test_case,
                project_key=project_key,
                folder_id=folder_id,
                story_key=story_key,
                dry_run=dry_run
            )
            created_tests.append((test_case['title'], test_key))
        except Exception as e:
            logger.error(f"❌ Failed: {test_case['title']}")
            failed_tests.append(test_case['title'])
    
    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("📊 Upload Summary")
    logger.info("=" * 80)
    logger.info(f"✅ Created: {len(created_tests)}")
    logger.info(f"❌ Failed: {len(failed_tests)}")
    
    if created_tests:
        logger.info("\n" + "=" * 80)
        logger.info("✅ CREATED TEST CASES (Zephyr IDs):")
        logger.info("=" * 80)
        for title, key in created_tests:
            logger.info(f"\n📝 {key}")
            logger.info(f"   Title: {title}")
            logger.info(f"   URL: https://plainid.atlassian.net/projects/{project_key}/testCase/{key}")
        
        logger.info("\n" + "=" * 80)
        logger.info("📋 QUICK COPY - Zephyr Test Keys:")
        logger.info("=" * 80)
        keys_only = ", ".join([key for _, key in created_tests])
        logger.info(f"{keys_only}")
    
    if failed_tests:
        logger.info("\n❌ Failed test cases:")
        for title in failed_tests:
            logger.info(f"  - {title}")
    
    logger.info("\n" + "=" * 80)
    logger.info("✅ Upload completed!")
    logger.info("=" * 80)
    
    # Cleanup: Delete the test plan JSON file
    try:
        import os
        os.remove(test_plan_file)
        logger.info(f"🧹 Cleaned up {test_plan_file}")
    except Exception as e:
        logger.warning(f"Could not delete {test_plan_file}: {e}")


if __name__ == "__main__":
    asyncio.run(main())

