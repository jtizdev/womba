#!/usr/bin/env python3
"""
Comprehensive test to validate the prompt fixes work correctly.

Tests:
1. API test generation (when story has API specs)
2. UI test navigation detail
3. Test naming (no "Verify" prefix)
4. Test data population
5. PlainID context injection
"""

import sys
import asyncio
import json
from pathlib import Path

sys.path.insert(0, '/Users/royregev/womba/src')

from aggregator.story_collector import StoryCollector
from ai.test_plan_generator import TestPlanGenerator
from ai.generation.prompt_builder import PromptBuilder
from models.enriched_story import EnrichedStory

async def test_plat_13541():
    """Generate and validate test plan for PLAT-13541"""
    print("=" * 80)
    print("TESTING IMPLEMENTATION: PLAT-13541")
    print("=" * 80)
    
    story_key = "PLAT-13541"
    
    # Step 1: Collect story context
    print("\n[1/4] Collecting story context...")
    collector = StoryCollector()
    context = await collector.collect_story_context(story_key)
    print(f"✓ Collected context for {story_key}")
    
    # Step 2: Generate test plan
    print("\n[2/4] Generating test plan with fixed prompts...")
    generator = TestPlanGenerator(use_openai=True)
    test_plan = await generator.generate_test_plan(context, use_rag=True)
    print(f"✓ Generated {len(test_plan.test_cases)} test cases")
    
    # Step 3: Validate the output
    print("\n[3/4] Validating test plan output...")
    validation_results = validate_test_plan(test_plan, context)
    
    # Step 4: Check prompt was built correctly (read from saved file)
    print("\n[4/4] Validating prompt structure...")
    prompt_file = Path("./debug_prompts") / f"prompt_{story_key}.txt"
    prompt_validation = validate_prompt_structure_from_file(prompt_file)
    
    # Print results
    print("\n" + "=" * 80)
    print("VALIDATION RESULTS")
    print("=" * 80)
    
    print_test_plan_validation(validation_results)
    print_prompt_validation(prompt_validation)
    
    # Save results
    output_file = Path("test_plans") / f"test_plan_{story_key}_VALIDATED.json"
    with open(output_file, 'w') as f:
        json.dump(test_plan.dict(), f, indent=2, default=str)
    print(f"\n✓ Saved validated test plan to: {output_file}")
    
    # Final verdict
    all_passed = (
        validation_results['api_tests_present'] and
        validation_results['api_tests_format_correct'] and
        validation_results['ui_tests_navigation_detailed'] and
        validation_results['test_naming_correct'] and
        validation_results['test_data_populated'] and
        prompt_validation['plainid_context_injected'] and
        prompt_validation['api_rule_present'] and
        prompt_validation['ui_example_present']
    )
    
    print("\n" + "=" * 80)
    if all_passed:
        print("✅ ALL VALIDATION CHECKS PASSED")
    else:
        print("❌ SOME VALIDATION CHECKS FAILED - SEE DETAILS ABOVE")
    print("=" * 80)
    
    return all_passed

def validate_test_plan(test_plan, context):
    """Validate the generated test plan meets all requirements"""
    results = {
        'api_tests_present': False,
        'api_tests_format_correct': False,
        'ui_tests_navigation_detailed': False,
        'test_naming_correct': False,
        'test_data_populated': True,
        'api_test_count': 0,
        'ui_test_count': 0,
        'issues': []
    }
    
    api_tests = []
    ui_tests = []
    
    for tc in test_plan.test_cases:
        # Count API and UI tests
        if "API" in (tc.tags or []):
            api_tests.append(tc)
            results['api_test_count'] += 1
        if "UI" in (tc.tags or []):
            ui_tests.append(tc)
            results['ui_test_count'] += 1
        
        # Check test naming (NO "Verify" prefix)
        if tc.title.startswith(("Verify", "Validate", "Test", "Check")):
            results['issues'].append(f"❌ Test '{tc.title}' starts with 'Verify/Validate' - should use business-focused naming")
        else:
            results['test_naming_correct'] = True
        
        # Check for HTTP status codes in title (should be in steps, not title)
        if any(code in tc.title for code in ["200", "400", "404", "500", "403", "401"]):
            results['issues'].append(f"❌ Test '{tc.title}' has HTTP status code in title - should be in steps")
        
        # Check test_data
        for step in tc.steps:
            step_dict = step if isinstance(step, dict) else step.model_dump() if hasattr(step, 'model_dump') else {}
            step_data = step_dict.get('test_data', '')
            if not step_data or (isinstance(step_data, str) and not step_data.strip()):
                results['test_data_populated'] = False
                results['issues'].append(f"❌ Test '{tc.title}' has empty test_data")
    
    # Check API tests
    if len(api_tests) > 0:
        results['api_tests_present'] = True
        
        # Check API test format
        all_have_http_methods = True
        all_have_endpoints = True
        for api_test in api_tests:
            has_http = False
            has_endpoint = False
            for step in api_test.steps:
                step_dict = step if isinstance(step, dict) else step.model_dump() if hasattr(step, 'model_dump') else {}
                action = step_dict.get('action', '')
                if any(method in action for method in ["GET ", "POST ", "PATCH ", "PUT ", "DELETE "]):
                    has_http = True
                if "/" in action and any(char in action for char in ["/policy-mgmt", "/api/", "/orchestrator", "/internal-assets"]):
                    has_endpoint = True
            if not has_http:
                all_have_http_methods = False
                results['issues'].append(f"❌ API test '{api_test.title}' missing HTTP method")
            if not has_endpoint:
                all_have_endpoints = False
                results['issues'].append(f"❌ API test '{api_test.title}' missing endpoint path")
        
        if all_have_http_methods and all_have_endpoints:
            results['api_tests_format_correct'] = True
    
    # Check UI tests
    if len(ui_tests) > 0:
        all_have_navigation = True
        all_have_workspace = True
        for ui_test in ui_tests:
            has_nav = False
            has_ws = False
            for step in ui_test.steps:
                step_dict = step if isinstance(step, dict) else step.model_dump() if hasattr(step, 'model_dump') else {}
                action = step_dict.get('action', '')
                if "Navigate to" in action or "→" in action:
                    has_nav = True
                if any(ws in action for ws in ["Authorization Workspace", "Identity Workspace", "Orchestration Workspace", "Administration Workspace"]):
                    has_ws = True
            if not has_nav:
                all_have_navigation = False
                results['issues'].append(f"❌ UI test '{ui_test.title}' missing navigation path")
            if not has_ws:
                all_have_workspace = False
                results['issues'].append(f"❌ UI test '{ui_test.title}' missing workspace in navigation")
        
        if all_have_navigation and all_have_workspace:
            results['ui_tests_navigation_detailed'] = True
    
    return results

def validate_prompt_structure_from_file(prompt_file: Path):
    """Validate the prompt file has correct structure"""
    results = {
        'plainid_context_injected': False,
        'api_rule_present': False,
        'ui_example_present': False,
        'negative_api_example_present': False,
        'prompt_file_exists': False
    }
    
    # First check prompts_optimized.py directly
    try:
        from ai.prompts_optimized import CORE_INSTRUCTIONS, FEW_SHOT_EXAMPLES
        
        # Check for API test requirement rule in CORE_INSTRUCTIONS
        if "API TEST REQUIREMENT (MANDATORY)" in CORE_INSTRUCTIONS or "MUST generate API tests" in CORE_INSTRUCTIONS:
            results['api_rule_present'] = True
        
        # Check for UI test example
        if "EXAMPLE 4 (Application Policies List - UI Test)" in FEW_SHOT_EXAMPLES:
            results['ui_example_present'] = True
        
        # Check for negative API example
        if "EXAMPLE 3 (Policy Search API - Negative Test Case)" in FEW_SHOT_EXAMPLES:
            results['negative_api_example_present'] = True
    except Exception as e:
        print(f"⚠ Could not check prompts_optimized.py: {e}")
    
    # Check prompt_builder.py for PlainID context injection
    try:
        prompt_builder_file = Path("src/ai/generation/prompt_builder.py")
        if prompt_builder_file.exists():
            builder_content = prompt_builder_file.read_text(encoding='utf-8')
            if "PLAINID UI STRUCTURE" in builder_content or "Authorization Workspace → Applications menu" in builder_content:
                # This means the code is there, but we still need to check if it's injected in the actual prompt
                pass
    except Exception as e:
        print(f"⚠ Could not check prompt_builder.py: {e}")
    
    # Then check the generated prompt file
    if prompt_file.exists():
        results['prompt_file_exists'] = True
        try:
            prompt = prompt_file.read_text(encoding='utf-8')
            
            # Check for PlainID context in generated prompt
            if "PLAINID UI STRUCTURE" in prompt or "Authorization Workspace → Applications menu" in prompt:
                results['plainid_context_injected'] = True
            
        except Exception as e:
            print(f"⚠ Could not read prompt file: {e}")
    else:
        print(f"⚠ Prompt file not found: {prompt_file} (will check source files only)")
    
    return results

def print_test_plan_validation(results):
    """Print test plan validation results"""
    print("\n📋 TEST PLAN VALIDATION:")
    print("-" * 80)
    
    print(f"API Tests Present: {'✅' if results['api_tests_present'] else '❌'} ({results['api_test_count']} found)")
    print(f"API Tests Format: {'✅' if results['api_tests_format_correct'] else '❌'} (HTTP methods + endpoints)")
    print(f"UI Tests Navigation: {'✅' if results['ui_tests_navigation_detailed'] else '❌'} ({results['ui_test_count']} found)")
    print(f"Test Naming: {'✅' if results['test_naming_correct'] else '❌'} (no 'Verify' prefix)")
    print(f"Test Data Populated: {'✅' if results['test_data_populated'] else '❌'}")
    
    if results['issues']:
        print(f"\n⚠ Issues found ({len(results['issues'])}):")
        for issue in results['issues'][:10]:
            print(f"  {issue}")
        if len(results['issues']) > 10:
            print(f"  ... and {len(results['issues']) - 10} more")

def print_prompt_validation(results):
    """Print prompt structure validation results"""
    print("\n📝 PROMPT STRUCTURE VALIDATION:")
    print("-" * 80)
    
    print(f"Prompt File Generated: {'✅' if results['prompt_file_exists'] else '❌'}")
    print(f"PlainID Context Injected: {'✅' if results['plainid_context_injected'] else '❌'}")
    print(f"API Test Rule Present: {'✅' if results['api_rule_present'] else '❌'}")
    print(f"UI Test Example Present: {'✅' if results['ui_example_present'] else '❌'}")
    print(f"Negative API Example Present: {'✅' if results['negative_api_example_present'] else '❌'}")

if __name__ == "__main__":
    success = asyncio.run(test_plat_13541())
    sys.exit(0 if success else 1)

