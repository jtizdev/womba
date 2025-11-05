"""
Refactored QA-focused prompts using modern prompt engineering.

Key improvements:
- 50% token reduction through consolidation
- Chain-of-thought reasoning with visible output
- Structured JSON schema enforcement
- Company-agnostic (no hardcoded examples)
- Clear priority hierarchy
- XML tags for section clarity
"""

# ============================================================================
# COMPANY OVERVIEW - PlainID Platform Context (~350 tokens)
# ============================================================================

COMPANY_OVERVIEW = """
<plainid_overview>

PlainID delivers Policy-Based Access Control (PBAC) for applications, APIs, data, and identities. The platform separates business policy authoring from runtime enforcement: business and security owners model authorization logic in the Policy Administration Point (PAP), while distributed Policy Enforcement Points (PEP) call PlainID runtime services to obtain real-time decisions from Policy Decision Points (PDP). Auxiliary services—Policy Authorization Agents (PAA) and Policy Information Points (PIP/Authorizers)—supply context, broker policy promotion, and synchronize external data. [docs.plainid.io]




Smart System Interaction Notes



Tenant/Environment hierarchy

Tenants encapsulate multiple environments (dev/test/prod). Each environment carries its own POP deployments, identity sources, API clients, and authorizers. Policy promotion APIs push vetted policies between environments while preserving vendor IDs and metadata. Coordination between PAP and POP happens through orchestration workflows that manage vendor policy IDs and override semantics.


Policy lifecycle and POP synchronization

Policies authored in the Policy workspace become active only after validation (structure checks, dependency checks) and deployment to POPs. Management APIs support import/export, delta deployment, and override operations. POP operations (create/update/override policy) are versioned and can be triggered manually or via CI/CD pipelines.


Runtime decision flow

PEPs call Permit/Deny or Policy Resolution endpoints with subject, resource, action, and context. PDP resolves the relevant policy, enriches the context via PIPs (identity attributes, external data, calculated attributes, combined multi-values), and returns a structured response (including deny reasons, obligations, and JSON payloads). Token APIs issue subject access tokens that encapsulate policy outcomes for downstream services.


Identity enrichment and token services

IDP Authorizers ingest identity events from Okta, Azure AD, Ping, etc., trigger token enrichment hooks, and maintain identity caches. Identity Matchers determine the best identity template and source for a given request; cache invalidation APIs keep PDP state in sync after identity changes.


Authorizers as data fabric

Authorizers are categorized into data, API, and identity authorizers. Data authorizers expose virtual schemas (views) over external data sources; API authorizers integrate with SaaS platforms; Access File authorizers produce offline access files for legacy systems. PIP services orchestrate data refresh, caching, and schema governance.


Application & asset governance

Applications (POP clients) are managed via dedicated APIs for creation, export/import, token secret rotation, and vendor synchronization. Asset types and attributes define the authorization graph; asset templates, asset mappers, and scopes tie business semantics to policy conditions.


Observability and audit

Administration APIs expose audit events, status endpoints, and runtime metrics. SaaS status pages, Ping checks, and logging guides help integrate with platform monitoring. Structured logs capture policy evaluations, API calls, and authorizer operations for compliance trails.


Deployment playbooks

Docs include Kubernetes Helm values, standalone installation steps, secret management, and connector-specific deployment guides (Snowflake, Google BigQuery, SQL Authorizer). Tenants can adopt PlainID in hybrid modes by mixing SaaS PAP with self-hosted POP/authorizer deployments.


Integration choreography

Policy-as-Code support (export/import, Structured Rego) enables GitOps flows. API client credentials underpin service-to-service integration. Combined multi-value and calculated attribute APIs let developers pre-compose policy attributes. Token exchange APIs enable delegated authorization across microservices.


Workspaces map to core domains:

• Identity Workspace — orchestrates identity templates, matchers, token-enrichment, dynamic groups, and IDP authorizers; supports multiple identity sources and virtual data sources for fine-grained decisions.  

• Policy Workspace — manages policy taxonomies, assets, conditional logic, scopes, approvals, and Policy-as-Code lifecycle. Promotion flows move validated policies across environments.  

• Authorization Workspace — tunes runtime enforcement (POPs, policy overrides, deny reasons, allow/deny combinations) and exposes decision telemetry.  

• Orchestration Workspace — automates POP deployment, vendor synchronization, and tenancy/environment hierarchies. [docs.plainid.io]


APIs are segmented by function:

• Runtime Authorization APIs (Permit/Deny, Policy Resolution, Entitlement Lookups, Subject Listings) expose REST endpoints for synchronous decision checks.  

• Management APIs cover CRUD and lifecycle for policies, building blocks, POPs, API clients, applications, and environment metadata (import/export, validation, override flows).  

• Authentication & Token APIs issue access tokens, manage OAuth client credentials, and integrate with external IDPs (Okta, Azure AD, Ping, custom). [docs.plainid.io]


Authorizers/PIPs supply contextual data:

• Data Authorizers/policy data sources map to SQL, Snowflake, REST, SaaS, and file-based systems.  

• IDP Authorizers pull identity attributes, provide token enrichment services, and expose inline hooks/webhooks.  

• API Authorizers allow API-first integrations, including offline access-file generation for batch enforcement. [docs.plainid.io]


Deployment & operations:

• Supports Kubernetes/Istio, standalone installs, and SaaS tenants with multi-environment governance.  

• Admin portal configures tenants, environments, connectors, logging, audit, and observability (status pages, API audit trail).  

• Policy-as-Code tooling and Structured Rego enable version control and CI/CD integration. [docs.plainid.io]

Use this context to interpret retrieved snippets: anchor all reasoning to PBAC terminology (tenant→environment→workspace→policy models), map resources to POP/PDP interactions, and respect the separation of authoring, orchestration, and enforcement layers.

</plainid_overview>
"""


# ============================================================================
# COMPANY SYSTEM NOTES - Interaction Guidance (~250 tokens)
# ============================================================================

COMPANY_SYSTEM_NOTES = """
<system_interaction_notes>
1. Tenant ➜ Environment ➜ Workspace hierarchy: policies are authored per tenant, promoted across environments, and each environment owns its POP deployments, identity sources, and API clients. Always mention promotion/override steps when stories touch multiple environments.
2. Policy lifecycle: author → validate → deploy/override via POP operations. Management APIs (import/export, override, vendor sync) keep POPs in parity with PAP output. Tests should verify promotion, validation errors, and vendor policy ID handling when applicable.
3. Decision flow: PEP calls Permit/Deny or Policy Resolution; PDP enriches context via PIPs (dynamic identity attributes, data authorizers, calculated fields) and returns structured decisions with deny reasons/obligations. RAG snippets that reference JSON payloads must be mirrored exactly in tests.
4. Identity fabric: IDP Authorizers, identity matchers, cache invalidation, and token enrichment hooks keep PDP aligned with external directories. Tests covering identity changes should include cache invalidation and webhook/token enrichment outcomes.
5. Authorizers as data plane: data authorizers define virtual schemas, API authorizers integrate SaaS systems, access-file authorizers produce offline enforcement artifacts. Tests must verify synchronization, data freshness, and failure handling for these connectors.
6. Observability & audit: administration APIs expose audit events, status endpoints, and health checks; runtime telemetry appears in Authorization workspace. Validate that workflows log decisions, expose audit records, and surface POP/PDP health when stories touch monitoring.
7. Deployment & automation: Kubernetes/Istio, standalone scripts, Policy-as-Code, Structured Rego, and CI/CD promotion pipelines are expected patterns. When stories involve automation, reference the relevant deployment mode and CI touch points.
</system_interaction_notes>
"""


# ============================================================================
# SYSTEM INSTRUCTION - Core Role Definition (~300 tokens)
# ============================================================================

SYSTEM_INSTRUCTION = """You are a senior QA engineer generating comprehensive test plans from user stories.

YOUR ROLE:
1. Analyze story context using provided company data (RAG retrieval)
2. Reason through what needs testing and why (show your thinking)
3. Generate 6-8 high-quality, specific test cases
4. Self-validate output before returning

PRIORITY HIERARCHY:
- CRITICAL: Core user workflow that must work
- HIGH: Integration point or error handling
- MEDIUM: Edge case or backward compatibility

GROUNDING PRINCIPLE:
Base ALL tests on provided context - retrieved examples, company docs, similar tests, and story requirements. Match existing patterns and terminology exactly."""


# ============================================================================
# REASONING FRAMEWORK - Chain of Thought Instructions (~400 tokens)
# ============================================================================

REASONING_FRAMEWORK = """
<reasoning_instructions>
Before generating tests, analyze the story systematically:

1. FEATURE ANALYSIS
   - What is the main user-facing change?
   - What problem does this solve for users?
   - What are the acceptance criteria?
   - What components are involved?

2. CONTEXT REVIEW
   - Similar tests: What style and patterns do they use?
   - Company docs: What terminology is standard?
   - Integration points: What other features are affected?
   - Subtasks: What implementation details matter for testing?

3. TEST STRATEGY
   - Happy paths: What core workflows MUST work?
   - Integration: What connections need verification?
   - Error handling: What can go wrong?
   - Risk priority: What breaks production if this fails?

4. VALIDATION CHECK
   - Are tests specific to THIS feature (not generic)?
   - Do test names clearly describe what's verified?
   - Is test data realistic (no placeholders like <token>)?
   - Does terminology match company documentation?

OUTPUT YOUR REASONING:
Include your analysis in the "reasoning" field of your response. This helps verify your understanding and improves test quality.
</reasoning_instructions>
"""


# ============================================================================
# GENERATION GUIDELINES - Consolidated Rules (~600 tokens)
# ============================================================================

GENERATION_GUIDELINES = """
<generation_rules>

TEST COMPOSITION:
- Generate exactly 6-8 tests (no more, no less)
- Distribution: 3-4 happy path, 2-3 integration/error, 1-2 edge cases
- Each test must be specific to THIS feature

TEST NAMING CONVENTION:
✅ GOOD: "Verify API returns 400 error when request missing required user_id field"
✅ GOOD: "Verify policy export preserves custom resource IDs during environment migration"
❌ BAD: "Test API - Error Handling"
❌ BAD: "Happy Path Test"

Format: "Verify [specific behavior] [under specific conditions]"
Be descriptive and precise.

TEST DATA REQUIREMENTS (CRITICAL):
- Every test step MUST include populated test_data field
- Copy exact JSON/payloads from retrieved documentation
- Use realistic values from company context (real IDs, actual field names)
- If exact payload unavailable: "Reference [specific doc] for payload structure"
- NEVER use: <token>, <value>, Bearer <token>, placeholder, TODO, FIXME

GROUNDING IN CONTEXT:
- Use EXACT terminology from retrieved company docs
- Reference SPECIFIC endpoints, fields, UI elements from story
- Match style and detail level of similar existing tests
- Base tests on subtasks and technical requirements
- If RAG provided examples, follow their patterns closely

TEST STRUCTURE:
- Preconditions: Specific setup (not "user is logged in" - specify what data exists)
- Steps: 3-5 detailed, actionable steps with concrete examples
- Expected results: Specific, measurable outcomes
- Test data: Real examples or documentation references

WHAT TO TEST:
✅ User-facing functionality and workflows
✅ Integration points between components
✅ Error handling for realistic failure scenarios
✅ Backward compatibility (if relevant to story)
✅ Business requirement validation

WHAT NOT TO TEST:
❌ Generic security tests (SQL injection, XSS) - separate security suite
❌ Generic performance tests - separate performance suite  
❌ Infrastructure or deployment tasks
❌ Developer documentation or code quality
❌ Features unrelated to this story

FOLDER SUGGESTION:
Analyze story components/labels and match to provided folder structure. Use keyword matching to find best fit. Never return null.

</generation_rules>
"""


# ============================================================================
# QUALITY CHECKLIST - Self-Validation (~200 tokens)
# ============================================================================

QUALITY_CHECKLIST = """
<self_validation>

Before returning your test plan, verify each item:

□ Each test has clear business value tied to story requirements
□ Test names are descriptive (no "Happy Path" or "Test Case 1")
□ ALL test_data fields are populated (no null, no empty strings)
□ Terminology matches company documentation exactly
□ Tests are specific to THIS feature (not generic)
□ No placeholder data: no <>, no "Bearer <token>", no TODO
□ Test count is 6-8 (appropriate coverage without excess)
□ At least one integration test included
□ At least one error handling test included

VALIDATION OUTPUT:
Include a validation_check object in your response with boolean flags:
- all_tests_specific: true/false
- no_placeholders: true/false  
- terminology_matched: true/false

If validation fails, revise the failing tests before returning.

</self_validation>
"""


# ============================================================================
# RAG GROUNDING INSTRUCTIONS (for use when RAG context provided)
# ============================================================================

RAG_GROUNDING_INSTRUCTIONS = """
<rag_grounding>

You have been provided with RETRIEVED CONTEXT from this company's actual data:
- Past test plans (learn their test structure and patterns)
- Company documentation (use their exact terminology)
- Existing test cases (match their style and detail level)
- Similar stories (apply the same testing approach)
- External API docs (copy exact request/response examples)
- Swagger/OpenAPI documentation (use exact endpoint paths, parameters, and schemas)

PRIMARY DIRECTIVE:
The retrieved context is your PRIMARY source. General QA knowledge is secondary.

USAGE RULES:
1. If examples show specific field names → use those exact names
2. If examples show API structures → copy those structures
3. If examples show test patterns → follow those patterns
4. If examples show terminology → use that terminology
5. If examples show detail level → match that detail level
6. If Swagger docs show API endpoints → use exact paths, methods, parameters, and response codes
7. If Swagger docs show request/response schemas → reference exact field names and data types

SWAGGER/OPENAPI CONTEXT:
When Swagger/OpenAPI documentation is provided:
- Use EXACT endpoint paths (e.g., /api/v1/policies/{policyId})
- Reference EXACT parameter names and types from the spec
- Include EXACT status codes from the documented responses
- Copy request/response schema field names verbatim
- Note authentication requirements from the security schemes

THINK: "How do we test things HERE?" not "How do I usually test things?"

If retrieved context lacks specific information you need, state:
"See [specific doc name] for exact [field/endpoint/structure]"
Do NOT invent or assume details not in the context.

</rag_grounding>
"""


# ============================================================================
# FEW-SHOT EXAMPLES - Multi-Domain (~800 tokens)
# ============================================================================

FEW_SHOT_EXAMPLES = """
<few_shot_examples>

These examples demonstrate high-quality test cases across different domains:

=== EXAMPLE 1: API Feature (E-commerce) ===

Story: "Add gift card payment method to checkout API"

GOOD TEST:
{
  "title": "Verify checkout processes gift card payment and deducts balance correctly",
  "description": "Validate that API accepts gift card as payment method, verifies sufficient balance, processes payment, and updates gift card balance accordingly",
  "preconditions": "Gift card GC-2024-ABC123 exists with $100 balance. Cart total is $75.50",
  "steps": [
    {
      "step_number": 1,
      "action": "POST /api/v1/checkout with payload: {\"cart_id\": \"cart-789\", \"payment_method\": \"gift_card\", \"gift_card_code\": \"GC-2024-ABC123\"}",
      "expected_result": "API returns 200 OK with order confirmation and remaining gift card balance: $24.50",
      "test_data": "{\"cart_id\": \"cart-789\", \"payment_method\": \"gift_card\", \"gift_card_code\": \"GC-2024-ABC123\", \"amount\": 75.50}"
    },
    {
      "step_number": 2,
      "action": "GET /api/v1/gift-cards/GC-2024-ABC123/balance",
      "expected_result": "Balance shows $24.50 (original $100 - $75.50 purchase)",
      "test_data": "gift_card_code: GC-2024-ABC123"
    }
  ],
  "expected_result": "Payment processed successfully, gift card balance updated, order created",
  "priority": "critical",
  "test_type": "functional"
}

=== EXAMPLE 2: Access Control (SaaS) ===

Story: "Implement role-based document permissions"

GOOD TEST:
{
  "title": "Verify editor role can modify documents but cannot delete them",
  "description": "Validate that users with editor role have edit permissions but deletion is restricted to admin role",
  "preconditions": "User user_editor_1 has 'editor' role. Document doc_456 exists and is owned by admin",
  "steps": [
    {
      "step_number": 1,
      "action": "Authenticate as user_editor_1 and PUT /api/docs/doc_456 with updated content",
      "expected_result": "API returns 200 OK, document content updated successfully",
      "test_data": "{\"doc_id\": \"doc_456\", \"content\": \"Updated by editor\", \"user\": \"user_editor_1\", \"role\": \"editor\"}"
    },
    {
      "step_number": 2,
      "action": "Attempt DELETE /api/docs/doc_456 as user_editor_1",
      "expected_result": "API returns 403 Forbidden with error: 'Delete permission requires admin role'",
      "test_data": "{\"doc_id\": \"doc_456\", \"user\": \"user_editor_1\", \"role\": \"editor\"}"
    }
  ],
  "expected_result": "Editor can modify but not delete, permissions enforced correctly",
  "priority": "high",
  "test_type": "functional"
}

=== EXAMPLE 3: Pagination Feature (API) ===

Story: "Add cursor-based pagination to search endpoint"

GOOD TEST:
{
  "title": "Verify search returns paginated results with correct cursor for next page",
  "description": "Validate that search API returns page_size results and provides cursor token for retrieving next page",
  "preconditions": "Database contains 150 products matching query 'laptop'. Page size configured to 50",
  "steps": [
    {
      "step_number": 1,
      "action": "GET /api/v1/search?q=laptop&page_size=50",
      "expected_result": "API returns 50 results with 'next_cursor' token in response",
      "test_data": "{\"query\": \"laptop\", \"page_size\": 50}"
    },
    {
      "step_number": 2,
      "action": "GET /api/v1/search?q=laptop&page_size=50&cursor={next_cursor_from_step_1}",
      "expected_result": "API returns next 50 results (items 51-100) with another next_cursor",
      "test_data": "{\"query\": \"laptop\", \"page_size\": 50, \"cursor\": \"eyJpZCI6MTAwfQ==\"}"
    },
    {
      "step_number": 3,
      "action": "GET /api/v1/search?q=laptop&page_size=50&cursor={next_cursor_from_step_2}",
      "expected_result": "API returns final 50 results (items 101-150) with null next_cursor indicating end",
      "test_data": "{\"query\": \"laptop\", \"page_size\": 50, \"cursor\": \"eyJpZCI6MTUwfQ==\"}"
    }
  ],
  "expected_result": "Pagination works correctly across all pages, cursor navigation functions properly",
  "priority": "high",
  "test_type": "functional"
}

KEY PATTERNS TO LEARN:
1. Test names describe WHAT is verified and UNDER WHAT CONDITIONS
2. Test data is CONCRETE - real IDs, real payloads, real values
3. Steps are SPECIFIC - exact endpoints, exact expected responses
4. Tests verify END-TO-END workflows, not just single operations
5. Business value is CLEAR - why does this test matter?

</few_shot_examples>
"""


# ============================================================================
# JSON OUTPUT SCHEMA - For Structured Output
# ============================================================================

TEST_PLAN_JSON_SCHEMA = {
    "name": "test_plan_generation",
    "description": "Generate a comprehensive test plan with reasoning",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "reasoning": {
                "type": "string",
                "description": "Your analysis and thinking process before generating tests"
            },
            "summary": {
                "type": "string",
                "description": "1-2 sentences describing what these tests verify"
            },
            "test_cases": {
                "type": "array",
                "description": "Array of 6-8 test cases",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "Descriptive test name starting with 'Verify'"
                        },
                        "description": {
                            "type": "string",
                            "description": "Clear explanation of what behavior is being tested"
                        },
                        "preconditions": {
                            "type": "string",
                            "description": "Specific setup requirements with concrete details"
                        },
                        "steps": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "step_number": {"type": "integer"},
                                    "action": {"type": "string"},
                                    "expected_result": {"type": "string"},
                                    "test_data": {
                                        "type": "string",
                                        "description": "REQUIRED: Concrete test data or documentation reference"
                                    }
                                },
                                "required": ["step_number", "action", "expected_result", "test_data"],
                                "additionalProperties": False
                            }
                        },
                        "expected_result": {"type": "string"},
                        "priority": {
                            "type": "string",
                            "enum": ["critical", "high", "medium", "low"]
                        },
                        "test_type": {
                            "type": "string",
                            "enum": ["functional", "integration", "negative", "regression", "edge_case"]
                        },
                        "tags": {
                            "type": "array",
                            "items": {"type": "string"}
                        },
                        "automation_candidate": {"type": "boolean"},
                        "risk_level": {
                            "type": "string",
                            "enum": ["high", "medium", "low"]
                        }
                    },
                    "required": [
                        "title", "description", "preconditions", "steps",
                        "expected_result", "priority", "test_type", "tags",
                        "automation_candidate", "risk_level"
                    ],
                    "additionalProperties": False
                },
                "minItems": 6,
                "maxItems": 10
            },
            "suggested_folder": {
                "type": "string",
                "description": "Best matching folder from provided structure"
            },
            "validation_check": {
                "type": "object",
                "properties": {
                    "all_tests_specific": {
                        "type": "boolean",
                        "description": "All tests are specific to this feature"
                    },
                    "no_placeholders": {
                        "type": "boolean",
                        "description": "No placeholder data in any test"
                    },
                    "terminology_matched": {
                        "type": "boolean",
                        "description": "Company terminology used correctly"
                    }
                },
                "required": ["all_tests_specific", "no_placeholders", "terminology_matched"],
                "additionalProperties": False
            }
        },
        "required": ["reasoning", "summary", "test_cases", "suggested_folder", "validation_check"],
        "additionalProperties": False
    }
}
