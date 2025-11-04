"""
Embedding service for converting text to vector embeddings.
Optimized with AsyncOpenAI, parallel processing, and smart batching.
"""

from typing import List, Optional, Tuple
import asyncio
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from openai import RateLimitError

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

# OpenAI API limits per request
MAX_BATCH_SIZE = 2048  # Max number of inputs per request
MAX_BATCH_TOKENS = 80000  # Conservative total token limit per request


class EmbeddingService:
    """
    High-performance embedding service using AsyncOpenAI.
    Features:
    - True async with parallel batch processing
    - Smart token-based batching
    - Automatic retry with exponential backoff
    - Handles rate limits gracefully
    """
    
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        """
        Initialize embedding service.
        
        Args:
            api_key: OpenAI API key (defaults to settings)
            model: Embedding model (defaults to text-embedding-3-small)
        """
        from openai import AsyncOpenAI
        
        self.api_key = api_key or settings.openai_api_key
        self.model = model or settings.embedding_model
        
        # Validate API key
        if not self.api_key:
            raise ValueError(
                "OpenAI API key not configured. Please set OPENAI_API_KEY in .env or run 'womba configure'"
            )
        
        # Initialize AsyncOpenAI client for true async performance
        self.client = AsyncOpenAI(api_key=self.api_key)
        
        # Get token limit for this model (with safety margin)
        self.max_tokens = MODEL_TOKEN_LIMITS.get(self.model, 8192)
        self.chunk_size = int(self.max_tokens * 0.70)  # Use 70% of limit for safety margin
        
        logger.info(f"Initialized async embedding service with model {self.model} (max tokens: {self.max_tokens}, chunk size: {self.chunk_size})")
        
    def _estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for a text.
        Uses conservative approximation: ~3 characters per token for English text.
        
        Args:
            text: Text to estimate
            
        Returns:
            Estimated token count (conservative estimate)
        """
        return len(text) // 3
    
    def _create_smart_batches(self, texts: List[str]) -> List[List[str]]:
        """
        Create batches respecting BOTH count and token limits.
        
        OpenAI limits:
        - Max 2048 inputs per request
        - Max ~100k total tokens per request (we use 80k to be safe)
        
        Args:
            texts: List of texts to batch
            
        Returns:
            List of text batches
        """
        batches = []
        current_batch = []
        current_tokens = 0
        
        # Conservative limits
        BATCH_TOKEN_LIMIT = MAX_BATCH_TOKENS
        BATCH_SIZE_LIMIT = 1000  # Reasonable balance (instead of 2048 max)
        
        for text in texts:
            tokens = self._estimate_tokens(text)
            
            # Start new batch if either limit would be exceeded
            if (current_tokens + tokens > BATCH_TOKEN_LIMIT or 
                len(current_batch) >= BATCH_SIZE_LIMIT):
                if current_batch:
                    batches.append(current_batch)
                current_batch = [text]
                current_tokens = tokens
            else:
                current_batch.append(text)
                current_tokens += tokens
        
        # Add remaining batch
        if current_batch:
            batches.append(current_batch)
        
        logger.debug(f"Created {len(batches)} smart batches from {len(texts)} texts")
        return batches
    
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
                        char_limit = max_tokens * 3  # ~3 chars per token (conservative)
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
                logger.warning(f"Chunk still too large ({chunk_tokens} tokens), applying emergency truncation")
                # Emergency truncation
                char_limit = max_tokens * 3
                final_chunks.append(chunk[:char_limit])
            else:
                final_chunks.append(chunk)
        
        return final_chunks
    
    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=4, max=60),
        retry=retry_if_exception_type(RateLimitError)
    )
    async def _embed_batch_with_retry(self, texts: List[str]) -> List[List[float]]:
        """
        Embed a batch of texts with automatic retry on rate limits.
        Uses exponential backoff for rate limit errors.
        
        Args:
            texts: Batch of texts to embed
            
        Returns:
            List of embedding vectors
        """
        # Final safety check: verify all texts are valid and within limit
        safe_texts = []
        for i, text in enumerate(texts):
            # OpenAI rejects empty strings, None, or whitespace-only strings
            if not text or not text.strip():
                logger.warning(f"Text {i+1} is empty or whitespace-only, replacing with placeholder")
                text = "Empty text placeholder"
            
            # Ensure text is a string
            text = str(text).strip()
            
            # Check token limit
            estimated = self._estimate_tokens(text)
            if estimated > self.max_tokens:
                logger.warning(f"Text has {estimated} estimated tokens (limit: {self.max_tokens}). Truncating!")
                char_limit = self.max_tokens * 3
                text = text[:char_limit]
            
            safe_texts.append(text)
        
        try:
            response = await self.client.embeddings.create(
                model=self.model,
                input=safe_texts
            )
            
            # Extract embeddings in order
            embeddings = [item.embedding for item in response.data]
            return embeddings
            
        except Exception as e:
            logger.error(f"OpenAI embedding error for batch of {len(texts)} texts: {e}")
            raise
    
    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a list of texts with parallel processing.
        
        Features:
        - Smart token-based batching
        - Parallel processing with semaphore (up to 5 concurrent batches)
        - Automatic retry with exponential backoff
        - Handles chunking for oversized texts
        
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
                logger.debug(f"Chunked text {i+1} into {len(chunks)} chunks")
                start_idx = len(chunked_texts)
                chunked_texts.extend(chunks)
                text_to_chunks_map[i] = (start_idx, start_idx + len(chunks))
            else:
                chunked_texts.append(text)
                text_to_chunks_map[i] = (len(chunked_texts) - 1, len(chunked_texts))
        
        # Create smart batches respecting BOTH count and token limits
        batches = self._create_smart_batches(chunked_texts)
        logger.info(f"Processing {len(batches)} batches in parallel (from {len(chunked_texts)} chunks)")
        
        # Process batches in parallel with semaphore to control concurrency
        semaphore = asyncio.Semaphore(5)  # Max 5 concurrent API requests
        
        async def process_batch(batch_idx: int, batch: List[str]) -> Tuple[int, List[List[float]]]:
            async with semaphore:
                try:
                    embeddings = await self._embed_batch_with_retry(batch)
                    logger.debug(f"✓ Batch {batch_idx+1}/{len(batches)} complete ({len(batch)} texts)")
                    return (batch_idx, embeddings)
                except Exception as e:
                    logger.error(f"✗ Batch {batch_idx+1}/{len(batches)} failed: {e}")
                    # Return zero vectors for failed batch
                    return (batch_idx, [[0.0] * 1536] * len(batch))
        
        # Run all batches in parallel
        results = await asyncio.gather(*[process_batch(i, batch) for i, batch in enumerate(batches)])
        
        # Sort results by batch index and flatten
        results.sort(key=lambda x: x[0])
        all_embeddings = []
        for _, batch_embeddings in results:
            all_embeddings.extend(batch_embeddings)
        
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
        
        logger.info(f"✓ Successfully generated {len(final_embeddings)} embeddings (processed {len(chunked_texts)} total chunks)")
        return final_embeddings
    
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
