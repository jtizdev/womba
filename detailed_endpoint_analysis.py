#!/usr/bin/env python3
"""
Detailed endpoint analysis - check what endpoints exist and what tests cover them.
"""

import sys
import json
import asyncio
from pathlib import Path

sys.path.insert(0, '/Users/royregev/womba/src')

from aggregator.story_collector import StoryCollector
from ai.story_enricher import StoryEnricher
from models.test_plan import TestPlan

async def analyze():
    print("=" * 80)
    print("DETAILED ENDPOINT ANALYSIS")
    print("=" * 80)
    
    # Get story endpoints
    print("\n[1/3] Collecting story context and extracting API endpoints...")
    collector = StoryCollector()
    context = await collector.collect_story_context('PLAT-13541')
    enricher = StoryEnricher()
    enriched = await enricher.enrich_story(context.main_story, context)
    
    print(f"\n📋 Story: PLAT-13541")
    print(f"📋 API Endpoints Found: {len(enriched.api_specifications)}")
    print("\n🔍 Endpoints in Story:")
    for i, api in enumerate(enriched.api_specifications, 1):
        methods = " ".join(api.http_methods) if api.http_methods else "UNKNOWN"
        print(f"  {i}. {methods} {api.endpoint_path}")
        if api.service_name:
            print(f"     Service: {api.service_name}")
        if api.parameters:
            print(f"     Parameters: {', '.join(api.parameters)}")
    
    # Load test plan
    print("\n[2/3] Loading generated test plan...")
    test_plan_file = Path("test_plans/test_plan_PLAT-13541_FIXED.json")
    with open(test_plan_file) as f:
        plan_data = json.load(f)
    test_plan = TestPlan(**plan_data)
    
    print(f"\n📋 Test Plan: {len(test_plan.test_cases)} tests")
    
    # Extract API tests
    api_tests = [tc for tc in test_plan.test_cases if "API" in (tc.tags or [])]
    print(f"📋 API Tests: {len(api_tests)}")
    
    # Map endpoints to tests
    print("\n[3/3] Mapping endpoints to tests...")
    print("\n" + "=" * 80)
    print("ENDPOINT COVERAGE ANALYSIS")
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
                if any(part in action for part in endpoint_parts if len(part) > 3):
                    endpoint_coverage[endpoint_key]['tests'].append(test)
                    
                    # Categorize scenario
                    if 'negative' in (test.tags or []) or 'NEGATIVE' in (test.tags or []):
                        endpoint_coverage[endpoint_key]['scenarios']['negative'].append(test)
                    elif 'invalid' in test.title.lower() or 'error' in test.title.lower():
                        endpoint_coverage[endpoint_key]['scenarios']['negative'].append(test)
                    else:
                        endpoint_coverage[endpoint_key]['scenarios']['positive'].append(test)
                    break
    
    # Display coverage
    print("\n📊 COVERAGE BY ENDPOINT:\n")
    for endpoint_key, coverage in endpoint_coverage.items():
        spec = coverage['spec']
        tests = coverage['tests']
        scenarios = coverage['scenarios']
        
        print(f"🔹 {endpoint_key}")
        print(f"   Methods: {', '.join(spec.http_methods)}")
        print(f"   Tests Found: {len(tests)}")
        print(f"   Positive: {len(scenarios['positive'])}")
        print(f"   Negative: {len(scenarios['negative'])}")
        print(f"   Edge Cases: {len(scenarios['edge_case'])}")
        
        if len(tests) == 0:
            print(f"   ❌ NO TESTS - MISSING COVERAGE")
        elif len(scenarios['positive']) == 0:
            print(f"   ⚠️  WARNING: No positive test case")
        elif len(scenarios['negative']) == 0:
            print(f"   ⚠️  WARNING: No negative test case (should have error handling)")
        
        if tests:
            print(f"   Test Titles:")
            for test in tests:
                print(f"     - {test.title}")
        print()
    
    # Summary
    print("=" * 80)
    print("COVERAGE SUMMARY")
    print("=" * 80)
    
    total_endpoints = len(enriched.api_specifications)
    covered_endpoints = sum(1 for cov in endpoint_coverage.values() if len(cov['tests']) > 0)
    endpoints_with_positive = sum(1 for cov in endpoint_coverage.values() if len(cov['scenarios']['positive']) > 0)
    endpoints_with_negative = sum(1 for cov in endpoint_coverage.values() if len(cov['scenarios']['negative']) > 0)
    
    print(f"\nTotal Endpoints: {total_endpoints}")
    print(f"Endpoints with Tests: {covered_endpoints}/{total_endpoints} ({covered_endpoints/total_endpoints*100:.1f}%)")
    print(f"Endpoints with Positive Tests: {endpoints_with_positive}/{total_endpoints}")
    print(f"Endpoints with Negative Tests: {endpoints_with_negative}/{total_endpoints}")
    
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
    
    print("\n" + "=" * 80)
    print("QA ASSESSMENT")
    print("=" * 80)
    
    print("\nThinking like a QA engineer:")
    print("1. Each endpoint should have:")
    print("   ✅ Positive test (happy path)")
    print("   ✅ Negative test (error handling)")
    print("   ✅ Edge case test (boundaries, limits)")
    print("   ✅ Integration test (if applicable)")
    
    print(f"\n2. Current state:")
    print(f"   - {covered_endpoints}/{total_endpoints} endpoints have tests")
    print(f"   - {endpoints_with_positive}/{total_endpoints} have positive tests")
    print(f"   - {endpoints_with_negative}/{total_endpoints} have negative tests")
    
    if covered_endpoints < total_endpoints or endpoints_with_negative < total_endpoints:
        print(f"\n❌ NOT READY: Missing coverage or scenarios")
        return False
    else:
        print(f"\n✅ READY: All endpoints have comprehensive coverage")
        return True

if __name__ == "__main__":
    success = asyncio.run(analyze())
    sys.exit(0 if success else 1)

