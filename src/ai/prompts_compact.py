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

COVERAGE PRINCIPLES:
- Every AC needs test coverage (sometimes 1 test, sometimes 5 - depends on complexity)
- ACs that interact need tests covering the interaction
- Include realistic negative cases (what users actually do wrong)
- Include edge cases that are LIKELY to occur in production
- Skip theoretical edge cases that would never happen
- The right number of tests = the number that covers real scenarios

CRITICAL - Read each AC literally:
- If an AC says "test X with Y" → you MUST have a test that specifically tests X with Y
- If an AC says "different X" → you MUST test with at least 2 different X values
- If an AC says "validate behavior for Z" → you MUST have a test specifically for Z
- Every single AC must map to at least one test - no exceptions

WRITING STYLE:
- Test titles describe WHAT HAPPENS, not what you're testing
  Good: "Audit log shows login event after user authenticates successfully"
  Good: "Root account login creates audit record with admin flag"
  Bad: "Verify audit log displays correctly"
  Bad: "Test login with different IDP"
  Bad: "Validate behavior for login with root account"
- Steps read like instructions to a human tester
- Use concrete values from the story/PRD (real tenant IDs, user names)
- Descriptions explain WHY this test matters

FORMATTING RULES:
- NEVER start titles with: "Verify", "Validate", "Test", "Check", "Ensure"
  Even if the AC says "Validate X" or "Test Y", rephrase the title!
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
  "reasoning": "Your analysis: (1) What is this feature doing? (2) List each AC and what test(s) will cover it. (3) Which ACs interact with each other?",
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

MANDATORY - Go through each AC one by one:
□ AC #1 - do I have a test for this? If not, add one.
□ AC #2 - do I have a test for this? If not, add one.
□ ... continue for ALL ACs listed above
□ If any AC mentions something specific, is that specific thing tested?

FORMAT CHECKS:
□ No test titles start with "Verify/Validate/Check/Ensure/Test"
□ Test data uses concrete values, not placeholders

If you're missing coverage for ANY AC, go back and add tests before submitting."""


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
        parts.append("⚠️ MANDATORY: You MUST create at least one test for EACH AC listed below.")
        parts.append("⚠️ Read each AC literally - if it mentions something specific, test that specific thing.")
        parts.append("⚠️ After generating, verify: Does every AC have a corresponding test? If not, add more tests.")
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

