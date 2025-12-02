"""
Compact QA test generator prompt - optimized for token efficiency.

Key optimizations:
- Reduced from 7 modules to 3 (Core Rules, Story Context, Output Format)
- Removed redundant rules (same rule appeared in multiple modules)
- Conditional examples (only included when RAG lacks similar tests)
- Target: ~4K words max (vs ~12K in original)

Structure:
- Section 1: CORE RULES (essential, non-negotiable requirements)
- Section 2: STORY CONTEXT (injected dynamically - story + ACs + APIs)
- Section 3: OUTPUT FORMAT (JSON schema + single example)

Logging: All prompt construction is logged for debugging.
"""

from typing import Optional, List, Dict, Any
from loguru import logger

# ============================================================================
# SECTION 1: CORE RULES (Compact - ~800 tokens)
# ============================================================================

COMPACT_SYSTEM_INSTRUCTION = """You are a senior QA engineer creating test plans. Think like a real tester, not a machine.

=== STEP 1: ANALYZE THE FEATURE (do this FIRST) ===

Before writing ANY tests, understand:
- What is this feature actually doing for users?
- What system components does it touch? (auth, database, UI, APIs)
- What could realistically go wrong in production?
- How do the acceptance criteria interact with each other?
- What would make a customer file a support ticket?

=== STEP 2: PLAN YOUR COVERAGE ===

Think through:
- What are the critical user journeys?
- Which ACs depend on or interact with other ACs?
- What negative cases would users actually encounter?
- What edge cases are LIKELY vs purely theoretical?
- What integration points exist with other system features?

=== STEP 3: GENERATE TESTS BASED ON YOUR ANALYSIS ===

THINK ABOUT WHAT COULD ACTUALLY BREAK:
- What if the API returns wrong data or wrong status code?
- What if the UI doesn't update after an action?
- What if filters don't work with certain combinations?
- What would make a customer file a support ticket?
- What edge cases are LIKELY to happen in production?

=== FORBIDDEN TEST PATTERNS (NEVER write these as standalone tests) ===

VISIBILITY/EXISTENCE TESTS - NOT REAL TESTS:
❌ "X is visible/displayed/present/shown" → If you interact with X and it works, X exists
❌ "X exists on page" → Test what X DOES, not that it exists
❌ "Page loads/opens correctly" → This is a precondition, not a test objective
❌ "Button/tab/link is clickable" → Test what happens AFTER you click it
❌ "Search bar is present" → Test the SEARCH FUNCTIONALITY instead

GENERIC UI TESTS - NOT HOW HUMANS WRITE TESTS:
❌ "Pagination functionality works" → Test viewing a LARGE DATASET (50+ items) - pagination is implicit
❌ "Sorting works" → Test viewing data SORTED BY [specific field] with expected order
❌ "Filtering works" → Test finding SPECIFIC items using [specific filter criteria]

TRANSFORM TRIVIAL TO FUNCTIONAL:
- "Search bar is present" → "Search filters policies by name and returns matching results"
- "Tab is visible" → "Clicking Policies tab displays list of policies with correct data"
- "Button exists" → "Clicking [Button] performs [action] and shows [result]"
- "Pagination works" → "Policies list displays correctly with 50+ policies across pages"
- "Empty state displayed" → "When no policies exist, user sees message and can navigate to create one"

TEST EFFICIENCY (CRITICAL):
- DON'T create separate tests for trivial things that are implicitly covered
  Bad: "Admin can access audit logs" (trivial - all tests require admin access)
  Bad: "Login requirements are met" (duplicate of successful login test)
  Bad: "Policies tab is displayed" (trivial - if you click it and it works, it exists)
- DO combine related scenarios into comprehensive tests
- A good test covers MULTIPLE assertions, not just one
- Ask yourself: "Would a real QA create a separate test for this, or just add an assertion?"

CHECK THE PRD/CONFLUENCE DOCUMENTATION FOR:
- UI requirements (fields that should be hidden, buttons that should be visible)
- Behavior requirements (input behavior, filter values, etc.)
- These are often missed if you only focus on ACs!
- If PRD says "Parent Name field hidden" → verify it's hidden in a test
- If PRD mentions "compare changes" → test the compare changes feature

AC COVERAGE:
- If an AC says "different X" → test with at least 2 different X values
- If an AC says "validate behavior for Z" → have a test for Z
- But DON'T create redundant tests - combine where it makes sense

WRITING STYLE:
- Test titles should sound like a human QA engineer wrote them, not a machine
- Write titles that describe the TEST OBJECTIVE naturally
  
  Good (natural, human-sounding):
  - "Validate policy list search works"
  - "Search filters policies by name correctly"
  - "Audit log captures login events from Keycloak"
  - "Root account login creates admin-flagged audit record"
  
  Bad (mechanical, AI-sounding):
  - "Verify that the audit log displays correctly" (too robotic)
  - "Test login with different IDP" (sounds like a task, not a test)
  - "Check search functionality filters policies" (mechanical prefix + gerund)
  - "Ensure pagination works correctly" (vague, what specifically?)

- Using "Validate" or "Verify" is FINE when it sounds natural
- The problem is MECHANICAL patterns like "Verify that X does Y correctly"
- Steps read like instructions to a human tester
- Use concrete values from the story/PRD (real tenant IDs, user names)
- Descriptions explain WHY this test matters

FORMATTING RULES:
- API tests: use exact endpoints from story (GET/POST/PUT/DELETE /path)
- test_data must be valid JSON with concrete values, no placeholders
- Only use endpoints/fields mentioned in story or API specs

=== USE THE PROVIDED CONTEXT ===

From PRD/Confluence: Understand the feature's purpose and requirements
From RAG context: Learn domain terminology, see similar tests, find realistic data
From API specs: Use exact endpoint paths and expected responses"""


# ============================================================================
# SECTION 2: COMPACT OUTPUT FORMAT (~400 tokens)
# ============================================================================

COMPACT_OUTPUT_FORMAT = """
OUTPUT FORMAT (JSON):

{
  "reasoning": "Your analysis: (1) What is this feature doing? (2) Which PATTERN RULES apply? (e.g., 'AC #7 says different IDP → need 2+ IDPs', 'AC #8 mentions root → need root test') (3) What tests will cover each AC?",
  "summary": {
    "story_key": "STORY-123",
    "story_title": "Feature title",
    "test_count": 15,
    "test_count_justification": "Explain why this number covers the real scenarios (not a formula)"
  },
  "test_cases": [
    {
      "title": "Natural description of what happens (NO 'Verify/Test/Check' prefix)",
      "description": "Why this test matters - what scenario or risk does it cover?",
      "preconditions": "Required setup using concrete values from story",
      "steps": [
        {
          "step_number": 1,
          "action": "Human-readable instruction (API: 'Call GET /endpoint', UI: 'Navigate to X and click Y')",
          "expected_result": "What should happen (include status codes for API)",
          "test_data": "{\"field\": \"concrete_value_from_story\"}"
        }
      ],
      "expected_result": "Overall expected outcome in plain language",
      "priority": "critical|high|medium|low",
      "test_type": "functional|integration|negative|edge_case|regression",
      "tags": ["RELEVANT", "TAGS"],
      "automation_candidate": true,
      "risk_level": "high|medium|low"
    }
  ],
  "suggested_folder": "Folder path",
  "validation_check": {
    "all_acs_covered": true,
    "realistic_scenarios": true,
    "no_forced_edge_cases": true,
    "natural_language": true
  }
}

=== SELF-REVIEW BEFORE SUBMITTING ===

FORBIDDEN PATTERN CHECK (DELETE any tests that match these):
□ Did I write any "X is visible/displayed/present" tests? → DELETE and test functionality instead
□ Did I write any "X exists on page" tests? → DELETE and test what X does
□ Did I write a standalone "Pagination works" test? → DELETE and test with large dataset instead
□ Did I write a standalone "Search bar is present" test? → DELETE and test search functionality

PATTERN CHECK (go through each AC):
□ For each AC that says "different/multiple/various X" → did I test 2+ X values?
□ For each AC that mentions a specific user type → did I test with that user?
□ For each AC that mentions a named feature → did I test that feature?
□ For each PRD requirement about hidden/visible elements → did I verify it?

QUALITY CHECK:
□ Are there redundant tests? → REMOVE them, add as assertions instead
□ Are there trivial standalone tests? → FOLD into other tests
□ Did I think about what could BREAK, not just "cover ACs"?
□ Would a real QA engineer create each test, or just add an assertion to another test?

FORMAT CHECK:
□ Do titles sound like a human QA wrote them, not a machine?
□ No mechanical patterns like "Verify that X does Y correctly"
□ No titles say "X is visible/displayed/present/exists"
□ No titles say "Pagination/paging functionality"
□ Test data uses concrete values, not placeholders"""


# ============================================================================
# SECTION 3: SINGLE COMPACT EXAMPLE (~300 tokens)
# ============================================================================

COMPACT_EXAMPLE = """
EXAMPLE - Notice how this test:
- Has a natural title describing what happens (not "Verify...")
- Explains WHY it matters in the description
- Uses concrete values from the domain
- Steps read like instructions to a human

{
  "title": "Tenant admin sees login audit record after user authenticates via Keycloak",
  "description": "Login events must be captured in tenant-level audit for compliance. This covers the core audit trail requirement.",
  "preconditions": "Tenant 'acme-corp' exists with admin user 'john.smith@acme.com' configured",
  "steps": [
    {
      "step_number": 1,
      "action": "Authenticate as john.smith@acme.com using Keycloak IDP with valid credentials",
      "expected_result": "Login succeeds, user receives access token",
      "test_data": "{\"tenant\": \"acme-corp\", \"user\": \"john.smith@acme.com\", \"idp\": \"keycloak\"}"
    },
    {
      "step_number": 2,
      "action": "Navigate to Tenant Administration > Audit Logs",
      "expected_result": "Audit log page loads showing recent events",
      "test_data": "{\"expectedPage\": \"tenant-admin/audit\"}"
    },
    {
      "step_number": 3,
      "action": "Filter audit log by event type 'LOGIN' and look for john.smith entry",
      "expected_result": "Login event appears with timestamp, user email, IDP source, and SUCCESS status",
      "test_data": "{\"filter\": \"LOGIN\", \"expectedUser\": \"john.smith@acme.com\", \"expectedStatus\": \"SUCCESS\"}"
    }
  ],
  "expected_result": "Tenant admins can see login activity in their audit trail for compliance purposes",
  "priority": "critical",
  "test_type": "functional",
  "tags": ["AUDIT", "LOGIN", "COMPLIANCE"],
  "automation_candidate": true,
  "risk_level": "high"
}"""


# ============================================================================
# PROMPT BUILDER FUNCTIONS
# ============================================================================

def build_compact_prompt(
    story_key: str,
    story_title: str,
    story_description: str,
    acceptance_criteria: List[str],
    api_specifications: Optional[List[Dict[str, Any]]] = None,
    subtasks: Optional[List[Dict[str, str]]] = None,
    confluence_docs: Optional[List[Dict[str, Any]]] = None,
    swagger_docs: Optional[List[Dict[str, Any]]] = None,  # NEW: Swagger docs from RAG
    existing_tests: Optional[List[Dict[str, Any]]] = None,  # NEW: Existing tests for duplicate detection
    rag_context: Optional[str] = None,
    include_example: bool = True,
    max_rag_tokens: int = 2000
) -> str:
    """
    Build a compact prompt for test generation.
    
    Target: ~4K words (16K tokens) max
    
    Args:
        story_key: Jira story key (e.g., "PLAT-11372")
        story_title: Story summary
        story_description: Full story description
        acceptance_criteria: List of ACs
        api_specifications: List of API specs (endpoints, methods, etc.)
        subtasks: List of engineering subtasks
        confluence_docs: List of extracted/focused Confluence doc references
        swagger_docs: List of Swagger/OpenAPI docs from RAG (NEW)
        existing_tests: List of existing tests for duplicate detection (NEW)
        rag_context: Pre-formatted RAG context (will be truncated if too long)
        include_example: Whether to include the example (skip if RAG has similar tests)
        max_rag_tokens: Maximum tokens for RAG context
        
    Returns:
        Complete prompt string
    """
    sections = []
    token_counts = {}
    
    # Section 1: Core rules
    sections.append(COMPACT_SYSTEM_INSTRUCTION)
    token_counts['rules'] = _estimate_tokens(COMPACT_SYSTEM_INSTRUCTION)
    logger.info(f"[PROMPT] Section 1 (rules): ~{token_counts['rules']} tokens")
    
    # Section 2: PRD/Confluence docs (CRITICAL - explains what the feature IS)
    if confluence_docs:
        confluence_section = "--- PRD / REQUIREMENTS DOCUMENTATION (READ THIS FIRST) ---\n"
        confluence_section += "This explains what the feature IS and what it DOES:\n"
        for doc in confluence_docs:
            doc_title = doc.get('title', 'Untitled Document')
            doc_url = doc.get('url', '')
            doc_content = doc.get('qa_summary') or doc.get('summary', '')
            
            if doc_url:
                confluence_section += f"\n📄 Document: {doc_title}\n🔗 URL: {doc_url}\n\n"
            else:
                confluence_section += f"\n📄 Document: {doc_title}\n\n"
            
            if doc_content:
                confluence_section += doc_content + "\n"
        
        sections.append(confluence_section)
        token_counts['confluence'] = _estimate_tokens(confluence_section)
        logger.info(f"[PROMPT] Section 2 (Confluence): ~{token_counts['confluence']} tokens")
    else:
        token_counts['confluence'] = 0
    
    # Section 3: Story context (PRIMARY - most important)
    story_section = _build_story_section(
        story_key=story_key,
        story_title=story_title,
        story_description=story_description,
        acceptance_criteria=acceptance_criteria,
        api_specifications=api_specifications,
        subtasks=subtasks
    )
    sections.append(story_section)
    token_counts['story'] = _estimate_tokens(story_section)
    logger.info(f"[PROMPT] Section 3 (story): ~{token_counts['story']} tokens")
    
    # Section 4: Swagger/API Documentation (NEW - from RAG)
    if swagger_docs:
        swagger_section = "\n--- SWAGGER/API DOCUMENTATION (Use exact endpoints) ---\n"
        swagger_section += "⚠️ Use EXACT endpoint paths and request/response formats from these docs:\n\n"
        for doc in swagger_docs[:3]:  # Limit to 3
            service = doc.get('service', 'Unknown')
            content = doc.get('content', '')
            similarity = doc.get('similarity', 0)
            swagger_section += f"📡 Service: {service} (relevance: {similarity:.2f})\n"
            swagger_section += f"{content[:1500]}\n\n"  # Truncate each doc
        
        sections.append(swagger_section)
        token_counts['swagger'] = _estimate_tokens(swagger_section)
        logger.info(f"[PROMPT] Section 4 (Swagger): ~{token_counts['swagger']} tokens")
    else:
        token_counts['swagger'] = 0
    
    # Section 5: Existing Tests (NEW - for duplicate detection)
    if existing_tests:
        tests_section = "\n--- EXISTING TESTS (Avoid duplicates!) ---\n"
        tests_section += "⚠️ These tests already exist. Do NOT create duplicates:\n\n"
        for test in existing_tests[:5]:  # Limit to 5
            test_name = test.get('name', 'Unknown')
            test_content = test.get('content', '')[:300]  # Truncate
            tests_section += f"• {test_name}\n  {test_content}\n\n"
        
        sections.append(tests_section)
        token_counts['existing_tests'] = _estimate_tokens(tests_section)
        logger.info(f"[PROMPT] Section 5 (Existing Tests): ~{token_counts['existing_tests']} tokens")
    else:
        token_counts['existing_tests'] = 0
    
    # Section 6: RAG context (if provided, truncated to budget)
    if rag_context:
        truncated_rag = _truncate_to_tokens(rag_context, max_rag_tokens)
        sections.append(f"\n--- REFERENCE CONTEXT (from company data) ---\n{truncated_rag}")
        token_counts['rag'] = _estimate_tokens(truncated_rag)
        logger.info(f"[PROMPT] Section 6 (RAG): ~{token_counts['rag']} tokens (truncated from {_estimate_tokens(rag_context)})")
    else:
        token_counts['rag'] = 0
        logger.info("[PROMPT] Section 6 (RAG): skipped (no context)")
    
    # Section 7: Example (conditional)
    if include_example:
        sections.append(f"\n--- EXAMPLE (structure only) ---\n{COMPACT_EXAMPLE}")
        token_counts['example'] = _estimate_tokens(COMPACT_EXAMPLE)
        logger.info(f"[PROMPT] Section 7 (example): ~{token_counts['example']} tokens")
    else:
        token_counts['example'] = 0
        logger.info("[PROMPT] Section 7 (example): skipped (RAG has similar tests)")
    
    # Section 8: Output format
    sections.append(f"\n--- OUTPUT REQUIREMENTS ---\n{COMPACT_OUTPUT_FORMAT}")
    token_counts['output'] = _estimate_tokens(COMPACT_OUTPUT_FORMAT)
    logger.info(f"[PROMPT] Section 8 (output): ~{token_counts['output']} tokens")
    
    # Combine and log totals
    prompt = "\n\n".join(sections)
    total_tokens = sum(token_counts.values())
    total_words = len(prompt.split())
    total_chars = len(prompt)
    
    logger.info(f"[PROMPT] TOTAL: ~{total_tokens} tokens, {total_words} words, {total_chars} chars")
    logger.info(f"[PROMPT] Section breakdown: rules={token_counts['rules']}, confluence={token_counts['confluence']}, "
                f"story={token_counts['story']}, swagger={token_counts['swagger']}, "
                f"existing_tests={token_counts['existing_tests']}, rag={token_counts['rag']}, "
                f"example={token_counts['example']}, output={token_counts['output']}")
    
    # Warn if over budget
    if total_tokens > 16000:
        logger.warning(f"[PROMPT] WARNING: Prompt exceeds 16K token budget ({total_tokens} tokens)")
    
    return prompt


def _build_story_section(
    story_key: str,
    story_title: str,
    story_description: str,
    acceptance_criteria: List[str],
    api_specifications: Optional[List[Dict[str, Any]]] = None,
    subtasks: Optional[List[Dict[str, str]]] = None
) -> str:
    """Build the story context section."""
    parts = []
    
    parts.append("=" * 60)
    parts.append("STORY REQUIREMENTS (PRIMARY INPUT - Test THIS)")
    parts.append("=" * 60)
    
    # Story header
    parts.append(f"\nStory: {story_key} - {story_title}")
    
    # Description (truncated if too long)
    if story_description:
        desc = story_description[:3000] if len(story_description) > 3000 else story_description
        parts.append(f"\nDescription:\n{desc}")
        if len(story_description) > 3000:
            parts.append(f"... [truncated, {len(story_description)} chars total]")
    
    # Acceptance Criteria (CRITICAL - must map to tests)
    if acceptance_criteria:
        parts.append(f"\n--- ACCEPTANCE CRITERIA ({len(acceptance_criteria)} items) ---")
        parts.append("")
        parts.append("⚠️ PATTERN RULES - Scan each AC and apply these rules:")
        parts.append("")
        parts.append("1. DIFFERENT/MULTIPLE PATTERN:")
        parts.append("   If AC contains 'different', 'multiple', or 'various' followed by a noun")
        parts.append("   → You MUST test with at least 2 different values of that noun")
        parts.append("   Example: 'different IDP' → test with Keycloak AND SAML/Okta")
        parts.append("")
        parts.append("2. SPECIFIC USER PATTERN:")
        parts.append("   If AC mentions a specific user type (root, admin, guest, etc.)")
        parts.append("   → You MUST have a test that uses that specific user type")
        parts.append("   Example: 'root account' → test login with root user")
        parts.append("")
        parts.append("3. NAMED FEATURE PATTERN:")
        parts.append("   If AC mentions a feature name (compare, filter, sort, export, etc.)")
        parts.append("   → You MUST test that specific feature")
        parts.append("   Example: 'compare changes' → test the compare changes functionality")
        parts.append("")
        parts.append("4. HIDDEN/VISIBLE PATTERN:")
        parts.append("   If PRD says something should be hidden or visible")
        parts.append("   → You MUST verify that UI state in a test")
        parts.append("")
        parts.append("EFFICIENCY RULES:")
        parts.append("- DON'T create separate tests for trivial permission checks")
        parts.append("- DO combine related scenarios into comprehensive tests")
        parts.append("")
        for i, ac in enumerate(acceptance_criteria, 1):
            parts.append(f"AC #{i}: {ac}")
    
    # API Specifications (if any)
    if api_specifications:
        parts.append(f"\n--- API SPECIFICATIONS ({len(api_specifications)} endpoints) ---")
        parts.append("⚠️ Use ONLY these endpoints - do NOT invent others!")
        for api in api_specifications:
            methods = " ".join(api.get('http_methods', ['UNKNOWN']))
            path = api.get('endpoint_path', 'unknown')
            parts.append(f"• {methods} {path}")
            if api.get('parameters'):
                parts.append(f"  Params: {', '.join(api['parameters'])}")
            if api.get('request_example'):
                parts.append(f"  Request: {api['request_example'][:200]}")
            if api.get('response_example'):
                parts.append(f"  Response: {api['response_example'][:200]}")
    
    # Subtasks (engineering tasks - contain implementation details)
    if subtasks:
        parts.append(f"\n--- ENGINEERING TASKS ({len(subtasks)} subtasks) ---")
        for task in subtasks[:10]:  # Limit to 10
            summary = task.get('summary', 'Unknown')
            parts.append(f"• {summary}")
            if task.get('description'):
                desc = task['description'][:200]
                parts.append(f"  {desc}")
    
    parts.append("\n" + "=" * 60)
    
    return "\n".join(parts)


def _estimate_tokens(text: str) -> int:
    """Estimate token count (rough: 1 token ≈ 4 chars for English)."""
    return len(text) // 4


def _truncate_to_tokens(text: str, max_tokens: int) -> str:
    """Truncate text to fit within token budget."""
    max_chars = max_tokens * 4
    if len(text) <= max_chars:
        return text
    
    truncated = text[:max_chars]
    # Try to end at a sentence boundary
    last_period = truncated.rfind('.')
    if last_period > max_chars * 0.8:
        truncated = truncated[:last_period + 1]
    
    return truncated + f"\n... [truncated to ~{max_tokens} tokens]"


# ============================================================================
# JSON SCHEMA FOR STRUCTURED OUTPUT
# ============================================================================

COMPACT_JSON_SCHEMA = {
    "name": "test_plan_compact",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "reasoning": {
                "type": "string",
                "description": "2-4 sentences explaining feature understanding and AC-to-test mapping"
            },
            "summary": {
                "type": "object",
                "properties": {
                    "story_key": {"type": "string"},
                    "story_title": {"type": "string"},
                    "test_count": {"type": "integer"},
                    "test_count_justification": {"type": "string"}
                },
                "required": ["story_key", "story_title", "test_count", "test_count_justification"],
                "additionalProperties": False
            },
            "test_cases": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "description": {"type": "string"},
                        "preconditions": {"type": "string"},
                        "steps": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "step_number": {"type": "integer"},
                                    "action": {"type": "string"},
                                    "expected_result": {"type": "string"},
                                    "test_data": {"type": "string"}
                                },
                                "required": ["step_number", "action", "expected_result", "test_data"],
                                "additionalProperties": False
                            },
                            "minItems": 2
                        },
                        "expected_result": {"type": "string"},
                        "priority": {"type": "string", "enum": ["critical", "high", "medium", "low"]},
                        "test_type": {"type": "string", "enum": ["functional", "integration", "negative", "edge_case", "regression"]},
                        "tags": {"type": "array", "items": {"type": "string"}},
                        "automation_candidate": {"type": "boolean"},
                        "risk_level": {"type": "string", "enum": ["high", "medium", "low"]}
                    },
                    "required": ["title", "description", "preconditions", "steps", "expected_result", 
                                "priority", "test_type", "tags", "automation_candidate", "risk_level"],
                    "additionalProperties": False
                }
            },
            "suggested_folder": {"type": "string"},
            "validation_check": {
                "type": "object",
                "properties": {
                    "all_acs_covered": {"type": "boolean"},
                    "realistic_scenarios": {"type": "boolean"},
                    "no_forced_edge_cases": {"type": "boolean"},
                    "natural_language": {"type": "boolean"}
                },
                "required": ["all_acs_covered", "realistic_scenarios", "no_forced_edge_cases", "natural_language"],
                "additionalProperties": False
            }
        },
        "required": ["reasoning", "summary", "test_cases", "suggested_folder", "validation_check"],
        "additionalProperties": False
    }
}


# ============================================================================
# STAGE 2: GENERATION PROMPT (Takes CoveragePlan from Stage 1)
# ============================================================================

STAGE2_SYSTEM_INSTRUCTION = """You are a senior QA engineer creating test cases from a coverage plan.

A previous analysis has already identified:
- Pattern matches (DIFFERENT_X, SPECIFIC_USER, NAMED_FEATURE, HIDDEN_VISIBLE)
- PRD requirements to test
- API endpoints to cover
- Existing tests to avoid duplicating
- A planned test structure

YOUR JOB: Convert each planned test into a complete, detailed test case.

=== FORBIDDEN TEST PATTERNS (NEVER write these) ===

VISIBILITY/EXISTENCE TESTS - DELETE IMMEDIATELY IF YOU SEE THESE:
❌ "X is visible/displayed/present/shown" → Test what X DOES, not that it exists
❌ "Empty state message is displayed" → Test what user can DO from empty state
❌ "Tab is displayed" → Test what happens when you CLICK the tab

BANNED WORDS IN TEST TITLES (will be rejected):
❌ "pagination" or "paging" → NEVER use these words in titles
❌ "empty state" → NEVER use this phrase in titles
❌ "is displayed" or "is visible" → NEVER use these phrases

WHAT TO WRITE INSTEAD:
- Instead of "Verify paging" → "Policy list handles 50+ items correctly"
- Instead of "Empty state is displayed" → "User can create policy when none exist"
- Instead of "Pagination functionality" → "Large policy list loads correctly"

=== MANDATORY REQUIREMENTS ===

1. EVERY planned test in the coverage plan MUST become a real test case
2. EVERY pattern match MUST be covered by at least one test
3. EVERY PRD requirement MUST be verified in a test
4. DO NOT create tests that overlap with existing tests listed

=== WRITING STYLE ===

- Test titles should sound like a human QA engineer wrote them
  
  Good (natural):
  - "Validate policy list search works"
  - "Audit log captures login events from Keycloak"
  - "Root account login creates admin-flagged audit record"
  
  Bad (mechanical/AI-sounding):
  - "Verify that audit log displays correctly" (robotic)
  - "Test login with different IDP" (sounds like a task)
  - "Empty state message is displayed" → FORBIDDEN
  - "Pagination displays correctly" → FORBIDDEN
  
- Using "Validate" or "Verify" is FINE when natural (e.g., "Validate search works")
- NEVER use "is visible/displayed/present" in titles
- NEVER use "Pagination/Paging functionality" as a test title
- Steps read like instructions to a human tester
- Use concrete values from the story/PRD
- Descriptions explain WHY this test matters

=== EFFICIENCY ===

- DON'T create separate tests for trivial things (e.g., "admin can access X")
- DO combine related scenarios into comprehensive tests
- A good test covers MULTIPLE assertions"""


def build_stage2_prompt(
    story_key: str,
    story_title: str,
    story_description: str,
    acceptance_criteria: List[str],
    coverage_plan: Dict[str, Any],
    confluence_docs: Optional[List[Dict[str, Any]]] = None,
    swagger_docs: Optional[List[Dict[str, Any]]] = None,
    api_specifications: Optional[List[Dict[str, Any]]] = None
) -> str:
    """
    Build Stage 2 generation prompt using the CoveragePlan from Stage 1.
    
    This prompt is focused on GENERATING tests from the analysis,
    not analyzing the story again.
    
    Args:
        story_key: Jira story key
        story_title: Story summary
        story_description: Full story description
        acceptance_criteria: List of ACs
        coverage_plan: CoveragePlan dict from Stage 1 analysis
        confluence_docs: PRD/Confluence documents
        swagger_docs: Swagger/API documentation
        api_specifications: API specs from story enrichment
        
    Returns:
        Complete Stage 2 generation prompt
    """
    sections = []
    
    # Section 1: System instruction
    sections.append(STAGE2_SYSTEM_INSTRUCTION)
    logger.info("[STAGE2 PROMPT] Added system instruction")
    
    # Section 2: Coverage Plan from Stage 1
    coverage_section = _build_coverage_plan_section(coverage_plan)
    sections.append(coverage_section)
    logger.info("[STAGE2 PROMPT] Added coverage plan section")
    
    # Section 3: Story context (abbreviated)
    story_section = f"""
============================================================
STORY CONTEXT
============================================================

Story: {story_key} - {story_title}

Description (abbreviated):
{story_description[:2000] if len(story_description) > 2000 else story_description}

--- ACCEPTANCE CRITERIA ---
"""
    for i, ac in enumerate(acceptance_criteria, 1):
        story_section += f"AC #{i}: {ac}\n"
    
    sections.append(story_section)
    logger.info(f"[STAGE2 PROMPT] Added story section with {len(acceptance_criteria)} ACs")
    
    # Section 4: API specs for exact endpoints
    if swagger_docs or api_specifications:
        api_section = "\n--- API ENDPOINTS (Use EXACT paths) ---\n"
        if swagger_docs:
            for doc in swagger_docs[:3]:
                service = doc.get('service', 'Unknown')
                content = doc.get('content', '')[:1000]
                api_section += f"📡 {service}:\n{content}\n\n"
        if api_specifications:
            for spec in api_specifications[:10]:
                method = spec.get('method', 'GET')
                path = spec.get('path', '')
                api_section += f"  {method} {path}\n"
        sections.append(api_section)
        logger.info("[STAGE2 PROMPT] Added API section")
    
    # Section 5: PRD for concrete values
    if confluence_docs:
        prd_section = "\n--- PRD/CONFLUENCE (For concrete values) ---\n"
        for doc in confluence_docs[:2]:
            title = doc.get('title', 'Untitled')
            content = doc.get('qa_summary') or doc.get('summary', '')
            prd_section += f"📄 {title}:\n{content[:1500]}\n\n"
        sections.append(prd_section)
        logger.info("[STAGE2 PROMPT] Added PRD section")
    
    # Section 6: Output format
    sections.append(f"\n--- OUTPUT FORMAT ---\n{COMPACT_OUTPUT_FORMAT}")
    logger.info("[STAGE2 PROMPT] Added output format")
    
    # Section 7: Example
    sections.append(f"\n--- EXAMPLE ---\n{COMPACT_EXAMPLE}")
    logger.info("[STAGE2 PROMPT] Added example")
    
    prompt = "\n\n".join(sections)
    logger.info(f"[STAGE2 PROMPT] Total length: {len(prompt)} chars, {len(prompt.split())} words")
    
    return prompt


def _build_coverage_plan_section(coverage_plan: Dict[str, Any]) -> str:
    """Build the coverage plan section from Stage 1 analysis."""
    parts = []
    
    parts.append("=" * 60)
    parts.append("COVERAGE PLAN (From Stage 1 Analysis)")
    parts.append("=" * 60)
    parts.append("")
    parts.append("⚠️ YOU MUST CREATE A TEST FOR EACH PLANNED TEST BELOW")
    parts.append("⚠️ YOU MUST COVER ALL PATTERN MATCHES AND PRD REQUIREMENTS")
    parts.append("")
    
    # Analysis reasoning
    if coverage_plan.get('analysis_reasoning'):
        parts.append("--- ANALYSIS SUMMARY ---")
        parts.append(coverage_plan['analysis_reasoning'])
        parts.append("")
    
    # Pattern matches
    pattern_matches = coverage_plan.get('pattern_matches', [])
    if pattern_matches:
        parts.append(f"--- PATTERN MATCHES ({len(pattern_matches)} patterns) ---")
        parts.append("Each pattern below MUST be covered by at least one test:")
        parts.append("")
        for pm in pattern_matches:
            ac_num = pm.get('ac_number', '?')
            pattern_type = pm.get('pattern_type', 'UNKNOWN')
            matched_text = pm.get('matched_text', '')
            requirement = pm.get('requirement', '')
            parts.append(f"  ⚡ [{pattern_type}] AC #{ac_num}: \"{matched_text}\"")
            parts.append(f"     → Requirement: {requirement}")
        parts.append("")
    
    # PRD requirements
    prd_requirements = coverage_plan.get('prd_requirements', [])
    if prd_requirements:
        parts.append(f"--- PRD REQUIREMENTS ({len(prd_requirements)} items) ---")
        parts.append("Each PRD requirement MUST be verified in a test:")
        parts.append("")
        for prd in prd_requirements:
            source = prd.get('source', 'PRD')
            requirement = prd.get('requirement', '')
            test_needed = prd.get('test_needed', '')
            parts.append(f"  📋 [{source}] {requirement}")
            parts.append(f"     → Test needed: {test_needed}")
        parts.append("")
    
    # API coverage
    api_coverage = coverage_plan.get('api_coverage', [])
    if api_coverage:
        parts.append(f"--- API COVERAGE ({len(api_coverage)} endpoints) ---")
        for api in api_coverage:
            endpoint = api.get('endpoint', '')
            must_test = "MUST TEST" if api.get('must_test', True) else "optional"
            parts.append(f"  📡 {endpoint} ({must_test})")
        parts.append("")
    
    # Existing test overlap
    existing_overlap = coverage_plan.get('existing_test_overlap', [])
    if existing_overlap:
        parts.append(f"--- EXISTING TESTS TO SKIP ({len(existing_overlap)} items) ---")
        parts.append("DO NOT create tests that duplicate these:")
        parts.append("")
        for overlap in existing_overlap:
            name = overlap.get('existing_test_name', '')
            reason = overlap.get('skip_reason', '')
            parts.append(f"  ❌ {name}")
            parts.append(f"     → {reason}")
        parts.append("")
    
    # Planned tests
    test_plan = coverage_plan.get('test_plan', [])
    if test_plan:
        parts.append(f"--- PLANNED TESTS ({len(test_plan)} tests) ---")
        parts.append("Create a detailed test case for EACH of these:")
        parts.append("")
        for i, test in enumerate(test_plan, 1):
            idea = test.get('test_idea', '')
            covers_acs = test.get('covers_acs', [])
            covers_patterns = test.get('covers_patterns', [])
            covers_prd = test.get('covers_prd', False)
            priority = test.get('priority', 'high')
            api_endpoints = test.get('api_endpoints', [])
            
            parts.append(f"  {i}. {idea}")
            parts.append(f"     ACs: {covers_acs}, Patterns: {covers_patterns}, PRD: {covers_prd}")
            parts.append(f"     Priority: {priority}, APIs: {api_endpoints}")
        parts.append("")
    
    parts.append("=" * 60)
    
    return "\n".join(parts)

