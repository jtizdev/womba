"""
Two-Stage Test Plan Generator.

Stage 1: Analyze story + RAG sources → CoveragePlan
Stage 2: Generate tests from CoveragePlan

This approach ensures:
- All patterns are detected (DIFFERENT_X, SPECIFIC_USER, etc.)
- All PRD requirements are extracted
- All API endpoints are identified
- Existing test overlap is noted
- Tests are generated according to the plan
"""

import json
from typing import Optional, Dict, Any, List
from loguru import logger

from src.aggregator.story_collector import StoryContext
from src.config.settings import settings
from src.models.test_plan import TestPlan
from src.models.enriched_story import EnrichedStory
from src.models.coverage_plan import CoveragePlan, PatternMatch, PRDRequirement, APICoverage, ExistingTestOverlap, PlannedTest
from src.ai.generation.ai_client_factory import AIClientFactory
from src.ai.generation.response_parser import ResponseParser
from src.ai.prompts_analysis import build_analysis_prompt, ANALYSIS_JSON_SCHEMA
from src.ai.prompts_compact import build_stage2_prompt, COMPACT_JSON_SCHEMA
from src.ai.enrichment_cache import EnrichmentCache
from src.ai.story_enricher import StoryEnricher


class TwoStageGenerator:
    """
    Two-stage test plan generator.
    
    Stage 1: Analysis - Detect patterns, extract PRD requirements, identify APIs
    Stage 2: Generation - Create tests from the coverage plan
    
    This approach separates "thinking" from "doing" for better results.
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        use_openai: bool = True,
    ):
        """Initialize two-stage generator."""
        # Create AI client
        self.client, self.model, self.use_openai = AIClientFactory.create_client(
            use_openai=use_openai,
            api_key=api_key,
            model=model
        )
        
        # AI parameters
        self.temperature = settings.temperature
        self.max_tokens = settings.max_tokens
        
        # Services
        self.response_parser = ResponseParser()
        self.enrichment_cache = EnrichmentCache()
        self.story_enricher = StoryEnricher()
        
        # API context builder
        from src.ai.api_context_builder import APIContextBuilder
        self.api_context_builder = APIContextBuilder()
        
        logger.info(f"[TWO-STAGE] Initialized with model={self.model}")
    
    async def generate_test_plan(
        self,
        context: StoryContext,
        existing_tests: list = None,
        folder_structure: list = None,
        use_rag: bool = None
    ) -> TestPlan:
        """
        Generate test plan using two-stage approach.
        
        Args:
            context: Story context with all aggregated information
            existing_tests: List of existing test cases from Zephyr
            folder_structure: Zephyr folder structure
            use_rag: Whether to use RAG for context retrieval
            
        Returns:
            TestPlan object with generated test cases
        """
        main_story = context.main_story
        logger.info(f"[TWO-STAGE] Generating test plan for {main_story.key}: {main_story.summary}")
        
        # Determine if RAG should be used
        if use_rag is None:
            use_rag = settings.enable_rag
        
        # Step 0: Enrich story
        enriched_story = await self._enrich_story(main_story, context) if settings.enable_story_enrichment else None
        
        # Step 1: Retrieve RAG context
        retrieved_context = None
        if use_rag:
            retrieved_context = await self._retrieve_rag_context(main_story, context)
        
        # Step 2: Build API context
        api_context = None
        if enriched_story:
            combined_text = self.story_enricher._build_combined_text(main_story, [])
            swagger_rag_docs = retrieved_context.similar_swagger_docs if retrieved_context else None
            api_context = await self.api_context_builder.build_api_context(
                main_story=main_story,
                story_context=context,
                combined_text=combined_text,
                swagger_rag_docs=swagger_rag_docs
            )
            logger.info(f"[TWO-STAGE] API context: {len(api_context.api_specifications)} endpoints")
        
        # Extract data for prompts
        acceptance_criteria = enriched_story.acceptance_criteria if enriched_story else []
        
        # Convert ConfluenceDocRef objects to dicts if needed
        confluence_docs = []
        if enriched_story and enriched_story.confluence_docs:
            for doc in enriched_story.confluence_docs:
                if hasattr(doc, 'model_dump'):
                    confluence_docs.append(doc.model_dump())
                elif hasattr(doc, 'dict'):
                    confluence_docs.append(doc.dict())
                else:
                    confluence_docs.append(doc)
        
        swagger_docs = retrieved_context.similar_swagger_docs if retrieved_context else []
        existing_tests_data = retrieved_context.similar_existing_tests if retrieved_context else []
        
        # Convert API specifications to dicts if needed
        api_specifications = []
        if api_context and api_context.api_specifications:
            for spec in api_context.api_specifications:
                if hasattr(spec, 'model_dump'):
                    api_specifications.append(spec.model_dump())
                elif hasattr(spec, 'dict'):
                    api_specifications.append(spec.dict())
                else:
                    api_specifications.append(spec)
        
        # ========================================
        # STAGE 1: ANALYSIS
        # ========================================
        logger.info("[TWO-STAGE] === STAGE 1: ANALYSIS ===")
        
        coverage_plan = await self._run_stage1_analysis(
            story_key=main_story.key,
            story_title=main_story.summary,
            story_description=main_story.description or "",
            acceptance_criteria=acceptance_criteria,
            confluence_docs=confluence_docs,
            swagger_docs=swagger_docs,
            existing_tests=existing_tests_data,
            api_specifications=api_specifications
        )
        
        logger.info(f"[TWO-STAGE] Analysis complete: {coverage_plan.get_summary()}")
        
        # Save Stage 1 output for debugging
        self._save_debug_file(main_story.key, "stage1_analysis", coverage_plan.to_dict())
        
        # ========================================
        # STAGE 2: GENERATION
        # ========================================
        logger.info("[TWO-STAGE] === STAGE 2: GENERATION ===")
        
        test_plan = await self._run_stage2_generation(
            story_key=main_story.key,
            story_title=main_story.summary,
            story_description=main_story.description or "",
            acceptance_criteria=acceptance_criteria,
            coverage_plan=coverage_plan,
            confluence_docs=confluence_docs,
            swagger_docs=swagger_docs,
            api_specifications=api_specifications,
            folder_structure=folder_structure,
            enriched_story=enriched_story
        )
        
        logger.info(f"[TWO-STAGE] Generation complete: {len(test_plan.test_cases)} tests")
        
        # ========================================
        # VALIDATION & RE-PROMPT IF NEEDED
        # ========================================
        logger.info("[TWO-STAGE] === VALIDATION ===")
        
        from src.ai.coverage_validator import validate_test_coverage
        validation_result = validate_test_coverage(coverage_plan, test_plan)
        
        if not validation_result.is_valid:
            logger.warning(f"[TWO-STAGE] Coverage gaps detected: {len(validation_result.gaps)} gaps")
            logger.warning(f"[TWO-STAGE] {validation_result.get_summary()}")
            
            # Try to fill gaps with a re-prompt (max 1 retry)
            if len(validation_result.gaps) > 0:
                logger.info("[TWO-STAGE] Attempting to fill coverage gaps...")
                
                additional_tests = await self._reprompt_for_gaps(
                    story_key=main_story.key,
                    story_title=main_story.summary,
                    story_description=main_story.description or "",
                    acceptance_criteria=acceptance_criteria,
                    coverage_plan=coverage_plan,
                    validation_result=validation_result,
                    confluence_docs=confluence_docs,
                    swagger_docs=swagger_docs,
                    api_specifications=api_specifications
                )
                
                if additional_tests:
                    # Merge additional tests into test plan
                    for test in additional_tests:
                        test_plan.test_cases.append(test)
                    logger.info(f"[TWO-STAGE] Added {len(additional_tests)} tests to fill gaps")
        else:
            logger.info("[TWO-STAGE] All patterns and requirements covered!")
        
        return test_plan
    
    async def _run_stage1_analysis(
        self,
        story_key: str,
        story_title: str,
        story_description: str,
        acceptance_criteria: List[str],
        confluence_docs: List[Dict],
        swagger_docs: List[Dict],
        existing_tests: List[Dict],
        api_specifications: List[Dict]
    ) -> CoveragePlan:
        """
        Run Stage 1: Analysis.
        
        Analyzes the story and RAG sources to produce a CoveragePlan.
        """
        # Build analysis prompt
        prompt = build_analysis_prompt(
            story_key=story_key,
            story_title=story_title,
            story_description=story_description,
            acceptance_criteria=acceptance_criteria,
            confluence_docs=confluence_docs,
            swagger_docs=swagger_docs,
            existing_tests=existing_tests,
            api_specifications=api_specifications
        )
        
        # Save prompt for debugging
        self._save_debug_file(story_key, "stage1_prompt", prompt)
        
        # Call AI
        response_text = await self._call_ai_api(prompt, use_json_schema=False)
        
        # Parse response
        try:
            # Extract JSON from response
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                analysis_data = json.loads(json_str)
            else:
                logger.error("[STAGE1] No JSON found in response")
                return self._create_empty_coverage_plan(story_key, story_title)
            
            # Build CoveragePlan from response
            coverage_plan = CoveragePlan(
                story_key=story_key,
                story_title=story_title,
                analysis_reasoning=analysis_data.get('analysis_reasoning', ''),
                pattern_matches=[
                    PatternMatch.from_dict(p) for p in analysis_data.get('pattern_matches', [])
                ],
                prd_requirements=[
                    PRDRequirement.from_dict(p) for p in analysis_data.get('prd_requirements', [])
                ],
                api_coverage=[
                    APICoverage.from_dict(a) for a in analysis_data.get('api_coverage', [])
                ],
                existing_test_overlap=[
                    ExistingTestOverlap.from_dict(e) for e in analysis_data.get('existing_test_overlap', [])
                ],
                test_plan=[
                    PlannedTest.from_dict(t) for t in analysis_data.get('test_plan', [])
                ]
            )
            
            return coverage_plan
            
        except json.JSONDecodeError as e:
            logger.error(f"[STAGE1] Failed to parse JSON: {e}")
            return self._create_empty_coverage_plan(story_key, story_title)
    
    async def _run_stage2_generation(
        self,
        story_key: str,
        story_title: str,
        story_description: str,
        acceptance_criteria: List[str],
        coverage_plan: CoveragePlan,
        confluence_docs: List[Dict],
        swagger_docs: List[Dict],
        api_specifications: List[Dict],
        folder_structure: list,
        enriched_story: Optional[EnrichedStory]
    ) -> TestPlan:
        """
        Run Stage 2: Generation.
        
        Generates tests from the CoveragePlan.
        """
        # Build Stage 2 prompt
        prompt = build_stage2_prompt(
            story_key=story_key,
            story_title=story_title,
            story_description=story_description,
            acceptance_criteria=acceptance_criteria,
            coverage_plan=coverage_plan.to_dict(),
            confluence_docs=confluence_docs,
            swagger_docs=swagger_docs,
            api_specifications=api_specifications
        )
        
        # Save prompt for debugging
        self._save_debug_file(story_key, "stage2_prompt", prompt)
        
        # Call AI
        response_text = await self._call_ai_api(prompt, use_json_schema=True)
        
        # Parse response
        test_plan_data, reasoning = self.response_parser.parse_ai_response(response_text)
        
        # Extract validation check
        validation_check = test_plan_data.get("validation_check")
        
        # Build TestPlan - use the enriched_story's data for main_story
        from src.models.story import JiraStory
        from datetime import datetime
        main_story = JiraStory(
            key=story_key,
            summary=story_title,
            description=story_description,
            status="Open",
            issue_type="Story",
            story_type="Story",
            priority="High",
            reporter="system",
            created=datetime.now(),
            updated=datetime.now()
        )
        
        test_plan = self.response_parser.build_test_plan(
            main_story=main_story,
            test_plan_data=test_plan_data,
            ai_model=self.model,
            folder_structure=folder_structure,
            reasoning=reasoning,
            validation_check=validation_check
        )
        
        # Validate test cases
        self.response_parser.validate_test_cases(test_plan, enriched_story=enriched_story)
        
        return test_plan
    
    async def _reprompt_for_gaps(
        self,
        story_key: str,
        story_title: str,
        story_description: str,
        acceptance_criteria: List[str],
        coverage_plan: CoveragePlan,
        validation_result: Any,
        confluence_docs: List[Dict],
        swagger_docs: List[Dict],
        api_specifications: List[Dict]
    ) -> List[Any]:
        """
        Re-prompt to fill coverage gaps.
        
        Creates a focused prompt asking for tests to cover the missing items.
        """
        try:
            # Build gap-filling prompt
            prompt = self._build_gap_filling_prompt(
                story_key=story_key,
                story_title=story_title,
                acceptance_criteria=acceptance_criteria,
                coverage_plan=coverage_plan,
                validation_result=validation_result,
                swagger_docs=swagger_docs
            )
            
            # Save prompt for debugging
            self._save_debug_file(story_key, "gap_filling_prompt", prompt)
            
            # Call AI
            response_text = await self._call_ai_api(prompt, use_json_schema=True)
            
            # Parse response
            test_plan_data, _ = self.response_parser.parse_ai_response(response_text)
            
            # Extract test cases
            test_cases_data = test_plan_data.get("test_cases", [])
            
            # Convert to TestCase objects
            from src.models.test_case import TestCase, TestStep
            additional_tests = []
            for tc_data in test_cases_data:
                steps = [
                    TestStep(
                        step_number=s.get("step_number", 1),
                        action=s.get("action", ""),
                        expected_result=s.get("expected_result", ""),
                        test_data=s.get("test_data", "{}")
                    )
                    for s in tc_data.get("steps", [])
                ]
                
                test_case = TestCase(
                    title=tc_data.get("title", ""),
                    description=tc_data.get("description", ""),
                    preconditions=tc_data.get("preconditions", ""),
                    steps=steps,
                    expected_result=tc_data.get("expected_result", ""),
                    priority=tc_data.get("priority", "high"),
                    test_type=tc_data.get("test_type", "functional"),
                    tags=tc_data.get("tags", []),
                    automation_candidate=tc_data.get("automation_candidate", True),
                    risk_level=tc_data.get("risk_level", "medium")
                )
                additional_tests.append(test_case)
            
            return additional_tests
            
        except Exception as e:
            logger.warning(f"[TWO-STAGE] Gap-filling failed: {e}")
            return []
    
    def _build_gap_filling_prompt(
        self,
        story_key: str,
        story_title: str,
        acceptance_criteria: List[str],
        coverage_plan: CoveragePlan,
        validation_result: Any,
        swagger_docs: List[Dict]
    ) -> str:
        """Build a prompt to fill coverage gaps."""
        parts = []
        
        parts.append("You are a QA engineer filling coverage gaps in a test plan.")
        parts.append("")
        parts.append(f"Story: {story_key} - {story_title}")
        parts.append("")
        parts.append("The following coverage gaps were detected. Create tests to fill them:")
        parts.append("")
        
        for gap in validation_result.gaps:
            if gap.severity == "critical":
                parts.append(f"⚠️ CRITICAL: {gap.description}")
            elif gap.severity == "high":
                parts.append(f"❗ HIGH: {gap.description}")
            else:
                parts.append(f"📋 {gap.description}")
        
        parts.append("")
        parts.append("ACCEPTANCE CRITERIA:")
        for i, ac in enumerate(acceptance_criteria, 1):
            parts.append(f"AC #{i}: {ac}")
        
        if swagger_docs:
            parts.append("")
            parts.append("API ENDPOINTS:")
            for doc in swagger_docs[:3]:
                parts.append(f"  {doc.get('service', 'Unknown')}: {doc.get('content', '')[:500]}")
        
        parts.append("")
        parts.append("Create ONLY the tests needed to fill these gaps. Output JSON with test_cases array.")
        parts.append("")
        parts.append("BANNED WORDS IN TITLES (will be rejected):")
        parts.append("- 'pagination' or 'paging' → Use 'Large dataset loads correctly' instead")
        parts.append("- 'empty state' → Use 'User can create X when none exist' instead")
        parts.append("- 'is displayed' or 'is visible' → Test the FUNCTIONALITY instead")
        parts.append("- 'User opens X' or 'User clicks X' → Describe what happens, not the navigation")
        parts.append("")
        parts.append("UI TEST NAVIGATION (MANDATORY):")
        parts.append("- Step 1 of EVERY UI test MUST include full navigation path")
        parts.append("- Format: 'Navigate to [Workspace] → [Menu] → [Item] → [Tab]'")
        parts.append("- Example: 'Navigate to Authorization Workspace → Applications → Select app-123 → Click Policies tab'")
        parts.append("- PlainID workspaces: Authorization Workspace, Identity Workspace, Orchestration Workspace, Administration Workspace")
        parts.append("- NEVER write 'Navigate to Policies tab' without the full path from workspace")
        parts.append("")
        parts.append("RULES:")
        parts.append("- Write titles that sound like a human QA wrote them")
        parts.append("- Use concrete values from the story")
        parts.append("- Each test must have at least 2 steps")
        
        return "\n".join(parts)
    
    def _validate_coverage(self, coverage_plan: CoveragePlan, test_plan: TestPlan) -> Dict[str, Any]:
        """
        Validate that all patterns and requirements are covered.
        
        Returns dict with:
        - all_covered: bool
        - gaps: list of missing items
        """
        gaps = []
        
        # Check pattern coverage
        test_texts = [f"{t.title} {t.description}".lower() for t in test_plan.test_cases]
        combined_text = " ".join(test_texts)
        
        for pattern in coverage_plan.pattern_matches:
            # Check if pattern's matched_text appears in any test
            if pattern.matched_text.lower() not in combined_text:
                gaps.append(f"Pattern not covered: {pattern.pattern_type} - {pattern.matched_text}")
        
        # Check PRD requirement coverage
        for prd in coverage_plan.prd_requirements:
            # Simple check - look for key words
            key_words = prd.requirement.lower().split()[:3]
            if not any(word in combined_text for word in key_words):
                gaps.append(f"PRD not covered: {prd.requirement}")
        
        return {
            'all_covered': len(gaps) == 0,
            'gaps': gaps
        }
    
    def _create_empty_coverage_plan(self, story_key: str, story_title: str) -> CoveragePlan:
        """Create an empty coverage plan when analysis fails."""
        return CoveragePlan(
            story_key=story_key,
            story_title=story_title,
            analysis_reasoning="Analysis failed - using fallback",
            pattern_matches=[],
            prd_requirements=[],
            api_coverage=[],
            existing_test_overlap=[],
            test_plan=[]
        )
    
    def _save_debug_file(self, story_key: str, stage: str, content: Any):
        """Save debug file for inspection."""
        try:
            from pathlib import Path
            debug_dir = Path("./debug_prompts")
            debug_dir.mkdir(exist_ok=True)
            
            if isinstance(content, str):
                file_path = debug_dir / f"{stage}_{story_key}.txt"
                file_path.write_text(content, encoding='utf-8')
            else:
                file_path = debug_dir / f"{stage}_{story_key}.json"
                file_path.write_text(json.dumps(content, indent=2), encoding='utf-8')
            
            logger.info(f"[TWO-STAGE] Saved debug file: {file_path}")
        except Exception as e:
            logger.debug(f"Failed to save debug file: {e}")
    
    async def _call_ai_api(self, prompt: str, use_json_schema: bool = False) -> str:
        """Call AI API with the prompt."""
        try:
            if self.use_openai:
                return await self._call_openai(prompt, use_json_schema)
            else:
                return await self._call_anthropic(prompt)
        except Exception as e:
            logger.error(f"AI API call failed: {e}")
            raise
    
    async def _call_openai(self, prompt: str, use_json_schema: bool = False) -> str:
        """Call OpenAI API."""
        from openai import AsyncOpenAI
        
        messages = [{"role": "user", "content": prompt}]
        
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        
        if use_json_schema:
            kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": COMPACT_JSON_SCHEMA
            }
        
        response = await self.client.chat.completions.create(**kwargs)
        return response.choices[0].message.content
    
    async def _call_anthropic(self, prompt: str) -> str:
        """Call Anthropic API."""
        from anthropic import AsyncAnthropic
        
        response = await self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text
    
    async def _enrich_story(self, main_story, story_context: StoryContext) -> Optional[EnrichedStory]:
        """Enrich story with comprehensive context."""
        try:
            cached = self.enrichment_cache.get_cached(
                story_key=main_story.key,
                story_updated=main_story.updated
            )
            
            if cached:
                logger.info(f"[TWO-STAGE] Using cached enrichment for {main_story.key}")
                return cached
            
            logger.info(f"[TWO-STAGE] Enriching story {main_story.key}...")
            enriched = await self.story_enricher.enrich_story(
                main_story=main_story,
                story_context=story_context
            )
            
            self.enrichment_cache.save_cached(enriched, main_story.updated)
            return enriched
            
        except Exception as e:
            logger.warning(f"[TWO-STAGE] Story enrichment failed: {e}")
            return None
    
    async def _retrieve_rag_context(self, main_story, story_context):
        """Retrieve RAG context."""
        try:
            from src.ai.rag_retriever import RAGRetriever
            
            logger.info("[TWO-STAGE] Retrieving RAG context...")
            rag_retriever = RAGRetriever()
            project_key = main_story.key.split('-')[0]
            
            retrieved_context = await rag_retriever.retrieve_optimized(
                story=main_story,
                project_key=project_key,
                story_context=story_context,
                max_docs_per_type=3
            )
            
            if retrieved_context and retrieved_context.has_context():
                logger.info(f"[TWO-STAGE] RAG: {retrieved_context.get_summary()}")
            
            return retrieved_context
            
        except Exception as e:
            logger.warning(f"[TWO-STAGE] RAG retrieval failed: {e}")
            return None

