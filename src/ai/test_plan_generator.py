"""
AI test plan generator - refactored for SOLID principles.
Orchestrates AI test generation using specialized services.
"""

from typing import Optional
from loguru import logger

from src.aggregator.story_collector import StoryContext
from src.config.settings import settings
from src.models.test_plan import TestPlan
from src.models.enriched_story import EnrichedStory
from src.ai.generation.ai_client_factory import AIClientFactory
from src.ai.generation.prompt_builder import PromptBuilder
from src.ai.generation.response_parser import ResponseParser
from src.ai.prompts_optimized import SYSTEM_INSTRUCTION
from src.ai.enrichment_cache import EnrichmentCache
from src.ai.story_enricher import StoryEnricher


class TestPlanGenerator:
    """
    AI-powered test plan generator (Refactored).
    Orchestrates test generation by delegating to specialized services.
    
    Follows SOLID principles:
    - Single Responsibility: Orchestration only
    - Dependency Injection: Uses injected services
    - Open/Closed: Easy to extend with new AI providers
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        use_openai: bool = True,
        prompt_builder: Optional[PromptBuilder] = None,
        response_parser: Optional[ResponseParser] = None,
    ):
        """
        Initialize test plan generator.
        
        Args:
            api_key: AI API key (defaults to settings)
            model: Model to use (defaults to settings)
            use_openai: Use OpenAI instead of Anthropic
            prompt_builder: Optional prompt builder (creates new if not provided)
            response_parser: Optional response parser (creates new if not provided)
        """
        # Create AI client
        self.client, self.model, self.use_openai = AIClientFactory.create_client(
            use_openai=use_openai,
            api_key=api_key,
            model=model
        )
        
        # AI parameters
        self.temperature = settings.temperature
        self.max_tokens = settings.max_tokens
        
        # Services (dependency injection)
        self.prompt_builder = prompt_builder or PromptBuilder(model=self.model, use_optimized=True)
        self.response_parser = response_parser or ResponseParser()
        
        # Story enrichment services
        self.enrichment_cache = EnrichmentCache()
        self.story_enricher = StoryEnricher()
        
        # API context builder (for fallback: story → swagger → MCP)
        from src.ai.api_context_builder import APIContextBuilder
        self.api_context_builder = APIContextBuilder()
        
        logger.info(f"TestPlanGenerator initialized with model: {self.model} (optimized prompts: {self.prompt_builder.use_optimized})")

    async def generate_test_plan(
        self,
        context: StoryContext,
        existing_tests: list = None,
        folder_structure: list = None,
        use_rag: bool = None
    ) -> TestPlan:
        """
        Generate a comprehensive test plan from story context.
        
        Args:
            context: Story context with all aggregated information
            existing_tests: List of existing test cases from Zephyr
            folder_structure: Zephyr folder structure
            use_rag: Whether to use RAG for context retrieval
            
        Returns:
            TestPlan object with generated test cases
            
        Raises:
            Exception: If AI generation fails
        """
        main_story = context.main_story
        logger.info(f"Generating test plan for {main_story.key}: {main_story.summary}")
        
        # Determine if RAG should be used
        if use_rag is None:
            use_rag = settings.enable_rag
        
        # Step 0: Enrich story (preprocess and compress) if enabled
        enriched_story = await self._enrich_story(main_story, context) if settings.enable_story_enrichment else None
        
        # Step 0.5: Build API context using fallback flow (story → swagger → MCP)
        api_context = None
        if enriched_story:
            combined_text = self.story_enricher._build_combined_text(main_story, [])
            api_context = await self.api_context_builder.build_api_context(
                main_story=main_story,
                story_context=context,
                combined_text=combined_text
            )
            logger.info(f"API context built: {len(api_context.api_specifications)} endpoints, flow={api_context.extraction_flow}")
        
        # Step 1: Retrieve RAG context if enabled (pass full context for better matching)
        rag_context = await self._retrieve_rag_context(main_story, context, use_rag)
        
        # Step 2: Build prompt (with enriched story + API context if available)
        prompt = self.prompt_builder.build_generation_prompt(
            context=context,
            rag_context=rag_context,
            existing_tests=existing_tests,
            folder_structure=folder_structure,
            enriched_story=enriched_story,
            api_context=api_context,
        )
        
        # DEBUG: Save prompt to file for inspection
        try:
            from pathlib import Path
            prompt_file = Path("./debug_prompts") / f"prompt_{main_story.key}.txt"
            prompt_file.parent.mkdir(exist_ok=True)
            prompt_file.write_text(prompt, encoding='utf-8')
            logger.info(f"Saved prompt to: {prompt_file}")
        except Exception as e:
            logger.debug(f"Failed to save prompt to file: {e}")
        
        # Step 3: Call AI API
        response_text = await self._call_ai_api(prompt)
        
        # Step 4: Parse response (extracts reasoning and data)
        test_plan_data, reasoning = self.response_parser.parse_ai_response(response_text)
        
        # Extract validation check if present
        validation_check = test_plan_data.get("validation_check")
        
        # Step 5: Build TestPlan object with reasoning
        test_plan = self.response_parser.build_test_plan(
            main_story=main_story,
            test_plan_data=test_plan_data,
            ai_model=self.model,
            folder_structure=folder_structure,
            reasoning=reasoning,
            validation_check=validation_check
        )
        
        logger.info(
            f"Successfully generated {len(test_plan.test_cases)} test cases for {main_story.key}"
        )
        
        # Step 6: Validate test cases (pass enriched_story for API spec validation)
        self.response_parser.validate_test_cases(test_plan, enriched_story=enriched_story)
        
        # Step 7: Auto-index test plan for future RAG retrieval if enabled
        if use_rag and settings.rag_auto_index:
            await self._auto_index_test_plan(test_plan, context)
        
        return test_plan

    async def _enrich_story(self, main_story, story_context: StoryContext) -> Optional[EnrichedStory]:
        """
        Enrich story with comprehensive context (uses cache if available).
        
        Args:
            main_story: Jira story
            story_context: Full StoryContext
            
        Returns:
            EnrichedStory if successful, None otherwise
        """
        try:
            # Check cache first
            cached = self.enrichment_cache.get_cached(
                story_key=main_story.key,
                story_updated=main_story.updated
            )
            
            if cached:
                logger.info(f"Using cached enrichment for {main_story.key}")
                return cached
            
            # Enrich story
            logger.info(f"Enriching story {main_story.key} (not in cache)...")
            enriched = await self.story_enricher.enrich_story(
                main_story=main_story,
                story_context=story_context
            )
            
            # Cache result
            self.enrichment_cache.save_cached(enriched, main_story.updated)
            
            # Debug: Log enrichment summary
            logger.debug("=" * 80)
            logger.debug(f"NEW ENRICHMENT CREATED FOR: {main_story.key}")
            logger.debug("=" * 80)
            logger.debug(f"Stories analyzed: {enriched.source_story_ids}")
            logger.debug(f"Acceptance Criteria count: {len(enriched.acceptance_criteria)}")
            logger.debug(f"Functional Points count: {len(enriched.functional_points)}")
            logger.debug(f"PlainID Components: {enriched.plainid_components}")
            logger.debug(f"Risk Areas: {enriched.risk_areas}")
            logger.debug("=" * 80)
            
            logger.info(
                f"Story enriched: {len(enriched.source_story_ids)} stories analyzed, "
                f"{len(enriched.acceptance_criteria)} ACs collected, "
                f"{len(enriched.functional_points)} functional points derived"
            )
            
            return enriched
            
        except Exception as e:
            logger.warning(f"Story enrichment failed (will use raw context): {e}")
            return None

    async def _retrieve_rag_context(self, main_story, story_context, use_rag: bool) -> Optional[str]:
        """
        Retrieve RAG context for the story.
        
        Args:
            main_story: Jira story
            story_context: Full StoryContext with subtasks, linked issues, etc.
            use_rag: Whether to use RAG
            
        Returns:
            RAG context string or None
        """
        if not use_rag:
            return None
        
        try:
            from src.ai.rag_retriever import RAGRetriever
            
            logger.info("Retrieving OPTIMIZED RAG context...")
            rag_retriever = RAGRetriever()
            project_key = main_story.key.split('-')[0]
            
            # Use optimized retrieval with filtering, re-ranking, deduplication
            retrieved_context = await rag_retriever.retrieve_optimized(
                story=main_story,
                project_key=project_key,
                story_context=story_context,
                max_docs_per_type=3  # Top 3 per collection
            )
            
            if retrieved_context.has_context():
                rag_context = self.prompt_builder.build_rag_context(retrieved_context)
                logger.info(f"✅ Optimized RAG context: {retrieved_context.get_summary()}")
                return rag_context
            else:
                logger.info("No RAG context found (database may be empty)")
                return None
        except Exception as e:
            logger.warning(f"RAG retrieval failed (will continue without RAG): {e}")
            return None

    async def _call_ai_api(self, prompt: str) -> str:
        """
        Call AI API with the prompt using structured output.
        
        OpenAI: Uses response_format with JSON schema for reliable parsing (for supported models)
        Claude: Uses XML tags as fallback (no native structured output support)
        
        Args:
            prompt: Complete prompt
            
        Returns:
            AI response text (JSON string for OpenAI, text with JSON for Claude)
        """
        try:
            # Debug: print the exact prompt being sent (visible when log level is DEBUG)
            try:
                approx_tokens = len(prompt) // 4
                logger.debug(f"AI prompt (~{approx_tokens} tokens, {len(prompt)} chars):\n{prompt}")
                logger.info(f"Max output tokens configured: {self.max_tokens}")
            except Exception:
                # Never block the API call on logging issues
                pass
            if self.use_openai:
                # Check if model supports json_schema (gpt-4o-2024-08-06+, gpt-4o-mini-2024-07-18+)
                supports_json_schema = (
                    "gpt-4o" in self.model.lower() and 
                    ("2024-08-06" in self.model or "2024-11" in self.model or "mini" in self.model.lower())
                ) or "o1" in self.model.lower()
                
                if supports_json_schema:
                    logger.info(f"Calling OpenAI API with structured output: {self.model}")
                    
                    # Get JSON schema from prompt builder
                    json_schema = self.prompt_builder.get_json_schema()
                    
                    # Use structured output for reliable JSON parsing
                    response = self.client.chat.completions.create(
                        model=self.model,
                        max_tokens=self.max_tokens,
                        temperature=self.temperature,
                        response_format={
                            "type": "json_schema",
                            "json_schema": json_schema
                        },
                        messages=[
                            {"role": "system", "content": SYSTEM_INSTRUCTION},
                            {"role": "user", "content": prompt}
                        ],
                    )
                    
                    response_text = response.choices[0].message.content
                    logger.info(f"OpenAI response: {len(response_text)} chars (structured JSON)")
                    return response_text
                else:
                    # Older OpenAI models (gpt-4-turbo, gpt-4, etc.) - use JSON mode
                    logger.info(f"Calling OpenAI API with JSON mode (legacy): {self.model}")
                    
                    json_prompt = prompt + "\n\n" + """
Return your response as valid JSON matching this exact structure:
{
  "reasoning": "your analysis here",
  "summary": "brief summary",
  "test_cases": [
    {
      "name": "test name",
      "description": "what this tests",
      "test_data": "concrete test data",
      "steps": [
        {
          "step_number": 1,
          "action": "what to do",
          "expected_result": "what should happen",
          "test_data": "data for this step"
        }
      ],
      "expected_result": "overall expected outcome",
      "priority": "high/medium/low",
      "test_type": "functional/integration/regression/etc",
      "tags": ["tag1", "tag2"]
    }
  ],
  "suggested_folder": "folder/path"
}
"""
                    
                    response = self.client.chat.completions.create(
                        model=self.model,
                        max_tokens=self.max_tokens,
                        temperature=self.temperature,
                        response_format={"type": "json_object"},
                        messages=[
                            {"role": "system", "content": SYSTEM_INSTRUCTION + "\n\nYou must respond with valid JSON only."},
                            {"role": "user", "content": json_prompt}
                        ],
                    )
                    
                    response_text = response.choices[0].message.content
                    logger.info(f"OpenAI response: {len(response_text)} chars (JSON mode)")
                    return response_text
                
            else:
                # Claude doesn't support response_format, use XML tags
                logger.info(f"Calling Claude API with XML-tagged output: {self.model}")
                
                # Add XML output instructions for Claude
                claude_prompt = prompt + "\n\n" + """
<output_instructions>
Return your response as valid JSON wrapped in <json> tags:
<json>
{
  "reasoning": "your analysis here",
  "summary": "...",
  "test_cases": [...],
  "suggested_folder": "...",
  "validation_check": {...}
}
</json>
</output_instructions>
"""
                
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    system=SYSTEM_INSTRUCTION,
                    messages=[{"role": "user", "content": claude_prompt}],
                )
                
                response_text = response.content[0].text
                logger.info(f"Claude response: {len(response_text)} chars")
                return response_text
                
        except Exception as e:
            logger.error(f"AI API call failed: {e}")
            raise

    async def _auto_index_test_plan(self, test_plan: TestPlan, context: StoryContext) -> None:
        """
        Auto-index test plan for future RAG retrieval.
        
        Args:
            test_plan: Generated test plan
            context: Story context
        """
        try:
            from src.ai.context_indexer import ContextIndexer
            
            logger.info("Auto-indexing test plan for future RAG retrieval...")
            indexer = ContextIndexer()
            await indexer.index_test_plan(test_plan, context)
        except Exception as e:
            logger.warning(f"Auto-indexing failed (test plan generated successfully): {e}")

