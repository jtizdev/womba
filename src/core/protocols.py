"""
Protocol interfaces for dependency inversion.
Defines contracts for major services to enable loose coupling and testability.
"""

from typing import Protocol, List, Dict, Any, Optional
from src.models.story import JiraStory
from src.models.test_plan import TestPlan


class IJiraClient(Protocol):
    """Interface for Jira client operations."""

    async def get_issue(self, key: str) -> JiraStory:
        """
        Get a single Jira issue by key.
        
        Args:
            key: Issue key (e.g., 'PROJ-123')
            
        Returns:
            JiraStory object
        """
        ...

    def search_issues(
        self,
        jql: str,
        max_results: int = 50,
        start_at: int = 0
    ) -> tuple[List[JiraStory], int]:
        """
        Search for issues using JQL.
        
        Args:
            jql: JQL query string
            max_results: Maximum number of results
            start_at: Starting index for pagination
            
        Returns:
            Tuple of (list of stories, total count)
        """
        ...


class IConfluenceClient(Protocol):
    """Interface for Confluence client operations."""

    def search_pages(
        self,
        cql: str,
        limit: int = 100,
        start: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Search for Confluence pages using CQL.
        
        Args:
            cql: CQL query string
            limit: Maximum number of results
            start: Starting index for pagination
            
        Returns:
            List of page dictionaries
        """
        ...

    def get_page_content(self, page_id: str) -> Optional[Dict[str, Any]]:
        """
        Get full content of a Confluence page.
        
        Args:
            page_id: Page ID
            
        Returns:
            Page dictionary with content or None
        """
        ...


class IZephyrClient(Protocol):
    """Interface for Zephyr Scale client operations."""

    async def get_test_cases(
        self,
        project_key: str,
        folder_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get test cases from Zephyr.
        
        Args:
            project_key: Project key
            folder_id: Optional folder ID to filter
            
        Returns:
            List of test case dictionaries
        """
        ...

    async def create_test_case(
        self,
        project_key: str,
        test_case_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create a test case in Zephyr.
        
        Args:
            project_key: Project key
            test_case_data: Test case data
            
        Returns:
            Created test case dictionary
        """
        ...


class IRAGVectorStore(Protocol):
    """Interface for RAG vector store operations."""

    async def add_documents(
        self,
        collection_name: str,
        documents: List[str],
        metadatas: List[Dict[str, Any]],
        ids: List[str]
    ) -> None:
        """
        Add documents to a collection.
        
        Args:
            collection_name: Name of the collection
            documents: List of document texts
            metadatas: List of metadata dictionaries
            ids: List of document IDs
        """
        ...

    async def query(
        self,
        collection_name: str,
        query_text: str,
        n_results: int = 5,
        where: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Query a collection for similar documents.
        
        Args:
            collection_name: Name of the collection
            query_text: Query text
            n_results: Number of results to return
            where: Optional metadata filter
            
        Returns:
            List of result dictionaries
        """
        ...


class IDocumentProcessor(Protocol):
    """Interface for document processing operations."""

    def strip_html_tags(self, html: str) -> str:
        """
        Convert HTML to readable text.
        
        Args:
            html: HTML content
            
        Returns:
            Clean text content
        """
        ...

    def build_test_plan_document(self, test_plan: TestPlan) -> str:
        """
        Build a searchable document from a test plan.
        
        Args:
            test_plan: Test plan to convert
            
        Returns:
            Formatted document text
        """
        ...


class IDocumentIndexer(Protocol):
    """Interface for document indexing operations."""

    async def index_test_plan(
        self,
        test_plan: TestPlan,
        doc_text: str
    ) -> None:
        """
        Index a test plan document.
        
        Args:
            test_plan: Test plan object
            doc_text: Formatted document text
        """
        ...

    async def index_confluence_docs(
        self,
        doc_texts: List[str],
        metadatas: List[Dict[str, Any]],
        ids: List[str],
        batch_size: int = 1000
    ) -> None:
        """
        Index Confluence documents with batching.
        
        Args:
            doc_texts: List of document texts
            metadatas: List of metadata dicts
            ids: List of document IDs
            batch_size: Batch size for indexing
        """
        ...


class IPromptBuilder(Protocol):
    """Interface for prompt building operations."""

    def build_generation_prompt(
        self,
        context: Any,  # StoryContext
        rag_context: Optional[str] = None,
        existing_tests: Optional[list] = None,
        folder_structure: Optional[list] = None
    ) -> str:
        """
        Build complete prompt for test generation.
        
        Args:
            context: Story context
            rag_context: Optional RAG context section
            existing_tests: Optional list of existing tests
            folder_structure: Optional Zephyr folder structure
            
        Returns:
            Complete prompt string
        """
        ...

    def build_rag_context(self, retrieved_context: Any) -> str:
        """
        Build RAG context section with token budgeting.
        
        Args:
            retrieved_context: RetrievedContext object
            
        Returns:
            Formatted RAG context string
        """
        ...


class IResponseParser(Protocol):
    """Interface for AI response parsing operations."""

    def parse_ai_response(self, response_text: str) -> dict:
        """
        Parse AI response text into structured data.
        
        Args:
            response_text: Raw response from AI
            
        Returns:
            Parsed dictionary
        """
        ...

    def build_test_plan(
        self,
        main_story: Any,  # JiraStory
        test_plan_data: dict,
        ai_model: str,
        folder_structure: Optional[List[Dict]] = None
    ) -> TestPlan:
        """
        Build TestPlan object from parsed AI data.
        
        Args:
            main_story: The main Jira story
            test_plan_data: Parsed test plan data from AI
            ai_model: AI model used
            folder_structure: Optional folder structure for fallback
            
        Returns:
            TestPlan object
        """
        ...


class IHTTPClient(Protocol):
    """Interface for HTTP client operations."""

    def get(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None
    ):
        """
        Perform GET request.
        
        Args:
            url: URL to fetch
            headers: Additional headers
            params: Query parameters
            
        Returns:
            Response object
        """
        ...

    def get_text(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        encoding: Optional[str] = None
    ) -> Optional[str]:
        """
        Fetch URL and return text content.
        
        Args:
            url: URL to fetch
            headers: Additional headers
            params: Query parameters
            encoding: Character encoding
            
        Returns:
            Text content or None on error
        """
        ...


class IHTMLParser(Protocol):
    """Interface for HTML parsing operations."""

    def strip_html_tags(self, html: str) -> str:
        """
        Convert HTML to readable text.
        
        Args:
            html: HTML content
            
        Returns:
            Clean text content
        """
        ...

    def extract_title(self, html: str, fallback: str = "Untitled") -> str:
        """
        Extract title from HTML.
        
        Args:
            html: HTML content
            fallback: Fallback title if extraction fails
            
        Returns:
            Extracted title or fallback
        """
        ...

    def find_code_blocks(self, html: str) -> list[str]:
        """
        Extract all code blocks from HTML.
        
        Args:
            html: HTML content
            
        Returns:
            List of code block contents
        """
        ...

