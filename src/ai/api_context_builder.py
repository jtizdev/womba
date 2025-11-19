"""
API and UI context builder with fallback flow.

Builds APIContext (API + UI specifications) using a fallback approach:
1. Extract from story text directly
2. Fall back to Swagger RAG collection if incomplete
3. Fall back to GitLab MCP if Swagger has nothing

This keeps the enriched story focused on Jira-native data while building
comprehensive API/UI specs separately for use in prompts.
"""

from typing import List
from loguru import logger

from src.models.story import JiraStory
from src.models.enriched_story import APIContext, APISpec, UISpec
from src.aggregator.story_collector import StoryContext
from src.ai.swagger_extractor import SwaggerExtractor
from src.ai.rag_store import RAGVectorStore
from src.config.settings import settings
import re


class APIContextBuilder:
    """Builds API context with fallback flow: story → swagger → MCP."""
    
    def __init__(self):
        """Initialize builder with dependencies."""
        self.swagger_extractor = SwaggerExtractor()
        self.rag_store = RAGVectorStore()
    
    async def build_api_context(
        self,
        main_story: JiraStory,
        story_context: StoryContext,
        combined_text: str = None
    ) -> APIContext:
        """
        Build API and UI context using fallback flow.
        
        Args:
            main_story: Primary story
            story_context: Story context with subtasks, linked stories
            combined_text: Combined text from main story + linked stories (optional, will be built if not provided)
            
        Returns:
            APIContext with api_specifications, ui_specifications, and extraction_flow
        """
        logger.info(f"Building API context for {main_story.key}")
        
        # If combined_text not provided, build it from story + subtasks + linked stories
        if not combined_text:
            subtasks = story_context.get("subtasks", [])
            linked_stories = story_context.get("linked_stories", [])
            
            # Build text including main story, subtasks, and linked stories
            parts = [
                f"Story: {main_story.summary}",
                main_story.description or "",
                main_story.acceptance_criteria or ""
            ]
            
            # Include subtask descriptions (where "we use" patterns are!)
            for subtask in subtasks:
                parts.append(f"\nSubtask: {subtask.summary}")
                if subtask.description:
                    parts.append(subtask.description)
            
            # Include linked stories
            for story in linked_stories:
                parts.append(f"\nLinked Story: {story.summary}")
                if story.description:
                    parts.append(story.description)
            
            combined_text = "\n".join(parts)
        
        api_specs = []
        extraction_flow_parts = []
        
        # Step 1: Extract from story text directly
        logger.debug("Step 1: Extracting endpoints from story text")
        api_specs_from_story = await self.swagger_extractor.extract_endpoints(
            story_text=combined_text,  # Now includes subtasks with "we use" patterns!
            project_key=main_story.key.split('-')[0],
            subtask_texts=[]  # Already included in combined_text
        )
        logger.info(f"  Found {len(api_specs_from_story)} endpoints in story")
        
        if api_specs_from_story:
            # Filter out example endpoints
            api_specs_from_story = await self._filter_example_endpoints(
                combined_text=combined_text,
                endpoints=api_specs_from_story,
                story_key=main_story.key
            )
            logger.info(f"  After filtering: {len(api_specs_from_story)} endpoints remain")
            api_specs.extend(api_specs_from_story)
            extraction_flow_parts.append("story")
        
        # Step 2: Fall back to Swagger RAG if incomplete
        if not api_specs:
            logger.info("Step 2: No endpoints from story, querying Swagger RAG")
            try:
                rag_results = await self.rag_store.retrieve_similar(
                    collection_name="swagger_docs",
                    query_text=f"{main_story.summary} API endpoints",
                    top_k=5
                )
                logger.debug(f"  Retrieved {len(rag_results)} Swagger docs from RAG")
                
                # Parse endpoints from Swagger RAG results
                for result in rag_results:
                    content = result.get("content", "")
                    # Extract endpoints from swagger content
                    specs = self._parse_swagger_content(content)
                    if specs:
                        api_specs.extend(specs)
                        logger.debug(f"  Extracted {len(specs)} endpoints from Swagger")
                
                if api_specs:
                    extraction_flow_parts.append("swagger")
            except Exception as e:
                logger.warning(f"Swagger RAG fallback failed: {e}")
        
        # Step 3: Fall back to GitLab MCP if still nothing
        if not api_specs:
            logger.info("Step 3: No endpoints from Swagger, trying GitLab MCP")
            try:
                from src.ai.gitlab_fallback_extractor import GitLabFallbackExtractor
                gitlab_extractor = GitLabFallbackExtractor()
                api_specs = await gitlab_extractor.extract_from_codebase(
                    story_key=main_story.key,
                    story_text=combined_text,
                    project_key=main_story.key.split('-')[0]
                )
                logger.info(f"  GitLab MCP found {len(api_specs)} endpoints")
                if api_specs:
                    # Filter to keep only relevant endpoints
                    api_specs = await self._filter_relevant_endpoints(
                        endpoints=api_specs,
                        story_key=main_story.key,
                        story_text=combined_text
                    )
                    logger.info(f"  After relevance filtering: {len(api_specs)} relevant endpoints")
                    if api_specs:
                        extraction_flow_parts.append("mcp")
                        
                        # Step 4: Analyze codebase for supplementary test scenarios
                        await self._integrate_code_analysis(
                            api_specs=api_specs,
                            main_story=main_story,
                            story_context=story_context,
                            combined_text=combined_text
                        )
            except Exception as e:
                logger.warning(f"GitLab MCP fallback failed: {e}")
        
        # Extract UI specifications (from story + RAG)
        ui_specs = await self._extract_ui_specifications(main_story, story_context, combined_text)
        
        # Build extraction flow description
        extraction_flow = "→".join(extraction_flow_parts) if extraction_flow_parts else "none"
        
        context = APIContext(
            api_specifications=api_specs,
            ui_specifications=ui_specs,
            extraction_flow=extraction_flow
        )
        
        logger.info(f"API context built: {len(api_specs)} endpoints, {len(ui_specs)} UI specs, flow={extraction_flow}")
        return context
    
    async def _filter_example_endpoints(
        self,
        combined_text: str,
        endpoints: List[APISpec],
        story_key: str
    ) -> List[APISpec]:
        """Use AI to determine if endpoints are actual requirements or just examples/references."""
        
        if not endpoints:
            return []
        
        # Use AI to classify endpoints
        try:
            from src.ai.generation.ai_client_factory import AIClientFactory
            
            client, model, use_openai = AIClientFactory.create_client(
                use_openai=True,
                model="gpt-4o-mini"
            )
            
            endpoint_list = "\n".join([
                f"{i+1}. {' '.join(ep.http_methods)} {ep.endpoint_path}"
                for i, ep in enumerate(endpoints)
            ])
            
            prompt = f"""Analyze these endpoints extracted from story {story_key}. Determine which are ACTUAL REQUIREMENTS vs EXAMPLES/REFERENCES.

Story Context:
{combined_text[:3000]}

Extracted Endpoints:
{endpoint_list}

For each endpoint, determine:
- ACTUAL: This endpoint is what needs to be created/tested for this story
- EXAMPLE: This endpoint is just an example/reference showing how similar endpoints work elsewhere
- REFERENCE: This endpoint is mentioned for comparison but not what this story implements

Respond with ONLY a JSON array, one entry per endpoint:
[
  {{"number": 1, "endpoint": "GET /policy-mgmt/...", "classification": "ACTUAL|EXAMPLE|REFERENCE", "reason": "brief explanation"}},
  ...
]

Be strict: If endpoints are listed together with phrases like "for X we use" or "similar to" or "idea: maybe", they are likely EXAMPLES."""

            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=1000
            )
            
            import json
            content = response.choices[0].message.content or ""
            
            # Extract JSON from response
            json_start = content.find('[')
            json_end = content.rfind(']') + 1
            if json_start != -1 and json_end > json_start:
                classifications = json.loads(content[json_start:json_end])
                
                kept = []
                filtered_out = []
                
                for i, ep in enumerate(endpoints):
                    # Find matching classification
                    classification = None
                    for cls in classifications:
                        if cls.get("number") == i + 1 or ep.endpoint_path in cls.get("endpoint", ""):
                            classification = cls.get("classification", "").upper()
                            break
                    
                    if classification in ["ACTUAL"]:
                        kept.append(ep)
                        logger.debug(f"  ✅ KEPT ({classification}): {ep.endpoint_path}")
                    else:
                        filtered_out.append(ep.endpoint_path)
                        logger.info(f"  ❌ FILTERED ({classification or 'UNKNOWN'}): {ep.endpoint_path}")
                
                if filtered_out:
                    logger.info(f"AI filtered {len(filtered_out)} example/reference endpoints")
                
                # Return kept endpoints (even if empty - empty means fallback to MCP)
                return kept
            else:
                logger.warning("AI response did not contain valid JSON, keeping all endpoints")
                return endpoints
                
        except Exception as e:
            logger.warning(f"AI filtering failed: {e}, keeping all endpoints")
            return endpoints
    
    async def _filter_relevant_endpoints(
        self,
        endpoints: List[APISpec],
        story_key: str,
        story_text: str
    ) -> List[APISpec]:
        """
        Filter MCP-found endpoints to keep only those relevant to the story.
        
        Uses AI to classify endpoints as:
        - RELEVANT: Directly implements the story feature
        - RELATED: Related but not the primary endpoint
        - UNRELATED: Not relevant to this story
        """
        if not endpoints:
            return []
        
        # If only one endpoint, likely relevant
        if len(endpoints) == 1:
            logger.debug(f"Only one MCP endpoint found, assuming relevant: {endpoints[0].endpoint_path}")
            return endpoints
        
        try:
            from src.ai.generation.ai_client_factory import AIClientFactory
            
            client, model, use_openai = AIClientFactory.create_client(
                use_openai=True,
                model="gpt-4o-mini"
            )
            
            endpoint_list = "\n".join([
                f"{i+1}. {' '.join(ep.http_methods)} {ep.endpoint_path}"
                for i, ep in enumerate(endpoints)
            ])
            
            story_snippet = ' '.join(story_text.split()[:500])  # First 500 words
            
            prompt = f"""Analyze these endpoints found via GitLab MCP for story {story_key}. Determine which are RELEVANT to this story.

Story Context:
{story_snippet}

Endpoints Found:
{endpoint_list}

For each endpoint, classify as:
- RELEVANT: This endpoint directly implements the feature described in the story
- RELATED: This endpoint is related but not the primary implementation
- UNRELATED: This endpoint is not relevant to this story

Respond with ONLY a JSON array:
[
  {{"number": 1, "endpoint": "GET /policy-mgmt/...", "classification": "RELEVANT|RELATED|UNRELATED", "reason": "brief explanation"}},
  ...
]

Be strict: Only mark endpoints as RELEVANT if they directly implement the story feature."""

            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=1000
            )
            
            import json
            content = response.choices[0].message.content or ""
            
            # Extract JSON from response
            json_start = content.find('[')
            json_end = content.rfind(']') + 1
            if json_start != -1 and json_end > json_start:
                classifications = json.loads(content[json_start:json_end])
                
                relevant = []
                related = []
                
                for i, ep in enumerate(endpoints):
                    # Find matching classification
                    classification = None
                    for cls in classifications:
                        if cls.get("number") == i + 1 or ep.endpoint_path in cls.get("endpoint", ""):
                            classification = cls.get("classification", "").upper()
                            break
                    
                    if classification == "RELEVANT":
                        relevant.append(ep)
                        logger.info(f"  ✅ RELEVANT: {ep.endpoint_path}")
                    elif classification == "RELATED":
                        related.append(ep)
                        logger.debug(f"  ⚠️  RELATED: {ep.endpoint_path}")
                    else:
                        logger.info(f"  ❌ UNRELATED: {ep.endpoint_path}")
                
                # Return RELEVANT endpoints, or RELATED if no RELEVANT found
                if relevant:
                    logger.info(f"Found {len(relevant)} relevant endpoint(s), {len(related)} related, {len(endpoints) - len(relevant) - len(related)} unrelated")
                    return relevant
                elif related:
                    logger.info(f"No relevant endpoints found, using {len(related)} related endpoint(s)")
                    return related
                else:
                    logger.warning("No relevant or related endpoints found, keeping all")
                    return endpoints
            else:
                logger.warning("AI response did not contain valid JSON, keeping all endpoints")
                return endpoints
                
        except Exception as e:
            logger.warning(f"Relevance filtering failed: {e}, keeping all endpoints")
            return endpoints
    
    async def _deduplicate_scenarios(
        self,
        story_scenarios: List[str],
        code_scenarios: List[str]
    ) -> List[str]:
        """
        Remove redundant code-based scenarios that are already covered by story-based scenarios.
        
        Uses semantic similarity to identify duplicates.
        
        Args:
            story_scenarios: Scenarios derived from story requirements, AC, functional points
            code_scenarios: Scenarios found in codebase analysis
            
        Returns:
            List of unique code-based scenarios (duplicates removed)
        """
        if not code_scenarios:
            return []
        
        if not story_scenarios:
            # No story scenarios to compare against, return all code scenarios
            return code_scenarios
        
        try:
            from src.ai.embedding_service import EmbeddingService
            
            embedding_service = EmbeddingService()
            
            # Generate embeddings for story scenarios
            story_embeddings = await embedding_service.embed_texts(story_scenarios)
            if not story_embeddings:
                logger.warning("Failed to generate embeddings for story scenarios")
                return code_scenarios
            
            # Generate embeddings for code scenarios
            code_embeddings = await embedding_service.embed_texts(code_scenarios)
            if not code_embeddings:
                logger.warning("Failed to generate embeddings for code scenarios")
                return code_scenarios
            
            # Calculate similarity between each code scenario and all story scenarios
            unique_scenarios = []
            threshold = 0.85  # Similarity threshold for duplicates
            
            import numpy as np
            
            for i, code_scenario in enumerate(code_scenarios):
                code_embedding = code_embeddings[i]
                
                # Check similarity against all story scenarios
                is_duplicate = False
                max_similarity = 0.0
                
                for story_embedding in story_embeddings:
                    # Calculate cosine similarity
                    similarity = np.dot(code_embedding, story_embedding) / (
                        np.linalg.norm(code_embedding) * np.linalg.norm(story_embedding)
                    )
                    max_similarity = max(max_similarity, similarity)
                    
                    if similarity > threshold:
                        is_duplicate = True
                        logger.debug(f"Filtered duplicate scenario (similarity {similarity:.2f}): {code_scenario[:50]}...")
                        break
                
                if not is_duplicate:
                    unique_scenarios.append(code_scenario)
                    logger.debug(f"Kept unique scenario (max similarity {max_similarity:.2f}): {code_scenario[:50]}...")
            
            logger.info(f"Deduplication: {len(code_scenarios)} code scenarios -> {len(unique_scenarios)} unique (filtered {len(code_scenarios) - len(unique_scenarios)} duplicates)")
            return unique_scenarios
            
        except Exception as e:
            logger.warning(f"Deduplication failed: {e}, keeping all code scenarios")
            return code_scenarios
    
    async def _integrate_code_analysis(
        self,
        api_specs: List[APISpec],
        main_story: JiraStory,
        story_context: StoryContext,
        combined_text: str
    ) -> None:
        """
        Integrate codebase analysis with deduplication for each endpoint.
        
        For each relevant endpoint:
        1. Analyze codebase for test patterns
        2. Extract story-based scenarios from AC and functional points
        3. Deduplicate code-based scenarios against story-based
        4. Attach unique suggestions to APISpec objects
        """
        if not api_specs:
            return
        
        logger.info(f"Integrating codebase analysis for {len(api_specs)} endpoint(s)")
        
        # Extract story-based scenarios from acceptance criteria and functional points
        story_scenarios = []
        
        # From acceptance criteria
        if main_story.acceptance_criteria:
            for ac in main_story.acceptance_criteria:
                # Convert AC to test scenario format
                story_scenarios.append(f"Verify {ac}")
        
        # From subtasks (engineering tasks often contain test scenarios)
        subtasks = story_context.get("subtasks", [])
        for subtask in subtasks:
            if subtask.description:
                # Look for test-related keywords in subtask descriptions
                import re
                test_keywords = re.findall(
                    r'(?:test|verify|validate|check|ensure).*?(?:when|with|for|that)\s+([^.!?]+)',
                    subtask.description,
                    re.IGNORECASE
                )
                for keyword_match in test_keywords[:3]:  # Limit per subtask
                    story_scenarios.append(f"Test {keyword_match.strip()}")
        
        # From story text: look for functional requirements patterns
        import re
        functional_patterns = re.findall(
            r'(?:should|must|need to|will|shall)\s+([^.!?]+)',
            combined_text,
            re.IGNORECASE
        )
        for pattern in functional_patterns[:10]:  # Limit to 10
            clean_pattern = pattern.strip()
            if len(clean_pattern) > 10:  # Only meaningful patterns
                story_scenarios.append(f"Test {clean_pattern}")
        
        logger.debug(f"Extracted {len(story_scenarios)} story-based scenarios")
        
        # Analyze codebase for each endpoint
        for api_spec in api_specs:
            try:
                from src.ai.gitlab_fallback_extractor import GitLabFallbackExtractor
                gitlab_extractor = GitLabFallbackExtractor()
                
                # Analyze codebase for this endpoint
                code_analysis = await gitlab_extractor._analyze_codebase_for_tests(
                    endpoint=api_spec,
                    story_key=main_story.key,
                    story_text=combined_text
                )
                
                code_scenarios = code_analysis.get("suggested_test_scenarios", [])
                code_examples = code_analysis.get("code_examples", {})
                
                if code_scenarios:
                    # Deduplicate against story scenarios
                    unique_scenarios = await self._deduplicate_scenarios(
                        story_scenarios=story_scenarios,
                        code_scenarios=code_scenarios
                    )
                    
                    if unique_scenarios:
                        api_spec.suggested_test_scenarios = unique_scenarios
                        logger.info(f"  Attached {len(unique_scenarios)} unique test scenarios to {api_spec.endpoint_path}")
                
                if code_examples:
                    api_spec.code_examples = code_examples
                    logger.debug(f"  Attached code examples to {api_spec.endpoint_path}")
                    
            except Exception as e:
                logger.warning(f"Code analysis integration failed for {api_spec.endpoint_path}: {e}")
                continue
    
    def _parse_swagger_content(self, content: str) -> List[APISpec]:
        """Parse API endpoints from Swagger documentation."""
        specs = []
        
        # Look for endpoint patterns in Swagger content
        # GET /path/to/endpoint
        endpoint_pattern = r'(GET|POST|PUT|PATCH|DELETE|HEAD)\s+(/[^\s\n]+)'
        
        for match in re.finditer(endpoint_pattern, content, re.IGNORECASE):
            method, path = match.groups()
            specs.append(APISpec(
                endpoint_path=path,
                http_methods=[method.upper()],
                service_name="swagger_rag"
            ))
        
        # Deduplicate by endpoint_path
        seen = set()
        unique_specs = []
        for spec in specs:
            if spec.endpoint_path not in seen:
                unique_specs.append(spec)
                seen.add(spec.endpoint_path)
        
        return unique_specs
    
    async def _extract_ui_specifications(
        self,
        main_story: JiraStory,
        story_context: StoryContext,
        combined_text: str
    ) -> List[UISpec]:
        """
        Extract UI navigation and access specifications.
        
        Sources:
        1. Story description (explicit navigation paths)
        2. RAG similar UI patterns
        """
        ui_specs = []
        
        # Pattern 1: Explicit navigation in story
        nav_patterns = [
            r'navigate\s+to\s+([^.]+?)(?:\s+→\s+([^.]+?))?(?:\s+→\s+([^.]+?))?',
            r'from\s+(?:the\s+)?([^,]+?),?\s+click\s+(?:the\s+)?([^.]+)',
            r'(?:click|select|open)\s+(?:the\s+)?([^.]+?)\s+(?:tab|menu|button)',
            r'in\s+(?:the\s+)?([^,]+?),?\s+(?:click|select)\s+([^.]+)',
        ]
        
        for pattern in nav_patterns:
            matches = re.finditer(pattern, combined_text, re.IGNORECASE)
            for match in matches:
                parts = [p.strip() for p in match.groups() if p]
                if parts:
                    nav_path = " → ".join(parts)
                    ui_specs.append(UISpec(
                        feature_name=main_story.summary,
                        navigation_path=nav_path,
                        access_method=f"Navigate: {nav_path}",
                        ui_elements=parts,
                        source="story_text"
                    ))
        
        # Pattern 2: Query RAG for similar UI patterns
        try:
            rag_results = await self.rag_store.retrieve_similar(
                collection_name="test_plans",
                query_text=f"{main_story.summary} UI navigation",
                top_k=3
            )
            for result in rag_results:
                content = result.get("content", "")
                nav_matches = re.findall(
                    r'Navigate to ([^→]+(?:→[^→]+)*)',
                    content,
                    re.IGNORECASE
                )
                for nav in nav_matches[:2]:
                    ui_specs.append(UISpec(
                        feature_name=main_story.summary,
                        navigation_path=nav.strip(),
                        access_method=f"Navigate: {nav.strip()}",
                        ui_elements=[e.strip() for e in nav.split('→')],
                        source="rag_similar_tests"
                    ))
        except Exception as e:
            logger.debug(f"RAG UI pattern extraction failed: {e}")
        
        return ui_specs

