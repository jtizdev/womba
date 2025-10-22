"""
Embedding service for converting text to vector embeddings.
Supports OpenAI embeddings with batch processing.
"""

from typing import List, Optional
import asyncio
from loguru import logger

from src.config.settings import settings


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
        
    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a list of texts with batch processing.
        
        Args:
            texts: List of text strings to embed
            
        Returns:
            List of embedding vectors
        """
        if not texts:
            return []
        
        logger.info(f"Generating embeddings for {len(texts)} texts using {self.model}")
        
        all_embeddings = []
        
        # Process in batches to handle rate limits
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]
            
            try:
                # Run synchronous OpenAI call in executor to avoid blocking
                embeddings = await asyncio.to_thread(self._embed_batch, batch)
                all_embeddings.extend(embeddings)
                
                logger.debug(f"Embedded batch {i//self.batch_size + 1}/{(len(texts)-1)//self.batch_size + 1}")
                
            except Exception as e:
                logger.error(f"Failed to embed batch {i//self.batch_size + 1}: {e}")
                # Return zero vectors for failed embeddings
                all_embeddings.extend([[0.0] * 1536] * len(batch))
        
        logger.info(f"Successfully generated {len(all_embeddings)} embeddings")
        return all_embeddings
    
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

