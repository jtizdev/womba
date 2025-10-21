"""
Context indexer for populating the RAG vector store with company-specific data.
Indexes: test plans, Confluence docs, Jira stories, existing tests.
"""

from typing import List, Dict, Optional, Any
import json
from datetime import datetime

from loguru import logger

from src.ai.rag_store import RAGVectorStore
from src.models.test_plan import TestPlan
from src.models.story import JiraStory
from src.aggregator.story_collector import StoryContext


class ContextIndexer:
    """
    Indexes company-specific context into the RAG vector store.
    Enables semantic search and retrieval for test generation.
    """
    
    def __init__(self):
        """Initialize context indexer with RAG store."""
        self.store = RAGVectorStore()
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
        logger.info(f"Indexing test plan for story {test_plan.story.key}")
        
        try:
            # Build document text from test plan
            doc_text = self._build_test_plan_document(test_plan)
            
            # Build metadata
            metadata = {
                "story_key": test_plan.story.key,
                "project_key": test_plan.story.key.split('-')[0],
                "summary": test_plan.story.summary[:200],
                "components": ','.join(test_plan.story.components) if test_plan.story.components else '',
                "test_count": len(test_plan.test_cases),
                "timestamp": datetime.now().isoformat(),
                "ai_model": test_plan.metadata.ai_model
            }
            
            # Generate unique ID
            doc_id = f"testplan_{test_plan.story.key}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # Add to vector store
            await self.store.add_documents(
                collection_name=self.store.TEST_PLANS_COLLECTION,
                documents=[doc_text],
                metadatas=[metadata],
                ids=[doc_id]
            )
            
            logger.info(f"Successfully indexed test plan {test_plan.story.key}")
            
        except Exception as e:
            logger.error(f"Failed to index test plan: {e}")
            # Don't raise - indexing failure shouldn't block test generation
    
    def _build_test_plan_document(self, test_plan: TestPlan) -> str:
        """
        Build a searchable document from a test plan.
        
        Args:
            test_plan: Test plan to convert
            
        Returns:
            Formatted document text
        """
        sections = []
        
        # Story context
        sections.append(f"Story: {test_plan.story.key} - {test_plan.story.summary}")
        sections.append(f"Components: {', '.join(test_plan.story.components or [])}")
        sections.append(f"\nSummary: {test_plan.summary}")
        
        # Test cases
        sections.append(f"\n{len(test_plan.test_cases)} Test Cases:")
        for i, tc in enumerate(test_plan.test_cases[:10], 1):  # Limit to first 10 for doc size
            sections.append(f"\n{i}. {tc.title}")
            sections.append(f"   Type: {tc.test_type}, Priority: {tc.priority}")
            sections.append(f"   Description: {tc.description[:200]}")
            if tc.steps:
                sections.append(f"   Steps: {len(tc.steps)} steps")
                # Include first step as example
                if tc.steps:
                    sections.append(f"   Example: {tc.steps[0].action[:100]}")
        
        return "\n".join(sections)
    
    async def index_confluence_docs(
        self,
        docs: List[Dict[str, Any]],
        project_key: Optional[str] = None
    ) -> None:
        """
        Index Confluence documentation for retrieval.
        Uses batching to handle large datasets.
        
        Args:
            docs: List of Confluence document dicts (from story_collector)
            project_key: Optional project key for filtering
        """
        if not docs:
            logger.info("No Confluence docs to index")
            return
        
        logger.info(f"Indexing {len(docs)} Confluence documents")
        
        # ChromaDB batch size limit
        BATCH_SIZE = 1000
        
        try:
            total_indexed = 0
            
            # Process in batches
            for i in range(0, len(docs), BATCH_SIZE):
                batch = docs[i:i + BATCH_SIZE]
                batch_num = (i // BATCH_SIZE) + 1
                total_batches = (len(docs) - 1) // BATCH_SIZE + 1
                
                if len(docs) > BATCH_SIZE:
                    logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch)} docs)")
                
                documents = []
                metadatas = []
                ids = []
                
                for doc in batch:
                    # Build document text
                    doc_text = f"Title: {doc.get('title', 'Unknown')}\n\n{doc.get('content', '')[:5000]}"
                    documents.append(doc_text)
                    
                    # Build metadata
                    metadata = {
                        "doc_id": str(doc.get('id', '')),
                        "title": str(doc.get('title', ''))[:200],
                        "space": str(doc.get('space', '')),
                        "url": str(doc.get('url', '')),
                        "project_key": str(project_key or 'unknown'),
                        "timestamp": datetime.now().isoformat()
                    }
                    metadatas.append(metadata)
                    
                    # Generate unique ID
                    doc_id = f"confluence_{doc.get('id', doc.get('title', 'unknown'))}_{datetime.now().strftime('%Y%m%d')}"
                    ids.append(doc_id)
                
                # Add batch to vector store
                await self.store.add_documents(
                    collection_name=self.store.CONFLUENCE_DOCS_COLLECTION,
                    documents=documents,
                    metadatas=metadatas,
                    ids=ids
                )
                
                total_indexed += len(batch)
                if len(docs) > BATCH_SIZE:
                    logger.info(f"Indexed batch {batch_num}/{total_batches} ({total_indexed}/{len(docs)} total)")
            
            logger.info(f"Successfully indexed {len(docs)} Confluence documents")
            
        except Exception as e:
            logger.error(f"Failed to index Confluence docs: {e}")
    
    async def index_jira_stories(
        self,
        stories: List[JiraStory],
        project_key: Optional[str] = None
    ) -> None:
        """
        Index Jira stories for pattern learning.
        Uses batching to handle large datasets.
        
        Args:
            stories: List of Jira stories
            project_key: Optional project key for filtering
        """
        if not stories:
            logger.info("No Jira stories to index")
            return
        
        logger.info(f"Indexing {len(stories)} Jira stories")
        
        # ChromaDB batch size limit
        BATCH_SIZE = 1000
        
        try:
            total_indexed = 0
            
            # Process in batches
            for i in range(0, len(stories), BATCH_SIZE):
                batch = stories[i:i + BATCH_SIZE]
                batch_num = (i // BATCH_SIZE) + 1
                total_batches = (len(stories) - 1) // BATCH_SIZE + 1
                
                if len(stories) > BATCH_SIZE:
                    logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch)} stories)")
                
                documents = []
                metadatas = []
                ids = []
                
                for story in batch:
                    # Build document text
                    doc_text = f"Story: {story.key} - {story.summary}\n\n"
                    if story.description:
                        doc_text += f"Description: {story.description[:2000]}\n\n"
                    if hasattr(story, 'acceptance_criteria') and story.acceptance_criteria:
                        doc_text += f"Acceptance Criteria: {story.acceptance_criteria[:2000]}"
                    
                    documents.append(doc_text)
                    
                    # Build metadata
                    metadata = {
                        "story_key": story.key,
                        "project_key": project_key or story.key.split('-')[0],
                        "summary": story.summary[:200],
                        "issue_type": story.issue_type,
                        "status": story.status,
                        "components": ','.join(story.components) if story.components else '',
                        "timestamp": datetime.now().isoformat()
                    }
                    metadatas.append(metadata)
                    
                    # Generate unique ID
                    doc_id = f"jira_{story.key}"
                    ids.append(doc_id)
                
                # Add batch to vector store
                await self.store.add_documents(
                    collection_name=self.store.JIRA_STORIES_COLLECTION,
                    documents=documents,
                    metadatas=metadatas,
                    ids=ids
                )
                
                total_indexed += len(batch)
                if len(stories) > BATCH_SIZE:
                    logger.info(f"Indexed batch {batch_num}/{total_batches} ({total_indexed}/{len(stories)} total)")
            
            logger.info(f"Successfully indexed {len(stories)} Jira stories")
            
        except Exception as e:
            logger.error(f"Failed to index Jira stories: {e}")
    
    async def index_existing_tests(
        self,
        tests: List[Dict[str, Any]],
        project_key: str
    ) -> None:
        """
        Index existing Zephyr test cases for duplicate detection and style learning.
        Uses batching to handle large datasets.
        
        Args:
            tests: List of existing test case dicts from Zephyr
            project_key: Project key for filtering
        """
        if not tests:
            logger.info("No existing tests to index")
            return
        
        logger.info(f"Indexing {len(tests)} existing test cases")
        
        # ChromaDB batch size limit (be conservative)
        BATCH_SIZE = 1000
        
        try:
            total_indexed = 0
            
            # Process in batches
            for i in range(0, len(tests), BATCH_SIZE):
                batch = tests[i:i + BATCH_SIZE]
                batch_num = (i // BATCH_SIZE) + 1
                total_batches = (len(tests) - 1) // BATCH_SIZE + 1
                
                logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch)} tests)")
                
                documents = []
                metadatas = []
                ids = []
                
                for test in batch:
                    # Build document text
                    doc_text = f"Test: {test.get('name', 'Unknown')}\n\n"
                    if test.get('objective'):
                        doc_text += f"Objective: {test.get('objective', '')[:1000]}\n\n"
                    if test.get('precondition'):
                        doc_text += f"Precondition: {test.get('precondition', '')[:500]}"
                    
                    documents.append(doc_text)
                    
                    # Build metadata (ensure all values are primitives, not dicts)
                    status = test.get('status', '')
                    if isinstance(status, dict):
                        status = status.get('name', '')
                    
                    priority = test.get('priority', '')
                    if isinstance(priority, dict):
                        priority = priority.get('name', '')
                    
                    metadata = {
                        "test_key": str(test.get('key', '')),
                        "test_name": str(test.get('name', ''))[:200],
                        "project_key": str(project_key),
                        "status": str(status),
                        "priority": str(priority),
                        "timestamp": datetime.now().isoformat()
                    }
                    metadatas.append(metadata)
                    
                    # Generate unique ID
                    test_key = test.get('key', test.get('name', 'unknown'))
                    doc_id = f"test_{test_key}_{datetime.now().strftime('%Y%m%d')}"
                    ids.append(doc_id)
                
                # Add batch to vector store
                await self.store.add_documents(
                    collection_name=self.store.EXISTING_TESTS_COLLECTION,
                    documents=documents,
                    metadatas=metadatas,
                    ids=ids
                )
                
                total_indexed += len(batch)
                logger.info(f"Indexed batch {batch_num}/{total_batches} ({total_indexed}/{len(tests)} total)")
            
            logger.info(f"Successfully indexed {len(tests)} existing tests in {total_batches} batches")
            
        except Exception as e:
            logger.error(f"Failed to index existing tests: {e}")
    
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

