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
    assert "external_docs" in stats


@pytest.mark.asyncio
async def test_embedding_service_with_mock():
    """Test embedding service with mocked OpenAI."""
    # Mock OpenAI client
    mock_response = Mock()
    mock_response.data = [Mock(embedding=[0.1] * 1536)]
    
    with patch('openai.OpenAI') as mock_openai:
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
    
    with patch('openai.OpenAI') as mock_openai:
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
    from src.config import settings
    original_key = settings.settings.openai_api_key
    
    try:
        # Temporarily set API key to None
        settings.settings.openai_api_key = None
        
        with pytest.raises(ValueError, match="OpenAI API key not configured"):
            EmbeddingService()
    finally:
        # Restore original key
        settings.settings.openai_api_key = original_key


@pytest.mark.asyncio
@pytest.mark.skip(reason="Context indexer refactoring - tested via integration tests")
async def test_context_indexer_with_mock():
    """Test context indexer with mocked dependencies."""
    from datetime import datetime
    
    with patch('src.ai.rag_store.RAGVectorStore') as mock_store_class:
        mock_store = Mock()
        mock_store.add_documents = AsyncMock()
        mock_store.JIRA_STORIES_COLLECTION = "jira_stories"
        mock_store_class.return_value = mock_store
        
        # Create indexer (it will create its own DocumentIndexer internally)
        indexer = ContextIndexer()
        indexer.indexer.store = mock_store  # Override the store
        
        # Test indexing Jira stories
        story = JiraStory(
            key="TEST-123",
            summary="Test story",
            description="Test description",
            issue_type="Story",
            status="Open",
            priority="Medium",
            reporter="test@example.com",
            created=datetime.now(),
            updated=datetime.now()
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
    from datetime import datetime
    
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
            priority="Medium",
            reporter="test@example.com",
            created=datetime.now(),
            updated=datetime.now()
        )
        
        # Should not raise error with empty collections
        context = await retriever.retrieve_for_story(story, "TEST")
        
        assert context is not None
        assert not context.has_context()


@pytest.mark.asyncio
async def test_rag_retriever_with_results():
    """Test RAG retriever with populated collections."""
    from datetime import datetime
    
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
        mock_store.EXTERNAL_DOCS_COLLECTION = "external_docs"
        mock_store_class.return_value = mock_store
        
        retriever = RAGRetriever()
        
        story = JiraStory(
            key="TEST-123",
            summary="Test story",
            description="Test description",
            issue_type="Story",
            status="Open",
            priority="Medium",
            reporter="test@example.com",
            created=datetime.now(),
            updated=datetime.now()
        )
        
        context = await retriever.retrieve_for_story(story, "TEST")
        
        assert context is not None
        assert context.has_context()
        assert len(context.similar_test_plans) > 0


@pytest.mark.asyncio
async def test_external_docs_collection():
    """Test that external_docs collection works correctly."""
    store = RAGVectorStore()
    
    # Clear external_docs collection
    store.clear_collection(store.EXTERNAL_DOCS_COLLECTION)
    
    # Add external documentation
    documents = [
        "PlainID API endpoint documentation",
        "Authentication guide for PlainID"
    ]
    metadatas = [
        {"source": "plainid", "url": "https://docs.plainid.io/endpoint1"},
        {"source": "plainid", "url": "https://docs.plainid.io/auth"}
    ]
    ids = ["plainid_endpoint1", "plainid_auth"]
    
    await store.add_documents(
        collection_name=store.EXTERNAL_DOCS_COLLECTION,
        documents=documents,
        metadatas=metadatas,
        ids=ids
    )
    
    # Verify documents were added
    stats = store.get_collection_stats(store.EXTERNAL_DOCS_COLLECTION)
    assert stats['count'] == 2
    
    # Clean up
    store.clear_collection(store.EXTERNAL_DOCS_COLLECTION)


@pytest.mark.asyncio
async def test_upsert_with_timestamps():
    """Test upsert logic with last_modified timestamps."""
    store = RAGVectorStore()
    
    # Clear test collection
    store.clear_collection("test_upsert_timestamps")
    
    # Add initial document
    documents = ["Original content"]
    metadatas = [{"id": "1", "last_modified": "2024-01-01T00:00:00Z"}]
    ids = ["upsert_test_1"]
    
    await store.add_documents("test_upsert_timestamps", documents, metadatas, ids)
    
    # Verify document was added
    stats = store.get_collection_stats("test_upsert_timestamps")
    assert stats['count'] == 1
    
    # Try to add same document with same timestamp (should skip)
    await store.add_documents("test_upsert_timestamps", documents, metadatas, ids)
    stats = store.get_collection_stats("test_upsert_timestamps")
    assert stats['count'] == 1  # Still 1, not duplicated
    
    # Update document with new timestamp (should update)
    updated_documents = ["Updated content"]
    updated_metadatas = [{"id": "1", "last_modified": "2024-01-02T00:00:00Z"}]
    
    await store.add_documents("test_upsert_timestamps", updated_documents, updated_metadatas, ids)
    stats = store.get_collection_stats("test_upsert_timestamps")
    assert stats['count'] == 1  # Still 1, updated not duplicated
    
    # Clean up
    store.clear_collection("test_upsert_timestamps")


@pytest.mark.asyncio
async def test_clear_all_collections_file_deletion():
    """Test that clear_all_collections deletes ChromaDB files."""
    from pathlib import Path
    from src.config.settings import settings
    
    store = RAGVectorStore()
    
    # Add some data to collections
    test_collections = [
        store.TEST_PLANS_COLLECTION,
        store.CONFLUENCE_DOCS_COLLECTION,
        store.JIRA_STORIES_COLLECTION,
        store.EXISTING_TESTS_COLLECTION,
        store.EXTERNAL_DOCS_COLLECTION
    ]
    
    for collection in test_collections:
        await store.add_documents(
            collection,
            [f"Test document for {collection}"],
            [{"test": "data"}],
            [f"{collection}_test"]
        )
    
    # Verify data exists
    chroma_path = Path(settings.rag_collection_path)
    items_before = list(chroma_path.iterdir())
    assert len(items_before) > 1  # Should have multiple files/dirs
    
    # Clear all collections
    store.clear_all_collections()
    
    # Verify files are deleted
    items_after = list(chroma_path.iterdir())
    
    # Should only have chroma.sqlite3 or be empty
    for item in items_after:
        if item.is_file():
            assert item.name == "chroma.sqlite3", f"Unexpected file after clear: {item.name}"
        elif item.is_dir():
            # Some empty directories might remain, but they should be empty
            assert len(list(item.iterdir())) == 0, f"Directory {item.name} is not empty after clear"
    
    # Verify all collections are empty
    for collection in test_collections:
        stats = store.get_collection_stats(collection)
        assert stats['count'] == 0, f"Collection {collection} is not empty after clear"


@pytest.mark.asyncio
async def test_upsert_new_vs_existing():
    """Test that upsert correctly distinguishes new vs existing documents."""
    store = RAGVectorStore()
    
    # Clear test collection
    store.clear_collection("test_upsert_new_existing")
    
    # Add first document
    await store.add_documents(
        "test_upsert_new_existing",
        ["Document 1"],
        [{"id": "1", "last_modified": "2024-01-01T00:00:00Z"}],
        ["doc_1"]
    )
    
    stats = store.get_collection_stats("test_upsert_new_existing")
    assert stats['count'] == 1
    
    # Add second document (new)
    await store.add_documents(
        "test_upsert_new_existing",
        ["Document 2"],
        [{"id": "2", "last_modified": "2024-01-01T00:00:00Z"}],
        ["doc_2"]
    )
    
    stats = store.get_collection_stats("test_upsert_new_existing")
    assert stats['count'] == 2  # Now 2 documents
    
    # Try to add first document again with same content (should skip)
    await store.add_documents(
        "test_upsert_new_existing",
        ["Document 1"],
        [{"id": "1", "last_modified": "2024-01-01T00:00:00Z"}],
        ["doc_1"]
    )
    
    stats = store.get_collection_stats("test_upsert_new_existing")
    assert stats['count'] == 2  # Still 2, not 3
    
    # Clean up
    store.clear_collection("test_upsert_new_existing")

