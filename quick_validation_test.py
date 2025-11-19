#!/usr/bin/env python3
"""
Quick validation test - checks prompt structure without generating full test plan.
"""

import sys
from pathlib import Path

sys.path.insert(0, '/Users/royregev/womba/src')

print("=" * 80)
print("QUICK VALIDATION: PROMPT STRUCTURE")
print("=" * 80)

# Check 1: API Test Requirement Rule
print("\n[1/5] Checking API Test Requirement Rule...")
from ai.prompts_optimized import CORE_INSTRUCTIONS
if "API TEST REQUIREMENT (MANDATORY)" in CORE_INSTRUCTIONS:
    print("  ✅ API TEST REQUIREMENT rule found in CORE_INSTRUCTIONS")
    if "MUST generate API tests" in CORE_INSTRUCTIONS:
        print("  ✅ Rule enforces API test generation")
    if "HTTP methods" in CORE_INSTRUCTIONS and "GET /endpoint" in CORE_INSTRUCTIONS:
        print("  ✅ Rule specifies HTTP methods requirement")
else:
    print("  ❌ API TEST REQUIREMENT rule NOT found!")

# Check 2: UI Test Example
print("\n[2/5] Checking UI Test Example...")
from ai.prompts_optimized import FEW_SHOT_EXAMPLES
if "EXAMPLE 4 (Application Policies List - UI Test)" in FEW_SHOT_EXAMPLES:
    print("  ✅ UI test example (EXAMPLE 4) found")
    if "Navigate to Authorization Workspace → Applications menu" in FEW_SHOT_EXAMPLES:
        print("  ✅ Example shows detailed navigation path")
    if "Application policies list displays correct count" in FEW_SHOT_EXAMPLES:
        print("  ✅ Example uses business-focused title (no 'Verify')")
else:
    print("  ❌ UI test example NOT found!")

# Check 3: Negative API Test Example
print("\n[3/5] Checking Negative API Test Example...")
if "EXAMPLE 3 (Policy Search API - Negative Test Case)" in FEW_SHOT_EXAMPLES:
    print("  ✅ Negative API test example (EXAMPLE 3) found")
    if "returns correct response when application ID is invalid" in FEW_SHOT_EXAMPLES:
        print("  ✅ Example title describes behavior, not status code")
    if "API returns 400 Bad Request" in FEW_SHOT_EXAMPLES:
        print("  ✅ Example shows status code in steps, not title")
else:
    print("  ❌ Negative API test example NOT found!")

# Check 4: PlainID Context Injection
print("\n[4/5] Checking PlainID Context Injection Code...")
prompt_builder_file = Path("src/ai/generation/prompt_builder.py")
if prompt_builder_file.exists():
    builder_content = prompt_builder_file.read_text(encoding='utf-8')
    if "PLAINID UI STRUCTURE" in builder_content:
        print("  ✅ PlainID UI structure code found in prompt_builder.py")
    if "Authorization Workspace → Applications menu" in builder_content:
        print("  ✅ Detailed navigation paths found in prompt_builder.py")
    if "UI TEST STEP REQUIREMENTS (CRITICAL)" in builder_content:
        print("  ✅ UI test step requirements found")
else:
    print("  ❌ prompt_builder.py not found!")

# Check 5: Validation Rules
print("\n[5/5] Checking Validation Rules...")
from ai.prompts_optimized import VALIDATION_RULES
if "API TESTS (MANDATORY IF STORY HAS API SPECS)" in VALIDATION_RULES:
    print("  ✅ API test validation checks found")
if "UI TESTS (MANDATORY IF STORY HAS UI)" in VALIDATION_RULES:
    print("  ✅ UI test validation checks found")
if "TEST NAMING" in VALIDATION_RULES and "Verify" in VALIDATION_RULES:
    print("  ✅ Test naming validation checks found")
if "Status codes: Are HTTP status codes in test STEPS, NOT in test titles" in VALIDATION_RULES:
    print("  ✅ Status code placement validation found")

# Check 6: KEY TAKEAWAYS
print("\n[6/6] Checking KEY TAKEAWAYS...")
if "API TEST RULE" in FEW_SHOT_EXAMPLES:
    print("  ✅ API TEST RULE mentioned in KEY TAKEAWAYS")
if "UI TEST RULE" in FEW_SHOT_EXAMPLES:
    print("  ✅ UI TEST RULE mentioned in KEY TAKEAWAYS")
if "TEST NAMING RULE" in FEW_SHOT_EXAMPLES:
    print("  ✅ TEST NAMING RULE mentioned in KEY TAKEAWAYS")

print("\n" + "=" * 80)
print("VALIDATION COMPLETE")
print("=" * 80)
print("\nAll prompt structure checks completed.")
print("Next: Run full test to generate test plan and validate output.")

