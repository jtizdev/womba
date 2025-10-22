"""
Unit tests for RAG vector store.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from src.ai.rag_store import RAGVectorStore
from src.ai.embedding_service import EmbeddingService
from src.ai.context_indexer import ContextIndexer
from src.ai.rag_retriever import RAGRetriever
from src.models.story import JiraStory


@pytest.mark.asyncio
async def test_rag_store_initialization():
    """Test that RAG store initializes correctly."""
    store = RAGVectorStore()
    assert store is not None
    assert store.collection_path.exists()


@pytest.mark.asyncio
async def test_add_and_retrieve_documents():
    """Test adding and retrieving documents from RAG store."""
    store = RAGVectorStore()
    
    # Clear test collection first
    try:
        store.clear_collection("test_collection")
    except:
        pass
    
    # Add test documents
    documents = [
        "This is a test document about authentication",
        "This is a test document about authorization",
        "This is a test document about user management"
    ]
    metadatas = [
        {"type": "test", "id": "1"},
        {"type": "test", "id": "2"},
        {"type": "test", "id": "3"}
    ]
    ids = ["test_1", "test_2", "test_3"]
    
    await store.add_documents(
        collection_name="test_collection",
        documents=documents,
        metadatas=metadatas,
        ids=ids
    )
    
    # Retrieve similar documents
    results = await store.retrieve_similar(
        collection_name="test_collection",
        query_text="authentication and authorization",
        top_k=2
    )
    
    assert len(results) > 0
    assert len(results) <= 2
    
    # Clean up
    store.clear_collection("test_collection")


@pytest.mark.asyncio
async def test_get_collection_stats():
    """Test getting collection statistics."""
    store = RAGVectorStore()
    
    # Get stats for test_plans collection
    stats = store.get_collection_stats(store.TEST_PLANS_COLLECTION)
    
    assert "name" in stats
    assert "count" in stats
    assert stats["name"] == store.TEST_PLANS_COLLECTION


@pytest.mark.asyncio
async def test_get_all_stats():
    """Test getting all collection statistics."""
    store = RAGVectorStore()
    
    stats = store.get_all_stats()
    
    assert "total_documents" in stats
    assert "storage_path" in stats
    assert "test_plans" in stats
    assert "confluence_docs" in stats
    assert "jira_stories" in stats
    assert "existing_tests" in stats


@pytest.mark.asyncio
async def test_embedding_service_with_mock():
    """Test embedding service with mocked OpenAI."""
    # Mock OpenAI client
    mock_response = Mock()
    mock_response.data = [Mock(embedding=[0.1] * 1536)]
    
    with patch('src.ai.embedding_service.OpenAI') as mock_openai:
        mock_client = Mock()
        mock_client.embeddings.create.return_value = mock_response
        mock_openai.return_value = mock_client
        
        service = EmbeddingService(api_key="test_key")
        
        # Test single embedding
        text = "This is a test document"
        embedding = await service.embed_single(text)
        
        assert embedding is not None
        assert len(embedding) == 1536
        assert isinstance(embedding, list)
        assert all(isinstance(x, float) for x in embedding)


@pytest.mark.asyncio
async def test_embedding_service_batch_with_mock():
    """Test embedding service batch processing with mocked OpenAI."""
    # Mock OpenAI client
    mock_response = Mock()
    mock_response.data = [
        Mock(embedding=[0.1] * 1536),
        Mock(embedding=[0.2] * 1536),
        Mock(embedding=[0.3] * 1536)
    ]
    
    with patch('src.ai.embedding_service.OpenAI') as mock_openai:
        mock_client = Mock()
        mock_client.embeddings.create.return_value = mock_response
        mock_openai.return_value = mock_client
        
        service = EmbeddingService(api_key="test_key")
        
        # Test batch embeddings
        texts = [
            "First test document",
            "Second test document",
            "Third test document"
        ]
        embeddings = await service.embed_texts(texts)
        
        assert len(embeddings) == len(texts)
        assert all(len(emb) == 1536 for emb in embeddings)


def test_embedding_service_missing_api_key():
    """Test that embedding service raises error with missing API key."""
    with patch('src.ai.embedding_service.settings') as mock_settings:
        mock_settings.openai_api_key = None
        mock_settings.embedding_model = "text-embedding-3-small"
        
        with pytest.raises(ValueError, match="OpenAI API key not configured"):
            EmbeddingService()


@pytest.mark.asyncio
async def test_context_indexer_with_mock():
    """Test context indexer with mocked dependencies."""
    with patch('src.ai.context_indexer.RAGVectorStore') as mock_store_class:
        mock_store = Mock()
        mock_store.add_documents = AsyncMock()
        mock_store_class.return_value = mock_store
        
        indexer = ContextIndexer()
        
        # Test indexing Jira stories
        story = JiraStory(
            key="TEST-123",
            summary="Test story",
            description="Test description",
            issue_type="Story",
            status="Open",
            priority="Medium"
        )
        
        await indexer.index_jira_stories([story], "TEST")
        
        # Verify add_documents was called
        mock_store.add_documents.assert_called_once()
        call_args = mock_store.add_documents.call_args
        assert call_args[1]['collection_name'] == mock_store.JIRA_STORIES_COLLECTION
        assert len(call_args[1]['documents']) == 1
        assert "TEST-123" in call_args[1]['documents'][0]


@pytest.mark.asyncio
async def test_rag_retriever_empty_collections():
    """Test RAG retriever handles empty collections gracefully."""
    with patch('src.ai.rag_retriever.RAGVectorStore') as mock_store_class:
        mock_store = Mock()
        mock_store.get_collection_stats.return_value = {'count': 0}
        mock_store_class.return_value = mock_store
        
        retriever = RAGRetriever()
        
        story = JiraStory(
            key="TEST-123",
            summary="Test story",
            description="Test description",
            issue_type="Story",
            status="Open",
            priority="Medium"
        )
        
        # Should not raise error with empty collections
        context = await retriever.retrieve_for_story(story, "TEST")
        
        assert context is not None
        assert not context.has_context()


@pytest.mark.asyncio
async def test_rag_retriever_with_results():
    """Test RAG retriever with populated collections."""
    mock_results = [
        {
            'id': 'test_1',
            'document': 'Test document',
            'metadata': {'project_key': 'TEST'},
            'distance': 0.1
        }
    ]
    
    with patch('src.ai.rag_retriever.RAGVectorStore') as mock_store_class:
        mock_store = Mock()
        mock_store.get_collection_stats.return_value = {'count': 10}
        mock_store.retrieve_similar = AsyncMock(return_value=mock_results)
        mock_store.TEST_PLANS_COLLECTION = "test_plans"
        mock_store.CONFLUENCE_DOCS_COLLECTION = "confluence_docs"
        mock_store.JIRA_STORIES_COLLECTION = "jira_stories"
        mock_store.EXISTING_TESTS_COLLECTION = "existing_tests"
        mock_store_class.return_value = mock_store
        
        retriever = RAGRetriever()
        
        story = JiraStory(
            key="TEST-123",
            summary="Test story",
            description="Test description",
            issue_type="Story",
            status="Open",
            priority="Medium"
        )
        
        context = await retriever.retrieve_for_story(story, "TEST")
        
        assert context is not None
        assert context.has_context()
        assert len(context.similar_test_plans) > 0

