"""
RAG Vector Store using ChromaDB for semantic search and retrieval.
"""

from typing import List, Dict, Optional, Any
from pathlib import Path
import json

import chromadb
from chromadb.config import Settings as ChromaSettings
from loguru import logger

from src.config.settings import settings
from src.ai.embedding_service import EmbeddingService


class RAGVectorStore:
    """
    Vector database for storing and retrieving context using ChromaDB.
    Stores: test plans, Confluence docs, Jira stories, existing tests.
    """
    
    # Collection names
    TEST_PLANS_COLLECTION = "test_plans"
    CONFLUENCE_DOCS_COLLECTION = "confluence_docs"
    JIRA_STORIES_COLLECTION = "jira_stories"
    EXISTING_TESTS_COLLECTION = "existing_tests"
    
    def __init__(self, collection_path: Optional[str] = None):
        """
        Initialize RAG vector store.
        
        Args:
            collection_path: Path to ChromaDB storage (defaults to settings)
        """
        self.collection_path = Path(collection_path or settings.rag_collection_path)
        self.collection_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize ChromaDB client
        self.client = chromadb.PersistentClient(
            path=str(self.collection_path),
            settings=ChromaSettings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        # Initialize embedding service
        self.embedding_service = EmbeddingService()
        
        logger.info(f"Initialized RAG vector store at {self.collection_path}")
    
    def get_or_create_collection(self, collection_name: str):
        """
        Get or create a ChromaDB collection.
        
        Args:
            collection_name: Name of the collection
            
        Returns:
            ChromaDB collection object
        """
        try:
            collection = self.client.get_or_create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"}  # Use cosine similarity
            )
            return collection
        except Exception as e:
            logger.error(f"Failed to get/create collection {collection_name}: {e}")
            raise
    
    async def add_documents(
        self,
        collection_name: str,
        documents: List[str],
        metadatas: List[Dict[str, Any]],
        ids: List[str]
    ) -> None:
        """
        Add documents to a collection with embeddings.
        
        Args:
            collection_name: Name of the collection
            documents: List of document texts
            metadatas: List of metadata dicts for each document
            ids: List of unique IDs for each document
        """
        if not documents:
            logger.warning("No documents to add")
            return
        
        if len(documents) != len(metadatas) != len(ids):
            raise ValueError("documents, metadatas, and ids must have the same length")
        
        logger.info(f"Adding {len(documents)} documents to {collection_name}")
        
        # Generate embeddings
        embeddings = await self.embedding_service.embed_texts(documents)
        
        # Get collection
        collection = self.get_or_create_collection(collection_name)
        
        # Add to ChromaDB
        try:
            collection.add(
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )
            logger.info(f"Successfully added {len(documents)} documents to {collection_name}")
        except Exception as e:
            logger.error(f"Failed to add documents to {collection_name}: {e}")
            raise
    
    async def retrieve_similar(
        self,
        collection_name: str,
        query_text: str,
        top_k: int = 10,
        metadata_filter: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve similar documents using semantic search.
        
        Args:
            collection_name: Name of the collection to search
            query_text: Query text for similarity search
            top_k: Number of results to return
            metadata_filter: Optional metadata filters (e.g., {"project_key": "PLAT"})
            
        Returns:
            List of retrieved documents with metadata and similarity scores
        """
        logger.info(f"Retrieving top {top_k} similar documents from {collection_name}")
        
        # Generate query embedding
        query_embedding = await self.embedding_service.embed_single(query_text)
        
        # Get collection
        try:
            collection = self.get_or_create_collection(collection_name)
        except Exception as e:
            logger.error(f"Collection {collection_name} not found: {e}")
            return []
        
        # Query ChromaDB
        try:
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=metadata_filter
            )
            
            # Format results
            documents = []
            if results['documents'] and len(results['documents']) > 0:
                for i, doc in enumerate(results['documents'][0]):
                    documents.append({
                        'id': results['ids'][0][i],
                        'document': doc,
                        'metadata': results['metadatas'][0][i] if results['metadatas'] else {},
                        'distance': results['distances'][0][i] if results['distances'] else None
                    })
            
            logger.info(f"Retrieved {len(documents)} similar documents")
            return documents
            
        except Exception as e:
            logger.error(f"Failed to query {collection_name}: {e}")
            return []
    
    def get_collection_stats(self, collection_name: str) -> Dict[str, Any]:
        """
        Get statistics for a collection.
        
        Args:
            collection_name: Name of the collection
            
        Returns:
            Dictionary with collection statistics
        """
        try:
            collection = self.get_or_create_collection(collection_name)
            count = collection.count()
            
            return {
                "name": collection_name,
                "count": count,
                "exists": True
            }
        except Exception as e:
            logger.error(f"Failed to get stats for {collection_name}: {e}")
            return {
                "name": collection_name,
                "count": 0,
                "exists": False,
                "error": str(e)
            }
    
    def get_all_stats(self) -> Dict[str, Any]:
        """
        Get statistics for all collections.
        
        Returns:
            Dictionary with all collection statistics
        """
        collections = [
            self.TEST_PLANS_COLLECTION,
            self.CONFLUENCE_DOCS_COLLECTION,
            self.JIRA_STORIES_COLLECTION,
            self.EXISTING_TESTS_COLLECTION
        ]
        
        stats = {}
        total_documents = 0
        
        for collection_name in collections:
            collection_stats = self.get_collection_stats(collection_name)
            stats[collection_name] = collection_stats
            total_documents += collection_stats.get('count', 0)
        
        stats['total_documents'] = total_documents
        stats['storage_path'] = str(self.collection_path)
        
        return stats
    
    def clear_collection(self, collection_name: str) -> None:
        """
        Clear all documents from a collection.
        
        Args:
            collection_name: Name of the collection to clear
        """
        try:
            self.client.delete_collection(collection_name)
            logger.info(f"Cleared collection: {collection_name}")
        except Exception as e:
            logger.warning(f"Failed to clear collection {collection_name}: {e}")
    
    def clear_all_collections(self) -> None:
        """Clear all RAG collections."""
        collections = [
            self.TEST_PLANS_COLLECTION,
            self.CONFLUENCE_DOCS_COLLECTION,
            self.JIRA_STORIES_COLLECTION,
            self.EXISTING_TESTS_COLLECTION
        ]
        
        for collection_name in collections:
            self.clear_collection(collection_name)
        
        logger.info("Cleared all RAG collections")

