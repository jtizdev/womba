#!/usr/bin/env python3
"""
Phase 4: Comprehensive validation of the newly generated test plan.
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, '/Users/royregev/womba/src')

from models.test_plan import TestPlan
from models.enriched_story import EnrichedStory, APISpec
from ai.generation.response_parser import ResponseParser

def validate_test_plan_comprehensive(test_plan_file: Path):
    """Comprehensive validation of test plan output"""
    
    print("=" * 80)
    print("PHASE 4: COMPREHENSIVE OUTPUT VALIDATION")
    print("=" * 80)
    
    # Load test plan
    if not test_plan_file.exists():
        print(f"❌ Test plan file not found: {test_plan_file}")
        return False
    
    print(f"\n[1/7] Loading test plan from {test_plan_file}...")
    with open(test_plan_file) as f:
        plan_data = json.load(f)
    
    test_plan = TestPlan(**plan_data)
    print(f"✓ Loaded {len(test_plan.test_cases)} test cases")
    
    # Create mock enriched story with API specs
    print("\n[2/7] Creating enriched story context...")
    mock_enriched = EnrichedStory(
        story_key="PLAT-13541",
        story_summary="Show Policy list by Application",
        feature_narrative="UI capability to view policies by application",
        plainid_components=["PAP"],
        api_specifications=[
            APISpec(
                endpoint_path="/policy-mgmt/policy/application/{applicationId}/search",
                http_methods=["GET"],
                service_name="policy-mgmt"
            )
        ]
    )
    print("✓ Created enriched story with 1 API endpoint")
    
    # Run validation logic
    print("\n[3/7] Running validation logic...")
    parser = ResponseParser()
    warnings = parser.validate_test_cases(test_plan, enriched_story=mock_enriched)
    
    # Phase 4 checks
    print("\n[4/7] Checking test distribution (test pyramid)...")
    api_tests = [tc for tc in test_plan.test_cases if "API" in (tc.tags or [])]
    ui_tests = [tc for tc in test_plan.test_cases if "UI" in (tc.tags or [])]
    integration_tests = [tc for tc in test_plan.test_cases if "INTEGRATION" in (tc.tags or [])]
    
    total = len(test_plan.test_cases)
    api_pct = (len(api_tests) / total * 100) if total > 0 else 0
    ui_pct = (len(ui_tests) / total * 100) if total > 0 else 0
    
    print(f"  Total: {total}")
    print(f"  API: {len(api_tests)} ({api_pct:.1f}%)")
    print(f"  UI: {len(ui_tests)} ({ui_pct:.1f}%)")
    print(f"  Integration: {len(integration_tests)}")
    
    pyramid_ok = api_pct >= 40  # At least 40% API tests (allowing for UI-heavy stories)
    print(f"  {'✅' if pyramid_ok else '❌'} Test pyramid: {'OK' if pyramid_ok else 'Too few API tests'}")
    
    # Check API tests format
    print("\n[5/7] Validating API tests format...")
    api_issues = []
    for tc in api_tests:
        has_http = False
        has_endpoint = False
        has_payload = False
        has_response = False
        
        for step in tc.steps:
            step_dict = step if isinstance(step, dict) else step.model_dump() if hasattr(step, 'model_dump') else {}
            action = step_dict.get('action', '')
            expected = step_dict.get('expected_result', '')
            test_data = step_dict.get('test_data', '')
            
            if any(m in action for m in ["GET ", "POST ", "PATCH ", "PUT ", "DELETE "]):
                has_http = True
            if "/" in action and any(char in action for char in ["/policy-mgmt", "/api/", "/orchestrator", "/internal-assets"]):
                has_endpoint = True
            if test_data and test_data.strip() and test_data != "{}":
                has_payload = True
            if expected and ("200" in expected or "400" in expected or "404" in expected or "response" in expected.lower()):
                has_response = True
        
        if not has_http:
            api_issues.append(f"  ❌ '{tc.title}' missing HTTP method")
        if not has_endpoint:
            api_issues.append(f"  ❌ '{tc.title}' missing endpoint path")
        if not has_payload:
            api_issues.append(f"  ⚠ '{tc.title}' missing request payload")
        if not has_response:
            api_issues.append(f"  ⚠ '{tc.title}' missing expected response")
    
    if api_issues:
        print("  Issues found:")
        for issue in api_issues[:10]:
            print(issue)
        if len(api_issues) > 10:
            print(f"  ... and {len(api_issues) - 10} more")
    else:
        print("  ✅ All API tests have HTTP methods and endpoints")
    
    # Check UI tests navigation
    print("\n[6/7] Validating UI tests navigation...")
    ui_issues = []
    for tc in ui_tests:
        has_nav = False
        has_workspace = False
        
        for step in tc.steps:
            step_dict = step if isinstance(step, dict) else step.model_dump() if hasattr(step, 'model_dump') else {}
            action = step_dict.get('action', '')
            
            if "Navigate to" in action or "→" in action:
                has_nav = True
            if any(ws in action for ws in ["Authorization Workspace", "Identity Workspace", "Orchestration Workspace", "Administration Workspace"]):
                has_workspace = True
        
        if not has_nav:
            ui_issues.append(f"  ❌ '{tc.title}' missing navigation path")
        if not has_workspace:
            ui_issues.append(f"  ❌ '{tc.title}' missing workspace in navigation")
    
    if ui_issues:
        print("  Issues found:")
        for issue in ui_issues[:10]:
            print(issue)
        if len(ui_issues) > 10:
            print(f"  ... and {len(ui_issues) - 10} more")
    else:
        print("  ✅ All UI tests have detailed navigation")
    
    # Check test naming
    print("\n[7/7] Validating test naming...")
    verify_tests = [tc for tc in test_plan.test_cases if tc.title.startswith(("Verify", "Validate", "Test", "Check"))]
    status_in_title = [tc for tc in test_plan.test_cases if any(code in tc.title for code in ["200", "400", "404", "500", "403", "401"])]
    
    if verify_tests:
        print(f"  ❌ {len(verify_tests)} tests start with 'Verify/Validate':")
        for tc in verify_tests[:5]:
            print(f"    - {tc.title}")
    else:
        print("  ✅ No tests start with 'Verify' prefix")
    
    if status_in_title:
        print(f"  ❌ {len(status_in_title)} tests have HTTP status codes in title:")
        for tc in status_in_title[:5]:
            print(f"    - {tc.title}")
    else:
        print("  ✅ No HTTP status codes in test titles")
    
    # Check test_data
    print("\n[8/7] Validating test_data fields...")
    empty_data = []
    for tc in test_plan.test_cases:
        for step in tc.steps:
            step_dict = step if isinstance(step, dict) else step.model_dump() if hasattr(step, 'model_dump') else {}
            test_data = step_dict.get('test_data', '')
            if not test_data or (isinstance(test_data, str) and not test_data.strip()):
                empty_data.append(f"  ❌ '{tc.title}' has empty test_data")
                break
    
    if empty_data:
        print(f"  Found {len(empty_data)} tests with empty test_data")
        for issue in empty_data[:5]:
            print(issue)
    else:
        print("  ✅ All test_data fields are populated")
    
    # Final summary
    print("\n" + "=" * 80)
    print("VALIDATION SUMMARY")
    print("=" * 80)
    
    critical_issues = len([w for w in warnings if "MANDATORY" in w or "missing" in w.lower()])
    total_issues = len(warnings) + len(api_issues) + len(ui_issues) + len(verify_tests) + len(status_in_title) + len(empty_data)
    
    print(f"\nValidation Logic Issues: {len(warnings)} ({critical_issues} critical)")
    print(f"API Test Issues: {len(api_issues)}")
    print(f"UI Test Issues: {len(ui_issues)}")
    print(f"Naming Issues: {len(verify_tests) + len(status_in_title)}")
    print(f"Test Data Issues: {len(empty_data)}")
    print(f"\nTotal Issues: {total_issues}")
    
    if total_issues == 0:
        print("\n✅ ALL VALIDATION CHECKS PASSED!")
        return True
    elif critical_issues == 0:
        print("\n⚠️  Some non-critical issues found, but all mandatory checks passed")
        return True
    else:
        print("\n❌ CRITICAL ISSUES FOUND - Need to fix and re-test")
        return False

if __name__ == "__main__":
    test_plan_file = Path("test_plans/test_plan_PLAT-13541_NEW.json")
    success = validate_test_plan_comprehensive(test_plan_file)
    sys.exit(0 if success else 1)

