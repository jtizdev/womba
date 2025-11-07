"""
Prompt builder for constructing AI prompts from context.
Single Responsibility: Building prompts with RAG, context, and examples.

Refactored to support:
- Structured JSON output with schema
- Chain-of-thought reasoning
- Optimized section ordering
- Token-efficient construction
"""

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


class PromptBuilder:
    """
    Builds AI prompts from various context sources.
    Features:
    - RAG context integration with token budgeting
    - Existing tests context
    - Engineering tasks context
    - Folder structure context
    """

    def __init__(self, model: str = "gpt-4o"):
        """
        Initialize prompt builder.
        
        Args:
            model: Model name for token budget calculation
        """
        self.model = model.lower() if model else "gpt-4o"
    
    def get_json_schema(self) -> Dict[str, Any]:
        """
        Get the JSON schema for structured output.
        
        Returns:
            JSON schema dict for test plan generation
        """
        return TEST_PLAN_JSON_SCHEMA

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
                for api in enriched_story.api_specifications:
                    sections.append(f"\nEndpoint: {api.http_methods} {api.endpoint_path}")
                    if api.service_name:
                        sections.append(f"Service: {api.service_name}")
                    if api.parameters:
                        sections.append(f"Parameters: {', '.join(api.parameters)}")
                    if api.request_schema:
                        sections.append(f"Request: {api.request_schema}")
                    if api.response_schema:
                        sections.append(f"Response: {api.response_schema}")
                    if api.authentication:
                        sections.append(f"Auth: {api.authentication}")
            
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
        sections.append(REASONING_FRAMEWORK)
        
        # 3. GENERATION GUIDELINES - rules for creating tests (MOVED UP - instructions BEFORE examples!)
        sections.append(GENERATION_GUIDELINES)
        
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
        """Add similar test plans section."""
        if not retrieved_context.similar_test_plans:
            return tokens_remaining
        
        sections.append("\n--- SIMILAR PAST TEST PLANS (Learn patterns from these) ---\n")
        # Show more test plan examples (increased from 3 to 6)
        for i, doc in enumerate(retrieved_context.similar_test_plans[:6], 1):
            sections.append(f"\n{i}. Test Plan Example:")
            sections.append(f"   Similarity: {1 - doc.get('distance', 0):.2f}")
            # Increased from 800 to 1500 chars per test plan
            sections.append(f"   {doc.get('document', '')[:1500]}")
            sections.append("   " + "-" * 70)
        
        return tokens_remaining

    def _add_confluence_section(self, sections: list, retrieved_context, tokens_remaining: int) -> int:
        """Add Confluence docs section with dynamic budgeting."""
        if not retrieved_context.similar_confluence_docs or tokens_remaining < 1000:
            return tokens_remaining
        
        sections.append("\n--- COMPANY DOCUMENTATION (Use this terminology) ---\n")
        # Increased per-doc budget from 2500 to 4000 tokens for fuller content
        tokens_per_doc = min(tokens_remaining // len(retrieved_context.similar_confluence_docs[:10]), 4000)
        
        # Show more Confluence docs (increased from 5 to 10)
        for i, doc in enumerate(retrieved_context.similar_confluence_docs[:10], 1):
            if tokens_remaining < 500:
                break
            
            doc_text = doc.get('document', '')
            max_chars = tokens_per_doc * 4
            if len(doc_text) > max_chars:
                doc_text = doc_text[:max_chars] + f"\n... [truncated for budget]"
            
            doc_section = f"\n{i}. Document: {doc.get('metadata', {}).get('title', 'Unknown')}\n   Similarity: {1 - doc.get('distance', 0):.2f}\n   {doc_text}\n   " + "-" * 70
            section_tokens = self._estimate_tokens(doc_section)
            
            if section_tokens <= tokens_remaining:
                sections.append(doc_section)
                tokens_remaining -= section_tokens
        
        return tokens_remaining

    def _add_stories_section(self, sections: list, retrieved_context, tokens_remaining: int) -> int:
        """Add similar stories section with dynamic budgeting."""
        if not retrieved_context.similar_jira_stories or tokens_remaining < 1000:
            return tokens_remaining
        
        sections.append("\n--- SIMILAR PAST STORIES (Apply same approach) ---\n")
        # Increased per-story budget from 2000 to 3000 tokens
        tokens_per_story = min(tokens_remaining // len(retrieved_context.similar_jira_stories[:10]), 3000)
        
        # Show more stories (increased from 5 to 10)
        for i, doc in enumerate(retrieved_context.similar_jira_stories[:10], 1):
            if tokens_remaining < 500:
                break
            
            doc_text = doc.get('document', '')
            max_chars = tokens_per_story * 4
            if len(doc_text) > max_chars:
                doc_text = doc_text[:max_chars] + f"\n... [truncated for budget]"
            
            doc_section = f"\n{i}. Story: {doc.get('metadata', {}).get('story_key', 'Unknown')}\n   {doc_text}\n   " + "-" * 70
            section_tokens = self._estimate_tokens(doc_section)
            
            if section_tokens <= tokens_remaining:
                sections.append(doc_section)
                tokens_remaining -= section_tokens
        
        return tokens_remaining

    def _add_existing_tests_section(self, sections: list, retrieved_context, tokens_remaining: int) -> int:
        """Add existing tests section with dynamic budgeting."""
        if not retrieved_context.similar_existing_tests or tokens_remaining < 1000:
            return tokens_remaining
        
        sections.append("\n--- EXISTING TESTS (CRITICAL: Check for duplicates before generating!) ---\n")
        sections.append("⚠️  DUPLICATE DETECTION REQUIREMENT:\n")
        sections.append("• Review these existing tests carefully - do they already cover your scenario?\n")
        sections.append("• If a test already exists for this functionality → DO NOT create a duplicate!\n")
        sections.append("• Document in your reasoning: 'Checked existing tests: [found/not found duplicates]'\n")
        sections.append("• If similar test exists: Reference it and explain how yours differs, or skip it\n")
        sections.append("• Better to skip a test than create redundant coverage\n\n")
        # Increased per-test budget from 1500 to 2500 tokens for complete test examples
        tokens_per_test = min(tokens_remaining // len(retrieved_context.similar_existing_tests[:20]), 2500)
        
        # Show more existing tests (increased from 10 to 20)
        for i, doc in enumerate(retrieved_context.similar_existing_tests[:20], 1):
            if tokens_remaining < 300:
                break
            
            doc_text = doc.get('document', '')
            max_chars = tokens_per_test * 4
            if len(doc_text) > max_chars:
                doc_text = doc_text[:max_chars] + f"\n... [truncated for budget]"
            
            doc_section = f"\n{i}. Test: {doc.get('metadata', {}).get('test_name', 'Unknown')}\n   {doc_text}\n   " + "-" * 70
            section_tokens = self._estimate_tokens(doc_section)
            
            if section_tokens <= tokens_remaining:
                sections.append(doc_section)
                tokens_remaining -= section_tokens
        
        return tokens_remaining

    def _add_external_docs_section(self, sections: list, retrieved_context, tokens_remaining: int) -> int:
        """Add external API documentation section with priority budgeting."""
        if not retrieved_context.similar_external_docs or tokens_remaining < 2000:
            return tokens_remaining
        
        sections.append("\n--- EXTERNAL API DOCUMENTATION (Use exact endpoints/payloads) ---\n")
        sections.append("Requirements for test data:")
        sections.append("• Copy EXACT JSON structures from documentation - do NOT modify")
        sections.append("• Include ALL required fields shown in examples")
        sections.append("• Use actual field names and data types")
        sections.append("• If JSON example shown, include it verbatim in test steps")
        sections.append("• NO generic placeholders like '<token>' or 'Bearer <value>'")
        sections.append("• If exact payload unavailable: state 'Reference [doc name] for payload'\n")
        
        # Increased per-doc budget from 4000 to 6000 tokens for complete API docs
        tokens_per_api_doc = min(tokens_remaining // len(retrieved_context.similar_external_docs[:10]), 6000)
        
        # Show more external docs (increased from 5 to 10)
        for i, doc in enumerate(retrieved_context.similar_external_docs[:10], 1):
            if tokens_remaining < 1000:
                break
            
            metadata = doc.get('metadata', {})
            doc_text = doc.get('document', '')
            max_chars = tokens_per_api_doc * 4
            if len(doc_text) > max_chars:
                doc_text = doc_text[:max_chars] + f"\n... [truncated for budget]"
            
            doc_section = f"\n{i}. API Doc: {metadata.get('title', 'Unknown')}\n   Source: {metadata.get('source_url', 'N/A')}\n   Similarity: {1 - doc.get('distance', 0):.2f}\n   {doc_text}\n   " + "-" * 70
            section_tokens = self._estimate_tokens(doc_section)
            
            if section_tokens <= tokens_remaining:
                sections.append(doc_section)
                tokens_remaining -= section_tokens
        
        return tokens_remaining

    def _add_swagger_docs_section(self, sections: list, retrieved_context, tokens_remaining: int) -> int:
        """Add Swagger/OpenAPI documentation section with priority budgeting."""
        if not retrieved_context.similar_swagger_docs or tokens_remaining < 2000:
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
        
        # Increased per-doc budget from 4000 to 6000 tokens for complete swagger specs
        tokens_per_swagger_doc = min(tokens_remaining // len(retrieved_context.similar_swagger_docs[:8]), 6000)
        
        # Show more swagger docs (increased from 5 to 8)
        for i, doc in enumerate(retrieved_context.similar_swagger_docs[:8], 1):
            if tokens_remaining < 1000:
                break
            
            metadata = doc.get('metadata', {})
            doc_text = doc.get('document', '')
            max_chars = tokens_per_swagger_doc * 4
            if len(doc_text) > max_chars:
                doc_text = doc_text[:max_chars] + f"\n... [truncated for budget]"
            
            doc_section = f"\n{i}. Swagger API: {metadata.get('service_name', 'Unknown')}\n   File: {metadata.get('file_path', 'N/A')}\n   Type: {metadata.get('api_type', 'N/A')}\n   Similarity: {1 - doc.get('distance', 0):.2f}\n   {doc_text}\n   " + "-" * 70
            section_tokens = self._estimate_tokens(doc_section)
            
            if section_tokens <= tokens_remaining:
                sections.append(doc_section)
                tokens_remaining -= section_tokens
        
        return tokens_remaining

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count (rough: 1 token ≈ 4 chars for English)."""
        return len(text) // 4

