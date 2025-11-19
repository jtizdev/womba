#!/usr/bin/env python3
"""
Generate a NEW test plan for PLAT-13541 to validate the fixed prompts work.
"""

import sys
import asyncio
import json
from pathlib import Path

sys.path.insert(0, '/Users/royregev/womba/src')

from aggregator.story_collector import StoryCollector
from ai.test_plan_generator import TestPlanGenerator
from ai.generation.response_parser import ResponseParser

async def main():
    print("=" * 80)
    print("PHASE 3: GENERATING NEW TEST PLAN FOR PLAT-13541")
    print("=" * 80)
    print("\nThis will test if the fixed prompts generate:")
    print("  ✅ API tests with HTTP methods")
    print("  ✅ UI tests with detailed navigation")
    print("  ✅ Proper test naming (no 'Verify')")
    print("  ✅ All test_data populated")
    print("\nGenerating... (this may take 1-2 minutes)\n")
    
    story_key = "PLAT-13541"
    
    try:
        # Collect story context
        print("[1/3] Collecting story context...")
        collector = StoryCollector()
        context = await collector.collect_story_context(story_key)
        print(f"✓ Collected context for {story_key}")
        
        # Generate test plan
        print("\n[2/3] Generating test plan with fixed prompts...")
        generator = TestPlanGenerator(use_openai=True)
        test_plan = await generator.generate_test_plan(context, use_rag=True)
        print(f"✓ Generated {len(test_plan.test_cases)} test cases")
        
        # Save for inspection
        output_file = Path("test_plans") / f"test_plan_{story_key}_NEW.json"
        with open(output_file, 'w') as f:
            json.dump(test_plan.dict(), f, indent=2, default=str)
        print(f"✓ Saved to: {output_file}")
        
        # Run validation
        print("\n[3/3] Running validation logic on new test plan...")
        parser = ResponseParser()
        
        # Get enriched story for validation
        enriched_story = None
        try:
            from ai.story_enricher import StoryEnricher
            enricher = StoryEnricher()
            enriched_story = await enricher.enrich_story(context.main_story, context)
        except Exception as e:
            print(f"⚠ Could not enrich story for validation: {e}")
        
        warnings = parser.validate_test_cases(test_plan, enriched_story=enriched_story)
        
        print("\n" + "=" * 80)
        print("VALIDATION RESULTS")
        print("=" * 80)
        print(f"\nFound {len(warnings)} validation issues:\n")
        
        if warnings:
            for i, warning in enumerate(warnings[:20], 1):
                print(f"{i}. {warning}")
            if len(warnings) > 20:
                print(f"\n... and {len(warnings) - 20} more issues")
        else:
            print("✅ No validation issues found!")
        
        # Quick analysis
        print("\n" + "=" * 80)
        print("QUICK ANALYSIS")
        print("=" * 80)
        
        api_tests = [tc for tc in test_plan.test_cases if "API" in (tc.tags or [])]
        ui_tests = [tc for tc in test_plan.test_cases if "UI" in (tc.tags or [])]
        verify_tests = [tc for tc in test_plan.test_cases if tc.title.startswith(("Verify", "Validate", "Test", "Check"))]
        
        print(f"\nTotal Tests: {len(test_plan.test_cases)}")
        print(f"API Tests: {len(api_tests)}")
        print(f"UI Tests: {len(ui_tests)}")
        print(f"Tests with 'Verify' prefix: {len(verify_tests)}")
        
        if len(api_tests) > 0:
            print(f"\nAPI Test Examples:")
            for tc in api_tests[:3]:
                print(f"  - {tc.title}")
                for step in tc.steps[:1]:
                    step_dict = step if isinstance(step, dict) else step.model_dump() if hasattr(step, 'model_dump') else {}
                    action = step_dict.get('action', '')
                    if any(m in action for m in ["GET ", "POST ", "PATCH ", "PUT ", "DELETE "]):
                        print(f"    ✓ Has HTTP method: {action[:80]}")
                    else:
                        print(f"    ❌ Missing HTTP method: {action[:80]}")
        
        if len(ui_tests) > 0:
            print(f"\nUI Test Examples:")
            for tc in ui_tests[:3]:
                print(f"  - {tc.title}")
                for step in tc.steps[:1]:
                    step_dict = step if isinstance(step, dict) else step.model_dump() if hasattr(step, 'model_dump') else {}
                    action = step_dict.get('action', '')
                    if "Navigate to" in action and "→" in action:
                        print(f"    ✓ Has detailed navigation: {action[:80]}")
                    else:
                        print(f"    ❌ Missing detailed navigation: {action[:80]}")
        
        print("\n" + "=" * 80)
        print("NEXT STEPS")
        print("=" * 80)
        print(f"\n1. Review the generated test plan: {output_file}")
        print("2. Check the prompt file: debug_prompts/prompt_PLAT-13541.txt")
        print("3. If issues found, proceed to Phase 5: Fix and Re-test")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return len(warnings) == 0

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)

