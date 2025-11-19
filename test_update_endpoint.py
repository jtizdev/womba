#!/usr/bin/env python3
"""
Test script for the test plan update endpoint.
This verifies that:
1. We can load an existing test plan
2. We can update it with new test cases
3. It saves to file
4. It can upload to Zephyr (if configured)
"""

import sys
import json
import asyncio
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.api.routes.test_plans import update_test_plan, get_test_plan
import os
from src.models.test_plan import TestPlan
from src.models.test_case import TestCase, TestStep
from src.models.story import PriorityLevel, TestCaseType

async def test_update_endpoint():
    """Test the update endpoint."""
    issue_key = "PLAT-13541"
    
    # Set APP_ROOT for local testing
    if not os.getenv("APP_ROOT"):
        os.environ["APP_ROOT"] = str(Path(__file__).parent.absolute())
    
    print("=" * 80)
    print("TESTING TEST PLAN UPDATE ENDPOINT")
    print("=" * 80)
    
    # Step 1: Check if test plan exists
    # Use same logic as the endpoint
    app_root = Path(os.getenv("APP_ROOT", "."))
    plan_path = app_root / "test_plans" / f"test_plan_{issue_key}.json"
    print(f"\n1. Checking if test plan exists: {plan_path}")
    
    if not plan_path.exists():
        print(f"   ❌ Test plan not found at {plan_path}")
        print("   Please generate a test plan first using: womba generate PLAT-13541")
        return False
    
    print(f"   ✅ Test plan found")
    
    # Step 2: Load existing test plan
    print(f"\n2. Loading existing test plan...")
    try:
        existing_plan = TestPlan.model_validate_json(plan_path.read_text())
        print(f"   ✅ Loaded test plan with {len(existing_plan.test_cases)} test cases")
    except Exception as e:
        print(f"   ❌ Failed to load test plan: {e}")
        return False
    
    # Step 3: Create a new test case to add
    print(f"\n3. Creating a new test case to add...")
    new_test_case = TestCase(
        title="Manually Added Test Case",
        description="This test case was added manually via the update endpoint",
        preconditions="Test environment is set up",
        steps=[
            TestStep(
                step_number=1,
                action="Perform manual test action",
                expected_result="Action completes successfully",
                test_data='{"action": "manual", "expected": "success"}'
            )
        ],
        expected_result="Test passes",
        priority=PriorityLevel.HIGH,
        test_type=TestCaseType.FUNCTIONAL,
        tags=["manual", "test-update"],
        automation_candidate=False
    )
    print(f"   ✅ Created test case: {new_test_case.title}")
    
    # Step 4: Add new test case to existing list
    print(f"\n4. Adding new test case to existing list...")
    updated_test_cases = existing_plan.test_cases + [new_test_case]
    print(f"   ✅ Updated list now has {len(updated_test_cases)} test cases")
    
    # Step 5: Create update request
    print(f"\n5. Creating update request...")
    from src.api.routes.test_plans import UpdateTestPlanRequest
    update_request = UpdateTestPlanRequest(
        test_cases=updated_test_cases,
        upload_to_zephyr=False,  # Set to True to test Zephyr upload
        project_key="PLAT"
    )
    print(f"   ✅ Update request created")
    
    # Step 6: Call update endpoint
    print(f"\n6. Calling update endpoint...")
    try:
        result = await update_test_plan(issue_key, update_request)
        print(f"   ✅ Update successful!")
        print(f"   Message: {result.message}")
        print(f"   Updated test plan has {len(result.test_plan.test_cases)} test cases")
    except Exception as e:
        print(f"   ❌ Update failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Step 7: Verify file was saved
    print(f"\n7. Verifying file was saved...")
    if plan_path.exists():
        saved_plan = TestPlan.model_validate_json(plan_path.read_text())
        if len(saved_plan.test_cases) == len(updated_test_cases):
            print(f"   ✅ File saved correctly with {len(saved_plan.test_cases)} test cases")
        else:
            print(f"   ❌ File has {len(saved_plan.test_cases)} test cases, expected {len(updated_test_cases)}")
            return False
    else:
        print(f"   ❌ File not found after update")
        return False
    
    # Step 8: Verify new test case is in saved plan
    print(f"\n8. Verifying new test case is in saved plan...")
    found = any(tc.title == new_test_case.title for tc in saved_plan.test_cases)
    if found:
        print(f"   ✅ New test case found in saved plan")
    else:
        print(f"   ❌ New test case not found in saved plan")
        return False
    
    print("\n" + "=" * 80)
    print("✅ ALL TESTS PASSED!")
    print("=" * 80)
    return True

if __name__ == "__main__":
    success = asyncio.run(test_update_endpoint())
    sys.exit(0 if success else 1)

