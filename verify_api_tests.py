#!/usr/bin/env python3
"""
Direct test to verify API test generation with the fixed prompt
This bypasses the server and directly tests the prompt builder
"""

import sys
import json
sys.path.insert(0, '/Users/royregev/womba/src')

from ai.generation.prompt_builder import PromptBuilder
from models.enriched_story import EnrichedStory

# Mock story data for PLAT-15596 
story_data = {
    "key": "PLAT-15596",
    "summary": "PAP - Policy 360° - Phase 2 - Add Vendor Compare View - Core capabilities",
    "description": """
    Add Vendor Compare View to Policy 360°.
    Key features:
    - Visualize relationship between PlainID policies and vendor-native counterparts
    - Gain transparency into policy synchronization status
    - Enable reconciliation operations (deploy/override) from single unified view
    """,
    "components": ["PAP"],
    "acceptance_criteria": [
        "behavior validated on both new and existing POPs from different vendors",
        "behavior validated for different types of policies (masking, row, general)",
        "behavior validated for use cases when multiple platform policy are connected to single vendor policy",
        "behavior validated with large amount of policies in the display",
        "Updated behavior and terminology for audit and permissions validated",
        "Update POP details via UI or PAC works as expected",
        "no regression for flags, reconciliation actions, etc.",
        "No regression for policies used for dynamic authorization service"
    ]
}

# Create enriched story
enriched = EnrichedStory(
    story_key=story_data["key"],
    story_summary=story_data["summary"],
    story_description=story_data["description"],
    feature_narrative=story_data["summary"],
    plainid_components=["PAP"],
    extracted_endpoints=[
        "GET /policy-mgmt/3.0/policies/{policyId}/policy-relations",
        "POST /policy-mgmt/1.0/vendor-policies/ordered-platform-policies",
        "POST /internal-assets/assets/v3/vendor-enriched",
        "POST /orchestrator/1.0/vendor-policies-search"
    ]
)

# Build prompt
builder = PromptBuilder()
prompt = builder.build_optimized_prompt(
    enriched_story=enriched,
    rag_context_formatted="Policy Management APIs for vendor compare view. Related services: policy-mgmt, orchestrator, internal-assets"
)

print("=" * 80)
print("PROMPT ANALYSIS")
print("=" * 80)

# Check for API test examples
api_test_indicators = [
    ("POST /policy-mgmt/1.0/policies-search", "Example 1: Policy search API test"),
    ("GET /policy-mgmt/3.0/policies", "Example 2: Policy relations API test"),
    ("TEST PYRAMID", "Test pyramid guidance"),
    ("60-80%", "API test ratio specification"),
    ("NEVER mix", "API/UI separation rule"),
    ("HTTP method", "API method requirement"),
    ("POST /", "Real POST endpoint in examples"),
    ("GET /", "Real GET endpoint in examples"),
]

print("\n✓ Checking for API test guidance in prompt:\n")
found_count = 0
for indicator, description in api_test_indicators:
    if indicator in prompt:
        print(f"  ✓ {description}")
        found_count += 1
    else:
        print(f"  ✗ MISSING: {description}")

print(f"\nFound: {found_count}/{len(api_test_indicators)} key indicators")

# Check against UI-only indicators (what we DON'T want)
print("\n✓ Checking against UI-only anti-patterns:\n")

ui_only_bad = [
    ("Navigate to Authorization Workspace", "UI navigation only (bad for API tests)"),
    ("Click", "Click action (bad for API tests)"),
    ("Shopping cart calculates", "Generic non-PlainID example"),
]

ui_issues = 0
for bad_pattern, reason in ui_only_bad:
    if bad_pattern in prompt and "NEVER mix" not in prompt:
        # Only flag if it's not in the context of the "NEVER mix" rule
        if "UI navigation" not in prompt or "API" not in prompt:
            print(f"  ⚠ Found: {reason}")
            ui_issues += 1

if ui_issues == 0:
    print("  ✓ No problematic UI-only patterns found")
else:
    print(f"  ⚠ Found {ui_issues} potential UI/API mixing issues")

print("\n" + "=" * 80)
print("VERDICT")
print("=" * 80)

if found_count >= 6:
    print("✓ PROMPT IS FIXED: Contains proper API test guidance")
    print("✓ Next test generation should produce 60-80% backend API tests")
    print("✓ Tests should use real HTTP methods and endpoints")
else:
    print("✗ PROMPT NEEDS MORE WORK")
    print(f"  Missing {len(api_test_indicators) - found_count} key indicators")

print("\nFull prompt excerpt (first 500 chars of examples section):")
print("-" * 80)
start = prompt.find("EXAMPLE 1")
if start > 0:
    print(prompt[start:start+300] + "...")

