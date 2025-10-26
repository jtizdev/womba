"""
AI test plan generator - the core intelligence of the system.
"""

import json
from typing import Optional, List, Dict

from loguru import logger

from src.aggregator.story_collector import StoryContext
from src.config.settings import settings
from src.models.test_plan import TestPlan, TestPlanMetadata

from .prompts_qa_focused import (
    EXPERT_QA_SYSTEM_PROMPT,
    FEW_SHOT_EXAMPLES,
    USER_FLOW_GENERATION_PROMPT,
    BUSINESS_CONTEXT_PROMPT,
    MANAGEMENT_API_CONTEXT,
    RAG_GROUNDING_PROMPT,
)


class TestPlanGenerator:
    """
    AI-powered test plan generator.
    Uses OpenAI GPT-4 or Claude 3.5 Sonnet with sophisticated prompting to generate comprehensive test plans.
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None, use_openai: bool = True):
        """
        Initialize test plan generator.

        Args:
            api_key: AI API key (defaults to settings)
            model: Model to use (defaults to settings)
            use_openai: Use OpenAI instead of Anthropic
        """
        self.use_openai = use_openai
        self.temperature = settings.temperature
        self.max_tokens = settings.max_tokens
        
        if use_openai:
            from openai import OpenAI
            self.api_key = api_key or settings.openai_api_key
            self.model = model or "gpt-4o"  # GPT-4o - best for structured JSON output
            self.client = OpenAI(api_key=self.api_key)
        else:
            from anthropic import Anthropic
            self.api_key = api_key or settings.anthropic_api_key
            self.model = model or settings.default_ai_model
            self.client = Anthropic(api_key=self.api_key)

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
            existing_tests: List of existing test cases from Zephyr (for duplicate detection)
            folder_structure: Zephyr folder structure (for suggesting test location)
            use_rag: Whether to use RAG for context retrieval (defaults to settings)

        Returns:
            TestPlan object with generated test cases

        Raises:
            Exception: If AI generation fails
        """
        main_story = context.main_story
        logger.info(f"Generating test plan for {main_story.key}: {main_story.summary}")
        
        # Calculate story complexity for dynamic test count
        complexity = self._calculate_story_complexity(context)
        logger.info(
            f"Story complexity: {complexity['level']} "
            f"(score: {complexity['score']}, suggested tests: {complexity['suggested_test_count']})"
        )
        
        # Determine if RAG should be used
        if use_rag is None:
            use_rag = settings.enable_rag
        
        # Step 1: Retrieve relevant context from RAG if enabled
        rag_context_section = ""
        if use_rag:
            try:
                from src.ai.rag_retriever import RAGRetriever
                
                logger.info("Retrieving RAG context...")
                rag_retriever = RAGRetriever()
                project_key = main_story.key.split('-')[0]
                retrieved_context = await rag_retriever.retrieve_for_story(
                    story=main_story,
                    project_key=project_key
                )
                
                if retrieved_context.has_context():
                    rag_context_section = self._build_rag_context(retrieved_context)
                    logger.info(f"RAG context retrieved: {retrieved_context.get_summary()}")
                else:
                    logger.info("No RAG context found (database may be empty)")
            except Exception as e:
                logger.warning(f"RAG retrieval failed (will continue without RAG): {e}")
                use_rag = False

        # Build the prompt with full context
        full_context = context.get("full_context_text", "")
        
        # Build complexity analysis section for the prompt
        subtasks_count = len(context.get("subtasks", [])) if isinstance(context, dict) else len(context.subtasks)
        linked_stories_count = len(context.get("linked_stories", [])) if isinstance(context, dict) else len(context.linked_stories)
        confluence_docs_count = len(context.get("confluence_docs", [])) if isinstance(context, dict) else len(context.confluence_docs)
        comments_count = len(context.get("comments", [])) if isinstance(context, dict) else len(context.comments)
        
        context_stats = f"""
=== STORY COMPLEXITY ANALYSIS ===
- Subtasks: {subtasks_count} (implementation details you MUST analyze)
- Linked Issues: {linked_stories_count} (integration points to test)
- Confluence Docs: {confluence_docs_count} (business requirements and terminology)
- Comments: {comments_count} (edge cases and clarifications)
- Complexity Score: {complexity['score']}
- Complexity Level: {complexity['level']}
- Required Test Count: {complexity['min_tests']}-{complexity['max_tests']} high-quality tests

**YOU MUST GENERATE {complexity['suggested_test_count']} HIGH-QUALITY, DEEPLY ANALYZED TESTS**

Each piece of context contains crucial information:
- Subtasks reveal WHAT is being built (APIs, fields, validations, UI changes)
- Linked issues show WHERE this integrates with other features
- Confluence docs provide WHY (business logic, workflows, terminology)
- Comments expose edge cases and special requirements

DO NOT generate generic tests. Extract specific details from each context source.
"""
        
        # Add existing tests context to check for duplicates
        # OPTIMIZATION: If RAG is enabled, we'll use RAG's semantic search instead of keyword matching
        # This is much more accurate and doesn't require fetching all tests via API
        existing_tests_context = ""
        if use_rag and rag_context_section:
            # RAG will provide similar existing tests via semantic search (see rag_context_section)
            logger.info("Using RAG for existing tests (skipping redundant Zephyr API call)")
        elif existing_tests:
            # Fallback to keyword-based matching if RAG is disabled
            logger.info(f"RAG disabled, using keyword matching on {len(existing_tests)} tests")
            existing_tests_context = "\n=== EXISTING TEST CASES IN ZEPHYR (Check for Duplicates!) ===\n"
            existing_tests_context += "(IMPORTANT: DO NOT create tests that already exist. If a test already covers the flow, mention it in 'related_existing_tests'.)\n\n"
            
            # Show relevant tests (search for keywords from story)
            story_keywords = main_story.summary.lower().split()
            relevant_tests = []
            
            for test in existing_tests[:500]:  # Check first 500 most recent
                test_name = test.get('name', '').lower()
                test_obj = (test.get('objective') or '').lower()  # Handle None
                
                # Check if test is relevant to this story
                if any(keyword in test_name or keyword in test_obj for keyword in story_keywords if len(keyword) > 3):
                    relevant_tests.append(test)
                    if len(relevant_tests) >= 50:  # Show top 50 relevant
                        break
            
            if relevant_tests:
                existing_tests_context += f"Found {len(relevant_tests)} potentially relevant existing tests:\n\n"
                for test in relevant_tests[:20]:  # Show top 20
                    existing_tests_context += f"- {test.get('key', 'N/A')}: {test.get('name', 'N/A')}\n"
                    if test.get('objective'):
                        existing_tests_context += f"  Description: {test['objective'][:150]}...\n"
            else:
                existing_tests_context += f"Searched {len(existing_tests)} tests, none seem directly related.\n"
        
        # Add engineering tasks context
        tasks_context = ""
        subtasks = context.get("subtasks", [])
        if subtasks:
            tasks_context = "\n=== ENGINEERING TASKS FOR THIS STORY ===\n"
            tasks_context += "(Use these to identify regression test scenarios)\n\n"
            for task in subtasks:
                tasks_context += f"- {task.key}: {task.summary}\n"
                if task.description:
                    desc = task.description[:200] if len(task.description) > 200 else task.description
                    tasks_context += f"  Details: {desc}\n"
        
        # Add folder structure context for smart placement
        folder_context = ""
        if folder_structure:
            folder_context = "\n=== ZEPHYR TEST FOLDER STRUCTURE ===\n"
            folder_context += "(Suggest the most appropriate folder based on the feature area)\n\n"
            for folder in folder_structure[:15]:  # Show top folders
                folder_name = folder.get('name', 'Unknown')
                folder_id = folder.get('id', 'N/A')
                folder_context += f"- {folder_name} (ID: {folder_id})\n"
                # Show subfolders if they exist
                if folder.get('folders'):
                    for subfolder in folder['folders'][:5]:
                        subfolder_name = subfolder.get('name', 'Unknown')
                        folder_context += f"  └── {subfolder_name}\n"
        
        # Build Figma context (if available)
        figma_context = ""
        # TODO: Integrate Figma client to extract UI elements
        # For now, placeholder
        
        # Build the final prompt with RAG grounding if available
        if use_rag and rag_context_section:
            # Add RAG grounding at the top for emphasis
            prompt = RAG_GROUNDING_PROMPT + "\n\n" + rag_context_section + "\n\n" + context_stats + "\n\n"
        else:
            prompt = context_stats + "\n\n"
        
        prompt += USER_FLOW_GENERATION_PROMPT.format(
            business_context=BUSINESS_CONTEXT_PROMPT,
            management_api_context=MANAGEMENT_API_CONTEXT,
            context=full_context,
            existing_tests_context=existing_tests_context,
            tasks_context=tasks_context,
            folder_context=folder_context,
            figma_context=figma_context or "(No Figma designs available)",
            num_subtasks=subtasks_count,
            num_linked_issues=linked_stories_count,
            num_confluence_docs=confluence_docs_count,
            num_comments=comments_count,
            suggested_test_count=complexity['suggested_test_count'],
            complexity_score=complexity['score'],
            min_tests=complexity['min_tests'],
            max_tests=complexity['max_tests']
        )

        # Add few-shot examples for better quality
        prompt = FEW_SHOT_EXAMPLES + "\n\n" + prompt

        try:
            # Call AI API
            if self.use_openai:
                logger.info(f"Calling OpenAI API with model: {self.model}")
                response = self.client.chat.completions.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    messages=[
                        {"role": "system", "content": EXPERT_QA_SYSTEM_PROMPT},
                        {"role": "user", "content": prompt}
                    ],
                )
                response_text = response.choices[0].message.content
            else:
                logger.info(f"Calling Claude API with model: {self.model}")
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    system=EXPERT_QA_SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": prompt}],
                )
                response_text = response.content[0].text
            
            logger.debug(f"AI Response received: {len(response_text)} characters")

            # Parse JSON response
            test_plan_data = self._parse_ai_response(response_text)

            # Build TestPlan object
            test_plan = self._build_test_plan(
                main_story=main_story,
                test_plan_data=test_plan_data,
                ai_model=self.model,
            )

            logger.info(
                f"Successfully generated {len(test_plan.test_cases)} test cases for {main_story.key}"
            )
            
            # Auto-index test plan for future RAG retrieval if enabled
            if use_rag and settings.rag_auto_index:
                try:
                    from src.ai.context_indexer import ContextIndexer
                    
                    logger.info("Auto-indexing test plan for future RAG retrieval...")
                    indexer = ContextIndexer()
                    # Run indexing in background (don't block test generation)
                    import asyncio
                    asyncio.create_task(indexer.index_test_plan(test_plan, context))
                except Exception as e:
                    logger.warning(f"Auto-indexing failed (non-critical): {e}")
            
            return test_plan

        except Exception as e:
            logger.error(f"Failed to generate test plan: {e}")
            raise

    def _parse_ai_response(self, response_text: str) -> dict:
        """
        Parse AI response text into structured data.

        Args:
            response_text: Raw response from AI

        Returns:
            Parsed dictionary

        Raises:
            ValueError: If response cannot be parsed
        """
        # Try to find JSON in the response (AI might add explanation text)
        json_start = response_text.find("{")
        json_end = response_text.rfind("}") + 1

        if json_start == -1 or json_end == 0:
            raise ValueError("No JSON found in AI response")

        json_text = response_text[json_start:json_end]

        try:
            data = json.loads(json_text)
            return data
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {e}")
            logger.error(f"Response text: {json_text[:500]}")
            raise ValueError(f"Invalid JSON in AI response: {e}")

    def _build_test_plan(
        self, main_story: any, test_plan_data: dict, ai_model: str
    ) -> TestPlan:
        """
        Build TestPlan object from parsed AI data.

        Args:
            main_story: The main Jira story
            test_plan_data: Parsed test plan data from AI
            ai_model: AI model used

        Returns:
            TestPlan object
        """
        from src.models.test_case import TestCase, TestStep

        # Extract test cases
        test_cases = []
        for tc_data in test_plan_data.get("test_cases", []):
            # Parse steps
            steps = [
                TestStep(
                    step_number=step.get("step_number", idx + 1),
                    action=step.get("action", ""),
                    expected_result=step.get("expected_result", ""),
                    test_data=step.get("test_data"),
                )
                for idx, step in enumerate(tc_data.get("steps", []))
            ]

            # Create test case
            test_case = TestCase(
                title=tc_data.get("title", "Untitled Test"),
                description=tc_data.get("description", ""),
                preconditions=tc_data.get("preconditions"),
                steps=steps,
                expected_result=tc_data.get("expected_result", ""),
                priority=tc_data.get("priority", "medium"),
                test_type=tc_data.get("test_type", "functional"),
                tags=tc_data.get("tags", []),
                automation_candidate=tc_data.get("automation_candidate", True),
                risk_level=tc_data.get("risk_level", "medium"),
            )
            test_cases.append(test_case)

        # Count test types
        edge_case_count = sum(
            1 for tc in test_cases if tc.test_type == "edge_case" or "edge" in tc.tags
        )
        integration_test_count = sum(
            1 for tc in test_cases if tc.test_type == "integration"
        )

        # Build metadata
        metadata = TestPlanMetadata(
            ai_model=ai_model,
            source_story_key=main_story.key,
            total_test_cases=len(test_cases),
            edge_case_count=edge_case_count,
            integration_test_count=integration_test_count,
            confidence_score=0.9,  # Could be computed based on various factors
        )

        # Extract suggested folder (with fallback logic)
        suggested_folder = test_plan_data.get("suggested_folder")
        
        # FALLBACK: If AI didn't suggest folder, extract dynamically from story
        if not suggested_folder:
            suggested_folder = self._extract_folder_from_story(main_story, folder_structure)
            logger.warning(f"AI didn't suggest folder, using dynamic fallback: {suggested_folder}")
        
        # Build test plan
        test_plan = TestPlan(
            story=main_story,
            test_cases=test_cases,
            metadata=metadata,
            summary=test_plan_data.get("summary", ""),
            coverage_analysis=test_plan_data.get("coverage_analysis"),
            risk_assessment=test_plan_data.get("risk_assessment"),
            dependencies=test_plan_data.get("dependencies", []),
            estimated_execution_time=test_plan_data.get("estimated_execution_time"),
            suggested_folder=suggested_folder,
        )

        return test_plan

    def _build_rag_context(self, retrieved_context) -> str:
        """
        Build RAG context section from retrieved documents.
        
        Args:
            retrieved_context: RetrievedContext object from RAG retriever
            
        Returns:
            Formatted RAG context string
        """
        sections = []
        sections.append("=" * 80)
        sections.append("=== RETRIEVED COMPANY-SPECIFIC CONTEXT (RAG) ===")
        sections.append("=" * 80)
        sections.append("\nThe following context has been retrieved from your company's actual data.")
        sections.append("Use this as your PRIMARY reference for generating tests.\n")
        
        # Similar test plans
        if retrieved_context.similar_test_plans:
            sections.append("\n--- SIMILAR PAST TEST PLANS (Learn patterns from these) ---\n")
            for i, doc in enumerate(retrieved_context.similar_test_plans[:3], 1):
                sections.append(f"\n{i}. Test Plan Example:")
                sections.append(f"   Similarity: {1 - doc.get('distance', 0):.2f}")
                sections.append(f"   {doc.get('document', '')[:800]}")  # First 800 chars
                sections.append("   " + "-" * 70)
        
        # Similar Confluence docs
        if retrieved_context.similar_confluence_docs:
            sections.append("\n--- COMPANY DOCUMENTATION (Use this terminology) ---\n")
            for i, doc in enumerate(retrieved_context.similar_confluence_docs[:5], 1):
                sections.append(f"\n{i}. Document: {doc.get('metadata', {}).get('title', 'Unknown')}")
                sections.append(f"   Similarity: {1 - doc.get('distance', 0):.2f}")
                sections.append(f"   {doc.get('document', '')[:600]}")  # First 600 chars
                sections.append("   " + "-" * 70)
        
        # Similar stories
        if retrieved_context.similar_jira_stories:
            sections.append("\n--- SIMILAR PAST STORIES (Apply same approach) ---\n")
            for i, doc in enumerate(retrieved_context.similar_jira_stories[:5], 1):
                sections.append(f"\n{i}. Story: {doc.get('metadata', {}).get('story_key', 'Unknown')}")
                sections.append(f"   {doc.get('document', '')[:400]}")  # First 400 chars
                sections.append("   " + "-" * 70)
        
        # Similar existing tests
        if retrieved_context.similar_existing_tests:
            sections.append("\n--- EXISTING TESTS (Match this style, avoid duplicates) ---\n")
            for i, doc in enumerate(retrieved_context.similar_existing_tests[:10], 1):
                sections.append(f"\n{i}. Test: {doc.get('metadata', {}).get('test_name', 'Unknown')}")
                sections.append(f"   {doc.get('document', '')[:300]}")  # First 300 chars
                sections.append("   " + "-" * 70)
        
        sections.append("\n" + "=" * 80)
        sections.append("END OF RETRIEVED CONTEXT - Use the patterns above as your guide")
        sections.append("=" * 80 + "\n")
        
        return "\n".join(sections)
    
    def _extract_folder_from_story(
        self, main_story: any, folder_structure: List[Dict]
    ) -> str:
        """
        Dynamically extract folder from story by analyzing:
        1. Story component/labels
        2. Story summary keywords
        3. Existing folder structure
        
        Args:
            main_story: The main Jira story
            folder_structure: List of folders from Zephyr
            
        Returns:
            Suggested folder path
        """
        summary_lower = main_story.summary.lower()
        description_lower = (main_story.description or "").lower()
        combined_text = f"{summary_lower} {description_lower}"
        
        # Extract all folder names from structure
        folder_names = []
        for folder in folder_structure:
            folder_names.append(folder.get('name', ''))
            if folder.get('folders'):
                for subfolder in folder['folders']:
                    folder_names.append(f"{folder.get('name')}/{subfolder.get('name')}")
        
        # Score each folder based on keyword matches
        folder_scores = {}
        for folder_name in folder_names:
            if not folder_name:
                continue
            
            folder_lower = folder_name.lower()
            score = 0
            
            # Check for keyword matches
            folder_keywords = folder_lower.replace('/', ' ').split()
            for keyword in folder_keywords:
                if len(keyword) > 3:  # Ignore short words
                    if keyword in combined_text:
                        score += 2  # Strong match
                    elif any(keyword in word for word in combined_text.split()):
                        score += 1  # Partial match
            
            if score > 0:
                folder_scores[folder_name] = score
        
        # Return folder with highest score
        if folder_scores:
            best_folder = max(folder_scores, key=folder_scores.get)
            logger.info(f"Dynamic folder selection: {best_folder} (score: {folder_scores[best_folder]})")
            return best_folder
        
        # Last resort: extract component from summary or use General
        # Look for patterns like "(Component)" or "- Component -"
        import re
        component_match = re.search(r'\(([A-Z][A-Za-z\s]+)\)', main_story.summary)
        if component_match:
            component = component_match.group(1).strip()
            return f"{component}/Feature Tests"
        
        # Check for common patterns in first part of summary
        parts = main_story.summary.split('-')
        if len(parts) > 1:
            potential_component = parts[0].strip()
            if len(potential_component) < 20:  # Likely a component name
                return f"{potential_component}/Feature Tests"
        
        return "General/Automated Tests"

    def _calculate_story_complexity(self, context: StoryContext) -> dict:
        """
        Calculate story complexity score and suggest appropriate test count.
        
        Scoring algorithm:
        - Subtasks × 2 (each subtask represents implementation work to test)
        - Linked issues × 1.5 (integration points and dependencies)
        - Confluence docs × 1 (business context and requirements)
        - Comments / 3 (discussion and edge cases)
        
        Complexity levels:
        - Simple (< 5): 4-6 tests
        - Medium (5-12): 6-10 tests
        - Complex (12+): 10-15 tests
        
        Args:
            context: StoryContext with all aggregated information
            
        Returns:
            dict with score, level, suggested_test_count, min_tests, max_tests
        """
        # Handle both dict and StoryContext object
        if isinstance(context, dict):
            subtasks = context.get("subtasks", [])
            linked_stories = context.get("linked_stories", [])
            confluence_docs = context.get("confluence_docs", [])
            comments = context.get("comments", [])
        else:
            subtasks = context.subtasks
            linked_stories = context.linked_stories
            confluence_docs = context.confluence_docs
            comments = context.comments
        
        # Calculate weighted score
        subtasks_score = len(subtasks) * 2
        linked_issues_score = len(linked_stories) * 1.5
        confluence_score = len(confluence_docs) * 1
        comments_score = len(comments) / 3
        
        total_score = subtasks_score + linked_issues_score + confluence_score + comments_score
        
        # Determine complexity level and test count range
        if total_score < 5:
            level = "Simple"
            min_tests = 4
            max_tests = 6
            suggested = 5
        elif total_score < 12:
            level = "Medium"
            min_tests = 6
            max_tests = 10
            suggested = 8
        else:
            level = "Complex"
            min_tests = 10
            max_tests = 15
            # For very complex stories, scale up further
            if total_score > 20:
                max_tests = 20
                suggested = 15
            else:
                suggested = 12
        
        return {
            "score": round(total_score, 1),
            "level": level,
            "suggested_test_count": suggested,
            "min_tests": min_tests,
            "max_tests": max_tests,
            "breakdown": {
                "subtasks": round(subtasks_score, 1),
                "linked_issues": round(linked_issues_score, 1),
                "confluence": round(confluence_score, 1),
                "comments": round(comments_score, 1)
            }
        }


