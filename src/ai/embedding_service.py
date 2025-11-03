"""
Embedding service for converting text to vector embeddings.
Supports OpenAI embeddings with batch processing and automatic chunking.
"""

from typing import List, Optional, Tuple
import asyncio
from loguru import logger

try:
    import numpy as np
except ImportError:
    np = None

from src.config.settings import settings

# Token limits for different embedding models (approximate)
MODEL_TOKEN_LIMITS = {
    "text-embedding-3-small": 8192,
    "text-embedding-3-large": 8192,
    "text-embedding-ada-002": 8191,
}


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
        
        # Get token limit for this model (with safety margin)
        self.max_tokens = MODEL_TOKEN_LIMITS.get(self.model, 8192)
        self.chunk_size = int(self.max_tokens * 0.85)  # Use 85% of limit for safety margin
        
        logger.info(f"Initialized embedding service with model {self.model} (max tokens: {self.max_tokens})")
        
    def _estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for a text.
        Uses rough approximation: ~4 characters per token for English text.
        
        Args:
            text: Text to estimate
            
        Returns:
            Estimated token count
        """
        # Rough estimate: 1 token ≈ 4 characters
        # This is conservative and safe
        return len(text) // 4
    
    def _chunk_text(self, text: str, max_tokens: int) -> List[str]:
        """
        Split text into chunks that fit within token limit.
        
        Args:
            text: Text to chunk
            max_tokens: Maximum tokens per chunk
            
        Returns:
            List of text chunks
        """
        estimated_tokens = self._estimate_tokens(text)
        
        if estimated_tokens <= max_tokens:
            return [text]
        
        # Need to chunk - split by paragraphs first, then by sentences, then by characters
        chunks = []
        
        # Try splitting by double newlines (paragraphs)
        if '\n\n' in text:
            paragraphs = text.split('\n\n')
        else:
            paragraphs = [text]
        
        current_chunk = []
        current_size = 0
        
        for para in paragraphs:
            para_tokens = self._estimate_tokens(para)
            
            # If paragraph itself is too large, split by sentences
            if para_tokens > max_tokens:
                # First, add current chunk if exists
                if current_chunk:
                    chunks.append('\n\n'.join(current_chunk))
                    current_chunk = []
                    current_size = 0
                
                # Split large paragraph by sentences
                sentences = para.replace('. ', '.\n').replace('! ', '!\n').replace('? ', '?\n').split('\n')
                for sent in sentences:
                    if not sent.strip():
                        continue
                    sent_tokens = self._estimate_tokens(sent)
                    
                    # If sentence itself is too large, split by character count
                    if sent_tokens > max_tokens:
                        # Add current chunk first
                        if current_chunk:
                            chunks.append('\n\n'.join(current_chunk))
                            current_chunk = []
                            current_size = 0
                        
                        # Split by character count (safety fallback)
                        char_limit = max_tokens * 4  # ~4 chars per token
                        for i in range(0, len(sent), char_limit):
                            sub_sent = sent[i:i + char_limit]
                            chunks.append(sub_sent)
                    else:
                        # Add sentence to current chunk if it fits
                        if current_size + sent_tokens > max_tokens and current_chunk:
                            chunks.append('\n\n'.join(current_chunk))
                            current_chunk = []
                            current_size = 0
                        current_chunk.append(sent)
                        current_size += sent_tokens
            else:
                # Add paragraph to current chunk if it fits
                if current_size + para_tokens > max_tokens and current_chunk:
                    chunks.append('\n\n'.join(current_chunk))
                    current_chunk = []
                    current_size = 0
                current_chunk.append(para)
                current_size += para_tokens
        
        # Add remaining chunk
        if current_chunk:
            chunks.append('\n\n'.join(current_chunk))
        
        # Verify all chunks are within limit
        final_chunks = []
        for chunk in chunks:
            chunk_tokens = self._estimate_tokens(chunk)
            if chunk_tokens > max_tokens:
                # Last resort: split by character count
                char_limit = max_tokens * 4
                for i in range(0, len(chunk), char_limit):
                    final_chunks.append(chunk[i:i + char_limit])
            else:
                final_chunks.append(chunk)
        
        return final_chunks
    
    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a list of texts with batch processing and automatic chunking.
        
        Large texts that exceed token limits are automatically chunked and embedded separately.
        The embeddings are averaged for the original text (or returned as multiple embeddings).
        
        Args:
            texts: List of text strings to embed
            
        Returns:
            List of embedding vectors (one per input text, averaged if chunked)
        """
        if not texts:
            return []
        
        logger.info(f"Generating embeddings for {len(texts)} texts using {self.model}")
        
        # Chunk texts that are too large
        chunked_texts = []
        text_to_chunks_map = {}  # Map original index to chunk indices
        
        for i, text in enumerate(texts):
            chunks = self._chunk_text(text, self.chunk_size)
            if len(chunks) > 1:
                logger.debug(f"Chunked text {i+1} into {len(chunks)} chunks ({self._estimate_tokens(text)} tokens total)")
                start_idx = len(chunked_texts)
                chunked_texts.extend(chunks)
                text_to_chunks_map[i] = (start_idx, start_idx + len(chunks))
            else:
                chunked_texts.append(text)
                text_to_chunks_map[i] = (len(chunked_texts) - 1, len(chunked_texts))
        
        # Generate embeddings for all chunks
        all_embeddings = []
        
        # Process in batches to handle rate limits
        for i in range(0, len(chunked_texts), self.batch_size):
            batch = chunked_texts[i:i + self.batch_size]
            
            try:
                # Run synchronous OpenAI call in executor to avoid blocking
                embeddings = await asyncio.to_thread(self._embed_batch, batch)
                all_embeddings.extend(embeddings)
                
                logger.debug(f"Embedded batch {i//self.batch_size + 1}/{(len(chunked_texts)-1)//self.batch_size + 1}")
                
            except Exception as e:
                logger.error(f"Failed to embed batch {i//self.batch_size + 1}: {e}")
                # Return zero vectors for failed embeddings
                all_embeddings.extend([[0.0] * 1536] * len(batch))
        
        # Average embeddings for chunked texts
        final_embeddings = []
        for i in range(len(texts)):
            start_idx, end_idx = text_to_chunks_map[i]
            chunk_embeddings = all_embeddings[start_idx:end_idx]
            
            if len(chunk_embeddings) == 1:
                final_embeddings.append(chunk_embeddings[0])
            else:
                # Average the embeddings from chunks
                if np is not None:
                    averaged = np.mean(chunk_embeddings, axis=0).tolist()
                else:
                    # Fallback: manual average if numpy not available
                    averaged = [sum(col) / len(chunk_embeddings) for col in zip(*chunk_embeddings)]
                final_embeddings.append(averaged)
        
        logger.info(f"Successfully generated {len(final_embeddings)} embeddings (processed {len(chunked_texts)} total chunks)")
        return final_embeddings
    
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
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector
        """
        embeddings = await self.embed_texts([text])
        return embeddings[0] if embeddings else [0.0] * 1536

