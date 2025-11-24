"""
RAG retriever for intelligent context retrieval.
Retrieves similar test plans, docs, stories, and tests for grounded generation.
"""

from typing import List, Dict, Optional, Any
from dataclasses import dataclass

from loguru import logger

from src.ai.rag_store import RAGVectorStore
from src.models.story import JiraStory
from src.config.settings import settings


@dataclass
class RetrievedContext:
    """Container for retrieved RAG context."""
    similar_test_plans: List[Dict[str, Any]]
    similar_confluence_docs: List[Dict[str, Any]]
    similar_jira_stories: List[Dict[str, Any]]
    similar_existing_tests: List[Dict[str, Any]]
    similar_external_docs: List[Dict[str, Any]] = None
    similar_swagger_docs: List[Dict[str, Any]] = None
    
    def __post_init__(self):
        """Initialize optional fields if not provided."""
        if self.similar_external_docs is None:
            self.similar_external_docs = []
        if self.similar_swagger_docs is None:
            self.similar_swagger_docs = []
    
    def has_context(self) -> bool:
        """Check if any context was retrieved."""
        return bool(
            self.similar_test_plans or
            self.similar_confluence_docs or
            self.similar_jira_stories or
            self.similar_existing_tests or
            self.similar_external_docs or
            self.similar_swagger_docs
        )
    
    def get_summary(self) -> str:
        """Get a summary of retrieved context."""
        return (
            f"Retrieved: {len(self.similar_test_plans)} test plans, "
            f"{len(self.similar_confluence_docs)} docs, "
            f"{len(self.similar_jira_stories)} stories, "
            f"{len(self.similar_existing_tests)} existing tests, "
            f"{len(self.similar_external_docs)} external docs, "
            f"{len(self.similar_swagger_docs)} swagger docs"
        )


class RAGRetriever:
    """
    Intelligent retriever for RAG-based test generation.
    Uses semantic search to find relevant company-specific context.
    
    Optimizations:
    - Relevance threshold filtering (min similarity 0.65)
    - Keyword-based re-ranking
    - Document type prioritization
    - Deduplication of similar docs
    - Smart summarization of long docs
    """
    
    def __init__(self):
        """Initialize RAG retriever."""
        self.store = RAGVectorStore()
        self.top_k_tests = settings.rag_top_k_tests
        self.top_k_docs = settings.rag_top_k_docs
        self.top_k_stories = settings.rag_top_k_stories
        self.top_k_existing = settings.rag_top_k_existing
        self.top_k_swagger = settings.rag_top_k_swagger
        
        # Optimization settings
        self.min_similarity = 0.65  # Only include high-quality matches
        # NO TOKEN LIMIT - include full documents without truncation
        self.dedup_threshold = 0.85  # Remove near-duplicates
        
        logger.info("Initialized RAG retriever with optimization filters")
    
    async def retrieve_for_story(
        self,
        story: JiraStory,
        project_key: Optional[str] = None,
        story_context: Optional[Any] = None
    ) -> RetrievedContext:
        """
        Retrieve relevant context for a story from all RAG collections.
        
        Args:
            story: Jira story to retrieve context for
            project_key: Optional project key for filtering
            story_context: Optional StoryContext with additional context (subtasks, etc.)
            
        Returns:
            RetrievedContext with all retrieved information
        """
        logger.info(f"Retrieving RAG context for story {story.key}")
        
        # Extract project key
        if not project_key:
            project_key = story.key.split('-')[0]
        
        # Build comprehensive query from story and context
        query = self._build_query(story, story_context)
        
        # Log query preview
        query_preview = query[:300] + "..." if len(query) > 300 else query
        logger.debug(f"RAG query preview: {query_preview}")
        
        # Metadata filter for project
        metadata_filter = {"project_key": project_key}
        
        # Retrieve from all collections in parallel
        import asyncio
        
        similar_test_plans, similar_docs, similar_stories, similar_tests, similar_external, similar_swagger = await asyncio.gather(
            self._retrieve_similar_test_plans(query, metadata_filter),
            self._retrieve_similar_confluence_docs(query, metadata_filter),
            self._retrieve_similar_jira_stories(query, metadata_filter),
            self._retrieve_similar_existing_tests(query, metadata_filter),
            self._retrieve_similar_external_docs(query, metadata_filter),
            self._retrieve_similar_swagger_docs(query, metadata_filter),
            return_exceptions=True
        )
        
        # Handle exceptions
        if isinstance(similar_test_plans, Exception):
            logger.error(f"Failed to retrieve test plans: {similar_test_plans}")
            similar_test_plans = []
        if isinstance(similar_docs, Exception):
            logger.error(f"Failed to retrieve docs: {similar_docs}")
            similar_docs = []
        if isinstance(similar_stories, Exception):
            logger.error(f"Failed to retrieve stories: {similar_stories}")
            similar_stories = []
        if isinstance(similar_tests, Exception):
            logger.error(f"Failed to retrieve tests: {similar_tests}")
            similar_tests = []
        if isinstance(similar_external, Exception):
            logger.error(f"Failed to retrieve external docs: {similar_external}")
            similar_external = []
        if isinstance(similar_swagger, Exception):
            logger.error(f"Failed to retrieve swagger docs: {similar_swagger}")
            similar_swagger = []
        
        context = RetrievedContext(
            similar_test_plans=similar_test_plans,
            similar_confluence_docs=similar_docs,
            similar_jira_stories=similar_stories,
            similar_existing_tests=similar_tests,
            similar_external_docs=similar_external,
            similar_swagger_docs=similar_swagger
        )
        
        logger.info(context.get_summary())
        return context
    
    def _build_query(self, story: JiraStory, story_context: Optional[Any] = None) -> str:
        """
        Build comprehensive search query from story and context.
        
        This query is the PRIMARY input for semantic search across all RAG collections.
        The richer the query, the better the retrieval quality.
        
        Args:
            story: Jira story
            story_context: Optional StoryContext with subtasks, linked issues, etc.
            
        Returns:
            Query string for semantic search
        """
        query_parts = []
        
        # 1. Core story information - ALWAYS INCLUDED
        query_parts.append(f"Story: {story.summary}")
        
        if story.description:
            # Include more description - up to 1000 chars for better semantic matching
            desc_text = story.description[:1000]
            query_parts.append(f"Description: {desc_text}")
        
        # 2. Acceptance Criteria - CRITICAL for matching relevant docs and APIs
        if story.acceptance_criteria:
            # This often contains specific requirements that match swagger endpoints
            query_parts.append(f"Acceptance Criteria: {story.acceptance_criteria}")
        
        # 3. Components and Labels - categorization for filtering
        if story.components:
            query_parts.append(f"Components: {', '.join(story.components)}")
        
        if story.labels:
            # Labels often indicate feature areas that match documentation
            query_parts.append(f"Labels: {', '.join(story.labels[:10])}")
        
        # 4. Issue type and priority - context for search ranking
        query_parts.append(f"Type: {story.issue_type}")
        if story.priority != "Medium":  # Only include if not default
            query_parts.append(f"Priority: {story.priority}")
        
        # 5. Subtasks/Engineering Tasks - CRITICAL for matching swagger endpoints
        # Subtasks often mention specific endpoint paths, API methods, database changes
        if story_context:
            subtasks = story_context.get("subtasks", [])
            if subtasks:
                query_parts.append("\nEngineering Tasks:")
                for task in subtasks[:8]:  # Include up to 8 subtasks
                    query_parts.append(f"- {task.summary}")
                    # Include task description if it's short and meaningful
                    if task.description and len(task.description) < 200:
                        query_parts.append(f"  {task.description}")
        
        # 6. Linked issues - related work that might share APIs/docs
        if story.linked_issues:
            # Just the keys - helps find related documentation
            query_parts.append(f"Related: {', '.join(story.linked_issues[:5])}")
        
        query = "\n".join(query_parts)
        
        # Log query length for debugging
        logger.debug(f"Built RAG query: {len(query)} characters, {len(query_parts)} parts")
        
        return query
    
    async def _retrieve_similar_test_plans(
        self,
        query: str,
        metadata_filter: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Retrieve similar past test plans."""
        try:
            # Check if collection has documents
            stats = self.store.get_collection_stats(self.store.TEST_PLANS_COLLECTION)
            if stats.get('count', 0) == 0:
                logger.info("Test plans collection is empty, skipping retrieval")
                return []
            
            results = await self.store.retrieve_similar(
                collection_name=self.store.TEST_PLANS_COLLECTION,
                query_text=query,
                top_k=self.top_k_tests,
                metadata_filter=metadata_filter
            )
            logger.info(f"Retrieved {len(results)} similar test plans")
            return results
        except Exception as e:
            logger.warning(f"No similar test plans found: {e}")
            return []
    
    async def _retrieve_similar_confluence_docs(
        self,
        query: str,
        metadata_filter: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Retrieve similar Confluence documentation."""
        try:
            # Check if collection has documents
            stats = self.store.get_collection_stats(self.store.CONFLUENCE_DOCS_COLLECTION)
            if stats.get('count', 0) == 0:
                logger.info("Confluence docs collection is empty, skipping retrieval")
                return []
            
            results = await self.store.retrieve_similar(
                collection_name=self.store.CONFLUENCE_DOCS_COLLECTION,
                query_text=query,
                top_k=self.top_k_docs,
                metadata_filter=metadata_filter
            )
            logger.info(f"Retrieved {len(results)} similar Confluence docs")
            return results
        except Exception as e:
            logger.warning(f"No similar Confluence docs found: {e}")
            return []
    
    async def _retrieve_similar_jira_stories(
        self,
        query: str,
        metadata_filter: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Retrieve similar Jira stories."""
        try:
            # Check if collection has documents
            stats = self.store.get_collection_stats(self.store.JIRA_ISSUES_COLLECTION)
            if stats.get('count', 0) == 0:
                logger.info("Jira stories collection is empty, skipping retrieval")
                return []
            
            results = await self.store.retrieve_similar(
                collection_name=self.store.JIRA_ISSUES_COLLECTION,
                query_text=query,
                top_k=self.top_k_stories,
                metadata_filter=metadata_filter
            )
            logger.info(f"Retrieved {len(results)} similar Jira stories")
            return results
        except Exception as e:
            logger.warning(f"No similar Jira stories found: {e}")
            return []
    
    async def _retrieve_similar_existing_tests(
        self,
        query: str,
        metadata_filter: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Retrieve similar existing test cases."""
        try:
            # Check if collection has documents
            stats = self.store.get_collection_stats(self.store.EXISTING_TESTS_COLLECTION)
            if stats.get('count', 0) == 0:
                logger.info("Existing tests collection is empty, skipping retrieval")
                return []
            
            results = await self.store.retrieve_similar(
                collection_name=self.store.EXISTING_TESTS_COLLECTION,
                query_text=query,
                top_k=self.top_k_existing,
                metadata_filter=metadata_filter
            )
            logger.info(f"Retrieved {len(results)} similar existing tests")
            return results
        except Exception as e:
            logger.warning(f"No similar existing tests found: {e}")
            return []
    
    async def _retrieve_similar_external_docs(
        self,
        query: str,
        metadata_filter: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Retrieve similar external documentation (external API docs)."""
        try:
            # Check if collection has documents
            stats = self.store.get_collection_stats(self.store.EXTERNAL_DOCS_COLLECTION)
            if stats.get('count', 0) == 0:
                logger.debug("External docs collection is empty, skipping retrieval")
                return []
            
            # Don't filter by project_key for external docs (they're global)
            results = await self.store.retrieve_similar(
                collection_name=self.store.EXTERNAL_DOCS_COLLECTION,
                query_text=query,
                top_k=10,  # Get top 10 external docs
                metadata_filter=None  # No project filter for external docs
            )
            logger.info(f"Retrieved {len(results)} external documentation entries")
            return results
        except Exception as e:
            logger.warning(f"No similar external docs found: {e}")
            return []
    
    async def _retrieve_similar_swagger_docs(
        self,
        query: str,
        metadata_filter: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Retrieve similar Swagger/OpenAPI documentation from GitLab services."""
        try:
            # Check if collection has documents
            stats = self.store.get_collection_stats(self.store.SWAGGER_DOCS_COLLECTION)
            if stats.get('count', 0) == 0:
                logger.debug("Swagger docs collection is empty, skipping retrieval")
                return []
            
            # Filter by project_key for swagger docs
            results = await self.store.retrieve_similar(
                collection_name=self.store.SWAGGER_DOCS_COLLECTION,
                query_text=query,
                top_k=self.top_k_swagger,
                metadata_filter=metadata_filter
            )
            logger.info(f"Retrieved {len(results)} Swagger documentation entries")
            return results
        except Exception as e:
            logger.warning(f"No similar swagger docs found: {e}")
            return []
    
    def filter_by_similarity(self, docs: List[Dict[str, Any]], min_similarity: float = None) -> List[Dict[str, Any]]:
        """Filter documents by similarity threshold."""
        if min_similarity is None:
            min_similarity = self.min_similarity
        
        filtered = [doc for doc in docs if doc.get('similarity', 0) >= min_similarity]
        
        if len(filtered) < len(docs):
            logger.info(f"Filtered {len(docs)} → {len(filtered)} docs (similarity >= {min_similarity:.2f})")
        
        return filtered
    
    def rerank_by_keywords(self, docs: List[Dict[str, Any]], story_keywords: List[str]) -> List[Dict[str, Any]]:
        """Re-rank documents by keyword overlap with story."""
        if not story_keywords:
            return docs
        
        def keyword_score(doc: Dict[str, Any]) -> float:
            doc_text = doc.get('document', '').lower()
            # Count how many story keywords appear in doc
            matches = sum(1 for kw in story_keywords if kw.lower() in doc_text)
            # Boost score by keyword density
            base_similarity = doc.get('similarity', 0)
            keyword_boost = matches * 0.03  # +3% per keyword match
            return base_similarity + keyword_boost
        
        ranked = sorted(docs, key=keyword_score, reverse=True)
        logger.debug(f"Re-ranked {len(docs)} docs by keywords: {story_keywords[:5]}")
        return ranked
    
    def prioritize_by_type(self, docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Prioritize documents by source type relevance."""
        # Define priority multipliers
        type_priority = {
            'jira_issues': 1.15,      # Related stories = most relevant
            'swagger_docs': 1.12,      # API specs = very relevant
            'existing_tests': 1.10,    # Similar tests = helpful for style
            'confluence_docs': 1.05,   # Internal docs = somewhat relevant
            'external_docs': 1.02,     # External docs = background only
        }
        
        def priority_score(doc: Dict[str, Any]) -> float:
            source_type = doc.get('metadata', {}).get('source_type', 'unknown')
            multiplier = type_priority.get(source_type, 1.0)
            base_similarity = doc.get('similarity', 0)
            return base_similarity * multiplier
        
        prioritized = sorted(docs, key=priority_score, reverse=True)
        logger.debug(f"Prioritized {len(docs)} docs by type")
        return prioritized
    
    def deduplicate_docs(self, docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove near-duplicate documents."""
        if len(docs) <= 1:
            return docs
        
        unique_docs = []
        seen_content = []
        
        for doc in docs:
            doc_text = doc.get('document', '')
            # Check if similar to any already-included doc
            is_duplicate = False
            for seen in seen_content:
                overlap = self._text_similarity(doc_text, seen)
                if overlap > self.dedup_threshold:
                    is_duplicate = True
                    logger.debug(f"Skipping duplicate doc (overlap: {overlap:.2f})")
                    break
            
            if not is_duplicate:
                unique_docs.append(doc)
                seen_content.append(doc_text)
        
        if len(unique_docs) < len(docs):
            logger.info(f"Deduplicated {len(docs)} → {len(unique_docs)} docs")
        
        return unique_docs
    
    def _text_similarity(self, text1: str, text2: str) -> float:
        """Quick text similarity using set overlap (Jaccard similarity)."""
        if not text1 or not text2:
            return 0.0
        
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        return intersection / union if union > 0 else 0.0
    
    def truncate_long_docs(self, docs: List[Dict[str, Any]], max_tokens: int = None) -> List[Dict[str, Any]]:
        """Truncate documents that exceed token budget."""
        if max_tokens is None:
            max_tokens = self.max_tokens_per_doc
        
        truncated = []
        for doc in docs:
            doc_text = doc.get('document', '')
            doc_tokens = len(doc_text) // 4  # Rough estimate
            
            if doc_tokens > max_tokens:
                # Truncate to max_tokens
                max_chars = max_tokens * 4
                truncated_text = doc_text[:max_chars] + f"\n... [truncated from {doc_tokens} to {max_tokens} tokens]"
                doc = doc.copy()
                doc['document'] = truncated_text
                doc['truncated'] = True
                logger.debug(f"Truncated doc from {doc_tokens} → {max_tokens} tokens")
            
            truncated.append(doc)
        
        return truncated
    
    def extract_keywords(self, story: JiraStory, story_context: Optional[Any] = None) -> List[str]:
        """Extract key terms from story for re-ranking."""
        keywords = []
        
        # Extract from summary (most important)
        if story.summary:
            # Remove common words and extract meaningful terms
            summary_words = story.summary.lower().split()
            keywords.extend([w for w in summary_words if len(w) > 3])
        
        # Extract from components
        if story.components:
            keywords.extend([c.lower() for c in story.components])
        
        # Extract from labels
        if story.labels:
            keywords.extend([l.lower() for l in story.labels[:5]])
        
        # Extract from issue type
        if story.issue_type:
            keywords.append(story.issue_type.lower())
        
        # Deduplicate and limit
        keywords = list(dict.fromkeys(keywords))  # Preserve order, remove dupes
        keywords = keywords[:15]  # Top 15 keywords
        
        logger.debug(f"Extracted keywords: {keywords}")
        return keywords
    
    async def retrieve_optimized(
        self,
        story: JiraStory,
        project_key: Optional[str] = None,
        story_context: Optional[Any] = None,
        max_docs_per_type: int = 3
    ) -> RetrievedContext:
        """
        Retrieve and optimize RAG context with all filters applied.
        
        This is the MAIN method to use for prompt building.
        It applies all optimizations:
        - Retrieves more candidates than needed
        - Filters by similarity threshold
        - Re-ranks by keywords
        - Prioritizes by document type
        - Deduplicates similar docs
        - Truncates long docs
        - Returns top N per type
        
        Args:
            story: Jira story
            project_key: Optional project key
            story_context: Optional story context with subtasks
            max_docs_per_type: Max documents to return per collection
            
        Returns:
            Optimized RetrievedContext
        """
        logger.info(f"Retrieving OPTIMIZED RAG context for {story.key}")
        
        # Step 1: Retrieve raw context (casts wide net)
        raw_context = await self.retrieve_for_story(story, project_key, story_context)
        
        # Step 2: Extract keywords for re-ranking
        keywords = self.extract_keywords(story, story_context)
        
        # Step 3: Optimize each collection
        optimized_test_plans = self._optimize_docs(
            raw_context.similar_test_plans,
            keywords,
            max_docs_per_type,
            "test_plans"
        )
        
        optimized_confluence = self._optimize_docs(
            raw_context.similar_confluence_docs,
            keywords,
            max_docs_per_type,
            "confluence"
        )
        
        optimized_stories = self._optimize_docs(
            raw_context.similar_jira_stories,
            keywords,
            max_docs_per_type,
            "jira_stories"
        )
        
        optimized_tests = self._optimize_docs(
            raw_context.similar_existing_tests,
            keywords,
            max_docs_per_type,
            "existing_tests"
        )
        
        optimized_external = self._optimize_docs(
            raw_context.similar_external_docs,
            keywords,
            max_docs_per_type,
            "external_docs"
        )
        
        optimized_swagger = self._optimize_docs(
            raw_context.similar_swagger_docs,
            keywords,
            max_docs_per_type + 2,  # Allow more swagger docs (important for APIs)
            "swagger"
        )
        
        optimized_context = RetrievedContext(
            similar_test_plans=optimized_test_plans,
            similar_confluence_docs=optimized_confluence,
            similar_jira_stories=optimized_stories,
            similar_existing_tests=optimized_tests,
            similar_external_docs=optimized_external,
            similar_swagger_docs=optimized_swagger
        )
        
        logger.info(f"✅ Optimized RAG context: {optimized_context.get_summary()}")
        return optimized_context
    
    def _optimize_docs(
        self,
        docs: List[Dict[str, Any]],
        keywords: List[str],
        max_docs: int,
        collection_name: str
    ) -> List[Dict[str, Any]]:
        """Apply all optimization steps to a document collection."""
        if not docs:
            return []
        
        logger.debug(f"Optimizing {collection_name}: {len(docs)} docs")
        
        # Step 1: Filter by similarity
        filtered = self.filter_by_similarity(docs)
        if not filtered:
            logger.debug(f"  No docs passed similarity threshold for {collection_name}")
            return []
        
        # Step 2: Re-rank by keywords
        reranked = self.rerank_by_keywords(filtered, keywords)
        
        # Step 3: Prioritize by type
        prioritized = self.prioritize_by_type(reranked)
        
        # Step 4: Deduplicate
        unique = self.deduplicate_docs(prioritized)
        
        # Step 5: Take top N (NO TRUNCATION - keep full documents)
        top_docs = unique[:max_docs]
        
        logger.debug(f"  {collection_name}: {len(docs)} → {len(top_docs)} docs (optimized, FULL documents)")
        return top_docs

