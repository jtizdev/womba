"""
Context indexer for populating the RAG vector store with company-specific data.
Indexes: test plans, Confluence docs, Jira stories, existing tests.
"""

import asyncio
import hashlib
import json
import re
from datetime import datetime
from typing import List, Dict, Optional, Any
from urllib.error import URLError, HTTPError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from loguru import logger

from src.ai.rag_store import RAGVectorStore
from src.models.test_plan import TestPlan
from src.models.story import JiraStory
from src.aggregator.story_collector import StoryContext
from src.config.settings import settings
from src.external.plainid_crawler import PlainIDDocCrawler, PlainIDDocument

try:  # pragma: no cover - optional dependency
    from bs4 import BeautifulSoup  # type: ignore
except ImportError:  # pragma: no cover
    BeautifulSoup = None  # type: ignore


class ContextIndexer:
    """
    Indexes company-specific context into the RAG vector store.
    Enables semantic search and retrieval for test generation.
    """
    
    def __init__(self):
        """Initialize context indexer with RAG store."""
        self.store = RAGVectorStore()
        logger.info("Initialized context indexer")

    @staticmethod
    def _strip_html_tags(html: str) -> str:
        """Convert HTML to readable text by stripping scripts/styles and tags."""
        if not html:
            return ""

        # Use BeautifulSoup if available for better parsing
        if BeautifulSoup is not None:
            try:
                soup = BeautifulSoup(html, "html.parser")
                # Remove script and style elements
                for tag in soup(["script", "style", "nav", "header", "footer"]):
                    tag.decompose()
                # Get text with preserved line breaks
                text = soup.get_text("\n")
                # Clean up whitespace
                text = re.sub(r"\r", "\n", text)  # Normalize line endings
                text = re.sub(r"\n{3,}", "\n\n", text)  # Collapse multiple newlines
                return text.strip()
            except Exception as e:
                logger.debug(f"BeautifulSoup parsing failed, using regex fallback: {e}")

        # Fallback: regex-based stripping
        cleaned = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html)
        cleaned = re.sub(r"(?i)<br[/\\s]*>", "\n", cleaned)
        cleaned = re.sub(r"(?i)</p>", "\n\n", cleaned)
        cleaned = re.sub(r"<[^>]+>", " ", cleaned)
        cleaned = re.sub(r"&nbsp;", " ", cleaned)
        cleaned = re.sub(r"&amp;", "&", cleaned)
        cleaned = re.sub(r"&lt;", "<", cleaned)
        cleaned = re.sub(r"&gt;", ">", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned)
        return cleaned.strip()

    @staticmethod
    def _extract_title(html: str, fallback: str) -> str:
        match = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        if match:
            return ContextIndexer._strip_html_tags(match.group(1))[:200]
        return fallback

    @staticmethod
    def _fetch_url(url: str) -> Optional[str]:
        try:
            headers = {"User-Agent": "WombaIndexer/1.0"}
            req = Request(url, headers=headers)
            with urlopen(req, timeout=30) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                return response.read().decode(charset, errors="ignore")
        except (HTTPError, URLError, TimeoutError) as exc:
            logger.warning(f"Failed to fetch {url}: {exc}")
        except Exception as exc:
            logger.warning(f"Unexpected error fetching {url}: {exc}")
        return None
    
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
        
        # Test cases - INDEX ALL with FULL details
        sections.append(f"\n{len(test_plan.test_cases)} Test Cases:")
        for i, tc in enumerate(test_plan.test_cases, 1):  # Include ALL test cases
            sections.append(f"\n{i}. {tc.title}")
            sections.append(f"   Type: {tc.test_type}, Priority: {tc.priority}, Risk: {tc.risk_level}")
            # Include FULL description (no truncation)
            sections.append(f"   Description: {tc.description}")
            
            # Include preconditions
            if tc.preconditions:
                sections.append(f"   Preconditions: {tc.preconditions}")
            
            # Include ALL steps with full details
            if tc.steps:
                sections.append(f"   Steps ({len(tc.steps)} total):")
                for step in tc.steps:
                    sections.append(f"      Step {step.step_number}: {step.action}")
                    sections.append(f"         Expected: {step.expected_result}")
                    if step.test_data:
                        sections.append(f"         Test Data: {step.test_data}")
            
            # Include expected result
            if tc.expected_result:
                sections.append(f"   Expected Result: {tc.expected_result}")
            
            # Include tags for better searchability
            if tc.tags:
                sections.append(f"   Tags: {', '.join(tc.tags)}")
        
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
                    # Build document text - STORE COMPLETE CONTENT (no truncation!)
                    # Confluence docs are CRITICAL for terminology and context
                    doc_text = f"Title: {doc.get('title', 'Unknown')}\n\n{doc.get('content', '')}"
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
                    # Build document text with COMPLETE information
                    doc_text = f"Story: {story.key} - {story.summary}\n\n"
                    if story.description:
                        # Include FULL description - contains critical feature details
                        doc_text += f"Description: {story.description}\n\n"
                    if hasattr(story, 'acceptance_criteria') and story.acceptance_criteria:
                        # Include FULL acceptance criteria - essential for test generation
                        doc_text += f"Acceptance Criteria: {story.acceptance_criteria}"
                    
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
                    # Build document text with FULL details (no truncation)
                    doc_text = f"Test: {test.get('name', 'Unknown')}\n\n"
                    
                    # Include full objective
                    if test.get('objective'):
                        doc_text += f"Objective: {test.get('objective', '')}\n\n"
                    
                    # Include full precondition
                    if test.get('precondition'):
                        doc_text += f"Precondition: {test.get('precondition', '')}\n\n"
                    
                    # Include test script/steps if available
                    if test.get('testScript'):
                        script = test.get('testScript', {})
                        if isinstance(script, dict) and script.get('steps'):
                            doc_text += "Steps:\n"
                            for step in script.get('steps', []):
                                if isinstance(step, dict):
                                    doc_text += f"  - {step.get('description', '')}\n"
                                    if step.get('expectedResult'):
                                        doc_text += f"    Expected: {step.get('expectedResult')}\n"
                    
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

    async def index_external_docs(self) -> int:
        """
        Index external PlainID documentation using efficient two-phase approach:
        1. Discover URLs via lightweight crawl (if base_url configured)
        2. Fetch content via direct GET requests
        """

        if not settings.plainid_doc_index_enabled:
            logger.info("External documentation indexing disabled via settings")
            return 0

        # Initialize crawler if base_url is configured
        crawler = None
        base_url = settings.plainid_doc_base_url
        if base_url:
            crawler = PlainIDDocCrawler(
                base_url=base_url,
                max_pages=settings.plainid_doc_max_pages,
                delay=settings.plainid_doc_request_delay,
                max_depth=settings.plainid_doc_max_depth,
            )
            if not crawler.is_available():
                logger.warning("PlainID crawler dependencies not available, falling back to direct URL fetching")

        # Get URLs to index
        urls_to_index: List[str] = []
        
        # Option 1: Discover URLs via crawler (preferred for comprehensive indexing)
        if crawler and crawler.is_available():
            logger.info(f"Discovering URLs from base URL: {base_url}")
            discovered_urls = await asyncio.to_thread(crawler.discover_urls)
            if discovered_urls:
                urls_to_index = discovered_urls
                logger.info(f"Discovered {len(urls_to_index)} URLs to index")
        
        # Option 2: Use explicitly configured URLs (for specific pages)
        configured_urls = settings.plainid_doc_urls or []
        if configured_urls:
            if urls_to_index:
                # Merge with discovered URLs, avoiding duplicates
                existing = set(urls_to_index)
                for url in configured_urls:
                    if url not in existing:
                        urls_to_index.append(url)
            else:
                urls_to_index = configured_urls
            logger.info(f"Added {len(configured_urls)} explicitly configured URLs")

        if not urls_to_index:
            logger.info("No external documentation URLs to index (configure base_url or plainid_doc_urls)")
            return 0

        logger.info(f"Indexing {len(urls_to_index)} external documentation sources")

        # Fetch content for all URLs
        plainid_docs: List[PlainIDDocument] = []
        if crawler and crawler.is_available():
            # Use crawler's efficient batch fetching
            logger.info("Fetching content using crawler...")
            plainid_docs = await asyncio.to_thread(crawler.fetch_content, urls_to_index)
        else:
            # Fallback: fetch URLs individually
            logger.info("Fetching content for individual URLs...")
            for url in urls_to_index:
                html = await asyncio.to_thread(self._fetch_url, url)
                if not html:
                    continue
                
                if BeautifulSoup is not None and crawler:
                    soup = BeautifulSoup(html, "html.parser")
                    title = crawler._extract_title(soup, url)
                else:
                    title = self._extract_title(html, urlparse(url).path or url)
                
                plainid_docs.append(PlainIDDocument(url=url, title=title, html=html))

        if not plainid_docs:
            logger.warning("No external documentation content fetched (all requests failed)")
            return 0

        # Process and index documents
        documents: List[str] = []
        metadatas: List[Dict[str, Any]] = []
        ids: List[str] = []

        existing_hashes = set()
        try:
            existing_docs = self.store.get_all_documents(self.store.EXTERNAL_DOCS_COLLECTION)
            for doc in existing_docs:
                meta = doc.get('metadata', {})
                if meta.get('doc_hash'):
                    existing_hashes.add(meta['doc_hash'])
        except Exception as exc:
            logger.debug(f"Could not fetch existing external docs: {exc}")

        for doc in plainid_docs:
            url = doc.url
            title = doc.title
            html = doc.html

            # Extract text content from HTML
            text = self._strip_html_tags(html)
            if not text:
                logger.warning(f"No textual content extracted from {url}")
                continue

            # Build document text
            doc_text = f"Source: {url}\nTitle: {title}\n\nContent:\n{text}"
            
            # Extract endpoint info from URL for better metadata
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
            
            # Check if document contains request examples
            has_request_examples = "request" in text.lower() and ("{" in text or "[" in text)
            has_json_examples = "=== JSON EXAMPLES ===" in text
            
            documents.append(doc_text)

            # Check for duplicates
            doc_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
            if doc_hash in existing_hashes:
                logger.debug(f"Skipping already indexed documentation: {url}")
                documents.pop()
                continue

            metadata = {
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
            metadatas.append(metadata)
            ids.append(f"plainid_{doc_hash}_{datetime.now().strftime('%Y%m%d')}")
            existing_hashes.add(doc_hash)

        if not documents:
            logger.warning("No external documentation indexed (all documents were duplicates or had no content)")
            return 0

        # Batch add to vector store
        await self.store.add_documents(
            collection_name=self.store.EXTERNAL_DOCS_COLLECTION,
            documents=documents,
            metadatas=metadatas,
            ids=ids,
        )

        logger.info(f"Successfully indexed {len(documents)} external documentation entries")
        return len(documents)
    
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

