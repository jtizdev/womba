"""
Core document indexing service for adding documents to the vector store.
Single Responsibility: Adding documents to RAG vector store with proper metadata.
"""

import hashlib
from datetime import datetime
from typing import List, Dict, Any, Optional
from loguru import logger

from src.ai.rag_store import RAGVectorStore
from src.models.test_plan import TestPlan
from src.models.story import JiraStory
from src.config.settings import settings


class DocumentIndexer:
    """
    Core indexing service for adding documents to the vector store.
    Features:
    - Batch processing
    - Metadata management
    - Upsert logic
    """

    def __init__(self, store: Optional[RAGVectorStore] = None):
        """
        Initialize document indexer.
        
        Args:
            store: Optional RAG store (creates new if not provided)
        """
        self.store = store or RAGVectorStore()
        logger.info("Initialized document indexer")

    async def index_test_plan(
        self,
        test_plan: TestPlan,
        doc_text: str,
    ) -> None:
        """
        Index a test plan document.
        
        Args:
            test_plan: Test plan object
            doc_text: Formatted document text
        """
        logger.info(f"Indexing test plan for story {test_plan.story.key}")
        
        try:
            metadata = {
                "story_key": test_plan.story.key,
                "project_key": test_plan.story.key.split('-')[0],
                "summary": test_plan.story.summary[:200],
                "components": ','.join(test_plan.story.components) if test_plan.story.components else '',
                "test_count": len(test_plan.test_cases),
                "timestamp": datetime.now().isoformat(),
                "ai_model": test_plan.metadata.ai_model
            }
            
            doc_id = f"testplan_{test_plan.story.key}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            await self.store.add_documents(
                collection_name=self.store.TEST_PLANS_COLLECTION,
                documents=[doc_text],
                metadatas=[metadata],
                ids=[doc_id]
            )
            
            logger.info(f"Successfully indexed test plan {test_plan.story.key}")
            
        except Exception as e:
            logger.error(f"Failed to index test plan: {e}")

    async def index_confluence_docs(
        self,
        doc_texts: List[str],
        metadatas: List[Dict[str, Any]],
        ids: List[str],
        batch_size: int = 1000,
    ) -> None:
        """
        Index Confluence documents with batching.
        
        Args:
            doc_texts: List of document texts
            metadatas: List of metadata dicts
            ids: List of document IDs
            batch_size: Batch size for indexing
        """
        total = len(doc_texts)
        logger.info(f"📄 Indexing {total} Confluence documents (with upsert logic)")
        
        try:
            for i in range(0, total, batch_size):
                batch_docs = doc_texts[i:i + batch_size]
                batch_meta = metadatas[i:i + batch_size]
                batch_ids = ids[i:i + batch_size]
                
                await self.store.add_documents(
                    collection_name=self.store.CONFLUENCE_DOCS_COLLECTION,
                    documents=batch_docs,
                    metadatas=batch_meta,
                    ids=batch_ids
                )
                
                if total > batch_size:
                    batch_num = (i // batch_size) + 1
                    total_batches = (total - 1) // batch_size + 1
                    logger.info(f"📦 Processed batch {batch_num}/{total_batches}")
            
            logger.info(f"✅ Finished processing {total} Confluence documents")
            
        except Exception as e:
            logger.error(f"Failed to index Confluence docs: {e}")

    async def index_jira_stories(
        self,
        doc_texts: List[str],
        metadatas: List[Dict[str, Any]],
        ids: List[str],
        batch_size: int = 1000,
    ) -> None:
        """
        Index Jira stories with batching.
        
        Args:
            doc_texts: List of document texts
            metadatas: List of metadata dicts
            ids: List of document IDs
            batch_size: Batch size for indexing
        """
        total = len(doc_texts)
        logger.info(f"📋 Indexing {total} Jira stories (with upsert logic)")
        
        try:
            for i in range(0, total, batch_size):
                batch_docs = doc_texts[i:i + batch_size]
                batch_meta = metadatas[i:i + batch_size]
                batch_ids = ids[i:i + batch_size]
                
                await self.store.add_documents(
                    collection_name=self.store.JIRA_STORIES_COLLECTION,
                    documents=batch_docs,
                    metadatas=batch_meta,
                    ids=batch_ids
                )
                
                if total > batch_size:
                    batch_num = (i // batch_size) + 1
                    total_batches = (total - 1) // batch_size + 1
                    logger.info(f"📦 Processed batch {batch_num}/{total_batches}")
            
            logger.info(f"✅ Finished processing {total} Jira stories")
            
        except Exception as e:
            logger.error(f"Failed to index Jira stories: {e}")

    async def index_existing_tests(
        self,
        doc_texts: List[str],
        metadatas: List[Dict[str, Any]],
        ids: List[str],
        batch_size: int = 1000,
    ) -> None:
        """
        Index existing test cases with batching.
        
        Args:
            doc_texts: List of document texts
            metadatas: List of metadata dicts
            ids: List of document IDs
            batch_size: Batch size for indexing
        """
        total = len(doc_texts)
        logger.info(f"Indexing {total} existing test cases")
        
        try:
            for i in range(0, total, batch_size):
                batch_docs = doc_texts[i:i + batch_size]
                batch_meta = metadatas[i:i + batch_size]
                batch_ids = ids[i:i + batch_size]
                
                await self.store.add_documents(
                    collection_name=self.store.EXISTING_TESTS_COLLECTION,
                    documents=batch_docs,
                    metadatas=batch_meta,
                    ids=batch_ids
                )
                
                batch_num = (i // batch_size) + 1
                total_batches = (total - 1) // batch_size + 1
                logger.info(f"Indexed batch {batch_num}/{total_batches}")
            
            logger.info(f"Successfully indexed {total} existing tests")
            
        except Exception as e:
            logger.error(f"Failed to index existing tests: {e}")

    async def index_external_docs(
        self,
        doc_texts: List[str],
        metadatas: List[Dict[str, Any]],
        ids: List[str],
    ) -> int:
        """
        Index external documentation.
        
        Args:
            doc_texts: List of document texts
            metadatas: List of metadata dicts
            ids: List of document IDs
            
        Returns:
            Number of documents indexed
        """
        if not doc_texts:
            logger.warning("No external documentation to index")
            return 0
        
        try:
            await self.store.add_documents(
                collection_name=self.store.EXTERNAL_DOCS_COLLECTION,
                documents=doc_texts,
                metadatas=metadatas,
                ids=ids,
            )
            
            logger.info(f"Successfully indexed {len(doc_texts)} external documentation entries")
            return len(doc_texts)
            
        except Exception as e:
            logger.error(f"Failed to index external docs: {e}")
            return 0

    def create_confluence_metadata(
        self,
        doc: Dict[str, Any],
        project_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create metadata dict for Confluence document.
        
        Args:
            doc: Confluence document dict
            project_key: Optional project key
            
        Returns:
            Metadata dictionary
        """
        last_modified = doc.get('last_modified') or datetime.now().isoformat()
        
        return {
            "doc_id": str(doc.get('id', '')),
            "title": str(doc.get('title', ''))[:200],
            "space": str(doc.get('space', '')),
            "url": str(doc.get('url', '')),
            "project_key": str(project_key or 'unknown'),
            "timestamp": datetime.now().isoformat(),
            "last_modified": last_modified
        }

    def create_jira_metadata(
        self,
        story: JiraStory,
        project_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create metadata dict for Jira story.
        
        Args:
            story: JiraStory object
            project_key: Optional project key
            
        Returns:
            Metadata dictionary
        """
        last_modified = story.updated.isoformat() if hasattr(story, 'updated') and story.updated else datetime.now().isoformat()
        
        return {
            "story_key": story.key,
            "project_key": project_key or story.key.split('-')[0],
            "summary": story.summary[:200],
            "issue_type": story.issue_type,
            "status": story.status,
            "components": ','.join(story.components) if story.components else '',
            "timestamp": datetime.now().isoformat(),
            "last_modified": last_modified
        }

    def create_test_metadata(
        self,
        test: Dict[str, Any],
        project_key: str
    ) -> Dict[str, Any]:
        """
        Create metadata dict for existing test.
        
        Args:
            test: Test case dict
            project_key: Project key
            
        Returns:
            Metadata dictionary
        """
        status = test.get('status', '')
        if isinstance(status, dict):
            status = status.get('name', '')
        
        priority = test.get('priority', '')
        if isinstance(priority, dict):
            priority = priority.get('name', '')
        
        return {
            "test_key": str(test.get('key', '')),
            "test_name": str(test.get('name', ''))[:200],
            "project_key": str(project_key),
            "status": str(status),
            "priority": str(priority),
            "timestamp": datetime.now().isoformat()
        }

    def create_external_doc_metadata(
        self,
        url: str,
        title: str,
        text: str
    ) -> Dict[str, Any]:
        """
        Create metadata dict for external documentation.
        
        Args:
            url: Source URL
            title: Document title
            text: Document text content
            
        Returns:
            Metadata dictionary
        """
        # Extract endpoint type from URL
        endpoint_type = "unknown"
        if "/policy-resolution" in url:
            endpoint_type = "policy-resolution"
        elif "/authorization" in url:
            endpoint_type = "authorization"
        elif "/authentication" in url:
            endpoint_type = "authentication"
        elif "/users" in url:
            endpoint_type = "users"
        elif "/policies" in url:
            endpoint_type = "policies"
        
        # Check for examples
        has_request_examples = "request" in text.lower() and ("{" in text or "[" in text)
        has_json_examples = "=== JSON EXAMPLES ===" in text
        
        doc_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
        
        return {
            "source": "plainid_docs",
            "source_url": url,
            "title": title,
            "project_key": settings.plainid_doc_project_key,
            "doc_hash": doc_hash,
            "timestamp": datetime.now().isoformat(),
            "api_version": "v1-api",
            "endpoint_type": endpoint_type,
            "has_request_examples": str(has_request_examples),
            "has_json_examples": str(has_json_examples),
        }

    def create_stable_id(self, prefix: str, identifier: str) -> str:
        """
        Create a stable ID for document.
        
        Args:
            prefix: ID prefix (e.g., 'confluence', 'jira')
            identifier: Unique identifier
            
        Returns:
            Stable document ID
        """
        return f"{prefix}_{identifier}"

    def create_timestamped_id(self, prefix: str, identifier: str) -> str:
        """
        Create a timestamped ID for document.
        
        Args:
            prefix: ID prefix
            identifier: Unique identifier
            
        Returns:
            Timestamped document ID
        """
        return f"{prefix}_{identifier}_{datetime.now().strftime('%Y%m%d')}"

