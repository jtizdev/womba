"""
Embedding service for converting text to vector embeddings.
Supports OpenAI embeddings with batch processing and smart chunking for long documents.
"""

from typing import List, Optional, Tuple
import asyncio
from loguru import logger

from src.config.settings import settings

# Rough estimate: 1 token ≈ 4 characters (conservative, but some text can be denser)
# text-embedding-3-small max: 8192 tokens
# We'll use 3500 tokens per chunk ≈ 14000 chars for safety (dense technical text can be ~3 chars/token)
# This leaves plenty of headroom to avoid ANY token limit errors
MAX_CHUNK_LENGTH = 14000  # characters (~3500 tokens, safe for dense technical docs)
CHUNK_OVERLAP = 1000  # characters overlap between chunks to preserve context


class EmbeddingService:
    """
    Service for generating text embeddings using OpenAI.
    Handles batch processing and rate limiting.
    """
    
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        """
        Initialize embedding service.
        
        Args:
            api_key: OpenAI API key (defaults to settings)
            model: Embedding model (defaults to text-embedding-3-small)
        """
        from openai import OpenAI
        
        self.api_key = api_key or settings.openai_api_key
        self.model = model or settings.embedding_model
        
        # Validate API key
        if not self.api_key:
            raise ValueError(
                "OpenAI API key not configured. Please set OPENAI_API_KEY in .env or run 'womba configure'"
            )
        
        # Initialize OpenAI client with minimal parameters for compatibility
        self.client = OpenAI(api_key=self.api_key)
        self.batch_size = 100  # OpenAI allows up to 2048 texts per request
        
        logger.info(f"Initialized embedding service with model {self.model}")
        
    def _chunk_text(self, text: str) -> List[str]:
        """
        Intelligently chunk long text into smaller pieces.
        Tries to break at sentence/paragraph boundaries when possible.
        
        Args:
            text: Text to chunk
            
        Returns:
            List of text chunks
        """
        if len(text) <= MAX_CHUNK_LENGTH:
            return [text]
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + MAX_CHUNK_LENGTH
            
            if end >= len(text):
                # Last chunk - take everything remaining
                chunks.append(text[start:])
                break
            
            # Try to break at a newline or sentence boundary
            # Look for newlines near the end
            newline_pos = text.rfind('\n\n', start, end)
            if newline_pos > start + MAX_CHUNK_LENGTH // 2:
                # Found a paragraph break in the second half - use it
                end = newline_pos + 2
            else:
                # Look for single newline
                newline_pos = text.rfind('\n', start, end)
                if newline_pos > start + MAX_CHUNK_LENGTH // 2:
                    end = newline_pos + 1
                else:
                    # Last resort: look for sentence ending
                    for punct in ['. ', '.\n', '! ', '!\n', '? ', '?\n']:
                        punct_pos = text.rfind(punct, start, end)
                        if punct_pos > start + MAX_CHUNK_LENGTH // 2:
                            end = punct_pos + len(punct)
                            break
            
            chunks.append(text[start:end])
            
            # Move start forward with overlap
            start = end - CHUNK_OVERLAP
            if start < 0:
                start = 0
        
        logger.debug(f"Chunked text of {len(text)} chars into {len(chunks)} chunks")
        return chunks
    
    def _chunk_text_further(self, text: str, max_size: int = 8000) -> List[str]:
        """
        Further split a chunk that's still too large.
        Uses smaller chunks (8000 chars = ~2000 tokens).
        
        Args:
            text: Text that's still too large
            max_size: Maximum chunk size in characters
            
        Returns:
            List of smaller text chunks
        """
        if len(text) <= max_size:
            return [text]
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + max_size
            if end >= len(text):
                chunks.append(text[start:])
                break
            
            # Simple split at newline if possible
            newline_pos = text.rfind('\n', start, end)
            if newline_pos > start + max_size // 2:
                end = newline_pos + 1
            
            chunks.append(text[start:end])
            start = end - 500  # Small overlap
        
        logger.debug(f"Further chunked {len(text)} chars into {len(chunks)} smaller chunks")
        return chunks
    
    async def embed_texts(self, texts: List[str], chunk_long_docs: bool = True) -> List[List[List[float]]]:
        """
        Generate embeddings for a list of texts with batch processing.
        Long documents are automatically chunked.
        
        Args:
            texts: List of text strings to embed
            chunk_long_docs: If True, chunk documents that exceed token limit
            
        Returns:
            List of embedding vectors (each text may have multiple embeddings if chunked)
            Format: List[List[embedding]] where each inner list represents chunks for one document
        """
        if not texts:
            return []
        
        logger.info(f"Generating embeddings for {len(texts)} texts using {self.model}")
        
        # Chunk long documents
        text_chunks = []
        chunk_mapping = []  # Maps chunk index back to original text index
        
        for text_idx, text in enumerate(texts):
            if chunk_long_docs and len(text) > MAX_CHUNK_LENGTH:
                chunks = self._chunk_text(text)
                text_chunks.extend(chunks)
                chunk_mapping.extend([(text_idx, chunk_idx, len(chunks)) for chunk_idx in range(len(chunks))])
                logger.info(f"Document {text_idx} ({len(text)} chars) split into {len(chunks)} chunks")
            else:
                text_chunks.append(text)
                chunk_mapping.append((text_idx, 0, 1))
        
        if not text_chunks:
            return []
        
        all_chunk_embeddings = []
        
        # Process chunks in batches
        for i in range(0, len(text_chunks), self.batch_size):
            batch = text_chunks[i:i + self.batch_size]
            
            try:
                # Run synchronous OpenAI call in executor to avoid blocking
                embeddings = await asyncio.to_thread(self._embed_batch, batch)
                all_chunk_embeddings.extend(embeddings)
                
                logger.debug(f"Embedded batch {i//self.batch_size + 1}/{(len(text_chunks)-1)//self.batch_size + 1}")
                
            except Exception as e:
                error_msg = str(e)
                logger.warning(f"Batch embedding failed, retrying individual chunks: {e}")
                
                # If batch failed due to token limit, retry each chunk individually
                # This handles edge cases where a chunk might still be too large
                for chunk_text in batch:
                    try:
                        # Try embedding this chunk alone
                        chunk_emb = await asyncio.to_thread(self._embed_batch, [chunk_text])
                        all_chunk_embeddings.extend(chunk_emb)
                    except Exception as chunk_error:
                        # If even single chunk fails, it's definitely too big - chunk it further
                        logger.warning(f"Chunk still too large ({len(chunk_text)} chars), splitting further...")
                        smaller_chunks = self._chunk_text_further(chunk_text)
                        for small_chunk in smaller_chunks:
                            try:
                                small_emb = await asyncio.to_thread(self._embed_batch, [small_chunk])
                                all_chunk_embeddings.extend(small_emb)
                            except Exception as final_error:
                                logger.error(f"Failed to embed even smaller chunk: {final_error}")
                                # Last resort: return zero vector
                                all_chunk_embeddings.append([0.0] * 1536)
        
        # Group embeddings back by original document
        document_embeddings = []
        current_doc_idx = -1
        current_doc_embeddings = []
        
        for chunk_idx, (doc_idx, _, _) in enumerate(chunk_mapping):
            if doc_idx != current_doc_idx:
                if current_doc_embeddings:
                    document_embeddings.append(current_doc_embeddings)
                current_doc_idx = doc_idx
                current_doc_embeddings = []
            current_doc_embeddings.append(all_chunk_embeddings[chunk_idx])
        
        if current_doc_embeddings:
            document_embeddings.append(current_doc_embeddings)
        
        logger.info(f"Successfully generated {sum(len(e) for e in document_embeddings)} embeddings for {len(texts)} documents")
        return document_embeddings
    
    def _embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Synchronously embed a batch of texts.
        
        Args:
            texts: Batch of texts to embed
            
        Returns:
            List of embedding vectors
        """
        try:
            response = self.client.embeddings.create(
                model=self.model,
                input=texts
            )
            
            # Extract embeddings in order
            embeddings = [item.embedding for item in response.data]
            return embeddings
            
        except Exception as e:
            logger.error(f"OpenAI embedding error: {e}")
            raise
    
    async def embed_single(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.
        Returns the first chunk's embedding if the text was chunked.
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector (first chunk if text was split)
        """
        embeddings = await self.embed_texts([text], chunk_long_docs=True)
        if embeddings and embeddings[0]:
            return embeddings[0][0]  # Return first chunk's embedding
        return [0.0] * 1536

