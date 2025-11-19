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
        combined_text: str
    ) -> APIContext:
        """
        Build API and UI context using fallback flow.
        
        Args:
            main_story: Primary story
            story_context: Story context with subtasks, linked stories
            combined_text: Combined text from main story + linked stories
            
        Returns:
            APIContext with api_specifications, ui_specifications, and extraction_flow
        """
        logger.info(f"Building API context for {main_story.key}")
        
        api_specs = []
        extraction_flow_parts = []
        
        # Step 1: Extract from story text directly
        logger.debug("Step 1: Extracting endpoints from story text")
        subtask_texts = [s.description or s.summary for s in story_context.get("subtasks", [])]
        api_specs_from_story = await self.swagger_extractor.extract_endpoints(
            story_text=combined_text,
            project_key=main_story.key.split('-')[0],
            subtask_texts=subtask_texts
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
                    extraction_flow_parts.append("mcp")
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
        """Filter out example/reference endpoints using AI-based logic."""
        from src.ai.generation.ai_client_factory import AIClientFactory
        
        if not endpoints:
            return []
        
        try:
            client = AIClientFactory.get_client(model="gpt-4o-mini")
            prompt = f"""
Analyze these endpoints extracted from story {story_key}. Determine which are ACTUAL requirements vs EXAMPLES/REFERENCES.

Story context:
{combined_text[:2000]}

Endpoints found:
{chr(10).join([f"- {ep.http_methods[0] if ep.http_methods else 'GET'} {ep.endpoint_path}" for ep in endpoints])}

For each endpoint, respond ONLY with the path and YES (keep) or NO (filter out).
Format: /path → YES/NO
"""
            response = client.call_api(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=500
            )
            
            # Parse response to determine which endpoints to keep
            kept = []
            for ep in endpoints:
                if "→ YES" in response.get("content", ""):
                    kept.append(ep)
            
            return kept if kept else endpoints  # Default: keep all if parse fails
        except Exception as e:
            logger.warning(f"AI filtering failed: {e}, keeping all endpoints")
            return endpoints
    
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

