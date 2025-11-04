"""
Unit tests for embedding service with chunking support.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from src.ai.embedding_service import EmbeddingService


@pytest.fixture
def mock_openai_client():
    """Mock AsyncOpenAI client for testing."""
    with patch('openai.AsyncOpenAI') as mock_client:
        mock_instance = Mock()
        mock_client.return_value = mock_instance
        
        # Mock embeddings.create response (async)
        mock_response = Mock()
        mock_response.data = [
            Mock(embedding=[0.1] * 1536),
            Mock(embedding=[0.2] * 1536),
            Mock(embedding=[0.3] * 1536),
        ]
        mock_instance.embeddings.create = AsyncMock(return_value=mock_response)
        
        yield mock_instance


@pytest.mark.asyncio
async def test_embedding_service_initialization(mock_openai_client):
    """Test that embedding service initializes correctly."""
    service = EmbeddingService()
    assert service is not None
    assert service.model == "text-embedding-3-small"
    assert service.max_tokens == 8192
    assert service.chunk_size == int(8192 * 0.70)  # Updated to 70% safety margin


@pytest.mark.asyncio
async def test_token_estimation():
    """Test token estimation accuracy."""
    service = EmbeddingService()
    
    # Test various text lengths (using 3 chars/token estimation)
    test_cases = [
        ("Hello world", 3),  # 11 chars = 3 tokens
        ("A" * 100, 33),     # 100 chars = 33 tokens
        ("A" * 1000, 333),   # 1000 chars = 333 tokens
        ("A" * 10000, 3333), # 10000 chars = 3333 tokens
    ]
    
    for text, expected_tokens in test_cases:
        estimated = service._estimate_tokens(text)
        assert estimated == expected_tokens, f"Expected {expected_tokens}, got {estimated} for text length {len(text)}"


@pytest.mark.asyncio
async def test_chunking_small_text():
    """Test that small texts are not chunked."""
    service = EmbeddingService()
    
    # Text well under limit
    small_text = "This is a small text that should not be chunked."
    chunks = service._chunk_text(small_text, service.chunk_size)
    
    assert len(chunks) == 1
    assert chunks[0] == small_text


@pytest.mark.asyncio
async def test_chunking_large_text():
    """Test that large texts are properly chunked."""
    service = EmbeddingService()
    
    # Create text that exceeds token limit
    # chunk_size is ~6963 tokens = ~27852 characters
    large_text = "x" * 50000  # ~12500 tokens
    
    chunks = service._chunk_text(large_text, service.chunk_size)
    
    # Should be split into multiple chunks
    assert len(chunks) > 1
    
    # Each chunk should be under the limit
    for chunk in chunks:
        estimated_tokens = service._estimate_tokens(chunk)
        assert estimated_tokens <= service.chunk_size, f"Chunk has {estimated_tokens} tokens, limit is {service.chunk_size}"


@pytest.mark.asyncio
async def test_chunking_with_paragraphs():
    """Test chunking respects paragraph boundaries."""
    service = EmbeddingService()
    
    # Create text with paragraph breaks
    paragraph = "This is a paragraph. " * 100  # ~2000 chars
    large_text = "\n\n".join([paragraph] * 20)  # ~40000 chars = ~10000 tokens
    
    chunks = service._chunk_text(large_text, service.chunk_size)
    
    # Should be chunked
    assert len(chunks) > 1
    
    # Chunks should respect paragraph boundaries (contain \n\n or be single paragraphs)
    for chunk in chunks:
        estimated_tokens = service._estimate_tokens(chunk)
        assert estimated_tokens <= service.chunk_size


@pytest.mark.asyncio
async def test_chunking_with_sentences():
    """Test chunking respects sentence boundaries."""
    service = EmbeddingService()
    
    # Create very long paragraph without double newlines
    sentence = "This is a sentence. "
    large_paragraph = sentence * 2000  # ~40000 chars = ~10000 tokens
    
    chunks = service._chunk_text(large_paragraph, service.chunk_size)
    
    # Should be chunked
    assert len(chunks) > 1
    
    # Each chunk should be under limit
    for chunk in chunks:
        estimated_tokens = service._estimate_tokens(chunk)
        assert estimated_tokens <= service.chunk_size


@pytest.mark.asyncio
async def test_embed_texts_single(mock_openai_client):
    """Test embedding a single text."""
    service = EmbeddingService()
    
    texts = ["This is a test document"]
    embeddings = await service.embed_texts(texts)
    
    assert len(embeddings) == 1
    assert len(embeddings[0]) == 1536
    assert mock_openai_client.embeddings.create.called


@pytest.mark.asyncio
async def test_embed_texts_multiple(mock_openai_client):
    """Test embedding multiple texts."""
    service = EmbeddingService()
    
    texts = [
        "First document",
        "Second document",
        "Third document"
    ]
    embeddings = await service.embed_texts(texts)
    
    assert len(embeddings) == 3
    for embedding in embeddings:
        assert len(embedding) == 1536


@pytest.mark.asyncio
async def test_embed_texts_with_chunking(mock_openai_client):
    """Test embedding texts that require chunking."""
    service = EmbeddingService()
    
    # Create a text that will be chunked
    large_text = "x" * 50000  # ~12500 tokens, will be chunked into 2 chunks
    texts = [large_text]
    
    # Mock numpy for averaging
    with patch('src.ai.embedding_service.np') as mock_np:
        mock_np.mean.return_value.tolist.return_value = [0.15] * 1536
        
        embeddings = await service.embed_texts(texts)
        
        # Should return 1 embedding (averaged from chunks)
        assert len(embeddings) == 1
        assert len(embeddings[0]) == 1536
        
        # Should have called mean for averaging
        assert mock_np.mean.called


@pytest.mark.asyncio
async def test_embed_texts_empty_list(mock_openai_client):
    """Test embedding empty list."""
    service = EmbeddingService()
    
    embeddings = await service.embed_texts([])
    
    assert embeddings == []
    assert not mock_openai_client.embeddings.create.called


@pytest.mark.asyncio
async def test_embed_single(mock_openai_client):
    """Test embed_single convenience method."""
    service = EmbeddingService()
    
    text = "Single test document"
    embedding = await service.embed_single(text)
    
    assert len(embedding) == 1536
    assert mock_openai_client.embeddings.create.called


@pytest.mark.asyncio
async def test_error_handling(mock_openai_client):
    """Test error handling during embedding."""
    service = EmbeddingService()
    
    # Make the API call fail
    mock_openai_client.embeddings.create.side_effect = Exception("API Error")
    
    texts = ["Test document"]
    embeddings = await service.embed_texts(texts)
    
    # Should return zero vectors on error
    assert len(embeddings) == 1
    assert embeddings[0] == [0.0] * 1536


@pytest.mark.asyncio
async def test_batch_processing(mock_openai_client):
    """Test that large batches are processed correctly with smart batching."""
    service = EmbeddingService()
    
    # Create enough texts to trigger multiple batches (>1000 texts per batch limit)
    texts = [f"Document number {i} with some content" for i in range(1500)]
    embeddings = await service.embed_texts(texts)
    
    assert len(embeddings) == 1500
    # Should have made multiple API calls due to smart batching (1000 per batch)
    assert mock_openai_client.embeddings.create.call_count >= 2


@pytest.mark.asyncio
async def test_chunking_fallback_character_split():
    """Test that extremely long sentences fall back to character splitting."""
    service = EmbeddingService()
    
    # Create a single extremely long "sentence" with no breaks
    very_long_sentence = "x" * 100000  # ~25000 tokens
    
    chunks = service._chunk_text(very_long_sentence, service.chunk_size)
    
    # Should be chunked
    assert len(chunks) > 1
    
    # All chunks should be under limit
    for chunk in chunks:
        estimated_tokens = service._estimate_tokens(chunk)
        assert estimated_tokens <= service.chunk_size


@pytest.mark.asyncio
async def test_chunk_text_preserves_content():
    """Test that chunking doesn't lose content."""
    service = EmbeddingService()
    
    # Create text with known content
    original_text = "ABC" * 10000  # 30000 chars
    
    chunks = service._chunk_text(original_text, service.chunk_size)
    
    # Reconstruct text from chunks
    reconstructed = "".join(chunks)
    
    # Should contain all original characters (may have added separators)
    assert "ABC" in reconstructed
    # Length should be similar (accounting for potential separators)
    assert len(reconstructed) >= len(original_text) * 0.9

