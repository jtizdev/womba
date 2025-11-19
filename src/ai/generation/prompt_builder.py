"""
Prompt builder for constructing AI prompts from context.
Single Responsibility: Building prompts with RAG, context, and examples.

Refactored to support:
- Structured JSON output with schema
- Chain-of-thought reasoning
- Optimized section ordering
- Token-efficient construction
- Dynamic prompt overrides from configuration
"""

import json
from pathlib import Path
from typing import Optional, List, Dict, Any
from loguru import logger

from src.aggregator.story_collector import StoryContext
from src.models.enriched_story import EnrichedStory
from src.ai.prompts_qa_focused import (
    SYSTEM_INSTRUCTION,
    REASONING_FRAMEWORK,
    GENERATION_GUIDELINES,
    QUALITY_CHECKLIST,
    RAG_GROUNDING_INSTRUCTIONS,
    FEW_SHOT_EXAMPLES,
    TEST_PLAN_JSON_SCHEMA,
)
from src.ai.prompts_optimized import (
    CORE_INSTRUCTIONS as OPTIMIZED_CORE_INSTRUCTIONS,
    FEW_SHOT_EXAMPLES as OPTIMIZED_EXAMPLES,
    TEST_PLAN_JSON_SCHEMA as OPTIMIZED_SCHEMA,
    VALIDATION_RULES,
)

# Path for prompt overrides
PROMPT_OVERRIDES_FILE = Path("data/prompt_overrides.json")


def _load_prompt_overrides() -> Dict[str, str]:
    """Load prompt overrides from disk."""
    try:
        if PROMPT_OVERRIDES_FILE.exists():
            with open(PROMPT_OVERRIDES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load prompt overrides: {e}")
    return {}


def _get_prompt_section(section_name: str, default_content: str) -> str:
    """Get prompt section content, with override if available."""
    overrides = _load_prompt_overrides()
    return overrides.get(section_name, default_content)


class PromptBuilder:
    """
    Builds AI prompts from various context sources.
    Features:
    - RAG context integration with token budgeting
    - Existing tests context
    - Engineering tasks context
    - Folder structure context
    """

    def __init__(self, model: str = "gpt-4o", use_optimized: bool = True):
        """
        Initialize prompt builder.
        
        Args:
            model: Model name for token budget calculation
            use_optimized: Use optimized prompt structure (default True)
        """
        self.model = model.lower() if model else "gpt-4o"
        self.use_optimized = use_optimized
    
    def get_json_schema(self) -> Dict[str, Any]:
        """
        Get the JSON schema for structured output.
        
        Returns:
            JSON schema dict for test plan generation
        """
        return OPTIMIZED_SCHEMA if self.use_optimized else TEST_PLAN_JSON_SCHEMA

    def build_generation_prompt(
        self,
        context: StoryContext,
        rag_context: Optional[str] = None,
        existing_tests: Optional[list] = None,
        folder_structure: Optional[list] = None,
        enriched_story: Optional[EnrichedStory] = None,
    ) -> str:
        """
        Build complete prompt for test generation with optimized structure.
        
        Uses enriched story (preprocessed narrative) if available, otherwise falls back to raw context.
        
        Optimized ordering:
        1. Story understanding (enriched narrative or raw context)
        2. Acceptance criteria (explicitly listed)
        3. API specifications (relevant endpoints)
        4. Risk areas (what to focus testing on)
        5. RAG grounding (examples for style)
        6. Few-shot examples
        7. Reasoning framework
        8. Generation guidelines
        9. Quality checklist
        
        Args:
            context: Story context
            rag_context: Optional RAG context section
            existing_tests: Optional list of existing tests
            folder_structure: Optional Zephyr folder structure
            enriched_story: Optional preprocessed EnrichedStory
            
        Returns:
            Complete prompt string
        """
        # Route to optimized prompt if enabled
        logger.info(f"Prompt builder state: use_optimized={self.use_optimized}, has_enriched_story={enriched_story is not None}")
        if self.use_optimized and enriched_story:
            logger.info("🚀 Using OPTIMIZED prompt structure (new strategy)")
            return self.build_optimized_prompt(
                enriched_story=enriched_story,
                rag_context_formatted=rag_context or "",
                existing_tests=existing_tests,
                folder_structure=folder_structure
            )
        
        main_story = context.main_story
        
        # Build auxiliary sections
        existing_tests_context = self._build_existing_tests_context(main_story, existing_tests, bool(rag_context))
        tasks_context = self._build_tasks_context(context)
        folder_context = self._build_folder_context(folder_structure)
        
        # Build prompt with STORY UNDERSTANDING FIRST
        sections = []
        
        sections.append("\n" + "=" * 80)
        sections.append("🚨 CRITICAL: READ AND UNDERSTAND THIS STORY FIRST 🚨")
        sections.append("=" * 80)
        sections.append("DO NOT PATTERN MATCH FROM EXAMPLES!")
        sections.append("DO NOT MAKE UP GENERIC TESTS!")
        sections.append("READ THIS STORY. UNDERSTAND THE FEATURE. TEST WHAT IT ACTUALLY DOES.")
        sections.append("=" * 80)
        sections.append("\n<story_to_test>")
        
        # Use enriched story if available (preprocessed and compressed)
        if enriched_story:
            sections.append(f"\n=== STORY: {enriched_story.story_key} ===\n")
            
            # Add PlainID architecture overview early if components are involved
            if enriched_story.plainid_components:
                from src.ai.prompts_qa_focused import COMPANY_OVERVIEW
                sections.append("--- PLAINID PLATFORM CONTEXT (Know the architecture) ---")
                sections.append(COMPANY_OVERVIEW)
                sections.append("-" * 80 + "\n")
            
            # FIRST: PRD content (explains WHAT things ARE)
            if enriched_story.confluence_docs:
                sections.append("--- PRD / REQUIREMENTS DOCUMENTATION (READ THIS FIRST) ---")
                sections.append("This explains what the feature IS and what it DOES:\n")
                for ref in enriched_story.confluence_docs:
                    title = ref.title or "Untitled Document"
                    sections.append(f"\n📄 Document: {title}")
                    sections.append(f"🔗 URL: {ref.url}\n")
                    if ref.qa_summary:
                        sections.append(ref.qa_summary)
                    elif ref.summary:
                        sections.append(f"{ref.summary}")
                sections.append("\n" + "-" * 80)
            
            sections.append("\n--- FEATURE OVERVIEW ---")
            sections.append(enriched_story.feature_narrative)
            
            if enriched_story.acceptance_criteria:
                sections.append("\n--- ACCEPTANCE CRITERIA (MANDATORY: Map each to test cases) ---")
                for i, ac in enumerate(enriched_story.acceptance_criteria, 1):
                    sections.append(f"{i}. {ac}")
            
            if enriched_story.functional_points:
                sections.append("\n--- FUNCTIONALITY TO TEST (Derived from Story + PRD) ---")
                # Show ALL functional points (no limit - we have context headroom)
                for i, fp in enumerate(enriched_story.functional_points, 1):
                    sections.append(f"{i}. {fp}")
            
            if enriched_story.api_specifications:
                sections.append("\n--- API SPECIFICATIONS (Use EXACT endpoints/schemas) ---")
                sections.append(f"\n⚠️ CRITICAL: This story has {len(enriched_story.api_specifications)} API endpoint(s). You MUST generate at least 1 API test for EACH endpoint listed below.")
                sections.append(f"⚠️ ENDPOINT CHECKLIST - Generate tests for ALL of these:")
                sections.append(f"\n🚨 MANDATORY: For EACH endpoint below, you MUST create at least ONE API test that uses that EXACT endpoint path.")
                sections.append(f"🚨 DO NOT reuse the same endpoint in multiple tests - each endpoint needs its own dedicated test(s).")
                sections.append(f"🚨 DO NOT skip any endpoint - if you see 4 endpoints, you need at least 4 API tests (one per endpoint minimum).")
                for i, api in enumerate(enriched_story.api_specifications, 1):
                    methods_str = " ".join(api.http_methods) if api.http_methods else "UNKNOWN"
                    sections.append(f"\n  [{i}/{len(enriched_story.api_specifications)}] {methods_str} {api.endpoint_path}")
                    sections.append(f"     ⚠️ YOU MUST CREATE A TEST FOR THIS ENDPOINT - DO NOT SKIP IT!")
                    if api.service_name:
                        sections.append(f"     Service: {api.service_name}")
                    if api.parameters:
                        sections.append(f"     Parameters: {', '.join(api.parameters)}")
                    if api.request_schema:
                        sections.append(f"     Request: {api.request_schema}")
                    if api.response_schema:
                        sections.append(f"     Response: {api.response_schema}")
                    if api.authentication:
                        sections.append(f"     Auth: {api.authentication}")
                sections.append(f"\n⚠️ REMINDER: You must generate API tests for ALL {len(enriched_story.api_specifications)} endpoints above. Do not skip any!")
                sections.append(f"⚠️ FINAL CHECK: Before returning, count your API tests. If you have fewer than {len(enriched_story.api_specifications)} API tests, you have FAILED!")
                sections.append(f"⚠️ FINAL CHECK: Verify each endpoint path appears in at least one API test step. If any endpoint is missing, you have FAILED!")
            
            if enriched_story.plainid_components:
                sections.append("\n--- PLAINID COMPONENTS INVOLVED ---")
                sections.append(", ".join(enriched_story.plainid_components))
            
            if enriched_story.risk_areas:
                sections.append("\n--- RISK AREAS & TESTING FOCUS ---")
                for risk in enriched_story.risk_areas:
                    sections.append(f"• {risk}")
            
            if enriched_story.related_stories:
                sections.append("\n--- RELATED STORIES ---")
                # Show ALL related stories (no limit)
                for related in enriched_story.related_stories:
                    sections.append(f"• {related}")
            
            # Debug: Log enriched story sections being added to prompt
            logger.debug("=" * 80)
            logger.debug(f"ENRICHED STORY INJECTED INTO PROMPT: {enriched_story.story_key}")
            logger.debug("=" * 80)
            logger.debug(f"Narrative length: {len(enriched_story.feature_narrative)} chars")
            logger.debug(f"Acceptance Criteria: {len(enriched_story.acceptance_criteria)}")
            logger.debug(f"API Specifications: {len(enriched_story.api_specifications)}")
            logger.debug(f"PlainID Components: {len(enriched_story.plainid_components)}")
            logger.debug(f"Risk Areas: {len(enriched_story.risk_areas)}")
            logger.debug(f"Related Stories: {len(enriched_story.related_stories)}")
            logger.debug("\nAPIs being sent to AI:")
            for api in enriched_story.api_specifications:
                logger.debug(f"  - {' '.join(api.http_methods)} {api.endpoint_path}")
            logger.debug("\nAcceptance Criteria being sent to AI:")
            for i, ac in enumerate(enriched_story.acceptance_criteria, 1):
                logger.debug(f"  {i}. {ac[:100]}{'...' if len(ac) > 100 else ''}")
            logger.debug("=" * 80)
            
            logger.info(f"Using enriched story context (analyzed {len(enriched_story.source_story_ids)} stories, {len(enriched_story.api_specifications)} APIs)")
        else:
            # Fallback to raw context
            full_context = context.get("full_context_text", "")
            sections.append(full_context)
            logger.info("Using raw story context (enrichment not available)")
        
        if existing_tests_context:
            sections.append(f"\n{existing_tests_context}")
        
        if tasks_context:
            sections.append(f"\n{tasks_context}")
        
        if folder_context:
            sections.append(f"\n{folder_context}")
        
        sections.append("\n</story_to_test>\n")
        
        # If we have API specs, add explicit API step requirements to force concrete payloads and paths
        if enriched_story and enriched_story.api_specifications:
            sections.append("\n" + "-" * 80)
            sections.append("MANDATORY API STEP REQUIREMENTS (Use the API SPECIFICATIONS above)")
            sections.append("-" * 80)
            sections.append("For ANY API-related test step, you MUST:")
            sections.append("- Include HTTP method and EXACT path (e.g., POST /api/v1/policies)")
            sections.append("- Include auth details if required (e.g., Bearer token, client ID)")
            sections.append("- Include parameters with exact names and types (path/query)")
            sections.append("- Include request body JSON with EXACT field names from schema, with realistic example values")
            sections.append("- State expected response code(s) and key response fields per schema")
            sections.append("- Only use endpoints listed in API SPECIFICATIONS (do NOT invent endpoints)")
            sections.append("")
        
        sections.append("\n" + "=" * 80)
        sections.append("⚠️  MANDATORY BEFORE GENERATING TESTS:")
        sections.append("=" * 80)
        sections.append("In your reasoning section, you MUST:")
        sections.append("1. EXPLAIN IN YOUR OWN WORDS: What does this feature do? What problem does it solve?")
        sections.append("2. LIST FUNCTIONALITY TO TEST: Use the bullets above (Derived from Story + PRD)")
        sections.append("3. ANALYZE ENGINEERING TASKS: List key subtasks and what they implement (APIs, UI, integrations)")
        sections.append("4. LIST EVERY ACCEPTANCE CRITERION and map each to test(s)")
        sections.append("5. EXPLAIN: What could break? What needs verification?")
        sections.append("6. THEN AND ONLY THEN: Generate tests based on YOUR UNDERSTANDING")
        sections.append("")
        sections.append("If you cannot explain the feature clearly, you cannot test it properly.")
        sections.append("Examples below are for STYLE/TERMINOLOGY ONLY - not for copying scenarios.")
        sections.append("=" * 80 + "\n")
        
        # 2. REASONING FRAMEWORK - think before generating (MOVED UP - instructions BEFORE examples!)
        sections.append(_get_prompt_section('reasoning_framework', REASONING_FRAMEWORK))
        
        # 3. GENERATION GUIDELINES - rules for creating tests (MOVED UP - instructions BEFORE examples!)
        sections.append(_get_prompt_section('generation_guidelines', GENERATION_GUIDELINES))
        
        # 4. RAG grounding (if available) - examples to learn patterns from (MOVED DOWN - after instructions!)
        if rag_context:
            sections.append("\n<reference_examples>")
            sections.append("⚠️  REMINDER: You've seen the RULES above. Now learn patterns and terminology from these examples.")
            sections.append("DO NOT copy scenarios from examples - they are for STYLE and TERMINOLOGY only.")
            sections.append("Your tests must be specific to the STORY you just read, following the RULES you just learned.")
            sections.append(RAG_GROUNDING_INSTRUCTIONS)
            sections.append(rag_context)
            sections.append("</reference_examples>\n")
        
        # 5. Few-shot examples - learn test structure (after RAG context)
        sections.append(FEW_SHOT_EXAMPLES)
        
        # 6. Quality checklist - final validation before returning
        sections.append(QUALITY_CHECKLIST)
        
        # 7. Output instructions
        sections.append("""
<output_format>
Generate your response as a JSON object matching the schema provided.
Include your reasoning, then the test plan, then validation check.
Ensure all required fields are populated with realistic values.
</output_format>
""")
        
        prompt = "\n\n".join(sections)
        
        # Log token estimate
        estimated_tokens = self._estimate_tokens(prompt)
        logger.info(f"Built prompt: ~{estimated_tokens} tokens ({len(prompt)} chars)")
        
        return prompt

    def build_rag_context(self, retrieved_context) -> str:
        """
        Build RAG context section with smart token budgeting.
        Simplified headers and better token management.
        
        Args:
            retrieved_context: RetrievedContext object from RAG retriever
            
        Returns:
            Formatted RAG context string
        """
        # Token budget based on model context window
        if "mini" in self.model or "turbo" in self.model:
            # Large context models
            MAX_TOTAL_TOKENS = 190000
            RESERVED_FOR_PROMPTS = 15000  # Reduced reserve (new prompts are shorter)
            RAG_BUDGET = MAX_TOTAL_TOKENS - RESERVED_FOR_PROMPTS
            logger.info(f"Using large context model ({self.model}): {RAG_BUDGET} tokens for RAG")
        else:
            # Standard models
            MAX_TOTAL_TOKENS = 28000
            RESERVED_FOR_PROMPTS = 8000  # Reduced reserve
            RAG_BUDGET = MAX_TOTAL_TOKENS - RESERVED_FOR_PROMPTS
            logger.info(f"Using standard model ({self.model}): {RAG_BUDGET} tokens for RAG")
        
        sections = []
        sections.append("<retrieved_context>")
        sections.append("=== COMPANY DATA (Retrieved from RAG) ===")
        sections.append("This is your PRIMARY reference for test generation.\n")
        
        # Track token usage
        header_text = "\n".join(sections)
        tokens_used = self._estimate_tokens(header_text)
        tokens_remaining = RAG_BUDGET - tokens_used
        
        # Add similar test plans
        tokens_remaining = self._add_test_plans_section(sections, retrieved_context, tokens_remaining)
        
        # Add Confluence docs
        tokens_remaining = self._add_confluence_section(sections, retrieved_context, tokens_remaining)
        
        # Add similar stories
        tokens_remaining = self._add_stories_section(sections, retrieved_context, tokens_remaining)
        
        # Add existing tests
        tokens_remaining = self._add_existing_tests_section(sections, retrieved_context, tokens_remaining)
        
        # Add external docs (PlainID API) - PRIORITY
        tokens_remaining = self._add_external_docs_section(sections, retrieved_context, tokens_remaining)
        
        # Add swagger docs (GitLab OpenAPI specs)
        tokens_remaining = self._add_swagger_docs_section(sections, retrieved_context, tokens_remaining)
        
        # Footer
        sections.append(f"\n=== END RETRIEVED CONTEXT ===")
        sections.append(f"Token budget: {RAG_BUDGET - tokens_remaining}/{RAG_BUDGET} used")
        sections.append("</retrieved_context>\n")
        
        result = "\n".join(sections)
        logger.info(f"RAG context: {self._estimate_tokens(result)} tokens, {len(result)} chars")
        return result

    def _build_existing_tests_context(self, main_story, existing_tests: Optional[list], has_rag: bool) -> str:
        """Build existing tests context section."""
        if has_rag:
            logger.info("Using RAG for existing tests (skipping redundant Zephyr API call)")
            return ""
        
        if not existing_tests:
            return ""
        
        logger.info(f"RAG disabled, using keyword matching on {len(existing_tests)} tests")
        context = "\n=== EXISTING TEST CASES IN ZEPHYR (Check for Duplicates!) ===\n"
        context += "(IMPORTANT: DO NOT create tests that already exist. If a test already covers the flow, mention it in 'related_existing_tests'.)\n\n"
        
        # Search for relevant tests
        story_keywords = main_story.summary.lower().split()
        relevant_tests = []
        
        for test in existing_tests[:500]:
            test_name = test.get('name', '').lower()
            test_obj = (test.get('objective') or '').lower()
            
            if any(keyword in test_name or keyword in test_obj for keyword in story_keywords if len(keyword) > 3):
                relevant_tests.append(test)
                if len(relevant_tests) >= 50:
                    break
        
        if relevant_tests:
            context += f"Found {len(relevant_tests)} potentially relevant existing tests:\n\n"
            for test in relevant_tests[:20]:
                context += f"- {test.get('key', 'N/A')}: {test.get('name', 'N/A')}\n"
                if test.get('objective'):
                    context += f"  Description: {test['objective']}\n"
        else:
            context += f"Searched {len(existing_tests)} tests, none seem directly related.\n"
        
        return context

    def _build_tasks_context(self, context: StoryContext) -> str:
        """Build engineering tasks context section with FULL descriptions (no truncation)."""
        subtasks = context.get("subtasks", [])
        if not subtasks:
            return ""
        
        tasks_context = "\n=== ENGINEERING TASKS FOR THIS STORY ===\n"
        tasks_context += "(CRITICAL: Use these implementation details for test scenarios - they often contain API endpoints, UI behavior, and edge cases)\n\n"
        for task in subtasks:
            tasks_context += f"- {task.key}: {task.summary}\n"
            if task.description:
                # NO TRUNCATION - AI needs full subtask details for proper test coverage
                tasks_context += f"  Details: {task.description}\n"
        
        return tasks_context

    def _build_folder_context(self, folder_structure: Optional[list]) -> str:
        """Build folder structure context section."""
        if not folder_structure:
            return ""
        
        folder_context = "\n=== ZEPHYR TEST FOLDER STRUCTURE ===\n"
        folder_context += "(Suggest the most appropriate folder based on the feature area)\n\n"
        for folder in folder_structure[:15]:
            folder_name = folder.get('name', 'Unknown')
            folder_id = folder.get('id', 'N/A')
            folder_context += f"- {folder_name} (ID: {folder_id})\n"
            if folder.get('folders'):
                for subfolder in folder['folders'][:5]:
                    subfolder_name = subfolder.get('name', 'Unknown')
                    folder_context += f"  └── {subfolder_name}\n"
        
        return folder_context

    def _add_test_plans_section(self, sections: list, retrieved_context, tokens_remaining: int) -> int:
        """Add similar test plans section - FULL CONTENT, NO TRUNCATION."""
        if not retrieved_context.similar_test_plans:
            return tokens_remaining
        
        sections.append("\n--- SIMILAR PAST TEST PLANS (Learn patterns from these) ---\n")
        for i, doc in enumerate(retrieved_context.similar_test_plans[:3], 1):
            sections.append(f"\n{i}. Test Plan Example:")
            sections.append(f"   Similarity: {1 - doc.get('distance', 0):.2f}")
            sections.append(f"   {doc.get('document', '')}")  # FULL CONTENT
            sections.append("   " + "-" * 70)
        
        return tokens_remaining

    def _add_confluence_section(self, sections: list, retrieved_context, tokens_remaining: int) -> int:
        """Add Confluence docs section - FULL CONTENT, NO TRUNCATION."""
        if not retrieved_context.similar_confluence_docs:
            return tokens_remaining
        
        sections.append("\n--- COMPANY DOCUMENTATION (Use this terminology) ---\n")
        
        for i, doc in enumerate(retrieved_context.similar_confluence_docs[:3], 1):
            metadata = doc.get('metadata', {})
            doc_text = doc.get('document', '')
            
            sections.append(f"\n{i}. {metadata.get('title', 'Unknown')}")
            if metadata.get('url'):
                sections.append(f"   Source: {metadata.get('url')}")
            sections.append(f"   Relevance: {1 - doc.get('distance', 0):.2f}")
            
            sections.append(f"\n   Content:")
            sections.append(f"   {'-' * 68}")
            # Add content with proper indentation
            for line in doc_text.split('\n'):
                sections.append(f"   {line}")
            sections.append(f"   {'-' * 68}")
        
        return tokens_remaining

    def _add_stories_section(self, sections: list, retrieved_context, tokens_remaining: int) -> int:
        """Add similar stories section - FULL CONTENT, NO TRUNCATION."""
        if not retrieved_context.similar_jira_stories:
            return tokens_remaining
        
        sections.append("\n--- SIMILAR PAST STORIES (Apply same approach) ---\n")
        
        for i, doc in enumerate(retrieved_context.similar_jira_stories[:3], 1):
            metadata = doc.get('metadata', {})
            doc_text = doc.get('document', '')
            
            sections.append(f"\n{i}. Story: {metadata.get('story_key', 'Unknown')}")
            sections.append(f"   {doc_text}")  # FULL CONTENT, NO TRUNCATION
            sections.append("   " + "-" * 70)
        
        return tokens_remaining

    def _add_existing_tests_section(self, sections: list, retrieved_context, tokens_remaining: int) -> int:
        """Add existing tests section - FULL CONTENT, NO TRUNCATION."""
        if not retrieved_context.similar_existing_tests:
            return tokens_remaining
        
        sections.append("\n--- EXISTING TESTS (CRITICAL: Check for duplicates before generating!) ---\n")
        sections.append("⚠️  DUPLICATE DETECTION REQUIREMENT:\n")
        sections.append("• Review these existing tests carefully - do they already cover your scenario?\n")
        sections.append("• If a test already exists for this functionality → DO NOT create a duplicate!\n")
        sections.append("• Document in your reasoning: 'Checked existing tests: [found/not found duplicates]'\n")
        sections.append("• If similar test exists: Reference it and explain how yours differs, or skip it\n")
        sections.append("• Better to skip a test than create redundant coverage\n\n")
        
        for i, doc in enumerate(retrieved_context.similar_existing_tests[:3], 1):
            metadata = doc.get('metadata', {})
            doc_text = doc.get('document', '')
            
            sections.append(f"\n{i}. Test: {metadata.get('test_name', 'Unknown')}")
            sections.append(f"   {doc_text}")  # FULL CONTENT, NO TRUNCATION
            sections.append("   " + "-" * 70)
        
        return tokens_remaining

    def _add_external_docs_section(self, sections: list, retrieved_context, tokens_remaining: int) -> int:
        """Add external API documentation section - FULL CONTENT, NO TRUNCATION."""
        if not retrieved_context.similar_external_docs:
            return tokens_remaining
        
        sections.append("\n--- EXTERNAL API DOCUMENTATION (Use exact endpoints/payloads) ---\n")
        sections.append("Requirements for test data:")
        sections.append("• Copy EXACT JSON structures from documentation - do NOT modify")
        sections.append("• Include ALL required fields shown in examples")
        sections.append("• Use actual field names and data types")
        sections.append("• If JSON example shown, include it verbatim in test steps")
        sections.append("• NO generic placeholders like '<token>' or 'Bearer <value>'")
        sections.append("• If exact payload unavailable: state 'Reference [doc name] for payload'\n")
        
        for i, doc in enumerate(retrieved_context.similar_external_docs[:3], 1):
            metadata = doc.get('metadata', {})
            doc_text = doc.get('document', '')
            
            # Build header with metadata
            sections.append(f"\n{i}. {metadata.get('title', 'Unknown')}")
            sections.append(f"   Source: {metadata.get('source_url', 'N/A')}")
            if metadata.get('last_updated'):
                sections.append(f"   Last Updated: {metadata.get('last_updated')}")
            sections.append(f"   Relevance: {1 - doc.get('distance', 0):.2f}")
            
            # Add full content with clear separation
            sections.append(f"\n   Content:")
            sections.append(f"   {'-' * 68}")
            # Add content with proper indentation
            for line in doc_text.split('\n'):
                sections.append(f"   {line}")
            sections.append(f"   {'-' * 68}")
        
        return tokens_remaining

    def _add_swagger_docs_section(self, sections: list, retrieved_context, tokens_remaining: int) -> int:
        """Add Swagger/OpenAPI documentation section - FULL CONTENT, NO TRUNCATION."""
        if not retrieved_context.similar_swagger_docs:
            return tokens_remaining
        
        sections.append("\n--- SWAGGER/OPENAPI DOCUMENTATION (Use exact API specs) ---\n")
        sections.append("Requirements for API test data:")
        sections.append("• Copy EXACT endpoint paths, methods, and parameters from Swagger specs")
        sections.append("• Use EXACT status codes documented in responses")
        sections.append("• Reference EXACT request/response schema field names and types")
        sections.append("• Include authentication requirements from security schemes")
        sections.append("• Match parameter names, types, and required/optional indicators")
        sections.append("• If request body schema shown, use exact field names in test data")
        sections.append("• NO invented endpoints - only use what's documented\n")
        
        for i, doc in enumerate(retrieved_context.similar_swagger_docs[:3], 1):
            metadata = doc.get('metadata', {})
            doc_text = doc.get('document', '')
            
            sections.append(f"\n{i}. Swagger API: {metadata.get('service_name', 'Unknown')}")
            sections.append(f"   File: {metadata.get('file_path', 'N/A')}")
            sections.append(f"   Type: {metadata.get('api_type', 'N/A')}")
            sections.append(f"   Similarity: {1 - doc.get('distance', 0):.2f}")
            sections.append(f"{doc_text}")  # FULL CONTENT, NO TRUNCATION
            sections.append("   " + "-" * 70)
        
        return tokens_remaining

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count (rough: 1 token ≈ 4 chars for English)."""
        return len(text) // 4
    
    def build_optimized_prompt(
        self,
        enriched_story: EnrichedStory,
        rag_context_formatted: str,
        existing_tests: Optional[list] = None,
        folder_structure: Optional[list] = None,
    ) -> str:
        """
        Build OPTIMIZED prompt with story-first structure.
        
        New structure (70% story, 30% context):
        1. Core instructions (concise)
        2. Story requirements (PROMINENT - 40% of tokens)
        3. Retrieved context (filtered - 30% of tokens)
        4. Examples (concise - 10% of tokens)
        5. Architecture reference (minimal - 10% of tokens)
        6. Output schema (10% of tokens)
        
        Args:
            enriched_story: Preprocessed story with all context
            rag_context_formatted: Pre-formatted RAG context (already optimized)
            existing_tests: Optional existing tests
            folder_structure: Optional folder structure
            
        Returns:
            Optimized prompt string
        """
        sections = []
        
        # ============================================================================
        # SECTION 1: CORE INSTRUCTIONS (1500 tokens)
        # ============================================================================
        sections.append(OPTIMIZED_CORE_INSTRUCTIONS)
        sections.append("\n" + "=" * 80 + "\n")
        
        # ============================================================================
        # SECTION 2: STORY REQUIREMENTS - MOST IMPORTANT (40% of budget)
        # ============================================================================
        sections.append("📋 STORY REQUIREMENTS (PRIMARY INPUT)\n")
        sections.append("=" * 80 + "\n")
        
        sections.append(f"**Story**: {enriched_story.story_key} - {enriched_story.feature_narrative.split('.')[0]}\n")
        
        # Feature narrative
        sections.append("**What This Feature Does**:\n")
        sections.append(enriched_story.feature_narrative)
        sections.append("\n")
        
        # Acceptance criteria (CRITICAL - map to tests)
        if enriched_story.acceptance_criteria:
            sections.append("**Acceptance Criteria** (MUST map each to tests):\n")
            for i, ac in enumerate(enriched_story.acceptance_criteria, 1):
                sections.append(f"{i}. {ac}\n")
            sections.append("\n")
        
        # Functional points
        if enriched_story.functional_points:
            sections.append("**Functionality to Test**:\n")
            for i, fp in enumerate(enriched_story.functional_points, 1):
                sections.append(f"- {fp}\n")
            sections.append("\n")
        
        # API specifications (if any)
        if enriched_story.api_specifications:
            sections.append("**API Specifications** (use exact endpoints):\n")
            for api in enriched_story.api_specifications:
                sections.append(f"- {' '.join(api.http_methods)} {api.endpoint_path}\n")
                if api.parameters:
                    sections.append(f"  Params: {', '.join(api.parameters)}\n")
                if api.request_schema:
                    sections.append(f"  Request Schema:\n{api.request_schema}\n")
                if api.response_schema:
                    sections.append(f"  Response Schema:\n{api.response_schema}\n")
            sections.append("\n")
        
        # Risk areas
        if enriched_story.risk_areas:
            sections.append("**Risk Areas** (focus testing here):\n")
            for risk in enriched_story.risk_areas:
                sections.append(f"- {risk}\n")
            sections.append("\n")
        
        sections.append("=" * 80 + "\n\n")
        
        # ============================================================================
        # SECTION 3: RETRIEVED CONTEXT (30% of budget - already optimized)
        # ============================================================================
        if rag_context_formatted:
            sections.append("📚 RETRIEVED CONTEXT (for terminology, APIs, style)\n")
            sections.append("=" * 80 + "\n")
            sections.append(rag_context_formatted)
            sections.append("\n" + "=" * 80 + "\n\n")
        
        # ============================================================================
        # SECTION 4: EXAMPLES (10% of budget - concise, cross-domain)
        # ============================================================================
        sections.append(OPTIMIZED_EXAMPLES)
        sections.append("\n")
        
        # ============================================================================
        # SECTION 5: COMPANY CONTEXT (conditional - only if PlainID detected)
        # ============================================================================
        # Check if PlainID context should be injected
        should_inject_plainid = (
            enriched_story.plainid_components or
            (rag_context_formatted and any(term in rag_context_formatted.lower() for term in ['plainid', 'pap', 'pdp', 'pop', 'pbac']))
        )
        
        if should_inject_plainid:
            # Inject PlainID architecture context from RAG or enriched story
            sections.append("🏢 COMPANY CONTEXT (PlainID Platform)\n")
            sections.append("=" * 80 + "\n")
            sections.append("PlainID uses Policy-Based Access Control (PBAC). Key terms:\n")
            sections.append("- PAP (Policy Administration Point): Web UI for policy authoring\n")
            sections.append("- PDP (Policy Decision Point): Runtime authorization engine\n")
            sections.append("- PEP (Policy Enforcement Point): Client-side enforcement\n")
            sections.append("- POP (Policy Object Point): Deployed policy storage\n")
            sections.append("- PIPs (Policy Information Points): Data sources that enrich policy evaluation context\n")
            sections.append("- Authorizers: Data connectors (IDP, Database, API, File-based) that feed PIPs\n")
            sections.append("\nWorkspaces:\n")
            sections.append("- Authorization Workspace: Policies, Applications, Assets\n")
            sections.append("- Identity Workspace: Identity sources, Dynamic Groups\n")
            sections.append("- Orchestration Workspace: POPs, Vendor integration\n")
            sections.append("- Administration Workspace: Audit, User management\n")
            sections.append("\nPLAINID UI STRUCTURE (for writing UI test steps):\n")
            sections.append("\nWORKSPACES & UI NAVIGATION:\n")
            sections.append("- **Authorization Workspace** (Policy authoring, main workspace for policies/assets/applications):\n")
            sections.append("  - Policies menu → Policy list → Create/Edit policy → Policy 360° views\n")
            sections.append("  - Applications menu → Application list → Application details → (tabs: General, Policies, API Mappers)\n")
            sections.append("  - Assets menu → Asset Types → Assets\n")
            sections.append("  - Scopes menu\n")
            sections.append("\n- **Identity Workspace** (Identity management):\n")
            sections.append("  - Identity Sources menu → IDP configuration\n")
            sections.append("  - Dynamic Groups menu → Group definitions\n")
            sections.append("  - Attributes menu\n")
            sections.append("  - Token Enrichment\n")
            sections.append("\n- **Orchestration Workspace** (Vendor integration, POPs):\n")
            sections.append("  - POPs menu → POP details → Discovery, Policies tabs\n")
            sections.append("  - Discovery menu → Vendor discovery status\n")
            sections.append("  - Reconciliation → Deployment/Override actions\n")
            sections.append("\n- **Administration Workspace** (System admin):\n")
            sections.append("  - Audit Events → Activity logs\n")
            sections.append("  - User Management → Roles, permissions\n")
            sections.append("  - Environment settings\n")
            sections.append("\nUI TEST STEP REQUIREMENTS (CRITICAL):\n")
            sections.append("- For UI tests, use UI navigation language: \"Navigate to...\", \"Click...\", \"Select...\", \"Verify displays...\"\n")
            sections.append("- Always specify workspace: \"In Authorization Workspace, navigate to Applications\"\n")
            sections.append("- Always specify menu/tab path: \"Applications → Select app-123 → Click Policies tab\"\n")
            sections.append("- Verify UI elements: \"Verify policy list displays with search bar and paging controls\"\n")
            sections.append("- NO API endpoints in UI test steps! (API calls go in separate backend/API tests)\n")
            sections.append("\nFor detailed architecture, see retrieved context above.\n")
            sections.append("=" * 80 + "\n\n")
        
        # ============================================================================
        # SECTION 5b: MANDATORY VALIDATION RULES (Self-check)
        # ============================================================================
        sections.append(VALIDATION_RULES)
        sections.append("\n")
        
        # ============================================================================
        # SECTION 6: OUTPUT FORMAT (10% of budget)
        # ============================================================================
        sections.append("📤 OUTPUT FORMAT\n")
        sections.append("=" * 80 + "\n")
        sections.append("Return JSON matching this schema exactly:\n")
        sections.append("- reasoning: Your analysis (2-4 sentences)\n")
        sections.append("- summary: Story info + test count justification\n")
        sections.append("- test_cases: Array of test objects\n")
        sections.append("- suggested_folder: Best folder from structure\n")
        sections.append("- validation_check: Self-validation flags\n")
        sections.append("\nEach test must have: title, description, preconditions, steps (with test_data), expected_result, priority, test_type, tags, automation_candidate, risk_level\n")
        sections.append("=" * 80 + "\n")
        
        prompt = "\n".join(sections)
        
        # Log token estimate
        estimated_tokens = self._estimate_tokens(prompt)
        logger.info(f"✅ Built OPTIMIZED prompt: ~{estimated_tokens} tokens ({len(prompt)} chars)")
        logger.info(f"   Story section: ~{self._estimate_tokens(enriched_story.feature_narrative)} tokens")
        logger.info(f"   RAG context: ~{self._estimate_tokens(rag_context_formatted) if rag_context_formatted else 0} tokens")
        
        return prompt

