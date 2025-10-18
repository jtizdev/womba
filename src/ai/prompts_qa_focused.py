"""
QA-Focused prompts that understand business context and user flows.
"""

MANAGEMENT_API_CONTEXT = """
=== PLAINID MANAGEMENT APIS CONTEXT ===
Management APIs for creating, updating, and promoting policies between environments.

**Key APIs for this feature**:
- **Create POP**: POST /pops - Now accepts custom 'id' field
- **Export Policy**: GET /policies/{id}/export - Must preserve custom POP IDs  
- **Import Policy**: POST /policies/import - Must work with custom POP IDs
- **Deploy to Vendor**: POST /pops/{id}/deploy - Must work with custom IDs

Reference: https://docs.plainid.io/apidocs/policy-management-apis
"""

EXPERT_QA_SYSTEM_PROMPT = """You are a senior QA engineer with 15+ years in enterprise software testing.
You understand business requirements deeply and think like both a QA AND a product manager.

MANDATORY REQUIREMENTS FOR EVERY RESPONSE:
1. Generate as many HIGH-QUALITY test cases as needed to thoroughly cover the feature (quality over quantity)
2. Each test MUST have 3-5 detailed steps (NOT 1-2)
3. MUST suggest a folder path based on story component (NEVER return null)
4. Use EXACT feature names, endpoints, UI elements from story
5. ONLY include tests that are highly relevant and have clear business value

Your approach:
- Study PRD/tech design from Confluence to understand implementation
- Read subtasks to know what developers are building
- Generate comprehensive test suite covering happy paths, errors, integration, edge cases
- Each test has multiple actionable steps with realistic data
- Folder suggestion based on component (e.g., "PAP/Policy Management", "Orchestration WS/POP Management")

For EVERY test case you generate, ask yourself:
- "Would a real customer do this?"
- "What business problem does this test verify?"
- "Does this test have enough detail (3-5 steps)?"
- "Did I use the EXACT feature name from the story?"
- "Does this test have high business value?" (If NO, discard it)

QUALITY THRESHOLD: Only include tests that score 80+ on relevance, clarity, and business value.
Better to have 6 excellent tests than 12 mediocre ones."""

BUSINESS_CONTEXT_PROMPT = """
=== BUSINESS CONTEXT & ANALYSIS FRAMEWORK ===

**Your Job**: Analyze the story context (PRD, tech design, subtasks, linked issues) and identify:
1. **What is the main feature/change?**
2. **What problem does it solve for users?**
3. **What are the critical user workflows?** (not generic API tests!)
4. **What other features/components does this touch?** (integration points)
5. **What could break if this fails?** (regression risks)

**How to Find Integration Points**:
- Look at subtasks: what are engineers building/modifying?
- Look at Confluence docs: what entities/features are mentioned?
- Look at linked issues: what related features exist?
- Look at story description: what components are involved?
- Think: "If I change X, what else uses X?"

**Examples of Integration Points**:
- If feature touches "POP" → Check: Applications, Policies, Orchestration, Export/Import
- If feature touches "Policy" → Check: Evaluation, Export/Import, Versioning, UI
- If feature touches "User" → Check: Authentication, Authorization, Audit, UI
- If feature touches "API" → Check: Breaking changes, Backward compatibility, Client SDKs

**Test Categories** (prioritize in this order):
1. **Happy Path** (3-4 tests): Core user workflows that MUST work
2. **Integration Points** (2-3 tests): How this feature connects to other features
3. **Error Handling** (2-3 tests): What happens when users make mistakes
4. **Backward Compatibility** (1-2 tests): Existing functionality still works

**Quality Rules**:
✅ Every test must relate to a REAL user action or business requirement
✅ Embed API calls within user scenarios (not "test POST /api/endpoint")
✅ Think "What would a product manager want to verify?"
✅ Think "What would break in production if this fails?"

**What to SKIP**:
❌ Generic security tests (SQL injection, XSS) - separate security testing
❌ Generic performance tests - separate perf testing
❌ Tests not related to THIS feature
❌ Theoretical edge cases users would never encounter
"""

USER_FLOW_GENERATION_PROMPT = """Based on the story context, generate comprehensive, feature-specific test cases that demonstrate DEEP understanding of the feature.

{business_context}

{management_api_context}

{context}

{existing_tests_context}

{tasks_context}

{folder_context}

**DEEP FEATURE UNDERSTANDING REQUIREMENTS**:
- Read the PRD/tech design from Confluence carefully - understand the WHY, not just WHAT
- Study the subtasks to understand implementation details
- Identify the EXACT endpoints, fields, UI components, database changes
- **For UI features**: Use Figma designs to identify EXACT element names, buttons, tabs, screens
- **For UI features**: Reference specific UI elements (e.g., "Click 'Save Policy' button on Policy Edit screen")
- Understand how this feature integrates with existing system
- Consider what could break in related features
- Review comments from Jira story and subtasks for edge cases

**STRICT RULES - FEATURE SPECIFICITY**:
- Generate as many high-quality tests as needed (minimum 6, no maximum - focus on quality)
- Each test MUST use EXACT feature terminology from the story (e.g., "custom POP ID", "Policies tab", specific API endpoint)
- NO generic tests like "Create entity" or "View list" - be hyper-specific: "Create POP with custom ID 'prod-pop-001' via POST /v1/pops endpoint"
- Steps must include ACTUAL request bodies, field names, UI element IDs, expected status codes
- Each test should have 3-5 detailed, actionable steps
- MUST suggest a folder based on component mentioned in story (REQUIRED, never null)

**Test Breakdown** (generate as many HIGH-QUALITY tests as needed - quality over quantity):
1. **Core Happy Paths** (2-3 tests) - Cover main user workflows
   - Use EXACT feature names, endpoints, field values from story
   - 3-5 detailed steps per test
   
2. **Error & Edge Cases** (2-3 tests) - Feature-specific validation scenarios
   - Invalid inputs specific to THIS feature
   - Boundary conditions mentioned in story/subtasks
   - Error messages and status codes
   
3. **Integration Scenarios** (2-3 tests) - How this feature affects other parts
   - Impact on related features mentioned in story
   - Data flow between components
   - API contract changes
   
4. **Advanced Workflows** (1-2 tests) - Complex, real-world scenarios
   - Multi-step user journeys
   - Cross-environment scenarios (if relevant)
   - Backward compatibility (if relevant)

**CRITICAL - DO NOT CREATE THESE**:
❌ Infrastructure/setup tasks (e.g., "Modify automation infrastructure")
❌ Development tasks (e.g., "Update API documentation")
❌ Deployment tasks (e.g., "Configure environment variables")
❌ Tests that verify developer work, not user functionality

**ONLY CREATE**:
✅ Tests that verify USER-FACING functionality
✅ Tests that a QA engineer would execute
✅ Tests that validate business requirements

**Test Case Format**:
{{
  "title": "Specific user scenario",
  "description": "WHY this matters: [business justification]. WHAT we're testing: [specific behavior]",
  "preconditions": "Realistic setup a user would have",
  "steps": [
    {{
      "step_number": 1,
      "action": "Specific user action with realistic data",
      "expected_result": "Observable outcome user would see",
      "test_data": "Real-world example values"
    }}
  ],
  "expected_result": "Clear success criteria from user perspective",
  "priority": "critical|high|medium",
  "test_type": "functional|integration|negative|regression",
  "tags": ["custom-pop-id", "management-api"],
  "automation_candidate": true,
  "risk_level": "high|medium|low",
  "related_existing_tests": []
}}

Generate the test plan in JSON format with these fields:
{{
  "summary": "1-2 sentences on what these tests verify",
  "test_cases": [array of test cases],
  "suggested_folder": "REQUIRED - must suggest based on component (e.g., 'Orchestration WS/POP Management')"
}}

**UI TEST SPECIAL REQUIREMENTS** (if this is a UI story):
{figma_context}

For UI features, MUST include:
- EXACT screen names (e.g., "Application Detail Screen", "Policy List View")
- EXACT element names (e.g., "Policies Tab", "Search Input", "Save Button")
- Visual validation (e.g., "Verify 'No policies' message displays", "Check pagination controls visible")
- User interactions (e.g., "Click", "Type", "Select", "Scroll")
- NOT generic "navigate" - be specific: "Click 'Policies' tab in Application sidebar"

**FOLDER SELECTION (REQUIRED - CRITICAL)**:
1. Analyze story summary/description for component keywords
2. Match against provided Zephyr folder structure
3. Score each folder by keyword overlap and select best match
4. Examples of dynamic matching:
   - Story contains "policy" + folders include "PAP/Policy Management" → select that
   - Story contains "orchestration" + "POP" → select "Orchestration WS/..."
   - Story contains "runtime" → select "Runtime/..."
5. **NEVER return null** - AI will dynamically match to best folder or use fallback

**REMEMBER**: 
- Folder selection is now DYNAMIC - system will match to user's actual folder structure
- No hardcoded PlainID-specific logic
- Works for any company's Zephyr structure
"""

FEW_SHOT_EXAMPLES = """
=== EXAMPLE: Good QA Test Cases for Custom POP ID Feature ===

Example 1: Core Happy Path
{{
  "title": "Create POP with custom ID and deploy policy using that ID",
  "description": "WHY: This is the primary use case - users need to create POPs with their own IDs and use them immediately. WHAT: Verify custom ID is accepted, stored, and can be referenced in policy deployment.",
  "preconditions": "User has Management API credentials. No POP with ID 'dev-payment-pop' exists.",
  "steps": [
    {{
      "step_number": 1,
      "action": "POST /pops with body {{'id': 'dev-payment-pop', 'name': 'Payment Service POP', 'type': 'Snowflake'}}",
      "expected_result": "POP created successfully, response includes custom ID 'dev-payment-pop'",
      "test_data": "id: 'dev-payment-pop'"
    }},
    {{
      "step_number": 2,
      "action": "Deploy a policy targeting POP ID 'dev-payment-pop'",
      "expected_result": "Policy deploys successfully to the custom POP",
      "test_data": "policy: payment_policy.json"
    }},
    {{
      "step_number": 3,
      "action": "Verify policy is active on Snowflake using POP 'dev-payment-pop'",
      "expected_result": "Policy is enforced in Snowflake",
      "test_data": null
    }}
  ],
  "expected_result": "End-to-end workflow works: create custom POP → deploy policy → verify enforcement",
  "priority": "critical",
  "test_type": "functional",
  "tags": ["custom-pop-id", "happy-path", "deployment"],
  "automation_candidate": true,
  "risk_level": "high"
}}

Example 2: Real User Error Scenario
{{
  "title": "Attempt to create POP with duplicate custom ID shows clear error",
  "description": "WHY: Users will make mistakes - they might try to reuse an ID. WHAT: Verify system prevents duplicates and gives actionable error message.",
  "preconditions": "POP with custom ID 'prod-hr-pop' already exists",
  "steps": [
    {{
      "step_number": 1,
      "action": "POST /pops with body {{'id': 'prod-hr-pop', 'name': 'Another POP'}}",
      "expected_result": "HTTP 409 Conflict with error: 'POP ID prod-hr-pop already exists in this environment'",
      "test_data": "id: 'prod-hr-pop'"
    }}
  ],
  "expected_result": "Clear error message helps user understand the problem and how to fix it",
  "priority": "high",
  "test_type": "negative",
  "tags": ["custom-pop-id", "error-handling", "uniqueness"],
  "automation_candidate": true,
  "risk_level": "medium"
}}

Example 3: Critical Migration Scenario
{{
  "title": "Export policy from dev (custom ID) and import to prod (no conflicts)",
  "description": "WHY: Main business value is env-to-env deployment. WHAT: Verify the export/import workflow preserves custom IDs.",
  "preconditions": "Dev environment has POP 'shared-pop-001'. Prod environment does not have this POP.",
  "steps": [
    {{
      "step_number": 1,
      "action": "Export policy from dev that references POP 'shared-pop-001'",
      "expected_result": "Export file contains POP ID 'shared-pop-001'",
      "test_data": "export_dev_policy.json"
    }},
    {{
      "step_number": 2,
      "action": "Create POP in prod with same ID 'shared-pop-001'",
      "expected_result": "POP created in prod",
      "test_data": null
    }},
    {{
      "step_number": 3,
      "action": "Import policy to prod",
      "expected_result": "Policy imports successfully, references prod POP 'shared-pop-001', no manual ID mapping needed",
      "test_data": "import to prod"
    }}
  ],
  "expected_result": "Policy migrates seamlessly between environments using consistent custom POP IDs",
  "priority": "critical",
  "test_type": "integration",
  "tags": ["custom-pop-id", "export-import", "cross-env"],
  "automation_candidate": true,
  "risk_level": "high"
}}

Use these as inspiration - notice how each test:
1. Has clear business justification (WHY)
2. Tests specific user scenario (WHAT)
3. Uses realistic data (real IDs like 'prod-hr-pop', not 'test123')
4. Covers end-to-end workflow
5. Has measurable success criteria
"""

