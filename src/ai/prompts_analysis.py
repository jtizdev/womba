"""
Stage 1: Analysis Prompt for Two-Stage Test Generation.

This prompt analyzes the story, ACs, PRD, Swagger, and existing tests
to produce a structured CoveragePlan that Stage 2 uses to generate tests.

Key features:
- Pattern detection (DIFFERENT_X, SPECIFIC_USER, NAMED_FEATURE, HIDDEN_VISIBLE)
- PRD requirement extraction
- API endpoint identification
- Existing test overlap detection
- Few-shot example showing REASONING, not just format
"""

from typing import List, Dict, Any, Optional
from loguru import logger


# =============================================================================
# STAGE 1: ANALYSIS SYSTEM INSTRUCTION
# =============================================================================

ANALYSIS_SYSTEM_INSTRUCTION = """You are a senior QA engineer analyzing a feature for test planning.

Your job is to ANALYZE the inputs and create a structured coverage plan. Do NOT write tests yet.

=== PATTERN DETECTION ===

Scan each Acceptance Criterion (AC) for these patterns:

1. DIFFERENT_X Pattern:
   - Trigger: AC contains "different", "multiple", "various" + noun
   - Example: "Test with different IDPs" → DIFFERENT_X, requirement: "Test 2+ IDPs"
   - Example: "Support multiple browsers" → DIFFERENT_X, requirement: "Test 2+ browsers"

2. SPECIFIC_USER Pattern:
   - Trigger: AC mentions specific user type (root, admin, guest, tenant, etc.)
   - Trigger: AC mentions "permissions" or "access" → test with different permission levels
   - Example: "Root account can login" → SPECIFIC_USER, requirement: "Test with root user"
   - Example: "Guest users see limited data" → SPECIFIC_USER, requirement: "Test with guest user"
   - Example: "Verify permissions" → SPECIFIC_USER, requirement: "Test with admin AND non-admin users"

3. NAMED_FEATURE Pattern:
   - Trigger: AC mentions a feature name (compare, filter, sort, export, import, link, unlink, etc.)
   - Example: "Compare changes between versions" → NAMED_FEATURE, requirement: "Test compare feature"
   - Example: "Filter by date range" → NAMED_FEATURE, requirement: "Test date filter"
   - Example: "Link/unlink applications" → NAMED_FEATURE, requirement: "Test link AND unlink operations"
   - Example: "Verify audit" → NAMED_FEATURE, requirement: "Test audit log entries are created"

4. HIDDEN_VISIBLE Pattern:
   - Trigger: PRD/story mentions hidden/visible/disabled UI elements
   - Example: "Parent Name field should be hidden" → HIDDEN_VISIBLE, requirement: "Verify field hidden"
   - Example: "Button disabled when empty" → HIDDEN_VISIBLE, requirement: "Verify button state"

5. LARGE_DATASET Pattern (NEW):
   - Trigger: AC mentions "paging", "pagination", or implies large lists
   - DO NOT create a "pagination works" test - instead test with LARGE DATASET
   - Example: "Verify paging" → LARGE_DATASET, requirement: "Test with 50+ items to verify list handles large data"

=== PRD REQUIREMENT EXTRACTION ===

Look in PRD/Confluence docs for:
- UI behavior requirements (fields, buttons, visibility)
- Input validation rules
- Feature-specific behavior
- Things NOT mentioned in ACs but required for the feature

=== API COVERAGE ===

From Swagger/API specs, identify endpoints that:
- Are directly related to the feature
- Must be tested for correct request/response
- Have specific status codes to verify

=== EXISTING TEST OVERLAP ===

Check existing tests to avoid duplicates:
- If a test already covers a scenario, note it to skip
- If a test partially covers, note what's still needed

=== TEST PLANNING ===

For each planned test, identify:
- What ACs it covers (by number)
- What patterns it satisfies
- What PRD requirements it verifies
- What API endpoints it tests

=== FORBIDDEN TEST PATTERNS (NEVER plan these) ===

VISIBILITY/EXISTENCE TESTS - NOT REAL TESTS:
❌ "X is visible/displayed/present" → If you interact with X and it works, X exists
❌ "Tab is displayed" → Test what happens when you CLICK the tab
❌ "Search bar is present" → Test the SEARCH FUNCTIONALITY instead
❌ "Page loads correctly" → This is a precondition, not a test

GENERIC UI TESTS - NOT HOW HUMANS WRITE TESTS:
❌ "Pagination functionality" → Test viewing LARGE DATASETS (50+ items) - pagination is implicit
❌ "Sorting works" → Test viewing data SORTED BY specific criteria
❌ "Filtering works" → Test finding SPECIFIC items with specific filters

INSTEAD, PLAN FUNCTIONAL TESTS:
✅ "Clicking Policies tab displays list of policies with correct data"
✅ "Search filters policies by name and returns matching results"
✅ "Policies list displays correctly with 50+ policies across multiple pages"
✅ "Sorting by date shows newest policies first"

EFFICIENCY RULES:
- Don't plan separate tests for trivial checks (e.g., "admin can access X" when all tests need admin)
- Don't plan visibility/existence tests - test the FUNCTIONALITY instead
- Combine related scenarios into comprehensive tests
- A good test covers multiple things, not just one AC"""


# =============================================================================
# ANALYSIS OUTPUT FORMAT (JSON Schema)
# =============================================================================

ANALYSIS_OUTPUT_FORMAT = """{
  "analysis_reasoning": "Your analysis: What is this feature? What patterns did you find? What PRD requirements exist?",
  
  "pattern_matches": [
    {
      "ac_number": 7,
      "pattern_type": "DIFFERENT_X",
      "matched_text": "different IDP",
      "requirement": "Test with at least 2 different IDPs (e.g., Keycloak, Okta)"
    }
  ],
  
  "prd_requirements": [
    {
      "source": "PRD",
      "requirement": "Parent Name field should be hidden for non-root users",
      "test_needed": "Verify Parent Name field visibility based on user type"
    }
  ],
  
  "api_coverage": [
    {
      "endpoint": "GET /audit/logs",
      "source": "swagger",
      "must_test": true,
      "description": "Retrieve audit logs with filtering"
    }
  ],
  
  "existing_test_overlap": [
    {
      "existing_test_name": "Basic login audit test",
      "skip_reason": "Already covers standard login audit scenario"
    }
  ],
  
  "test_plan": [
    {
      "test_idea": "Audit log shows login event after Keycloak authentication",
      "covers_acs": [1, 6],
      "covers_patterns": [],
      "covers_prd": false,
      "api_endpoints": ["GET /audit/logs"],
      "priority": "critical"
    },
    {
      "test_idea": "Audit log shows login event after SAML/Okta authentication",
      "covers_acs": [7],
      "covers_patterns": ["DIFFERENT_X"],
      "covers_prd": false,
      "api_endpoints": ["GET /audit/logs"],
      "priority": "high"
    },
    {
      "test_idea": "Root account login creates audit record with admin flag",
      "covers_acs": [8],
      "covers_patterns": ["SPECIFIC_USER"],
      "covers_prd": false,
      "api_endpoints": ["GET /audit/logs"],
      "priority": "high"
    },
    {
      "test_idea": "Compare changes feature shows differences between audit entries",
      "covers_acs": [3],
      "covers_patterns": ["NAMED_FEATURE"],
      "covers_prd": false,
      "api_endpoints": [],
      "priority": "high"
    },
    {
      "test_idea": "Parent Name field hidden for tenant admin users",
      "covers_acs": [],
      "covers_patterns": ["HIDDEN_VISIBLE"],
      "covers_prd": true,
      "api_endpoints": [],
      "priority": "medium"
    }
  ]
}"""


# =============================================================================
# FEW-SHOT EXAMPLE (Shows REASONING, not just format)
# =============================================================================

ANALYSIS_FEW_SHOT_EXAMPLE = """
=== EXAMPLE INPUT ===

Story: PLAT-99999 - User Login Audit Feature
ACs:
  AC #1: User can login successfully
  AC #2: Audit log records login events
  AC #3: Test with different browsers (Chrome, Firefox, Safari)
  AC #4: Admin users can view audit logs
  AC #5: Guest users cannot view audit logs

PRD Excerpt:
  "The login button should be disabled when email or password fields are empty.
   Failed login attempts should show an error message but NOT be logged to audit."

Swagger:
  POST /auth/login - Authenticate user
  GET /audit/logs - Retrieve audit logs (admin only)

Existing Tests:
  - "Basic login flow" - Tests successful login with valid credentials

=== EXAMPLE ANALYSIS ===

{
  "analysis_reasoning": "This is a login audit feature. I found: (1) DIFFERENT_X pattern in AC #3 for browsers, (2) SPECIFIC_USER patterns for admin and guest in AC #4-5, (3) PRD has hidden/disabled button requirement and a negative case about failed logins. The existing 'Basic login flow' test covers basic login but NOT audit logging, so we still need audit tests.",
  
  "pattern_matches": [
    {
      "ac_number": 3,
      "pattern_type": "DIFFERENT_X",
      "matched_text": "different browsers",
      "requirement": "Test login with at least 2 browsers (Chrome and Firefox minimum)"
    },
    {
      "ac_number": 4,
      "pattern_type": "SPECIFIC_USER",
      "matched_text": "Admin users",
      "requirement": "Test audit log access with admin user"
    },
    {
      "ac_number": 5,
      "pattern_type": "SPECIFIC_USER",
      "matched_text": "Guest users",
      "requirement": "Test audit log access denied for guest user"
    }
  ],
  
  "prd_requirements": [
    {
      "source": "PRD",
      "requirement": "Login button disabled when fields empty",
      "test_needed": "Verify button state changes based on field content"
    },
    {
      "source": "PRD",
      "requirement": "Failed logins NOT logged to audit",
      "test_needed": "Verify failed login does not create audit entry"
    }
  ],
  
  "api_coverage": [
    {
      "endpoint": "POST /auth/login",
      "source": "swagger",
      "must_test": true,
      "description": "Authentication endpoint"
    },
    {
      "endpoint": "GET /audit/logs",
      "source": "swagger",
      "must_test": true,
      "description": "Audit log retrieval"
    }
  ],
  
  "existing_test_overlap": [
    {
      "existing_test_name": "Basic login flow",
      "skip_reason": "Covers login success but NOT audit logging - still need audit tests"
    }
  ],
  
  "test_plan": [
    {
      "test_idea": "Successful login creates audit entry with user details",
      "covers_acs": [1, 2],
      "covers_patterns": [],
      "covers_prd": false,
      "api_endpoints": ["POST /auth/login", "GET /audit/logs"],
      "priority": "critical"
    },
    {
      "test_idea": "Login in Firefox creates same audit entry as Chrome",
      "covers_acs": [3],
      "covers_patterns": ["DIFFERENT_X"],
      "covers_prd": false,
      "api_endpoints": ["POST /auth/login", "GET /audit/logs"],
      "priority": "high"
    },
    {
      "test_idea": "Admin user views complete audit log with all entries",
      "covers_acs": [4],
      "covers_patterns": ["SPECIFIC_USER"],
      "covers_prd": false,
      "api_endpoints": ["GET /audit/logs"],
      "priority": "high"
    },
    {
      "test_idea": "Guest user receives 403 when accessing audit logs",
      "covers_acs": [5],
      "covers_patterns": ["SPECIFIC_USER"],
      "covers_prd": false,
      "api_endpoints": ["GET /audit/logs"],
      "priority": "high"
    },
    {
      "test_idea": "Login button disabled until both email and password entered",
      "covers_acs": [],
      "covers_patterns": ["HIDDEN_VISIBLE"],
      "covers_prd": true,
      "api_endpoints": [],
      "priority": "medium"
    },
    {
      "test_idea": "Failed login attempt does not appear in audit log",
      "covers_acs": [],
      "covers_patterns": [],
      "covers_prd": true,
      "api_endpoints": ["POST /auth/login", "GET /audit/logs"],
      "priority": "high"
    }
  ]
}

=== WHY THIS ANALYSIS IS GOOD ===

1. Found ALL patterns: DIFFERENT_X (browsers), SPECIFIC_USER (admin, guest)
2. Extracted PRD requirements: button disabled, failed logins not logged
3. Identified API endpoints from Swagger
4. Noted existing test overlap but explained why we still need new tests
5. Planned tests that cover patterns AND PRD requirements
6. Did NOT create trivial tests like "user can access login page"

=== TESTS WE DID NOT PLAN (AND WHY) ===

❌ "Login page is visible" → TRIVIAL - if you can login, the page exists
❌ "Login button is present" → TRIVIAL - covered by testing button disabled state
❌ "Pagination works on audit logs" → WRONG - test with large dataset instead
❌ "Search bar is displayed" → TRIVIAL - test search functionality instead
"""


# =============================================================================
# ANALYSIS JSON SCHEMA
# =============================================================================

ANALYSIS_JSON_SCHEMA = {
    "type": "object",
    "required": ["analysis_reasoning", "pattern_matches", "prd_requirements", "api_coverage", "test_plan"],
    "properties": {
        "analysis_reasoning": {
            "type": "string",
            "description": "Your analysis of the feature, patterns found, and PRD requirements"
        },
        "pattern_matches": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["ac_number", "pattern_type", "matched_text", "requirement"],
                "properties": {
                    "ac_number": {"type": "integer"},
                    "pattern_type": {"type": "string", "enum": ["DIFFERENT_X", "SPECIFIC_USER", "NAMED_FEATURE", "HIDDEN_VISIBLE", "LARGE_DATASET"]},
                    "matched_text": {"type": "string"},
                    "requirement": {"type": "string"}
                }
            }
        },
        "prd_requirements": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["source", "requirement", "test_needed"],
                "properties": {
                    "source": {"type": "string"},
                    "requirement": {"type": "string"},
                    "test_needed": {"type": "string"}
                }
            }
        },
        "api_coverage": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["endpoint", "source", "must_test"],
                "properties": {
                    "endpoint": {"type": "string"},
                    "source": {"type": "string"},
                    "must_test": {"type": "boolean"},
                    "description": {"type": "string"}
                }
            }
        },
        "existing_test_overlap": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["existing_test_name", "skip_reason"],
                "properties": {
                    "existing_test_name": {"type": "string"},
                    "skip_reason": {"type": "string"}
                }
            }
        },
        "test_plan": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["test_idea", "covers_acs", "priority"],
                "properties": {
                    "test_idea": {"type": "string"},
                    "covers_acs": {"type": "array", "items": {"type": "integer"}},
                    "covers_patterns": {"type": "array", "items": {"type": "string"}},
                    "covers_prd": {"type": "boolean"},
                    "api_endpoints": {"type": "array", "items": {"type": "string"}},
                    "priority": {"type": "string", "enum": ["critical", "high", "medium", "low"]}
                }
            }
        }
    }
}


# =============================================================================
# BUILD ANALYSIS PROMPT
# =============================================================================

def build_analysis_prompt(
    story_key: str,
    story_title: str,
    story_description: str,
    acceptance_criteria: List[str],
    confluence_docs: Optional[List[Dict[str, Any]]] = None,
    swagger_docs: Optional[List[Dict[str, Any]]] = None,
    existing_tests: Optional[List[Dict[str, Any]]] = None,
    api_specifications: Optional[List[Dict[str, Any]]] = None
) -> str:
    """
    Build the Stage 1 analysis prompt.
    
    This prompt asks the AI to analyze the story and produce a CoveragePlan,
    NOT to generate tests yet.
    
    Args:
        story_key: Jira story key
        story_title: Story summary
        story_description: Full story description
        acceptance_criteria: List of ACs
        confluence_docs: PRD/Confluence documents
        swagger_docs: Swagger/API documentation
        existing_tests: Existing tests to check for overlap
        api_specifications: API specs from story enrichment
        
    Returns:
        Complete analysis prompt
    """
    sections = []
    
    # Section 1: System instruction
    sections.append(ANALYSIS_SYSTEM_INSTRUCTION)
    logger.info("[ANALYSIS PROMPT] Added system instruction")
    
    # Section 2: Story context
    story_section = _build_story_section(
        story_key=story_key,
        story_title=story_title,
        story_description=story_description,
        acceptance_criteria=acceptance_criteria
    )
    sections.append(story_section)
    logger.info(f"[ANALYSIS PROMPT] Added story section with {len(acceptance_criteria)} ACs")
    
    # Section 3: PRD/Confluence docs
    if confluence_docs:
        prd_section = _build_prd_section(confluence_docs)
        sections.append(prd_section)
        logger.info(f"[ANALYSIS PROMPT] Added PRD section with {len(confluence_docs)} docs")
    
    # Section 4: Swagger/API docs
    if swagger_docs or api_specifications:
        api_section = _build_api_section(swagger_docs, api_specifications)
        sections.append(api_section)
        logger.info(f"[ANALYSIS PROMPT] Added API section")
    
    # Section 5: Existing tests
    if existing_tests:
        tests_section = _build_existing_tests_section(existing_tests)
        sections.append(tests_section)
        logger.info(f"[ANALYSIS PROMPT] Added existing tests section with {len(existing_tests)} tests")
    
    # Section 6: Few-shot example
    sections.append(f"\n{ANALYSIS_FEW_SHOT_EXAMPLE}")
    logger.info("[ANALYSIS PROMPT] Added few-shot example")
    
    # Section 7: Output format
    sections.append(f"\n=== YOUR TASK ===\n\nAnalyze the story above and output a JSON coverage plan:\n\n{ANALYSIS_OUTPUT_FORMAT}")
    logger.info("[ANALYSIS PROMPT] Added output format")
    
    prompt = "\n\n".join(sections)
    logger.info(f"[ANALYSIS PROMPT] Total length: {len(prompt)} chars, {len(prompt.split())} words")
    
    return prompt


def _build_story_section(
    story_key: str,
    story_title: str,
    story_description: str,
    acceptance_criteria: List[str]
) -> str:
    """Build the story context section."""
    parts = []
    
    parts.append("=" * 60)
    parts.append("STORY TO ANALYZE")
    parts.append("=" * 60)
    
    parts.append(f"\nStory: {story_key} - {story_title}")
    
    if story_description:
        desc = story_description[:3000] if len(story_description) > 3000 else story_description
        parts.append(f"\nDescription:\n{desc}")
    
    if acceptance_criteria:
        parts.append(f"\n--- ACCEPTANCE CRITERIA ({len(acceptance_criteria)} items) ---")
        parts.append("Scan each AC for patterns: DIFFERENT_X, SPECIFIC_USER, NAMED_FEATURE, HIDDEN_VISIBLE")
        parts.append("")
        for i, ac in enumerate(acceptance_criteria, 1):
            parts.append(f"AC #{i}: {ac}")
    
    return "\n".join(parts)


def _build_prd_section(confluence_docs: List[Any]) -> str:
    """Build the PRD/Confluence section."""
    parts = []
    
    parts.append("=" * 60)
    parts.append("PRD / CONFLUENCE DOCUMENTATION")
    parts.append("=" * 60)
    parts.append("Look for: hidden/visible elements, button states, validation rules, feature behavior")
    parts.append("")
    
    for doc in confluence_docs[:3]:  # Limit to 3 docs
        # Handle both dict and ConfluenceDocRef objects
        if hasattr(doc, 'title'):
            title = doc.title or 'Untitled'
            content = doc.qa_summary or doc.summary or ''
        else:
            title = doc.get('title', 'Untitled')
            content = doc.get('qa_summary') or doc.get('summary') or doc.get('content', '')
        
        parts.append(f"📄 {title}")
        parts.append("-" * 40)
        
        # Truncate if too long
        if len(content) > 2000:
            content = content[:2000] + "... [truncated]"
        parts.append(content)
        parts.append("")
    
    return "\n".join(parts)


def _build_api_section(
    swagger_docs: Optional[List[Dict[str, Any]]],
    api_specifications: Optional[List[Dict[str, Any]]]
) -> str:
    """Build the API/Swagger section."""
    parts = []
    
    parts.append("=" * 60)
    parts.append("API / SWAGGER DOCUMENTATION")
    parts.append("=" * 60)
    parts.append("Identify endpoints that must be tested")
    parts.append("")
    
    # Add swagger docs
    if swagger_docs:
        for doc in swagger_docs[:3]:
            service = doc.get('service', 'Unknown')
            content = doc.get('content', '')
            parts.append(f"📡 Service: {service}")
            parts.append(content[:1500] if len(content) > 1500 else content)
            parts.append("")
    
    # Add API specifications from enrichment
    if api_specifications:
        parts.append("--- API Endpoints from Story ---")
        for spec in api_specifications[:10]:
            method = spec.get('method', 'GET')
            path = spec.get('path', '')
            desc = spec.get('description', '')
            parts.append(f"  {method} {path} - {desc}")
    
    return "\n".join(parts)


def _build_existing_tests_section(existing_tests: List[Dict[str, Any]]) -> str:
    """Build the existing tests section."""
    parts = []
    
    parts.append("=" * 60)
    parts.append("EXISTING TESTS (Check for overlap)")
    parts.append("=" * 60)
    parts.append("If an existing test already covers a scenario, note it to skip")
    parts.append("")
    
    for test in existing_tests[:5]:  # Limit to 5 tests
        name = test.get('name', 'Unknown')
        content = test.get('content', '')[:300]
        parts.append(f"• {name}")
        if content:
            parts.append(f"  {content}")
        parts.append("")
    
    return "\n".join(parts)

