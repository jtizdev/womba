#!/usr/bin/env python3
"""
Generate a NEW test plan for PLAT-13541 and validate it meets all requirements.
"""

import sys
import asyncio
import json
from pathlib import Path

sys.path.insert(0, '/Users/royregev/womba/src')

from aggregator.story_collector import StoryCollector
from ai.test_plan_generator import TestPlanGenerator

async def main():
    print("=" * 80)
    print("GENERATING NEW TEST PLAN FOR PLAT-13541")
    print("=" * 80)
    print("\nThis will test if the fixed prompts generate:")
    print("  ✅ API tests with HTTP methods")
    print("  ✅ UI tests with detailed navigation")
    print("  ✅ Proper test naming (no 'Verify')")
    print("  ✅ All test_data populated")
    print("\nGenerating... (this may take 1-2 minutes)\n")
    
    story_key = "PLAT-13541"
    
    # Collect story context
    collector = StoryCollector()
    context = await collector.collect_story_context(story_key)
    
    # Generate test plan
    generator = TestPlanGenerator(use_openai=True)
    test_plan = await generator.generate_test_plan(context, use_rag=True)
    
    # Save for inspection
    output_file = Path("test_plans") / f"test_plan_{story_key}_NEW.json"
    with open(output_file, 'w') as f:
        json.dump(test_plan.dict(), f, indent=2, default=str)
    
    print(f"\n✓ Generated {len(test_plan.test_cases)} test cases")
    print(f"✓ Saved to: {output_file}")
    
    # Quick validation
    print("\n" + "=" * 80)
    print("QUICK VALIDATION")
    print("=" * 80)
    
    api_tests = [tc for tc in test_plan.test_cases if "API" in (tc.tags or [])]
    ui_tests = [tc for tc in test_plan.test_cases if "UI" in (tc.tags or [])]
    
    print(f"\nAPI Tests: {len(api_tests)}")
    for tc in api_tests[:3]:
        print(f"  - {tc.title}")
        has_http = False
        for step in tc.steps[:2]:
            step_dict = step if isinstance(step, dict) else step.model_dump() if hasattr(step, 'model_dump') else {}
            action = step_dict.get('action', '')
            if any(m in action for m in ["GET ", "POST ", "PATCH ", "PUT ", "DELETE "]):
                has_http = True
                print(f"    ✓ Has HTTP method: {action[:80]}")
        if not has_http:
            print(f"    ❌ Missing HTTP method")
    
    print(f"\nUI Tests: {len(ui_tests)}")
    for tc in ui_tests[:3]:
        print(f"  - {tc.title}")
        has_nav = False
        for step in tc.steps[:2]:
            step_dict = step if isinstance(step, dict) else step.model_dump() if hasattr(step, 'model_dump') else {}
            action = step_dict.get('action', '')
            if "Navigate to" in action and "→" in action:
                has_nav = True
                print(f"    ✓ Has detailed navigation: {action[:80]}")
        if not has_nav:
            print(f"    ❌ Missing detailed navigation")
    
    # Check naming
    verify_tests = [tc for tc in test_plan.test_cases if tc.title.startswith(("Verify", "Validate", "Test", "Check"))]
    print(f"\nTest Naming:")
    if len(verify_tests) == 0:
        print(f"  ✅ No tests start with 'Verify' ({len(test_plan.test_cases)} tests checked)")
    else:
        print(f"  ❌ {len(verify_tests)} tests still start with 'Verify':")
        for tc in verify_tests[:3]:
            print(f"    - {tc.title}")
    
    print("\n" + "=" * 80)
    print("FULL VALIDATION")
    print("=" * 80)
    print("\nRun validation logic:")
    print(f"  python test_validation_logic.py")
    print(f"\nOr check the generated file:")
    print(f"  {output_file}")

if __name__ == "__main__":
    asyncio.run(main())

