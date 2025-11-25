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
    JIRA_ISSUES_COLLECTION = "jira_issues"
    EXISTING_TESTS_COLLECTION = "existing_tests"
    EXTERNAL_DOCS_COLLECTION = "external_docs"
    SWAGGER_DOCS_COLLECTION = "swagger_docs"
    
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
            except TypeError as type_error:
                # ChromaDB bug: "object of type 'int' has no len()"
                # Skip the upsert check and just add all documents as new
                if "object of type" in str(type_error) and "has no len()" in str(type_error):
                    logger.warning(f"ChromaDB bug detected in add_documents for {collection_name}: {type_error}. Skipping upsert check.")
                    existing_docs = {}  # Treat all as new
                else:
                    raise
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
                try:
                    collection.add(
                        embeddings=all_embeddings,
                        documents=all_docs,
                        metadatas=all_metadatas,
                        ids=all_ids
                    )
                except TypeError as te:
                    # ChromaDB bug with embeddings - try adding without embeddings first
                    if "object of type" in str(te) and "has no len()" in str(te):
                        logger.warning(f"ChromaDB bug during collection.add() for {collection_name}: {te}. Retrying with upsert fallback...")
                        try:
                            # Try upsert as fallback (may avoid the embedding validation bug)
                            collection.upsert(
                                embeddings=all_embeddings,
                                documents=all_docs,
                                metadatas=all_metadatas,
                                ids=all_ids
                            )
                            logger.info(f"✅ Upsert fallback succeeded for {collection_name}")
                        except Exception as upsert_error:
                            logger.warning(f"Upsert fallback also failed: {upsert_error}. Attempting batch insert...")
                            # Try adding one at a time as last resort
                            failed_count = 0
                            for i, doc_id in enumerate(all_ids):
                                try:
                                    collection.add(
                                        embeddings=[all_embeddings[i]],
                                        documents=[all_docs[i]],
                                        metadatas=[all_metadatas[i]],
                                        ids=[doc_id]
                                    )
                                except Exception as individual_error:
                                    logger.error(f"Failed to add individual document {doc_id}: {individual_error}")
                                    failed_count += 1
                            
                            if failed_count > 0:
                                logger.error(f"Failed to add {failed_count}/{len(all_ids)} documents in batch mode")
                                raise ValueError(f"ChromaDB failed to add {failed_count} documents after all retry attempts")
                    else:
                        raise
                
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
        metadata_filter: Optional[Dict[str, Any]] = None,
        min_similarity_override: Optional[float] = None
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
            
            # Format results with similarity filtering and logging
            documents = []
            filtered_count = 0
            min_similarity = min_similarity_override if min_similarity_override is not None else settings.rag_min_similarity
            similarity_scores = []
            
            if results['documents'] and len(results['documents']) > 0:
                for i, doc in enumerate(results['documents'][0]):
                    distance = results['distances'][0][i] if results['distances'] else None
                    similarity = 1 - distance if distance is not None else 0.0
                    similarity_scores.append(similarity)
                    
                    # Filter by minimum similarity threshold
                    if similarity >= min_similarity:
                        documents.append({
                            'id': results['ids'][0][i],
                            'document': doc,
                            'metadata': results['metadatas'][0][i] if results['metadatas'] else {},
                            'distance': distance,
                            'similarity': similarity
                        })
                    else:
                        filtered_count += 1
                        logger.debug(
                            f"Filtered low-similarity document from {collection_name}: "
                            f"similarity={similarity:.3f} < threshold={min_similarity}"
                        )
            
            # Log retrieval quality metrics
            if similarity_scores:
                avg_similarity = sum(similarity_scores) / len(similarity_scores)
                max_similarity = max(similarity_scores)
                min_similarity_found = min(similarity_scores)
                
                logger.info(
                    f"Retrieved {len(documents)}/{len(similarity_scores)} documents from {collection_name} "
                    f"(filtered {filtered_count} below threshold={min_similarity:.2f})"
                )
                logger.info(
                    f"Similarity scores: avg={avg_similarity:.3f}, max={max_similarity:.3f}, "
                    f"min={min_similarity_found:.3f}"
                )
                
                # Warn if average similarity is low
                if avg_similarity < 0.6:
                    logger.warning(
                        f"Low average similarity ({avg_similarity:.3f}) for {collection_name}. "
                        f"Consider improving query or embeddings."
                    )
            else:
                logger.info(f"Retrieved {len(documents)} similar documents from {collection_name}")
            
            return documents
            
        except Exception as e:
            logger.error(f"Failed to query {collection_name}: {e}")
            return []
    
    async def get_test_plan_by_story_key(self, issue_key: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a test plan by story key (exact match).
        
        Args:
            issue_key: Jira issue key (e.g., "PLAT-13541")
            
        Returns:
            Dictionary with document data including metadata, or None if not found
        """
        logger.info(f"Retrieving test plan for {issue_key}")
        
        try:
            collection = self.get_or_create_collection(self.TEST_PLANS_COLLECTION)
            
            # Query by metadata filter for exact match
            results = collection.get(
                where={"story_key": issue_key},
                limit=1
            )
            
            if not results or not results.get('ids') or len(results['ids']) == 0:
                logger.info(f"Test plan not found for {issue_key}")
                return None
            
            # Return first result
            idx = 0
            return {
                'id': results['ids'][idx],
                'document': results['documents'][idx] if results.get('documents') else '',
                'metadata': results['metadatas'][idx] if results.get('metadatas') else {}
            }
            
        except Exception as e:
            logger.error(f"Failed to retrieve test plan for {issue_key}: {e}")
            return None
    
    async def update_test_plan(self, issue_key: str, test_plan_json: str, doc_text: str, metadata: Dict[str, Any]) -> None:
        """
        Update an existing test plan in RAG storage.
        
        Uses upsert logic: deletes old document and adds new one.
        
        Args:
            issue_key: Jira issue key
            test_plan_json: Full TestPlan JSON as string
            doc_text: Text representation for semantic search
            metadata: Metadata dictionary (should include test_plan_json field)
        """
        logger.info(f"Updating test plan for {issue_key} in RAG")
        
        doc_id = f"testplan_{issue_key}"
        
        try:
            collection = self.get_or_create_collection(self.TEST_PLANS_COLLECTION)
            
            # Delete existing document if it exists
            try:
                existing = collection.get(ids=[doc_id])
                if existing and existing.get('ids') and len(existing['ids']) > 0:
                    collection.delete(ids=[doc_id])
                    logger.debug(f"Deleted existing test plan document {doc_id}")
            except Exception as e:
                logger.debug(f"No existing document to delete for {doc_id}: {e}")
            
            # Add updated document
            await self.add_documents(
                collection_name=self.TEST_PLANS_COLLECTION,
                documents=[doc_text],
                metadatas=[metadata],
                ids=[doc_id]
            )
            
            logger.info(f"Successfully updated test plan for {issue_key} in RAG")
            
        except Exception as e:
            logger.error(f"Failed to update test plan for {issue_key}: {e}")
            raise
    
    def get_collection_stats(self, collection_name: str) -> Dict[str, Any]:
        """
        Get statistics for a collection.
        Handles ChromaDB 0.5.0 bug with count() and peek() on certain collections.
        
        Args:
            collection_name: Name of the collection
            
        Returns:
            Dictionary with collection statistics
        """
        try:
            collection = self.get_or_create_collection(collection_name)
            count_value = 0
            
            # Try count() method first
            try:
                count_result = collection.count()
                if isinstance(count_result, int):
                    count_value = count_result
                else:
                    # count() returned something unexpected, try alternative
                    raise TypeError("count() returned non-integer")
            except TypeError as type_error:
                # ChromaDB bug: "object of type 'int' has no len()" 
                # This happens with certain collections. Try query fallback.
                if "object of type" in str(type_error) and "has no len()" in str(type_error):
                    logger.warning(f"ChromaDB bug detected on {collection_name}: {type_error}. Trying query fallback.")
                    try:
                        # Try to query with limit=1 to see if collection has data
                        result = collection.get(limit=1)
                        if result and isinstance(result, dict) and 'ids' in result and result['ids']:
                            # Collection has data, but we can't reliably count it
                            count_value = 0  # Fallback to 0 for display
                    except Exception as query_error:
                        logger.debug(f"Query fallback also failed for {collection_name}: {query_error}")
                        count_value = 0
                else:
                    raise
            except (AttributeError, Exception) as count_error:
                # count() failed for other reasons, try peek()
                try:
                    peek_results = collection.peek(limit=1000)
                    if peek_results and isinstance(peek_results, dict):
                        ids = peek_results.get('ids', [])
                        if ids:
                            count_value = len(ids)
                            if len(ids) == 1000:
                                count_value = 1000
                except Exception as peek_error:
                    # ChromaDB bug also hit peek()
                    if "object of type" in str(peek_error) and "has no len()" in str(peek_error):
                        logger.warning(f"ChromaDB bug on peek() for {collection_name}: {peek_error}")
                        count_value = 0
                    else:
                        logger.debug(f"Could not count {collection_name}: count_error={count_error}, peek_error={peek_error}")
                        count_value = 0
            
            return {
                "name": collection_name,
                "count": count_value,
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
            self.JIRA_ISSUES_COLLECTION,
            self.EXISTING_TESTS_COLLECTION,
            self.EXTERNAL_DOCS_COLLECTION,
            self.SWAGGER_DOCS_COLLECTION
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
            self.JIRA_ISSUES_COLLECTION,
            self.EXISTING_TESTS_COLLECTION,
            self.EXTERNAL_DOCS_COLLECTION,
            self.SWAGGER_DOCS_COLLECTION
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

