"""
RAG Vector Store using ChromaDB for semantic search and retrieval.
"""

from typing import List, Dict, Optional, Any
from pathlib import Path
import json
import hashlib
import shutil

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
        
        # Add to ChromaDB with upsert logic - update changed documents
        try:
            # Check which IDs already exist and compare metadata
            existing_docs = {}
            try:
                existing = collection.get(ids=ids)
                if existing and existing.get('ids'):
                    for idx, doc_id in enumerate(existing['ids']):
                        existing_docs[doc_id] = {
                            'metadata': existing['metadatas'][idx] if existing.get('metadatas') else {},
                            'document': existing['documents'][idx] if existing.get('documents') else None
                        }
            except Exception:
                pass  # Collection might not exist yet
            
            # Separate documents into new, updated, and unchanged
            truly_new_docs = []
            truly_new_embeddings = []
            truly_new_metadatas = []
            truly_new_ids = []
            
            updated_docs = []
            updated_embeddings = []
            updated_metadatas = []
            updated_ids = []
            
            unchanged_count = 0
            
            for i, doc_id in enumerate(ids):
                if doc_id not in existing_docs:
                    # New document - never seen before
                    truly_new_docs.append(documents[i])
                    truly_new_embeddings.append(embeddings[i])
                    truly_new_metadatas.append(metadatas[i])
                    truly_new_ids.append(doc_id)
                else:
                    # Check if document has changed
                    existing_meta = existing_docs[doc_id]['metadata']
                    new_meta = metadatas[i]
                    
                    # Compare timestamps and content hashes
                    existing_timestamp = existing_meta.get('last_modified') or existing_meta.get('timestamp')
                    new_timestamp = new_meta.get('last_modified') or new_meta.get('timestamp')
                    
                    # Calculate content hash for comparison
                    existing_doc = existing_docs[doc_id].get('document', '')
                    existing_hash = hashlib.md5(existing_doc.encode()).hexdigest() if existing_doc else None
                    new_hash = hashlib.md5(documents[i].encode()).hexdigest()
                    
                    # Check if document has changed (timestamp or content)
                    has_changed = (
                        new_timestamp and existing_timestamp and new_timestamp > existing_timestamp
                    ) or (
                        existing_hash and new_hash != existing_hash
                    ) or (
                        new_timestamp and not existing_timestamp  # New timestamp metadata
                    )
                    
                    if has_changed:
                        # Document exists but has changed - needs update
                        try:
                            collection.delete(ids=[doc_id])
                            updated_docs.append(documents[i])
                            updated_embeddings.append(embeddings[i])
                            updated_metadatas.append(metadatas[i])
                            updated_ids.append(doc_id)
                        except Exception as e:
                            logger.warning(f"Failed to delete document {doc_id} for update: {e}")
                            # If delete fails, treat as new
                            truly_new_docs.append(documents[i])
                            truly_new_embeddings.append(embeddings[i])
                            truly_new_metadatas.append(metadatas[i])
                            truly_new_ids.append(doc_id)
                    else:
                        # Document unchanged - skip it
                        unchanged_count += 1
                        logger.debug(f"Skipping unchanged document: {doc_id}")
            
            # Combine new and updated for batch add
            all_docs = truly_new_docs + updated_docs
            all_embeddings = truly_new_embeddings + updated_embeddings
            all_metadatas = truly_new_metadatas + updated_metadatas
            all_ids = truly_new_ids + updated_ids
            
            # Add new and updated documents
            if all_docs:
                collection.add(
                    embeddings=all_embeddings,
                    documents=all_docs,
                    metadatas=all_metadatas,
                    ids=all_ids
                )
                
                # Clear, detailed logging
                total = len(ids)
                new_count = len(truly_new_ids)
                updated_count = len(updated_ids)
                unchanged = unchanged_count
                
                status_parts = []
                if new_count > 0:
                    status_parts.append(f"✨ {new_count} NEW")
                if updated_count > 0:
                    status_parts.append(f"🔄 {updated_count} UPDATED")
                if unchanged > 0:
                    status_parts.append(f"⏭️  {unchanged} UNCHANGED (skipped)")
                
                logger.info(f"📊 Collection '{collection_name}' upsert complete: {total} total processed - {', '.join(status_parts)}")
                
                # Summary for user visibility
                if new_count > 0 or updated_count > 0:
                    logger.info(f"   ✅ Successfully indexed: {new_count} new + {updated_count} updated = {new_count + updated_count} total changes")
                if unchanged > 0:
                    logger.info(f"   ⏭️  Skipped: {unchanged} unchanged documents")
            else:
                # All documents unchanged
                logger.info(f"⏭️  Collection '{collection_name}': All {len(ids)} documents unchanged - nothing to update")
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
            self.EXISTING_TESTS_COLLECTION,
            self.EXTERNAL_DOCS_COLLECTION
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
        """
        Clear all RAG collections and remove all data files.
        
        ChromaDB's delete_collection() doesn't remove underlying files,
        so we need to actually delete the storage directory to fully clear everything.
        """
        collections = [
            self.TEST_PLANS_COLLECTION,
            self.CONFLUENCE_DOCS_COLLECTION,
            self.JIRA_STORIES_COLLECTION,
            self.EXISTING_TESTS_COLLECTION,
            self.EXTERNAL_DOCS_COLLECTION
        ]
        
        # First, delete all collections
        for collection_name in collections:
            self.clear_collection(collection_name)
        
        # Then, completely delete all data files and directories
        # ChromaDB's reset() doesn't actually remove files, so we must do it manually
        try:
            logger.info("Deleting all ChromaDB data files and directories...")
            
            # Get list of items to delete before deletion (to avoid iteration issues)
            items_to_delete = list(self.collection_path.iterdir())
            deleted_dirs = 0
            deleted_files = 0
            
            for item in items_to_delete:
                try:
                    if item.is_dir():
                        shutil.rmtree(item, ignore_errors=True)
                        logger.debug(f"Deleted directory: {item.name}")
                        deleted_dirs += 1
                    elif item.is_file():
                        # Keep chroma.sqlite3 as ChromaDB may need it, but delete everything else
                        if item.name != "chroma.sqlite3":
                            item.unlink(missing_ok=True)
                            logger.debug(f"Deleted file: {item.name}")
                            deleted_files += 1
                except Exception as e:
                    logger.warning(f"Failed to delete {item.name}: {e}")
                    continue
            
            logger.info(f"✅ Deleted {deleted_dirs} directories and {deleted_files} files from ChromaDB storage")
            
            # Also try reset for good measure (but it usually doesn't do anything)
            try:
                self.client.reset()
            except Exception:
                pass  # Reset may fail, but that's okay if we manually deleted
            
        except Exception as e:
            logger.error(f"Failed to delete ChromaDB data files: {e}")
            raise
        
        logger.info("✅ Cleared all RAG collections and data files")

