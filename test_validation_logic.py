#!/usr/bin/env python3
"""
Test the validation logic on the existing PLAT-13541 test plan.
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, '/Users/royregev/womba/src')

from models.test_plan import TestPlan
from models.enriched_story import EnrichedStory
from ai.generation.response_parser import ResponseParser

print("=" * 80)
print("TESTING VALIDATION LOGIC ON EXISTING TEST PLAN")
print("=" * 80)

# Load existing test plan
test_plan_file = Path("test_plans/test_plan_PLAT-13541.json")
if not test_plan_file.exists():
    print(f"❌ Test plan file not found: {test_plan_file}")
    sys.exit(1)

print(f"\n[1/3] Loading test plan from {test_plan_file}...")
with open(test_plan_file) as f:
    plan_data = json.load(f)

test_plan = TestPlan(**plan_data)
print(f"✓ Loaded {len(test_plan.test_cases)} test cases")

# Create mock enriched story with API specs (since PLAT-13541 should have APIs)
print("\n[2/3] Creating mock enriched story with API specs...")
from models.enriched_story import APISpec

mock_enriched = EnrichedStory(
    story_key="PLAT-13541",
    story_summary="Show Policy list by Application",
    story_description="UI capability to view policies by application",
    feature_narrative="Test",
    plainid_components=["PAP"],
    api_specifications=[
        APISpec(
            endpoint_path="/policy-mgmt/policy/application/{applicationId}/search",
            http_methods=["GET"],
            service_name="policy-mgmt"
        )
    ]
)
print("✓ Created mock enriched story with 1 API endpoint")

# Run validation
print("\n[3/3] Running validation logic...")
parser = ResponseParser()
warnings = parser.validate_test_cases(test_plan, enriched_story=mock_enriched)

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

# Analyze what's wrong
print("\n" + "=" * 80)
print("ANALYSIS")
print("=" * 80)

api_tests = [tc for tc in test_plan.test_cases if "API" in (tc.tags or [])]
ui_tests = [tc for tc in test_plan.test_cases if "UI" in (tc.tags or [])]

print(f"\nAPI Tests: {len(api_tests)}")
for tc in api_tests:
    print(f"  - {tc.title}")
    for step in tc.steps[:1]:
        step_dict = step if isinstance(step, dict) else step.model_dump() if hasattr(step, 'model_dump') else {}
        action = step_dict.get('action', '')
        if "GET " in action or "POST " in action:
            print(f"    ✓ Has HTTP method")
        else:
            print(f"    ❌ Missing HTTP method: {action[:100]}")

print(f"\nUI Tests: {len(ui_tests)}")
for tc in ui_tests:
    print(f"  - {tc.title}")
    for step in tc.steps[:1]:
        step_dict = step if isinstance(step, dict) else step.model_dump() if hasattr(step, 'model_dump') else {}
        action = step_dict.get('action', '')
        if "Navigate to" in action and "→" in action:
            print(f"    ✓ Has detailed navigation")
        else:
            print(f"    ❌ Missing detailed navigation: {action[:100]}")

print("\n" + "=" * 80)

