"""
Reranking module for improving RAG retrieval relevance.
Uses cross-encoder models to rerank initial retrieval results.
"""

from typing import List, Dict, Any, Optional
from loguru import logger


class Reranker:
    """
    Reranks RAG retrieval results using cross-encoder models.
    Provides more accurate relevance scores than pure embedding similarity.
    """
    
    def __init__(self, model_name: str = 'cross-encoder/ms-marco-MiniLM-L-12-v2'):
        """
        Initialize reranker.
        
        Args:
            model_name: Cross-encoder model name
        """
        self.model_name = model_name
        self.model = None
        self._initialize_model()
    
    def _initialize_model(self):
        """Initialize cross-encoder model (lazy loading)."""
        try:
            from sentence_transformers import CrossEncoder
            self.model = CrossEncoder(self.model_name)
            logger.info(f"Initialized reranker with model: {self.model_name}")
        except ImportError:
            logger.warning(
                "sentence-transformers not installed. "
                "Install with: pip install sentence-transformers"
            )
            self.model = None
        except Exception as e:
            logger.error(f"Failed to initialize reranker: {e}")
            self.model = None
    
    def rerank(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        top_k: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Rerank documents based on relevance to query.
        
        Args:
            query: Search query
            documents: List of retrieved documents with metadata
            top_k: Number of top results to return (None = all)
            
        Returns:
            Reranked documents with updated scores
        """
        if not self.model or not documents:
            return documents
        
        try:
            # Prepare document texts
            doc_texts = [doc.get('document', '') for doc in documents]
            
            # Create query-document pairs
            pairs = [(query, text) for text in doc_texts]
            
            # Get reranking scores
            scores = self.model.predict(pairs)
            
            # Add scores to documents and sort
            reranked = []
            for doc, score in zip(documents, scores):
                doc_copy = doc.copy()
                doc_copy['rerank_score'] = float(score)
                reranked.append(doc_copy)
            
            # Sort by rerank score (higher = more relevant)
            reranked.sort(key=lambda x: x.get('rerank_score', 0), reverse=True)
            
            # Return top_k results
            if top_k:
                reranked = reranked[:top_k]
            
            logger.debug(f"Reranked {len(documents)} documents, returning top {len(reranked)}")
            return reranked
            
        except Exception as e:
            logger.error(f"Reranking failed: {e}")
            return documents
    
    async def rerank_async(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        top_k: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Async version of rerank (runs in thread pool to avoid blocking).
        
        Args:
            query: Search query
            documents: List of retrieved documents
            top_k: Number of top results to return
            
        Returns:
            Reranked documents
        """
        import asyncio
        from concurrent.futures import ThreadPoolExecutor
        
        # Run reranking in thread pool since model inference can be CPU-intensive
        with ThreadPoolExecutor(max_workers=1) as executor:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                executor,
                self.rerank,
                query,
                documents,
                top_k
            )
        
        return result


# Global reranker instance (singleton)
_reranker_instance: Optional[Reranker] = None


def get_reranker(model_name: str = 'cross-encoder/ms-marco-MiniLM-L-12-v2') -> Reranker:
    """
    Get global reranker instance (singleton).
    
    Args:
        model_name: Cross-encoder model name
        
    Returns:
        Reranker instance
    """
    global _reranker_instance
    if _reranker_instance is None:
        _reranker_instance = Reranker(model_name=model_name)
    return _reranker_instance

