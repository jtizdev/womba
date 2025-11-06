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
    """
    
    def __init__(self):
        """Initialize RAG retriever."""
        self.store = RAGVectorStore()
        self.top_k_tests = settings.rag_top_k_tests
        self.top_k_docs = settings.rag_top_k_docs
        self.top_k_stories = settings.rag_top_k_stories
        self.top_k_existing = settings.rag_top_k_existing
        self.top_k_swagger = settings.rag_top_k_swagger
        logger.info("Initialized RAG retriever")
    
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
            query_parts.append(f"Acceptance Criteria: {story.acceptance_criteria[:800]}")
        
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
            stats = self.store.get_collection_stats(self.store.JIRA_STORIES_COLLECTION)
            if stats.get('count', 0) == 0:
                logger.info("Jira stories collection is empty, skipping retrieval")
                return []
            
            results = await self.store.retrieve_similar(
                collection_name=self.store.JIRA_STORIES_COLLECTION,
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
        """Retrieve similar external documentation (PlainID API docs)."""
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

