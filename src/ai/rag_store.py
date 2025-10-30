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
    EXTERNAL_DOCS_COLLECTION = "external_docs"
    
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
        Long documents are automatically chunked for embedding, but full text is stored.
        
        Args:
            collection_name: Name of the collection
            documents: List of document texts (FULL content - no truncation!)
            metadatas: List of metadata dicts for each document
            ids: List of unique IDs for each document
        """
        if not documents:
            logger.warning("No documents to add")
            return
        
        if len(documents) != len(metadatas) != len(ids):
            raise ValueError("documents, metadatas, and ids must have the same length")
        
        logger.info(f"Adding {len(documents)} documents to {collection_name}")
        
        # Generate embeddings with automatic chunking
        document_embeddings_list = await self.embedding_service.embed_texts(documents, chunk_long_docs=True)
        
        # Flatten: create one entry per chunk, but store FULL document text in each
        all_embeddings = []
        all_chunk_documents = []  # Chunk text for embedding/similarity search
        all_full_documents = []   # FULL document text for retrieval
        all_chunk_metadatas = []
        all_chunk_ids = []
        
        for doc_idx, (original_doc, original_metadata, original_id) in enumerate(zip(documents, metadatas, ids)):
            doc_embeddings = document_embeddings_list[doc_idx]
            
            if len(doc_embeddings) == 1:
                # Single chunk - simple case
                all_embeddings.append(doc_embeddings[0])
                all_chunk_documents.append(original_doc)  # Chunk = full doc
                all_full_documents.append(original_doc)    # Full doc = full doc
                
                # Enhanced metadata to indicate full document
                chunk_metadata = original_metadata.copy()
                chunk_metadata['chunk_index'] = 0
                chunk_metadata['total_chunks'] = 1
                chunk_metadata['is_full_document'] = True
                all_chunk_metadatas.append(chunk_metadata)
                
                all_chunk_ids.append(original_id)
            else:
                # Multiple chunks - store each chunk with reference to full doc
                from src.ai.embedding_service import MAX_CHUNK_LENGTH, CHUNK_OVERLAP
                
                # Re-chunk to get chunk texts (same logic as embedding service)
                if len(original_doc) <= MAX_CHUNK_LENGTH:
                    chunks = [original_doc]
                else:
                    chunks = []
                    start = 0
                    while start < len(original_doc):
                        end = start + MAX_CHUNK_LENGTH
                        if end >= len(original_doc):
                            chunks.append(original_doc[start:])
                            break
                        # Smart boundary detection (same as embedding service)
                        newline_pos = original_doc.rfind('\n\n', start, end)
                        if newline_pos > start + MAX_CHUNK_LENGTH // 2:
                            end = newline_pos + 2
                        else:
                            newline_pos = original_doc.rfind('\n', start, end)
                            if newline_pos > start + MAX_CHUNK_LENGTH // 2:
                                end = newline_pos + 1
                        chunks.append(original_doc[start:end])
                        start = end - CHUNK_OVERLAP
                        if start < 0:
                            start = 0
                
                for chunk_idx, (chunk_text, chunk_embedding) in enumerate(zip(chunks, doc_embeddings)):
                    all_embeddings.append(chunk_embedding)
                    all_chunk_documents.append(chunk_text)  # Chunk text for similarity
                    all_full_documents.append(original_doc)  # FULL document always stored!
                    
                    # Enhanced metadata
                    chunk_metadata = original_metadata.copy()
                    chunk_metadata['chunk_index'] = chunk_idx
                    chunk_metadata['total_chunks'] = len(chunks)
                    chunk_metadata['is_full_document'] = False
                    chunk_metadata['original_doc_id'] = original_id  # Link back to original
                    all_chunk_metadatas.append(chunk_metadata)
                    
                    # Unique ID per chunk
                    chunk_id = f"{original_id}_chunk_{chunk_idx}"
                    all_chunk_ids.append(chunk_id)
                
                logger.info(f"Document '{original_id}' split into {len(chunks)} chunks for embedding")
        
        # Get collection
        collection = self.get_or_create_collection(collection_name)
        
        # Add to ChromaDB - store FULL documents, not chunks!
        # When retrieving, we'll get full documents even if they were chunked
        try:
            collection.add(
                embeddings=all_embeddings,
                documents=all_full_documents,  # Store FULL documents for retrieval!
                metadatas=all_chunk_metadatas,
                ids=all_chunk_ids
            )
            logger.info(f"Successfully added {len(documents)} documents ({len(all_chunk_ids)} entries after chunking) to {collection_name}")
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
        # Request more results since we'll deduplicate chunks
        # If a doc was chunked into 3 pieces and all match, we want the best chunk
        query_limit = top_k * 3  # Get 3x results to account for chunking
        
        try:
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=query_limit,
                where=metadata_filter
            )
            
            # Format results and deduplicate by document (chunks from same doc -> one result)
            seen_docs = {}  # Map original_doc_id -> best match
            
            if results['documents'] and len(results['documents']) > 0:
                for i, doc in enumerate(results['documents'][0]):
                    metadata = results['metadatas'][0][i] if results['metadatas'] else {}
                    # Use original_doc_id if this is a chunk, otherwise use the id
                    doc_id = metadata.get('original_doc_id') or results['ids'][0][i]
                    distance = results['distances'][0][i] if results['distances'] else None
                    
                    result_entry = {
                        'id': results['ids'][0][i],
                        'document': doc,  # This is the FULL document (not chunk)!
                        'metadata': metadata,
                        'distance': distance
                    }
                    
                    # If multiple chunks from same document match, keep the best (closest) one
                    if doc_id not in seen_docs:
                        seen_docs[doc_id] = result_entry
                    elif distance is not None and seen_docs[doc_id]['distance'] is not None:
                        if seen_docs[doc_id]['distance'] > distance:
                            seen_docs[doc_id] = result_entry
            
            # Return deduplicated results, sorted by similarity, limit to top_k
            documents = list(seen_docs.values())
            documents.sort(key=lambda x: x['distance'] if x['distance'] is not None else float('inf'))
            documents = documents[:top_k]  # Limit to requested number after deduplication
            
            num_chunks = len(results['documents'][0]) if results.get('documents') and len(results['documents']) > 0 else 0
            logger.info(f"Retrieved {len(documents)} unique documents (from {num_chunks} chunks)")
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
            self.EXISTING_TESTS_COLLECTION,
            self.EXTERNAL_DOCS_COLLECTION,
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
            self.EXISTING_TESTS_COLLECTION,
            self.EXTERNAL_DOCS_COLLECTION,
        ]
        
        for collection_name in collections:
            self.clear_collection(collection_name)
        
        logger.info("Cleared all RAG collections")
    
    def get_all_documents(
        self,
        collection_name: str,
        limit: Optional[int] = None,
        metadata_filter: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Get all documents from a collection (for viewing/indexing).
        
        Args:
            collection_name: Name of the collection
            limit: Optional limit on number of documents
            metadata_filter: Optional metadata filter
            
        Returns:
            List of all documents with their content and metadata
        """
        try:
            collection = self.get_or_create_collection(collection_name)
            
            # ChromaDB's get() method retrieves all documents
            # We can filter by metadata if needed
            results = collection.get(
                limit=limit,
                where=metadata_filter
            )
            
            documents = []
            if results and results.get('documents'):
                for i, doc in enumerate(results['documents']):
                    documents.append({
                        'id': results['ids'][i] if results.get('ids') else f"doc_{i}",
                        'document': doc,
                        'metadata': results['metadatas'][i] if results.get('metadatas') else {},
                    })
            
            logger.info(f"Retrieved {len(documents)} documents from {collection_name}")
            return documents
            
        except Exception as e:
            logger.error(f"Failed to get documents from {collection_name}: {e}")
            return []

