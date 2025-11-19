#!/usr/bin/env python3
"""
Regenerate test plan for PLAT-13541 and validate it meets all criteria.
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
    print("REGENERATING TEST PLAN FOR PLAT-13541")
    print("=" * 80)
    print("\nTesting with:")
    print("  ✅ Temperature: 0.2 (lower = more deterministic)")
    print("  ✅ Strengthened prompts (anti-Verify rules)")
    print("  ✅ Mandatory API test requirements")
    print("\nGenerating...\n")
    
    story_key = "PLAT-13541"
    
    try:
        # Collect story context
        print("[1/4] Collecting story context...")
        collector = StoryCollector()
        context = await collector.collect_story_context(story_key)
        print(f"✓ Collected context for {story_key}")
        
        # Generate test plan
        print("\n[2/4] Generating test plan with fixed prompts and temperature=0.2...")
        generator = TestPlanGenerator(use_openai=True)
        test_plan = await generator.generate_test_plan(context, use_rag=True)
        print(f"✓ Generated {len(test_plan.test_cases)} test cases")
        
        # Save for inspection
        output_file = Path("test_plans") / f"test_plan_{story_key}_FIXED.json"
        with open(output_file, 'w') as f:
            json.dump(test_plan.dict(), f, indent=2, default=str)
        print(f"✓ Saved to: {output_file}")
        
        # Run validation
        print("\n[3/4] Running validation logic...")
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
        
        # Comprehensive validation
        print("\n[4/4] Comprehensive validation...")
        
        api_tests = [tc for tc in test_plan.test_cases if "API" in (tc.tags or [])]
        ui_tests = [tc for tc in test_plan.test_cases if "UI" in (tc.tags or [])]
        verify_tests = [tc for tc in test_plan.test_cases if tc.title.startswith(("Verify", "Validate", "Test", "Check", "Ensure"))]
        trivial_tests = [tc for tc in test_plan.test_cases if any(word in tc.title.lower() for word in ["style aligns", "component is displayed", "tab is visible"])]
        
        print("\n" + "=" * 80)
        print("VALIDATION RESULTS")
        print("=" * 80)
        
        print(f"\n📊 Test Distribution:")
        print(f"  Total: {len(test_plan.test_cases)}")
        print(f"  API: {len(api_tests)}")
        print(f"  UI: {len(ui_tests)}")
        
        print(f"\n❌ Critical Issues:")
        critical_failures = []
        
        if len(verify_tests) > 0:
            print(f"  ❌ {len(verify_tests)} tests start with 'Verify/Validate/Test/Check/Ensure':")
            for tc in verify_tests:
                print(f"     - {tc.title}")
            critical_failures.append("Naming")
        else:
            print(f"  ✅ No tests start with 'Verify' prefix")
        
        if enriched_story and len(enriched_story.api_specifications) > 0:
            if len(api_tests) == 0:
                print(f"  ❌ Story has {len(enriched_story.api_specifications)} API endpoints but 0 API tests generated")
                critical_failures.append("API Tests")
            else:
                print(f"  ✅ Generated {len(api_tests)} API tests (story has {len(enriched_story.api_specifications)} endpoints)")
        else:
            print(f"  ⚠️  Could not check API test requirement (no enriched story)")
        
        if len(trivial_tests) > 0:
            print(f"  ❌ {len(trivial_tests)} trivial tests found:")
            for tc in trivial_tests:
                print(f"     - {tc.title}")
            critical_failures.append("Trivial Tests")
        else:
            print(f"  ✅ No trivial tests found")
        
        print(f"\n⚠️  Validation Logic Issues: {len(warnings)}")
        if warnings:
            for warning in warnings[:10]:
                print(f"  - {warning}")
            if len(warnings) > 10:
                print(f"  ... and {len(warnings) - 10} more")
        
        print("\n" + "=" * 80)
        if len(critical_failures) == 0 and len(warnings) == 0:
            print("✅ ALL VALIDATION CHECKS PASSED!")
            return True
        else:
            print(f"❌ VALIDATION FAILED: {', '.join(critical_failures)}")
            return False
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)

