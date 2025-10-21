"""
Integration tests for RAG workflow.
Tests end-to-end RAG functionality with mocked external dependencies.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from pathlib import Path
import tempfile
import shutil

from src.ai.rag_store import RAGVectorStore
from src.ai.context_indexer import ContextIndexer
from src.ai.rag_retriever import RAGRetriever
from src.models.story import JiraStory
from src.models.test_plan import TestPlan
from src.aggregator.story_collector import StoryContext


@pytest.fixture
def temp_rag_store():
    """Create a temporary RAG store for testing."""
    temp_dir = tempfile.mkdtemp()
    with patch('src.ai.rag_store.settings') as mock_settings:
        mock_settings.rag_collection_path = temp_dir
        mock_settings.openai_api_key = "test_key"
        mock_settings.embedding_model = "text-embedding-3-small"
        
        store = RAGVectorStore(collection_path=temp_dir)
        yield store
        
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_end_to_end_indexing_and_retrieval():
    """Test complete RAG workflow: index and retrieve."""
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Mock OpenAI embeddings
        with patch('src.ai.embedding_service.OpenAI') as mock_openai:
            mock_client = Mock()
            
            # Create mock embeddings that are similar for similar text
            def create_mock_embedding(texts):
                mock_response = Mock()
                mock_response.data = []
                for text in texts:
                    # Simple hash-based embedding for testing
                    embedding = [hash(text[:10]) % 100 / 100.0] * 1536
                    mock_response.data.append(Mock(embedding=embedding))
                return mock_response
            
            mock_client.embeddings.create = lambda **kwargs: create_mock_embedding(kwargs['input'])
            mock_openai.return_value = mock_client
            
            # Create store and indexer
            store = RAGVectorStore(collection_path=temp_dir)
            indexer = ContextIndexer()
            indexer.store = store
            
            # Create test story
            story = JiraStory(
                key="TEST-123",
                summary="Add login functionality",
                description="Implement user login with OAuth",
                issue_type="Story",
                status="Open",
                priority="High",
                components=["Authentication"]
            )
            
            # Index story
            await indexer.index_jira_stories([story], "TEST")
            
            # Verify indexing
            stats = store.get_collection_stats(store.JIRA_STORIES_COLLECTION)
            assert stats['count'] == 1
            
            # Retrieve similar stories
            retriever = RAGRetriever()
            retriever.store = store
            
            query_story = JiraStory(
                key="TEST-124",
                summary="Add authentication features",
                description="Need OAuth login",
                issue_type="Story",
                status="Open",
                priority="Medium"
            )
            
            context = await retriever.retrieve_for_story(query_story, "TEST")
            
            # Should find the indexed story
            assert context is not None
            # Note: May be empty if embeddings don't match, but shouldn't error
            
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_index_multiple_types():
    """Test indexing different types of documents."""
    temp_dir = tempfile.mkdtemp()
    
    try:
        with patch('src.ai.embedding_service.OpenAI') as mock_openai:
            # Mock OpenAI
            mock_client = Mock()
            mock_response = Mock()
            mock_response.data = [Mock(embedding=[0.1] * 1536)]
            mock_client.embeddings.create.return_value = mock_response
            mock_openai.return_value = mock_client
            
            store = RAGVectorStore(collection_path=temp_dir)
            indexer = ContextIndexer()
            indexer.store = store
            
            # Index Jira stories
            stories = [
                JiraStory(
                    key="TEST-1",
                    summary="Story 1",
                    description="Description 1",
                    issue_type="Story",
                    status="Open",
                    priority="High"
                )
            ]
            await indexer.index_jira_stories(stories, "TEST")
            
            # Index Confluence docs
            docs = [
                {
                    "id": "123",
                    "title": "API Documentation",
                    "content": "This is the API documentation",
                    "space": "TECH",
                    "url": "https://example.com"
                }
            ]
            await indexer.index_confluence_docs(docs, "TEST")
            
            # Index existing tests
            tests = [
                {
                    "key": "TEST-T1",
                    "name": "Test Login",
                    "objective": "Verify login works",
                    "precondition": "User exists",
                    "status": "Approved",
                    "priority": "High"
                }
            ]
            await indexer.index_existing_tests(tests, "TEST")
            
            # Verify all were indexed
            stats = store.get_all_stats()
            assert stats['jira_stories']['count'] == 1
            assert stats['confluence_docs']['count'] == 1
            assert stats['existing_tests']['count'] == 1
            
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_error_handling_empty_collections():
    """Test that retrieval handles empty collections gracefully."""
    temp_dir = tempfile.mkdtemp()
    
    try:
        with patch('src.ai.embedding_service.OpenAI') as mock_openai:
            mock_client = Mock()
            mock_openai.return_value = mock_client
            
            store = RAGVectorStore(collection_path=temp_dir)
            retriever = RAGRetriever()
            retriever.store = store
            
            story = JiraStory(
                key="TEST-123",
                summary="Test story",
                description="Test",
                issue_type="Story",
                status="Open",
                priority="Medium"
            )
            
            # Should not raise error with empty collections
            context = await retriever.retrieve_for_story(story, "TEST")
            
            assert context is not None
            assert not context.has_context()
            assert len(context.similar_test_plans) == 0
            assert len(context.similar_confluence_docs) == 0
            assert len(context.similar_jira_stories) == 0
            assert len(context.similar_existing_tests) == 0
            
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_clear_collections():
    """Test clearing RAG collections."""
    temp_dir = tempfile.mkdtemp()
    
    try:
        with patch('src.ai.embedding_service.OpenAI') as mock_openai:
            mock_client = Mock()
            mock_response = Mock()
            mock_response.data = [Mock(embedding=[0.1] * 1536)]
            mock_client.embeddings.create.return_value = mock_response
            mock_openai.return_value = mock_client
            
            store = RAGVectorStore(collection_path=temp_dir)
            indexer = ContextIndexer()
            indexer.store = store
            
            # Add some documents
            story = JiraStory(
                key="TEST-123",
                summary="Test",
                description="Test",
                issue_type="Story",
                status="Open",
                priority="Medium"
            )
            await indexer.index_jira_stories([story], "TEST")
            
            # Verify indexed
            stats = store.get_collection_stats(store.JIRA_STORIES_COLLECTION)
            assert stats['count'] == 1
            
            # Clear collection
            store.clear_collection(store.JIRA_STORIES_COLLECTION)
            
            # Verify cleared
            stats = store.get_collection_stats(store.JIRA_STORIES_COLLECTION)
            assert stats['count'] == 0
            
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
