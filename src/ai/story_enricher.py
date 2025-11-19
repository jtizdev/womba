"""
Story enrichment service that preprocesses stories for test generation.

Enriches stories by:
- Recursively following linked stories
- Extracting relevant API specifications from Swagger
- Querying RAG for related documentation
- Synthesizing into narrative brief
"""

import re
from typing import List, Optional, Set
from loguru import logger

from src.models.story import JiraStory
from src.models.enriched_story import EnrichedStory, APISpec, ConfluenceDocRef, UISpec
from src.aggregator.story_collector import StoryContext
from src.aggregator.jira_client import JiraClient
from src.ai.swagger_extractor import SwaggerExtractor
from src.ai.rag_store import RAGVectorStore
from src.config.settings import settings
from src.ai.confluence_processor import process_confluence_content
from src.ai.qa_summarizer import summarize_for_qa
from src.ai.generation.ai_client_factory import AIClientFactory


class StoryEnricher:
    """
    Enriches stories with linked context and API specifications.
    
    Creates a synthesized narrative that replaces raw story dumps in prompts.
    """
    
    def __init__(self):
        """Initialize story enricher with dependencies."""
        self.jira_client = JiraClient()
        self.swagger_extractor = SwaggerExtractor()
        self.rag_store = RAGVectorStore()
        self.max_hops = settings.enrichment_max_hops
    
    async def enrich_story(
        self,
        main_story: JiraStory,
        story_context: StoryContext
    ) -> EnrichedStory:
        """
        Enrich a story with comprehensive context.
        
        Args:
            main_story: Primary story to enrich
            story_context: StoryContext with subtasks, linked stories, etc.
            
        Returns:
            EnrichedStory with synthesized narrative and extracted APIs
        """
        logger.info(f"Enriching story {main_story.key} (max hops: {self.max_hops})")
        
        # 1. Collect linked stories recursively
        all_stories = await self._collect_linked_stories(main_story, story_context)
        logger.info(f"Collected {len(all_stories)} linked stories")
        
        # 2. Extract PlainID components mentioned
        plainid_components = self._extract_plainid_components(all_stories)
        logger.debug(f"Found PlainID components: {plainid_components}")
        
        # 3. Build combined text for API extraction
        combined_text = self._build_combined_text(main_story, all_stories)
        
        # 4. Extract relevant API specifications
        subtask_texts = [s.description or s.summary for s in story_context.get("subtasks", [])]
        api_specs = await self.swagger_extractor.extract_endpoints(
            story_text=combined_text,
            project_key=main_story.key.split('-')[0],
            subtask_texts=subtask_texts
        )
        logger.info(f"Extracted {len(api_specs)} API specifications")
        
        # 4.5. Filter out example endpoints using AI-based filtering
        if api_specs:
            api_specs = await self._filter_example_endpoints_via_ai(
                combined_text=combined_text,
                extracted_endpoints=api_specs,
                story_key=main_story.key
            )
            logger.info(f"After filtering: {len(api_specs)} API specifications remain")
        
        # 4.6. GitLab fallback if no endpoints found
        if not api_specs:
            logger.info("No endpoints found via normal extraction, trying GitLab fallback...")
            try:
                from src.ai.gitlab_fallback_extractor import GitLabFallbackExtractor
                gitlab_extractor = GitLabFallbackExtractor()
                api_specs = await gitlab_extractor.extract_from_codebase(
                    story_key=main_story.key,
                    story_text=combined_text,
                    project_key=main_story.key.split('-')[0]
                )
                logger.info(f"GitLab fallback found {len(api_specs)} API specifications")
            except Exception as e:
                logger.warning(f"GitLab fallback extraction failed: {e}")
                # Continue with empty api_specs
        
        # 5. Collect all acceptance criteria
        all_acceptance_criteria = self._collect_acceptance_criteria(all_stories)
        logger.debug(f"Collected {len(all_acceptance_criteria)} acceptance criteria")
        
        # 6. Integrate Confluence/PRD documents from context (if available)
        confluence_refs = await self._collect_confluence_docs(story_context)
        # Promote PRD acceptance criteria into global AC list
        if confluence_refs:
            prd_acs = []
            for ref in confluence_refs:
                if ref.acceptance_criteria:
                    prd_acs.extend(ref.acceptance_criteria)
            if prd_acs:
                # Deduplicate while preserving order
                seen = set()
                for ac in prd_acs:
                    if ac not in seen:
                        all_acceptance_criteria.append(ac)
                        seen.add(ac)

        # 6.5 Derive functional points from story + PRD + subtasks
        subtasks = story_context.get("subtasks", [])
        functional_points = self._derive_functional_points(main_story, confluence_refs, subtasks)
        if confluence_refs:
            logger.info(f"Including {len(confluence_refs)} Confluence/PRD document(s) in enrichment")

        # 7. Synthesize feature narrative
        feature_narrative = self._synthesize_narrative(
            main_story=main_story,
            linked_stories=all_stories[1:] if len(all_stories) > 1 else [],
            story_context=story_context,
            plainid_components=plainid_components
        )
        
        # 8. Build related stories summary
        related_stories = self._build_related_stories_summary(all_stories[1:] if len(all_stories) > 1 else [])
        
        # 9. Identify risk areas
        risk_areas = self._identify_risk_areas(
            main_story=main_story,
            linked_stories=all_stories,
            api_specs=api_specs,
            plainid_components=plainid_components
        )
        
        # 10. Extract UI specifications
        ui_specs = await self._extract_ui_specifications(main_story, story_context)
        logger.info(f"Extracted {len(ui_specs)} UI specifications")
        
        enriched = EnrichedStory(
            story_key=main_story.key,
            feature_narrative=feature_narrative,
            acceptance_criteria=all_acceptance_criteria,
            api_specifications=api_specs,
            related_stories=related_stories,
            risk_areas=risk_areas,
            source_story_ids=[s.key for s in all_stories],
            plainid_components=plainid_components,
            confluence_docs=confluence_refs,
            functional_points=functional_points,
            ui_specifications=ui_specs
        )
        
        # Debug: Log complete enrichment data
        logger.debug("=" * 80)
        logger.debug(f"ENRICHED STORY DATA: {enriched.story_key}")
        logger.debug("=" * 80)
        logger.debug(f"Feature Narrative ({len(feature_narrative)} chars):")
        logger.debug(feature_narrative)
        logger.debug(f"\nAcceptance Criteria ({len(all_acceptance_criteria)}):")
        for i, ac in enumerate(all_acceptance_criteria, 1):
            logger.debug(f"  {i}. {ac}")
        logger.debug(f"\nAPI Specifications ({len(api_specs)}):")
        for api in api_specs:
            logger.debug(f"  - {' '.join(api.http_methods)} {api.endpoint_path} (service: {api.service_name})")
        logger.debug(f"\nPlainID Components ({len(plainid_components)}):")
        for comp in plainid_components:
            logger.debug(f"  - {comp}")
        logger.debug(f"\nRisk Areas ({len(risk_areas)}):")
        for risk in risk_areas:
            logger.debug(f"  - {risk}")
        logger.debug(f"\nRelated Stories ({len(related_stories)}):")
        for related in related_stories[:5]:
            logger.debug(f"  - {related}")
        if functional_points:
            logger.debug(f"\nFunctional Points ({len(functional_points)}):")
            for i, fp in enumerate(functional_points[:15], 1):
                logger.debug(f"  {i}. {fp}")
        if confluence_refs:
            logger.debug(f"\nConfluence/PRD Docs ({len(confluence_refs)}):")
            for ref in confluence_refs:
                logger.debug(f"  - {ref.title or 'Untitled'} | {ref.url}")
                if ref.qa_summary:
                    summary_preview = ref.qa_summary[:200] + ('...' if len(ref.qa_summary) > 200 else '')
                    logger.debug(f"    QA Summary: {summary_preview}")
        logger.debug(f"\nSource Stories: {', '.join([s.key for s in all_stories])}")
        logger.debug("=" * 80)
        
        logger.info(f"Story enrichment complete for {main_story.key}")
        return enriched
    
    def _score_linked_story_relevance(
        self,
        main_story: JiraStory,
        linked_story: JiraStory,
        link_type: str = "relates to"
    ) -> float:
        """
        Score the relevance of a linked story to the main story.
        
        Higher scores = more relevant = should be prioritized in narrative.
        
        Args:
            main_story: Main story
            linked_story: Linked story to score
            link_type: Type of link relationship
            
        Returns:
            Relevance score (0-100)
        """
        score = 0.0
        
        # 1. Link type importance (critical links are most relevant)
        link_type_lower = link_type.lower()
        if "block" in link_type_lower:
            score += 40  # Blocks/Blocked by are critical
        elif "depend" in link_type_lower or "require" in link_type_lower:
            score += 30  # Dependencies are important
        elif "duplicate" in link_type_lower:
            score += 25  # Duplicates provide context
        elif "relate" in link_type_lower:
            score += 10  # Generic relations are less important
        else:
            score += 5  # Unknown link types
        
        # 2. Shared components (same area = more relevant)
        if main_story.components and linked_story.components:
            shared_components = set(main_story.components) & set(linked_story.components)
            score += len(shared_components) * 10  # +10 per shared component
        
        # 3. Shared labels (indicates related work)
        if main_story.labels and linked_story.labels:
            shared_labels = set(main_story.labels) & set(linked_story.labels)
            score += len(shared_labels) * 5  # +5 per shared label
        
        # 4. Issue type importance
        if linked_story.issue_type.lower() in ['bug', 'defect']:
            score += 15  # Bugs indicate risk areas
        elif linked_story.issue_type.lower() in ['story', 'feature']:
            score += 10  # Related features are important
        elif linked_story.issue_type.lower() in ['epic']:
            score += 5   # Epics provide broader context
        
        # 5. Priority alignment (high priority links are more relevant)
        priority_scores = {'critical': 15, 'highest': 15, 'high': 10, 'medium': 5, 'low': 2}
        linked_priority = linked_story.priority.lower()
        for key, value in priority_scores.items():
            if key in linked_priority:
                score += value
                break
        
        # 6. Recency (recently updated stories are more relevant)
        from datetime import datetime, timedelta
        if linked_story.updated:
            days_since_update = (datetime.utcnow() - linked_story.updated).days
            if days_since_update < 7:
                score += 10  # Very recent
            elif days_since_update < 30:
                score += 5   # Recent
            elif days_since_update < 90:
                score += 2   # Somewhat recent
        
        # 7. Status relevance (in-progress work is more relevant)
        status_lower = linked_story.status.lower()
        if status_lower in ['in progress', 'in development', 'in review']:
            score += 8
        elif status_lower in ['to do', 'open', 'ready']:
            score += 5
        elif status_lower in ['done', 'closed', 'resolved']:
            score += 3  # Still relevant but less urgent
        
        return min(score, 100)  # Cap at 100
    
    async def _collect_linked_stories(
        self,
        main_story: JiraStory,
        story_context: StoryContext,
        current_hop: int = 0
    ) -> List[JiraStory]:
        """
        Recursively collect linked stories up to max_hops, sorted by relevance.
        
        Args:
            main_story: Story to start from
            story_context: Initial story context
            current_hop: Current recursion depth
            
        Returns:
            List of all stories (main + linked at all hops, sorted by relevance)
        """
        all_stories = [main_story]
        seen_keys = {main_story.key}
        story_relevance_scores = {}  # Track scores for sorting
        
        if current_hop >= self.max_hops:
            return all_stories
        
        # Get linked stories from context or fetch them
        linked_stories = story_context.get("linked_stories", [])
        
        # Also check linked_issues field on main story
        for linked_key in main_story.linked_issues:
            if linked_key not in seen_keys:
                try:
                    linked_story, _ = await self.jira_client.get_issue_with_subtasks(linked_key)
                    linked_stories.append(linked_story)
                    seen_keys.add(linked_key)
                except Exception as e:
                    logger.debug(f"Could not fetch linked story {linked_key}: {e}")
        
        # Score and sort linked stories by relevance
        scored_stories = []
        for linked_story in linked_stories:
            if isinstance(linked_story, dict):
                linked_key = linked_story.get('key')
            else:
                linked_key = linked_story.key
            
            if linked_key not in seen_keys:
                # Convert dict to JiraStory for scoring if needed
                try:
                    from src.models.story import JiraStory
                    if not isinstance(linked_story, JiraStory):
                        linked_story = JiraStory(**linked_story)
                except Exception:
                    pass
                
                # Score this story's relevance
                relevance_score = self._score_linked_story_relevance(
                    main_story=main_story,
                    linked_story=linked_story,
                    link_type="relates to"  # Could extract from link metadata if available
                )
                scored_stories.append((linked_story, relevance_score))
                story_relevance_scores[linked_key] = relevance_score
                seen_keys.add(linked_key)
        
        # Sort by relevance score (highest first)
        scored_stories.sort(key=lambda x: x[1], reverse=True)
        
        # Debug: Log relevance scores
        if scored_stories:
            logger.debug("Linked story relevance scores:")
            for story, score in scored_stories[:10]:
                story_key = story.key if hasattr(story, 'key') else story.get('key')
                story_summary = story.summary if hasattr(story, 'summary') else story.get('summary', '')
                logger.debug(f"  - {story_key} (score: {score:.1f}): {story_summary[:60]}")
        
        # Add sorted stories to results
        for linked_story, score in scored_stories:
            all_stories.append(linked_story)
            
            # Recurse for next hop (only for high-relevance stories to avoid explosion)
            if current_hop + 1 < self.max_hops and score >= 30:  # Only recurse if relevance >= 30
                try:
                    if isinstance(linked_story, dict):
                        nested_links = linked_story.get('linked_issues', [])
                    else:
                        nested_links = linked_story.linked_issues
                    
                    for nested_key in nested_links:
                        if nested_key not in seen_keys:
                            try:
                                nested_story, _ = await self.jira_client.get_issue_with_subtasks(nested_key)
                                # Score nested story
                                nested_score = self._score_linked_story_relevance(
                                    main_story=main_story,
                                    linked_story=nested_story,
                                    link_type="relates to"
                                )
                                # Only include if reasonably relevant
                                if nested_score >= 20:
                                    all_stories.append(nested_story)
                                    story_relevance_scores[nested_key] = nested_score
                                    seen_keys.add(nested_key)
                                    logger.debug(f"  - Added nested story {nested_key} (score: {nested_score:.1f})")
                            except Exception as e:
                                logger.debug(f"Could not fetch nested story {nested_key}: {e}")
                except Exception as e:
                    logger.debug(f"Error processing nested links: {e}")
        
        logger.info(f"Collected {len(all_stories)} stories (1 main + {len(all_stories)-1} linked, scored by relevance)")
        return all_stories
    
    def _extract_plainid_components(self, stories: List[JiraStory]) -> List[str]:
        """
        Extract PlainID components mentioned in stories.
        
        Args:
            stories: List of stories to analyze
            
        Returns:
            List of unique PlainID components found
        """
        components = set()
        
        # PlainID architecture components
        plainid_terms = {
            'PAP': 'Policy Administration Point',
            'PDP': 'Policy Decision Point',
            'PEP': 'Policy Enforcement Point',
            'POP': 'Policy Object Provider',
            'PIP': 'Policy Information Point',
            'Authorizer': 'Authorization Service',
            'Runtime': 'Runtime Engine',
            'Policy': 'Policy Management',
            'Environment': 'PlainID Environment',
            'Workspace': 'PlainID Workspace',
            'Tenant': 'PlainID Tenant',
            'PBAC': 'Policy-Based Access Control',
            'Authorization API': 'Authorization API',
            'Management API': 'Management API'
        }
        
        for story in stories:
            text = f"{story.summary} {story.description or ''} {story.acceptance_criteria or ''}"
            text_upper = text.upper()
            
            for term in plainid_terms.keys():
                if term.upper() in text_upper or term.lower() in text.lower():
                    components.add(plainid_terms[term])
            
            # Also add components from story components field
            for comp in story.components:
                if comp:
                    components.add(comp)
        
        return sorted(list(components))
    
    def _build_combined_text(self, main_story: JiraStory, all_stories: List[JiraStory]) -> str:
        """
        Build combined text for API extraction.
        
        Args:
            main_story: Main story
            all_stories: All stories including linked ones
            
        Returns:
            Combined text string
        """
        parts = [
            f"Story: {main_story.summary}",
            main_story.description or "",
            main_story.acceptance_criteria or ""
        ]
        
        for story in all_stories[1:]:  # Skip main story
            parts.append(f"Related: {story.summary}")
            if story.description:
                parts.append(story.description)  # NO truncation
        
        return "\n".join(parts)
    
    def _collect_acceptance_criteria(self, stories: List[JiraStory]) -> List[str]:
        """
        Collect all acceptance criteria from stories.
        
        Args:
            stories: List of stories
            
        Returns:
            List of acceptance criteria strings
        """
        criteria = []
        
        for story in stories:
            if story.acceptance_criteria:
                # Split by common delimiters
                ac_text = story.acceptance_criteria
                
                # Try to split by bullet points or numbers
                if '\n' in ac_text:
                    lines = ac_text.split('\n')
                    for line in lines:
                        line = line.strip()
                        if line and len(line) > 10:  # Skip empty or very short lines
                            # Clean up bullet points and numbers
                            line = re.sub(r'^[-*•]\s*', '', line)
                            line = re.sub(r'^\d+\.\s*', '', line)
                            if line:
                                criteria.append(line)
                else:
                    criteria.append(ac_text)
        
        return criteria
    
    def _synthesize_narrative(
        self,
        main_story: JiraStory,
        linked_stories: List[JiraStory],
        story_context: StoryContext,
        plainid_components: List[str]
    ) -> str:
        """
        Synthesize feature narrative (2-3 paragraphs).
        
        Args:
            main_story: Main story
            linked_stories: Linked stories
            story_context: Story context with subtasks, comments, etc.
            plainid_components: PlainID components involved
            
        Returns:
            Narrative text explaining the feature
        """
        paragraphs = []
        
        # Paragraph 1: What and Why - USE FULL DESCRIPTION
        p1_parts = [f"**Story: {main_story.summary}**\n"]
        
        if main_story.description:
            # Include FULL description (no truncation - AI needs all details)
            desc = main_story.description.strip()
            p1_parts.append(f"**Full Description**:\n{desc}")
        
        if main_story.components:
            p1_parts.append(f"\nComponents: {', '.join(main_story.components[:5])}")
        
        paragraphs.append('\n'.join(p1_parts))
        
        # Paragraph 2: Technical context and architecture - INCLUDE IMPLEMENTATION DETAILS
        p2_parts = []
        
        if plainid_components:
            p2_parts.append(f"**PlainID Architecture**: {', '.join(plainid_components[:8])}")
        
        subtasks = story_context.get("subtasks", [])
        if subtasks:
            p2_parts.append(f"\n**Implementation** ({len(subtasks)} engineering tasks):")
            # Include ALL subtask details (NO truncation - AI needs complete context)
            for task in subtasks:  # Show ALL subtasks
                task_summary = f"- **{task.summary}**"
                if task.description and len(task.description) > 15:
                    # Include FULL description (no truncation)
                    task_summary += f": {task.description}"
                p2_parts.append(task_summary)
        
        if p2_parts:
            paragraphs.append('\n'.join(p2_parts))
        
        # Paragraph 3: Related work and context (focus on most relevant)
        if linked_stories:
            # Stories are already sorted by relevance, so first ones are most important
            p3_parts = [f"This work is related to {len(linked_stories)} other stories."]
            p3_parts.append("Most relevant:")
            for story in linked_stories[:3]:  # Top 3 most relevant
                status_info = f" ({story.status})" if story.status else ""
                p3_parts.append(f"{story.key}{status_info}: {story.summary}")
            if len(linked_stories) > 3:
                p3_parts.append(f"Plus {len(linked_stories) - 3} additional related stories.")
            paragraphs.append(' '.join(p3_parts))
        
        return '\n\n'.join(paragraphs)

    async def _collect_confluence_docs(self, context: StoryContext) -> List[ConfluenceDocRef]:
        """
        Collect Confluence/PRD documents from story context with RAG fallback.

        Args:
            context: StoryContext containing any fetched Confluence docs

        Returns:
            List of ConfluenceDocRef with title, url, and full content (no truncation)
        """
        refs: List[ConfluenceDocRef] = []
        try:
            docs = context.get("confluence_docs", []) or []
            main_story = context.get("main_story")
            
            for doc in docs[:5]:  # limit to 5
                title = doc.get("title")
                url = doc.get("url")
                content = doc.get("content") or ""
                
                if not url:
                    continue
                
                # FALLBACK: If content is empty or too short, try RAG
                if not content or len(content) < 100:
                    logger.info(f"Confluence doc '{title}' has no content, falling back to RAG")
                    try:
                        story_key = main_story.key if main_story else ""
                        rag_results = await self.rag_store.retrieve_similar(
                            collection_name="confluence_docs",
                            query_text=f"{title} {story_key}",
                            top_k=1
                        )
                        if rag_results:
                            content = rag_results[0].get("content", "")
                            logger.info(f"Retrieved {len(content)} chars from RAG for '{title}'")
                    except Exception as e:
                        logger.warning(f"RAG fallback failed for '{title}': {e}")
                
                if not content:
                    logger.warning(f"No content for Confluence doc '{title}', skipping")
                    continue
                
                # NO TRUNCATION - use full content
                summary = content
                structured = process_confluence_content(content)
                qa_summary = summarize_for_qa(
                    story_summary=None,  # Don't repeat story summary in PRD section
                    content=content,
                    max_chars=None  # NO LIMIT
                )
                
                refs.append(ConfluenceDocRef(
                    title=title,
                    url=url,
                    summary=summary,
                    headings=structured.get('headings', []),
                    functional_requirements=structured.get('functional_requirements', []),
                    use_cases=structured.get('use_cases', []),
                    acceptance_criteria=structured.get('acceptance_criteria', []),
                    non_functional=structured.get('non_functional', []),
                    notes=structured.get('notes', []),
                    qa_summary=qa_summary,
                ))
        except Exception as e:
            logger.error(f"Failed to collect Confluence docs: {e}", exc_info=True)
        return refs

    async def _extract_ui_specifications(
        self,
        main_story: JiraStory,
        story_context: StoryContext
    ) -> List[UISpec]:
        """
        Extract UI navigation and access specifications.
        
        Sources:
        1. Story description (explicit navigation paths)
        2. RAG similar UI patterns
        3. Inference from feature requirements
        """
        ui_specs = []
        combined_text = self._build_combined_text(main_story, [])
        
        # Pattern 1: Explicit navigation in story
        # "navigate to X → Y → Z"
        # "from the X page, click Y tab"
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
                # Extract navigation from test steps
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

    def _derive_functional_points(self, main_story: JiraStory, confluence_refs: List[ConfluenceDocRef], subtasks: List[JiraStory]) -> List[str]:
        """
        Derive concrete functionality bullets from story description and PRD content.
        """
        import re
        points: List[str] = []
        
        # From PRD structured fields if available
        for ref in confluence_refs or []:
            points.extend(ref.functional_requirements or [])
            points.extend(ref.use_cases or [])
            points.extend(ref.acceptance_criteria or [])
        
        # From story description - extract actionable/functional statements
        desc = main_story.description or ""
        if desc:
            # Split by lines
            lines = desc.splitlines()
            for line in lines:
                l = line.strip()
                if not l or len(l) < 10:
                    continue
                # Look for action-oriented content
                if re.search(r"\b(implement|add|create|update|delete|view|display|show|compare|filter|sort|export|import|validate|support|enable|allow|enforce|verify|check|click|select|open|close|save|edit|modify|remove|drag|drop|zoom|pinch|navigate|fetch|patch|post|get)\b", l, re.I):
                    # Strip bullets/numbers
                    l = re.sub(r"^([-*•]\s*|\d+\.\s*|[a-z]\.\s*)", "", l)
                    # Skip if it's a URL, recording link (NO LENGTH LIMIT - full text)
                    if not l.startswith('http') and 'zoom.us/rec' not in l and 'share link' not in l.lower():
                        points.append(l)
        
        # From subtasks - each subtask represents a functional capability
        for task in (subtasks or [])[:15]:
            task_point = task.summary
            # If subtask has description, include FULL text
            if task.description and len(task.description) > 20:
                task_point = f"{task.summary}: {task.description.strip()}"
            points.append(task_point)
        
        # Deduplicate, prefer earlier (NO TRUNCATION)
        seen = set()
        unique = []
        for p in points:
            normalized = p.lower().strip()
            if normalized not in seen and len(p) > 10:
                unique.append(p)  # NO TRUNCATION - full text
                seen.add(normalized)
            if len(unique) >= 30:
                break
        
        logger.debug(f"Derived {len(unique)} functional points from description ({len(desc)} chars), PRD ({len(confluence_refs)} docs), and subtasks ({len(subtasks)})")
        return unique
    
    def _build_related_stories_summary(self, linked_stories: List[JiraStory]) -> List[str]:
        """
        Build one-line summaries for related stories (already sorted by relevance).
        
        Args:
            linked_stories: List of linked stories (sorted by relevance)
            
        Returns:
            List of summary strings (most relevant first)
        """
        summaries = []
        for story in linked_stories[:10]:  # Limit to top 10 most relevant
            summary = f"{story.key}: {story.summary}"
            if story.status:
                summary += f" [{story.status}]"
            summaries.append(summary)
        
        return summaries
    
    def _identify_risk_areas(
        self,
        main_story: JiraStory,
        linked_stories: List[JiraStory],
        api_specs: List[APISpec],
        plainid_components: List[str]
    ) -> List[str]:
        """
        Identify risk areas and integration points.
        
        Args:
            main_story: Main story
            linked_stories: Linked stories
            api_specs: API specifications
            plainid_components: PlainID components
            
        Returns:
            List of risk descriptions
        """
        risks = []
        
        # API integration risks
        if api_specs:
            risks.append(f"API Integration: {len(api_specs)} endpoints involved - verify request/response formats, error handling, and auth")
        
        # Component interaction risks
        if len(plainid_components) > 1:
            risks.append(f"Multi-component interaction: {len(plainid_components)} components - test data flow and consistency")
        
        # Policy-related risks
        policy_keywords = ['policy', 'authorization', 'permission', 'access control', 'rbac', 'pbac']
        text = f"{main_story.summary} {main_story.description or ''}".lower()
        if any(kw in text for kw in policy_keywords):
            risks.append("Authorization logic: Verify policy evaluation, decision points, and enforcement")
        
        # Database/State risks
        state_keywords = ['database', 'persist', 'store', 'save', 'update', 'delete', 'crud']
        if any(kw in text for kw in state_keywords):
            risks.append("Data persistence: Test CRUD operations, data consistency, and rollback scenarios")
        
        # UI/UX risks
        ui_keywords = ['ui', 'interface', 'screen', 'page', 'form', 'button', 'display']
        if any(kw in text for kw in ui_keywords):
            risks.append("User interface: Verify user workflows, form validation, and error messages")
        
        # Performance risks
        perf_keywords = ['performance', 'speed', 'latency', 'cache', 'optimization', 'scale']
        if any(kw in text for kw in perf_keywords):
            risks.append("Performance: Monitor response times and resource usage (note: specific SLAs are for dev team)")
        
        # Migration/Compatibility risks
        if any(kw in text for kw in ['migration', 'upgrade', 'backward', 'compatibility', 'legacy']):
            risks.append("Migration/Compatibility: Test upgrade paths and backward compatibility with existing data")
        
        return risks
    
    async def _filter_example_endpoints_via_ai(
        self,
        combined_text: str,
        extracted_endpoints: List[APISpec],
        story_key: str
    ) -> List[APISpec]:
        """
        Filter out example/reference endpoints using AI-based analysis.
        
        Uses LLM to analyze context around each endpoint and determine if it's:
        - An example/reference (should be filtered out)
        - An actual endpoint being created/implemented (should be kept)
        
        Args:
            combined_text: Full story text with all context
            extracted_endpoints: List of extracted API specifications
            story_key: Story key for logging
            
        Returns:
            Filtered list of API specifications (only actual requirements)
        """
        if not extracted_endpoints:
            return extracted_endpoints
        
        try:
            # Create AI client for filtering
            client, model, use_openai = AIClientFactory.create_client(
                use_openai=True,
                model="gpt-4o-mini"  # Use lightweight model for filtering
            )
            
            # Build prompt for endpoint filtering
            endpoint_list = []
            for i, api in enumerate(extracted_endpoints, 1):
                methods_str = " ".join(api.http_methods) if api.http_methods else "UNKNOWN"
                endpoint_list.append(f"{i}. {methods_str} {api.endpoint_path}")
            
            filter_prompt = f"""You are analyzing a user story to identify which API endpoints are actual requirements vs examples/references.

STORY CONTEXT:
{combined_text[:3000]}  # Limit context to avoid token limits

EXTRACTED ENDPOINTS:
{chr(10).join(endpoint_list)}

TASK: For each endpoint, determine if it is:
1. AN EXAMPLE/REFERENCE - mentioned to show a pattern or existing implementation (e.g., "for ruleset we use GET /policy-mgmt/...")
2. AN ACTUAL REQUIREMENT - explicitly mentioned as being created/implemented in this story

Return a JSON array with one object per endpoint:
[
  {{"endpoint_index": 1, "is_example": true, "reason": "Found in example context: 'for ruleset we use'"}},
  {{"endpoint_index": 2, "is_example": false, "reason": "Explicitly mentioned as new endpoint to create"}}
]

Only mark as is_example:false if the endpoint is explicitly mentioned as being created/implemented in this story.
If uncertain, mark as is_example:true (better to filter out than test wrong endpoint)."""

            # Call AI
            if use_openai:
                # Request JSON array format
                filter_prompt_with_format = filter_prompt + "\n\nReturn ONLY a valid JSON array, no other text."
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": "You are an expert at analyzing software requirements and distinguishing examples from actual requirements. Always return valid JSON arrays."},
                        {"role": "user", "content": filter_prompt_with_format}
                    ],
                    temperature=0.2,  # Low temperature for consistent filtering
                )
                result_text = response.choices[0].message.content
            else:
                # Anthropic path (if needed)
                from anthropic import Anthropic
                response = client.messages.create(
                    model=model,
                    max_tokens=2000,
                    messages=[
                        {"role": "user", "content": filter_prompt}
                    ],
                    temperature=0.2
                )
                result_text = response.content[0].text
            
            # Parse AI response
            import json
            try:
                # Clean up response text
                result_text = result_text.strip()
                
                # Try to parse as JSON
                try:
                    parsed = json.loads(result_text)
                except json.JSONDecodeError:
                    # Try to find JSON array in response
                    json_match = re.search(r'\[.*\]', result_text, re.DOTALL)
                    if json_match:
                        parsed = json.loads(json_match.group(0))
                    else:
                        raise ValueError("No valid JSON found in AI response")
                
                # Handle different response formats
                if isinstance(parsed, list):
                    ai_results = parsed
                elif isinstance(parsed, dict):
                    if 'endpoints' in parsed:
                        ai_results = parsed['endpoints']
                    elif 'results' in parsed:
                        ai_results = parsed['results']
                    else:
                        # Single object, wrap in list
                        ai_results = [parsed]
                else:
                    raise ValueError(f"Unexpected response format: {type(parsed)}")
                
                # Validate structure
                if not isinstance(ai_results, list):
                    raise ValueError(f"Expected list, got {type(ai_results)}")
                    
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(f"Failed to parse AI filtering response for {story_key}: {e}. Response: {result_text[:200]}")
                # Fall back to rule-based filtering
                return self._filter_example_endpoints_rule_based(combined_text, extracted_endpoints)
            
            # Filter endpoints based on AI analysis
            filtered_endpoints = []
            filtered_out = []
            
            for i, api in enumerate(extracted_endpoints, 1):
                # Find AI result for this endpoint
                ai_result = next((r for r in ai_results if r.get('endpoint_index') == i), None)
                
                if ai_result and ai_result.get('is_example', True):
                    # Filter out - it's an example
                    filtered_out.append({
                        'endpoint': f"{' '.join(api.http_methods)} {api.endpoint_path}",
                        'reason': ai_result.get('reason', 'AI identified as example')
                    })
                    logger.debug(f"Filtered out example endpoint: {api.endpoint_path} - {ai_result.get('reason', 'N/A')}")
                else:
                    # Keep - it's an actual requirement
                    filtered_endpoints.append(api)
                    logger.debug(f"Kept endpoint: {api.endpoint_path} - {ai_result.get('reason', 'AI identified as requirement') if ai_result else 'No AI result, keeping by default'}")
            
            if filtered_out:
                logger.info(f"AI filtering for {story_key}: Filtered out {len(filtered_out)} example endpoint(s), kept {len(filtered_endpoints)} actual requirement(s)")
                for item in filtered_out:
                    logger.info(f"  - Filtered: {item['endpoint']} - {item['reason']}")
            
            return filtered_endpoints
            
        except Exception as e:
            logger.warning(f"AI-based endpoint filtering failed for {story_key}: {e}. Falling back to rule-based filtering.")
            # Fall back to rule-based filtering
            return self._filter_example_endpoints_rule_based(combined_text, extracted_endpoints)
    
    def _filter_example_endpoints_rule_based(
        self,
        combined_text: str,
        extracted_endpoints: List[APISpec]
    ) -> List[APISpec]:
        """
        Rule-based fallback for filtering example endpoints.
        
        Used when AI filtering fails or is unavailable.
        
        Args:
            combined_text: Full story text
            extracted_endpoints: List of extracted API specifications
            
        Returns:
            Filtered list of API specifications
        """
        filtered = []
        filtered_out = []
        
        # Example indicator patterns
        example_patterns = [
            r'for\s+[^.]+\s+we\s+use',
            r'similar\s+to',
            r'same\s+as\s+existing',
            r'example',
            r'pattern',
            r'reference',
            r'like\s+.*\s+we\s+use'
        ]
        
        # Requirement indicator patterns
        requirement_patterns = [
            r'create\s+endpoint',
            r'create\s+.*\s+endpoint',
            r'implement\s+endpoint',
            r'add\s+endpoint',
            r'new\s+endpoint',
            r'endpoint\s+for\s+.*\s+application',
            r'fetch.*by\s+application'
        ]
        
        text_lower = combined_text.lower()
        
        for api in extracted_endpoints:
            endpoint_path = api.endpoint_path
            # Find context around endpoint in text
            endpoint_pattern = re.escape(endpoint_path)
            match = re.search(endpoint_pattern, combined_text, re.IGNORECASE)
            
            if match:
                # Get context (200 chars before and after for better detection)
                start = max(0, match.start() - 200)
                end = min(len(combined_text), match.end() + 200)
                context = combined_text[start:end].lower()
                
                # Check if it's an example
                is_example = any(re.search(pattern, context, re.IGNORECASE) for pattern in example_patterns)
                
                # Check if it's explicitly a requirement
                is_requirement = any(re.search(pattern, context, re.IGNORECASE) for pattern in requirement_patterns)
                
                # Conservative: if it's in example context OR not explicitly a requirement, filter it out
                if is_example or not is_requirement:
                    reason = 'Found in example context' if is_example else 'Not explicitly mentioned as requirement'
                    filtered_out.append({
                        'endpoint': f"{' '.join(api.http_methods)} {api.endpoint_path}",
                        'reason': reason
                    })
                    logger.debug(f"Rule-based: Filtered out endpoint: {endpoint_path} - {reason}")
                else:
                    filtered.append(api)
                    logger.debug(f"Rule-based: Kept endpoint: {endpoint_path} - explicitly mentioned as requirement")
            else:
                # Endpoint not found in text - be conservative, filter it out
                filtered_out.append({
                    'endpoint': f"{' '.join(api.http_methods)} {api.endpoint_path}",
                    'reason': 'Endpoint not found in story text'
                })
                logger.debug(f"Rule-based: Filtered out endpoint not in text: {endpoint_path}")
        
        if filtered_out:
            logger.info(f"Rule-based filtering: Filtered out {len(filtered_out)} endpoint(s), kept {len(filtered)}")
            for item in filtered_out:
                logger.info(f"  - Filtered: {item['endpoint']} - {item['reason']}")
        
        return filtered

