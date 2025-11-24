"""
Context indexer for populating the RAG vector store with company-specific data.
Orchestrates document fetching, processing, and indexing.

Refactored to follow SOLID principles:
- Single Responsibility: Orchestration only
- Dependency Injection: Uses DocumentProcessor, DocumentFetcher, DocumentIndexer
"""

from datetime import datetime
from typing import List, Dict, Optional, Any

from loguru import logger

from src.ai.indexing.document_processor import DocumentProcessor
from src.ai.indexing.document_fetcher import DocumentFetcher
from src.ai.indexing.document_indexer import DocumentIndexer
from src.ai.rag_store import RAGVectorStore
from src.models.test_plan import TestPlan
from src.models.story import JiraStory
from src.aggregator.story_collector import StoryContext


class ContextIndexer:
    """
    Orchestrates document indexing workflow.
    Delegates processing, fetching, and indexing to specialized services.
    """
    
    def __init__(
        self,
        processor: Optional[DocumentProcessor] = None,
        fetcher: Optional[DocumentFetcher] = None,
        indexer: Optional[DocumentIndexer] = None
    ):
        """
        Initialize context indexer with services.
        
        Args:
            processor: Document processor (creates new if not provided)
            fetcher: Document fetcher (creates new if not provided)
            indexer: Document indexer (creates new if not provided)
        """
        self.processor = processor or DocumentProcessor()
        self.fetcher = fetcher or DocumentFetcher()
        self.indexer = indexer or DocumentIndexer()
        self.store = self.indexer.store  # Keep for backward compatibility
        logger.info("Initialized context indexer")

    
    async def index_test_plan(
        self,
        test_plan: TestPlan,
        context: StoryContext
    ) -> None:
        """
        Index a generated test plan for future retrieval.
        
        Args:
            test_plan: Generated test plan
            context: Story context used for generation
        """
        doc_text = self.processor.build_test_plan_document(test_plan)
        await self.indexer.index_test_plan(test_plan, doc_text)
    
    async def index_confluence_docs(
        self,
        docs: List[Dict[str, Any]],
        project_key: Optional[str] = None
    ) -> None:
        """
        Index Confluence documentation for retrieval.
        
        Args:
            docs: List of Confluence document dicts (from story_collector)
            project_key: Optional project key for filtering
        """
        if not docs:
            logger.info("No Confluence docs to index")
            return
        
        # Process documents
        doc_texts = []
        metadatas = []
        ids = []
        
        for doc in docs:
            doc_text = self.processor.build_confluence_document(doc)
            metadata = self.indexer.create_confluence_metadata(doc, project_key)
            doc_id = self.indexer.create_stable_id("confluence", str(doc.get('id', doc.get('title', 'unknown'))))
            
            doc_texts.append(doc_text)
            metadatas.append(metadata)
            ids.append(doc_id)
        
        # Index documents
        await self.indexer.index_confluence_docs(doc_texts, metadatas, ids)
    
    async def index_jira_stories(
        self,
        stories: List[JiraStory],
        project_key: Optional[str] = None
    ) -> None:
        """
        Index Jira stories for pattern learning.
        
        Args:
            stories: List of Jira stories
            project_key: Optional project key for filtering
        """
        if not stories:
            logger.info("No Jira stories to index")
            return
        
        # Process stories
        doc_texts = []
        metadatas = []
        ids = []
        
        for story in stories:
            doc_text = self.processor.build_jira_story_document(story)
            metadata = self.indexer.create_jira_metadata(story, project_key)
            doc_id = self.indexer.create_stable_id("jira", story.key)
            
            doc_texts.append(doc_text)
            metadatas.append(metadata)
            ids.append(doc_id)
        
        # Index stories
        await self.indexer.index_jira_stories(doc_texts, metadatas, ids)
    
    async def index_existing_tests(
        self,
        tests: List[Dict[str, Any]],
        project_key: str
    ) -> None:
        """
        Index existing Zephyr test cases for duplicate detection and style learning.
        
        Args:
            tests: List of existing test case dicts from Zephyr
            project_key: Project key for filtering
        """
        if not tests:
            logger.info("No existing tests to index")
            return
        
        # Process tests
        doc_texts = []
        metadatas = []
        ids = []
        
        for test in tests:
            doc_text = self.processor.build_test_case_document(test)
            metadata = self.indexer.create_test_metadata(test, project_key)
            test_key = test.get('key', test.get('name', 'unknown'))
            doc_id = self.indexer.create_stable_id("test", test_key)
            
            doc_texts.append(doc_text)
            metadatas.append(metadata)
            ids.append(doc_id)
        
        # Index tests
        await self.indexer.index_existing_tests(doc_texts, metadatas, ids)

    async def index_external_docs(self) -> int:
        """
        Index external PlainID documentation.
        Uses DocumentFetcher and DocumentIndexer services.
        
        Returns:
            Number of documents indexed
        """
        # Fetch external documents
        external_docs = await self.fetcher.fetch_external_docs()
        
        if not external_docs:
            return 0
        
        # Process documents (ChromaDB will handle upserts based on stable IDs)
        doc_texts = []
        metadatas = []
        ids = []
        
        for doc in external_docs:
            # Process document text
            doc_text = self.processor.build_external_doc_document(doc.url, doc.title, doc.html)
            if not doc_text:
                continue
            
            # Create metadata
            metadata = self.indexer.create_external_doc_metadata(doc.url, doc.title, doc_text)
            doc_hash = metadata['doc_hash']
            
            doc_texts.append(doc_text)
            metadatas.append(metadata)
            ids.append(f"plainid_{doc_hash}")
        
        if not doc_texts:
            logger.warning("No new external documentation to index")
            return 0
        
        # Index documents
        return await self.indexer.index_external_docs(doc_texts, metadatas, ids)
    
    async def index_story_context(
        self,
        context: StoryContext,
        project_key: str
    ) -> None:
        """
        Index all context for a story (Confluence docs, linked stories, etc.).
        
        Args:
            context: Story context from story collector
            project_key: Project key for filtering
        """
        logger.info(f"Indexing full context for story {context.main_story.key}")
        
        # Index Confluence docs
        confluence_docs = context.get('confluence_docs', [])
        if confluence_docs:
            await self.index_confluence_docs(confluence_docs, project_key)
        
        # Index linked stories
        linked_stories = context.get('linked_stories', [])
        if linked_stories:
            await self.index_jira_stories(linked_stories, project_key)
        
        # Index main story
        await self.index_jira_stories([context.main_story], project_key)
        
        logger.info(f"Successfully indexed context for {context.main_story.key}")

    async def index_gitlab_swagger_docs(self) -> int:
        """
        Index GitLab Swagger/OpenAPI documentation.
        Uses DocumentFetcher and DocumentIndexer services.
        
        Returns:
            Number of documents indexed
        """
        # Fetch GitLab Swagger documents
        swagger_docs = await self.fetcher.fetch_gitlab_swagger_docs()
        
        if not swagger_docs:
            return 0
        
        # Process documents (ChromaDB will handle upserts based on stable IDs)
        doc_texts = []
        metadatas = []
        ids = []
        
        for doc in swagger_docs:
            # Process document text
            doc_text = self.processor.build_swagger_document(doc)
            if not doc_text:
                continue
            
            # Create metadata
            # Extract project key from service name or use default
            project_key = doc.service_name.split('-')[0].upper() if '-' in doc.service_name else 'PLAT'
            metadata = self.indexer.create_swagger_metadata(doc, project_key)
            doc_hash = metadata['doc_hash']
            
            doc_texts.append(doc_text)
            metadatas.append(metadata)
            ids.append(f"swagger_{doc_hash}")
        
        if not doc_texts:
            logger.warning("No new Swagger documentation to index")
            return 0
        
        # Index documents
        return await self.indexer.index_swagger_docs(doc_texts, metadatas, ids)

