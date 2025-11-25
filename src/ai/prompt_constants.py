"""
Shared constants for prompt generation.
Single source of truth for all prompt rules to avoid duplication.
"""

# ============================================================================
# NAMING RULES
# ============================================================================

FORBIDDEN_TITLE_PREFIXES = ["Verify", "Validate", "Test", "Check", "Ensure"]

TITLE_PATTERN = "Feature/component – behavior when condition"

TITLE_EXAMPLE_GOOD = "Policy list displays 10 items per page when dataset exceeds 50 policies"
TITLE_EXAMPLE_BAD = "Verify policies tab displays policies"

# ============================================================================
# API TEST REQUIREMENTS
# ============================================================================

API_TEST_REQUIREMENT = """If story mentions API endpoints OR has API specifications → MUST generate API tests.
EVERY endpoint in API SPECIFICATIONS section MUST have at least ONE API test.
Each endpoint needs MULTIPLE scenarios: positive test (happy path), negative test (error handling), edge case test (if applicable).
API tests MUST use HTTP methods: GET /endpoint, POST /endpoint, PATCH /endpoint, PUT /endpoint, DELETE /endpoint.
API tests MUST include request payloads and expected responses.
API tests MUST NOT contain UI navigation steps.
API test steps MUST contain exact endpoint paths (e.g., "/policy-mgmt/1.0/policies-search").
API test steps MUST specify HTTP status codes in expected_result (e.g., "API returns 200 OK" or "API returns 400 Bad Request")."""

# ============================================================================
# TEST DATA REQUIREMENTS
# ============================================================================

TEST_DATA_REQUIREMENT = """EVERY step.test_data MUST be populated as JSON string (no empty strings, no null).
Use concrete, story-specific values: application IDs, policy names, actual payloads.
API payloads MUST include all required fields with realistic values.
NO generic placeholders: NOT "new-policy-id", NOT "<token>", NOT "TODO".
Include both INPUT data and EXPECTED output in test_data."""

TEST_DATA_EXAMPLES = [
    '{"applicationId": "app-prod-123", "offset": 0, "limit": 10}',
    '{"policyId": "policy-audit-write", "action": "UNLINK"}',
    '{"workspace": "Authorization Workspace", "expected_count": 5}'
]

# ============================================================================
# UI TEST FORMAT RULES
# ============================================================================

UI_TEST_FORMAT = """For UI tests, use UI navigation language: "Navigate to...", "Click...", "Select...", "Verify displays...".
Always specify workspace: "In Authorization Workspace, navigate to Applications".
Always specify menu/tab path: "Applications → Select app-123 → Click Policies tab".
Verify UI elements: "Verify policy list displays with search bar and paging controls".
NO API endpoints in UI test steps (API calls go in separate backend/API tests)."""

# ============================================================================
# TRIVIAL TEST PROHIBITIONS
# ============================================================================

TRIVIAL_TEST_PROHIBITION = """NEVER test only "component is displayed" or "tab is visible".
NEVER test purely cosmetic/styling unless story explicitly requires it.
Every test must validate functional behavior, not just UI presence."""

# ============================================================================
# TEST STEP REQUIREMENTS
# ============================================================================

STEP_REQUIREMENTS = """Write short, actionable steps like a real QA checklist.
Functional tests need 3-6 steps minimum (setup → action → verify).
Each step must be specific with concrete test data.
API steps: "Send POST to /endpoint with {payload}" → "Expect 200 with {response}".
UI steps: "Open X" → "Click Y" → "Enter Z" → "Confirm message displays".
NO generic steps like "Validate system works correctly".
Avoid robotic language: write like you're instructing a colleague."""

# ============================================================================
# NON-INVENTION RULE
# ============================================================================

NON_INVENTION_RULE = """If story/docs do NOT mention an endpoint/field/error code → do not invent it.
Use ONLY endpoints from API SPECIFICATIONS section.
Use ONLY fields from provided schemas.
When uncertain, reference documentation: "as defined in [doc name]".
Better to be generic than to hallucinate specifics."""

# ============================================================================
# HANDLING MISSING INFORMATION
# ============================================================================

MISSING_INFO_HANDLING = """If RAG doesn't provide UI navigation structure → reference generically ("Navigate to relevant screen").
If Swagger doesn't specify response fields → reference the spec ("See API response schema").
If error codes not documented → use generic descriptions ("Returns appropriate error message").
Never invent menu names, field names, or endpoint paths not in context."""

# ============================================================================
# ACCEPTANCE CRITERIA MAPPING
# ============================================================================

AC_MAPPING_REQUIREMENT = """EVERY acceptance criterion MUST map to at least ONE test (name it explicitly in reasoning).
Include negative cases (errors, invalid input, unauthorized access).
Include edge cases (boundaries, limits, empty states).
Include integration scenarios (link/unlink, state changes).
NO arbitrary test count limits - generate as many as needed for thorough coverage.
AT LEAST ONE test per acceptance criterion - verify in your reasoning section."""


