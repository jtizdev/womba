"""
RAG management API endpoints.
"""

from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from loguru import logger

from src.ai.rag_store import RAGVectorStore
from src.ai.context_indexer import ContextIndexer
from src.aggregator.story_collector import StoryCollector
from src.integrations.zephyr_integration import ZephyrIntegration
from src.cli.rag_commands import index_all_data


router = APIRouter(prefix="/api/v1/rag", tags=["rag"])


class IndexRequest(BaseModel):
    """Request to index a story."""
    story_key: str
    project_key: Optional[str] = None


class SearchRequest(BaseModel):
    """Request to search RAG."""
    query: str
    collection: str = "test_plans"
    top_k: int = 10
    project_key: Optional[str] = None
    min_similarity: Optional[float] = None  # Minimum similarity threshold for filtering results


@router.get("/stats")
async def get_rag_stats():
    """
    Get RAG database statistics.
    
    Returns:
        Statistics about all RAG collections
    """
    try:
        store = RAGVectorStore()
        stats = store.get_all_stats()
        return stats
    except Exception as e:
        logger.error(f"Failed to get RAG stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/index")
async def index_story(request: IndexRequest):
    """
    Index a story's context into RAG.
    
    Args:
        request: Index request with story key
        
    Returns:
        Success message with indexing results
    """
    try:
        logger.info(f"API: Indexing story {request.story_key}")
        
        # Collect story context
        collector = StoryCollector()
        context = await collector.collect_story_context(request.story_key)
        
        # Index the context
        indexer = ContextIndexer()
        project_key = request.project_key or request.story_key.split('-')[0]
        await indexer.index_story_context(context, project_key)
        
        return {
            "status": "success",
            "message": f"Successfully indexed {request.story_key}",
            "story_key": request.story_key,
            "project_key": project_key
        }
        
    except Exception as e:
        logger.error(f"Failed to index story {request.story_key}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/index/batch")
async def index_all_tests(project_key: str, max_tests: int = 1000):
    """
    Batch index existing tests from Zephyr.
    
    Args:
        project_key: Project key to index tests for
        max_tests: Maximum number of tests to index
        
    Returns:
        Success message with indexing results
    """
    try:
        logger.info(f"API: Batch indexing tests for project {project_key}")
        
        # Fetch existing tests
        zephyr = ZephyrIntegration()
        tests = await zephyr.get_test_cases_for_project(project_key, max_results=max_tests)
        
        # Index tests
        indexer = ContextIndexer()
        await indexer.index_existing_tests(tests, project_key)
        
        return {
            "status": "success",
            "message": f"Successfully indexed {len(tests)} tests",
            "project_key": project_key,
            "tests_indexed": len(tests)
        }
        
    except Exception as e:
        logger.error(f"Failed to batch index tests: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/index/all")
async def index_all(project_key: str, force: bool = False):
    """
    Index ALL available data for a project (full index-all).
    
    This endpoint runs the complete index-all process:
    - Zephyr tests
    - Jira stories
    - Confluence docs
    - External docs
    - GitLab Swagger docs
    
    Args:
        project_key: Project key to index all data for
        force: Force refresh even if recently indexed
        
    Returns:
        Success message with indexing results
    """
    try:
        logger.info(f"API: Running index-all for project {project_key} (force={force})")
        
        # Call the index_all_data function
        results = await index_all_data(
            project_key=project_key,
            force=force
        )
        
        return {
            "status": "success",
            "message": f"Successfully completed index-all for {project_key}",
            "project_key": project_key,
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Failed to run index-all: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/index/stories/all")
async def index_all_stories(project_key: str):
    """
    Batch index ALL Jira stories for a project (with automatic pagination).
    
    Args:
        project_key: Project key to index stories for
        
    Returns:
        Success message with indexing results
    """
    try:
        logger.info(f"API: Batch indexing ALL stories for project {project_key}")
        
        # Import JiraClient
        from src.aggregator.jira_client import JiraClient
        
        # Fetch ALL issues using the pagination method (all types for context)
        jira_client = JiraClient()
        jql = f"project = {project_key} ORDER BY created DESC"
        stories = jira_client.search_all_issues(jql)
        
        logger.info(f"Found {len(stories)} stories to index for {project_key}")
        
        if len(stories) == 0:
            return {
                "status": "success",
                "message": f"No stories found for project {project_key}",
                "project_key": project_key,
                "stories_indexed": 0
            }
        
        # Index stories
        indexer = ContextIndexer()
        await indexer.index_jira_stories(stories, project_key)
        
        return {
            "status": "success",
            "message": f"Successfully indexed ALL {len(stories)} stories",
            "project_key": project_key,
            "stories_indexed": len(stories)
        }
        
    except Exception as e:
        logger.error(f"Failed to batch index all stories: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search")
async def search_rag(request: SearchRequest):
    """
    Search RAG database for similar documents.
    
    Args:
        request: Search request with query and parameters
        
    Returns:
        List of similar documents
    """
    try:
        logger.info(f"API: Searching RAG collection '{request.collection}' with query: {request.query[:100]}")
        
        store = RAGVectorStore()
        
        # Build metadata filter
        metadata_filter = {}
        if request.project_key:
            metadata_filter["project_key"] = request.project_key
        
        # Check if query looks like a Jira key (e.g., "PROJ-12345")
        import re
        jira_key_pattern = r'^[A-Z]+-\d+$'
        exact_match = None
        
        if re.match(jira_key_pattern, request.query.strip(), re.IGNORECASE):
            # Try exact key match first (for jira_issues collection)
            if request.collection == "jira_issues":
                exact_key = request.query.strip().upper()
                try:
                    collection = store.client.get_collection(request.collection)
                    doc_id = f"jira_{exact_key}"
                    
                    exact_results = collection.get(
                        ids=[doc_id],
                        include=['documents', 'metadatas']
                    )
                    if exact_results and exact_results['ids']:
                        # Found exact match!
                        exact_match = {
                            'id': exact_results['ids'][0],
                            'document': exact_results['documents'][0],
                            'metadata': exact_results['metadatas'][0],
                            'distance': 0.0,
                            'similarity': 1.0  # Perfect match
                        }
                        logger.info(f"Found exact match for key: {exact_key}")
                    else:
                        # Also try searching by metadata story_key field
                        logger.info(f"Exact ID lookup failed for {exact_key}, trying metadata search...")
                        # Search with metadata filter for story_key
                        metadata_results = await store.retrieve_similar(
                            collection_name=request.collection,
                            query_text=exact_key,  # Use the key itself as query
                            top_k=50,  # Search more broadly
                            metadata_filter={"story_key": exact_key},  # Filter by story_key metadata
                            min_similarity_override=0.0
                        )
                        if metadata_results:
                            # Found by metadata filter - use first result
                            exact_match = metadata_results[0]
                            exact_match['similarity'] = 1.0  # Mark as perfect match
                            logger.info(f"Found {exact_key} via metadata filter")
                except Exception as e:
                    logger.warning(f"Exact lookup failed for {exact_key}: {e}")
        
        # Search with lower threshold for UI search (allow more results)
        # Use 0.0 threshold for UI searches to show all results, let user filter visually
        results = await store.retrieve_similar(
            collection_name=request.collection,
            query_text=request.query,
            top_k=request.top_k,
            metadata_filter=metadata_filter if metadata_filter else None,
            min_similarity_override=0.0  # No threshold for UI search - show all results
        )
        
        # If we found an exact match, put it first
        if exact_match:
            # Remove exact match from results if it's already there (avoid duplicates)
            results = [r for r in results if r.get('id') != exact_match['id']]
            results.insert(0, exact_match)
        
        # Apply similarity threshold if specified (for UI search)
        if request.min_similarity is not None:
            filtered_results = [r for r in results if r.get("distance", 0) <= (1.0 - request.min_similarity)]
            logger.info(f"Filtered {len(results)} results to {len(filtered_results)} using min_similarity={request.min_similarity}")
            results = filtered_results
        
        return {
            "status": "success",
            "collection": request.collection,
            "results_count": len(results),
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Failed to search RAG: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/clear")
async def clear_rag(collection: Optional[str] = None):
    """
    Clear RAG database (all collections or specific collection).
    
    Args:
        collection: Optional collection name to clear (clears all if not specified)
        
    Returns:
        Success message
    """
    try:
        store = RAGVectorStore()
        
        if collection:
            logger.info(f"API: Clearing RAG collection: {collection}")
            store.clear_collection(collection)
            return {
                "status": "success",
                "message": f"Cleared collection: {collection}"
            }
        else:
            logger.info("API: Clearing all RAG collections")
            store.clear_all_collections()
            return {
                "status": "success",
                "message": "Cleared all RAG collections"
            }
        
    except Exception as e:
        logger.error(f"Failed to clear RAG: {e}")
        raise HTTPException(status_code=500, detail=str(e))

