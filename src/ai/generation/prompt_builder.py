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
    ) -> str:
        """
        Build complete prompt for test generation with optimized structure.
        
        Optimized ordering:
        1. RAG grounding (if available)
        2. Few-shot examples (learn patterns first)
        3. Reasoning framework
        4. Generation guidelines
        5. Story context
        6. Quality checklist
        
        Args:
            context: Story context
            rag_context: Optional RAG context section
            existing_tests: Optional list of existing tests
            folder_structure: Optional Zephyr folder structure
            
        Returns:
            Complete prompt string
        """
        main_story = context.main_story
        full_context = context.get("full_context_text", "")
        
        # Build auxiliary sections
        existing_tests_context = self._build_existing_tests_context(main_story, existing_tests, bool(rag_context))
        tasks_context = self._build_tasks_context(context)
        folder_context = self._build_folder_context(folder_structure)
        
        # Build prompt in optimized order
        sections = []
        
        # 1. RAG grounding (if available) - establishes company-specific patterns
        if rag_context:
            sections.append(RAG_GROUNDING_INSTRUCTIONS)
            sections.append(rag_context)
        
        # 2. Few-shot examples - learn patterns before applying them
        sections.append(FEW_SHOT_EXAMPLES)
        
        # 3. Reasoning framework - think before generating
        sections.append(REASONING_FRAMEWORK)
        
        # 4. Generation guidelines - rules for creating tests
        sections.append(GENERATION_GUIDELINES)
        
        # 5. Story context - the specific story to test
        sections.append("\n<story_context>\n")
        sections.append(f"=== STORY TO TEST ===\n{full_context}")
        
        if existing_tests_context:
            sections.append(f"\n{existing_tests_context}")
        
        if tasks_context:
            sections.append(f"\n{tasks_context}")
        
        if folder_context:
            sections.append(f"\n{folder_context}")
        
        sections.append("\n</story_context>\n")
        
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
                    context += f"  Description: {test['objective'][:150]}...\n"
        else:
            context += f"Searched {len(existing_tests)} tests, none seem directly related.\n"
        
        return context

    def _build_tasks_context(self, context: StoryContext) -> str:
        """Build engineering tasks context section."""
        subtasks = context.get("subtasks", [])
        if not subtasks:
            return ""
        
        tasks_context = "\n=== ENGINEERING TASKS FOR THIS STORY ===\n"
        tasks_context += "(Use these to identify regression test scenarios)\n\n"
        for task in subtasks:
            tasks_context += f"- {task.key}: {task.summary}\n"
            if task.description:
                desc = task.description[:200] if len(task.description) > 200 else task.description
                tasks_context += f"  Details: {desc}\n"
        
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
        for i, doc in enumerate(retrieved_context.similar_test_plans[:3], 1):
            sections.append(f"\n{i}. Test Plan Example:")
            sections.append(f"   Similarity: {1 - doc.get('distance', 0):.2f}")
            sections.append(f"   {doc.get('document', '')[:800]}")
            sections.append("   " + "-" * 70)
        
        return tokens_remaining

    def _add_confluence_section(self, sections: list, retrieved_context, tokens_remaining: int) -> int:
        """Add Confluence docs section with dynamic budgeting."""
        if not retrieved_context.similar_confluence_docs or tokens_remaining < 1000:
            return tokens_remaining
        
        sections.append("\n--- COMPANY DOCUMENTATION (Use this terminology) ---\n")
        tokens_per_doc = min(tokens_remaining // len(retrieved_context.similar_confluence_docs[:5]), 2500)
        
        for i, doc in enumerate(retrieved_context.similar_confluence_docs[:5], 1):
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
        tokens_per_story = min(tokens_remaining // len(retrieved_context.similar_jira_stories[:5]), 2000)
        
        for i, doc in enumerate(retrieved_context.similar_jira_stories[:5], 1):
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
        
        sections.append("\n--- EXISTING TESTS (Match this style, avoid duplicates) ---\n")
        tokens_per_test = min(tokens_remaining // len(retrieved_context.similar_existing_tests[:10]), 1500)
        
        for i, doc in enumerate(retrieved_context.similar_existing_tests[:10], 1):
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
        
        tokens_per_api_doc = min(tokens_remaining // len(retrieved_context.similar_external_docs[:5]), 4000)
        
        for i, doc in enumerate(retrieved_context.similar_external_docs[:5], 1):
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

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count (rough: 1 token ≈ 4 chars for English)."""
        return len(text) // 4

