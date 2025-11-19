#!/usr/bin/env python3
"""
Comprehensive validation - check EVERYTHING and show detailed output
"""

import sys
import json
import asyncio
from pathlib import Path

sys.path.insert(0, '/Users/royregev/womba/src')

from aggregator.story_collector import StoryCollector
from ai.story_enricher import StoryEnricher
from models.test_plan import TestPlan

async def comprehensive_validation():
    print("=" * 80)
    print("COMPREHENSIVE VALIDATION - QA ASSESSMENT")
    print("=" * 80)
    
    # Get story endpoints
    print("\n[STEP 1] Collecting story context...")
    collector = StoryCollector()
    context = await collector.collect_story_context('PLAT-13541')
    enricher = StoryEnricher()
    enriched = await enricher.enrich_story(context.main_story, context)
    
    print(f"✓ Story: PLAT-13541")
    print(f"✓ Endpoints extracted: {len(enriched.api_specifications)}")
    
    # Load test plan
    print("\n[STEP 2] Loading generated test plan...")
    test_plan_file = Path("test_plans/test_plan_PLAT-13541_FIXED.json")
    if not test_plan_file.exists():
        print(f"❌ Test plan not found: {test_plan_file}")
        return False
    
    with open(test_plan_file) as f:
        plan_data = json.load(f)
    test_plan = TestPlan(**plan_data)
    
    print(f"✓ Test plan loaded: {len(test_plan.test_cases)} tests")
    
    # Extract API tests
    api_tests = [tc for tc in test_plan.test_cases if "API" in (tc.tags or [])]
    ui_tests = [tc for tc in test_plan.test_cases if "UI" in (tc.tags or [])]
    
    print(f"✓ API tests: {len(api_tests)}")
    print(f"✓ UI tests: {len(ui_tests)}")
    
    # Map endpoints to tests
    print("\n" + "=" * 80)
    print("[STEP 3] ENDPOINT COVERAGE ANALYSIS")
    print("=" * 80)
    
    endpoint_coverage = {}
    for api_spec in enriched.api_specifications:
        endpoint_key = f"{' '.join(api_spec.http_methods)} {api_spec.endpoint_path}"
        endpoint_coverage[endpoint_key] = {
            'spec': api_spec,
            'tests': [],
            'scenarios': {
                'positive': [],
                'negative': [],
                'edge_case': []
            }
        }
        
        # Find tests that cover this endpoint
        for test in api_tests:
            for step in test.steps:
                step_dict = step if isinstance(step, dict) else step.model_dump() if hasattr(step, 'model_dump') else {}
                action = step_dict.get('action', '')
                
                # Check if test covers this endpoint
                endpoint_parts = api_spec.endpoint_path.split('/')
                endpoint_found = False
                
                # Check if endpoint path is in action
                if api_spec.endpoint_path in action:
                    endpoint_found = True
                # Check if key parts of endpoint are in action
                elif any(len(part) > 3 and part in action for part in endpoint_parts):
                    endpoint_found = True
                # Check if service name is mentioned
                elif api_spec.service_name and api_spec.service_name.lower() in action.lower():
                    endpoint_found = True
                
                if endpoint_found:
                    if test not in endpoint_coverage[endpoint_key]['tests']:
                        endpoint_coverage[endpoint_key]['tests'].append(test)
                        
                        # Categorize scenario
                        if 'negative' in (test.tags or []) or 'NEGATIVE' in (test.tags or []):
                            endpoint_coverage[endpoint_key]['scenarios']['negative'].append(test)
                        elif 'invalid' in test.title.lower() or 'error' in test.title.lower() or 'denied' in test.title.lower():
                            endpoint_coverage[endpoint_key]['scenarios']['negative'].append(test)
                        else:
                            endpoint_coverage[endpoint_key]['scenarios']['positive'].append(test)
                    break
    
    # Display coverage
    print("\n📊 DETAILED COVERAGE BY ENDPOINT:\n")
    all_covered = True
    all_have_positive = True
    all_have_negative = True
    
    for endpoint_key, coverage in endpoint_coverage.items():
        spec = coverage['spec']
        tests = coverage['tests']
        scenarios = coverage['scenarios']
        
        print(f"🔹 {endpoint_key}")
        print(f"   Service: {spec.service_name}")
        print(f"   Tests Found: {len(tests)}")
        print(f"   Positive: {len(scenarios['positive'])}")
        print(f"   Negative: {len(scenarios['negative'])}")
        print(f"   Edge Cases: {len(scenarios['edge_case'])}")
        
        if len(tests) == 0:
            print(f"   ❌ NO TESTS - MISSING COVERAGE")
            all_covered = False
        elif len(scenarios['positive']) == 0:
            print(f"   ⚠️  WARNING: No positive test case")
            all_have_positive = False
        elif len(scenarios['negative']) == 0:
            print(f"   ⚠️  WARNING: No negative test case (should have error handling)")
            all_have_negative = False
        else:
            print(f"   ✅ COVERED")
        
        if tests:
            print(f"   Test Titles:")
            for test in tests:
                print(f"     - {test.title}")
        print()
    
    # Summary
    print("=" * 80)
    print("[STEP 4] VALIDATION SUMMARY")
    print("=" * 80)
    
    total_endpoints = len(enriched.api_specifications)
    covered_endpoints = sum(1 for cov in endpoint_coverage.values() if len(cov['tests']) > 0)
    endpoints_with_positive = sum(1 for cov in endpoint_coverage.values() if len(cov['scenarios']['positive']) > 0)
    endpoints_with_negative = sum(1 for cov in endpoint_coverage.values() if len(cov['scenarios']['negative']) > 0)
    
    print(f"\n📈 COVERAGE METRICS:")
    print(f"   Total Endpoints: {total_endpoints}")
    print(f"   Endpoints with Tests: {covered_endpoints}/{total_endpoints} ({covered_endpoints/total_endpoints*100:.1f}%)")
    print(f"   Endpoints with Positive Tests: {endpoints_with_positive}/{total_endpoints}")
    print(f"   Endpoints with Negative Tests: {endpoints_with_negative}/{total_endpoints}")
    
    # Missing coverage
    missing = [ep for ep, cov in endpoint_coverage.items() if len(cov['tests']) == 0]
    if missing:
        print(f"\n❌ MISSING COVERAGE ({len(missing)} endpoints):")
        for ep in missing:
            print(f"   - {ep}")
    
    # Endpoints needing more scenarios
    needs_more = []
    for ep, cov in endpoint_coverage.items():
        if len(cov['tests']) > 0:
            if len(cov['scenarios']['positive']) == 0:
                needs_more.append((ep, "Missing positive test"))
            elif len(cov['scenarios']['negative']) == 0:
                needs_more.append((ep, "Missing negative test"))
    
    if needs_more:
        print(f"\n⚠️  ENDPOINTS NEEDING MORE SCENARIOS ({len(needs_more)}):")
        for ep, reason in needs_more:
            print(f"   - {ep}: {reason}")
    
    # Final assessment
    print("\n" + "=" * 80)
    print("[STEP 5] FINAL QA ASSESSMENT")
    print("=" * 80)
    
    print("\n✅ REQUIREMENTS:")
    print("   1. Every endpoint must have at least 1 test")
    print("   2. Each endpoint should have positive + negative scenarios")
    print("   3. Test names should be business-focused (no 'Verify' prefix)")
    print("   4. Test data should be populated (no placeholders)")
    
    print("\n📊 CURRENT STATE:")
    print(f"   ✅ Endpoint Coverage: {covered_endpoints}/{total_endpoints} ({'PASS' if all_covered else 'FAIL'})")
    print(f"   ✅ Positive Tests: {endpoints_with_positive}/{total_endpoints} ({'PASS' if all_have_positive else 'FAIL'})")
    print(f"   ✅ Negative Tests: {endpoints_with_negative}/{total_endpoints} ({'PASS' if all_have_negative else 'FAIL'})")
    
    # Check test naming
    bad_names = [tc for tc in test_plan.test_cases if tc.title.startswith(("Verify", "Validate", "Test", "Check", "Ensure"))]
    print(f"   ✅ Test Naming: {len(bad_names)} bad names ({'PASS' if len(bad_names) == 0 else 'FAIL'})")
    
    # Check test data
    empty_data = []
    for tc in test_plan.test_cases:
        for step in tc.steps:
            step_dict = step if isinstance(step, dict) else step.model_dump() if hasattr(step, 'model_dump') else {}
            if not step_dict.get('test_data', ''):
                empty_data.append(f"{tc.title} step {step_dict.get('step_number', '?')}")
    print(f"   ✅ Test Data: {len(empty_data)} empty fields ({'PASS' if len(empty_data) == 0 else 'FAIL'})")
    
    # Final verdict
    print("\n" + "=" * 80)
    if all_covered and all_have_positive and all_have_negative and len(bad_names) == 0 and len(empty_data) == 0:
        print("✅ VALIDATION PASSED - ALL REQUIREMENTS MET")
        return True
    else:
        print("❌ VALIDATION FAILED - REQUIREMENTS NOT MET")
        print("\nMissing:")
        if not all_covered:
            print("   - Some endpoints have no tests")
        if not all_have_positive:
            print("   - Some endpoints missing positive tests")
        if not all_have_negative:
            print("   - Some endpoints missing negative tests")
        if len(bad_names) > 0:
            print(f"   - {len(bad_names)} tests with bad naming")
        if len(empty_data) > 0:
            print(f"   - {len(empty_data)} test steps with empty data")
        return False

if __name__ == "__main__":
    success = asyncio.run(comprehensive_validation())
    sys.exit(0 if success else 1)
