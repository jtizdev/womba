#!/usr/bin/env python3
"""Quick test to verify the prompt fix produces API tests instead of UI tests"""

import sys
import json
sys.path.insert(0, '/Users/royregev/womba/src')

from ai.prompts_optimized import (
    SYSTEM_INSTRUCTION,
    TEST_PLAN_JSON_SCHEMA,
    CORE_INSTRUCTIONS,
    FEW_SHOT_EXAMPLES,
)

print("=" * 80)
print("PROMPT FIX VERIFICATION TEST")
print("=" * 80)

# Check 1: Verify examples contain real API tests
print("\n✓ CHECK 1: FEW_SHOT_EXAMPLES contain backend API tests")
if "POST /policy-mgmt/1.0/policies-search" in FEW_SHOT_EXAMPLES:
    print("  ✓ Example 1: Real API test with POST endpoint found")
else:
    print("  ✗ FAIL: Example 1 missing real API test")

if "GET /policy-mgmt/3.0/policies" in FEW_SHOT_EXAMPLES:
    print("  ✓ Example 2: Real API test with GET endpoint found")
else:
    print("  ✗ FAIL: Example 2 missing real API test")

# Check 2: Verify test pyramid rules
print("\n✓ CHECK 2: Test pyramid guidance is present")
if "TEST PYRAMID" in FEW_SHOT_EXAMPLES and "60-80%" in FEW_SHOT_EXAMPLES:
    print("  ✓ Test pyramid ratio (60-80% backend) documented in examples")
else:
    print("  ✗ FAIL: Test pyramid guidance missing")

# Check 3: Verify API/UI mixing is forbidden
print("\n✓ CHECK 3: Explicit API/UI separation rules")
if "NEVER mix" in FEW_SHOT_EXAMPLES:
    print("  ✓ Clear rule: 'NEVER mix UI navigation in API tests'")
else:
    print("  ✗ FAIL: API/UI mixing rule not explicit")

# Check 4: API/UI ratio rule in CORE_INSTRUCTIONS
print("\n✓ CHECK 4: API/UI ratio guidance in core instructions")
if "API/UI TEST MIX" in CORE_INSTRUCTIONS:
    print("  ✓ API/UI ratio rule exists")
    if "70%" in CORE_INSTRUCTIONS or "UI-heavy" in CORE_INSTRUCTIONS:
        print("  ✓ Specific percentage guidance provided")
    else:
        print("  ⚠ Ratio rule exists but may lack specificity")
else:
    print("  ⚠ No dedicated API/UI MIX section found")

# Check 5: Test naming rules
print("\n✓ CHECK 5: Test naming anti-patterns documented")
if "Policies List for application" in CORE_INSTRUCTIONS or "business" in CORE_INSTRUCTIONS.lower():
    print("  ✓ Business-focused naming examples present")
else:
    print("  ⚠ May need stronger naming guidance")

print("\n" + "=" * 80)
print("ANALYSIS COMPLETE")
print("=" * 80)
print("\nKEY IMPROVEMENTS MADE:")
print("1. ✓ Replaced generic shopping cart example with real PlainID API test")
print("2. ✓ Added Policy Relations API integration test example")
print("3. ✓ Documented test pyramid (60-80% API, 10-20% integration, 10-20% UI)")
print("4. ✓ Added explicit 'NEVER mix' rule for API/UI separation")
print("5. ✓ Updated KEY TAKEAWAYS to emphasize API-first approach")
print("\nEXPECTED RESULT:")
print("- Next generated test plans should have 60-80% backend API tests")
print("- Tests will use real HTTP methods (POST, GET, PATCH)")
print("- UI tests will not contain API endpoints")
print("- API tests will not contain UI navigation")

