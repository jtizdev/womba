"""
API routes for story management.
"""

from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel
from typing import Optional

from src.aggregator.jira_client import JiraClient
from src.aggregator.story_collector import StoryCollector
from src.models.story import JiraStory
from src.config.settings import settings

router = APIRouter()


class SearchRequest(BaseModel):
    """Request to search for stories."""
    query: str
    max_results: int = 100
    project_key: Optional[str] = None


@router.get("/{issue_key}", response_model=JiraStory)
async def get_story(issue_key: str):
    """
    Fetch a Jira story by key.

    Args:
        issue_key: Jira issue key (e.g., PROJ-123)

    Returns:
        JiraStory object
    """
    logger.info(f"API: Fetching story {issue_key}")

    try:
        jira_client = JiraClient()
        story = await jira_client.get_issue(issue_key)
        return story
    except Exception as e:
        logger.error(f"Failed to fetch story {issue_key}: {e}")
        # Check if it's a JiraError with 404 status
        status_code = 500
        if hasattr(e, 'status_code') and e.status_code == 404:
            status_code = 404
        elif hasattr(e, 'status') and e.status == 404:
            status_code = 404
        elif "404" in str(e) or "does not exist" in str(e).lower() or "not found" in str(e).lower():
            status_code = 404
        raise HTTPException(status_code=status_code, detail=str(e))


@router.post("/search")
async def search_stories(request: SearchRequest):
    """
    Search for Jira stories by keyword (Stories ONLY, not bugs/tasks).
    Returns results sorted by last_modified DESC (newest first).

    Args:
        request: Search request with query and optional filters

    Returns:
        List of matching stories, sorted by last modified
    """
    logger.info(f"API: Searching for stories with query: {request.query}")

    try:
        from src.ai.rag_store import RAGVectorStore
        store = RAGVectorStore()
        
        import re
        collection = store.client.get_collection("jira_issues")
        
        # Check if query looks like a Jira key (e.g., "PROJ-12345")
        jira_key_pattern = r'^[A-Z]+-\d+$'
        if re.match(jira_key_pattern, request.query.strip(), re.IGNORECASE):
            # Try exact key match first
            exact_key = request.query.strip().upper()
            exact_results = collection.get(
                ids=[f"jira_{exact_key}"],
                include=['documents', 'metadatas']
            )
            if exact_results and exact_results['ids']:
                # Found exact match, use it with perfect similarity
                results = [{
                    'document': exact_results['documents'][0],
                    'metadata': exact_results['metadatas'][0],
                    'distance': 0.0,  # Perfect match
                    'similarity': 1.0  # Perfect similarity for exact matches
                }]
                logger.info(f"Found exact match for key: {exact_key}")
            else:
                # No exact match, fall back to semantic search
                results = await store.retrieve_similar(
                    collection_name="jira_issues",
                    query_text=request.query,
                    top_k=request.max_results * 2
                )
        else:
            # Try multiple query variations to improve semantic search matching
            # Longer queries sometimes don't match well, so try both original and simplified
            
            # Extract project key if query contains something like "PROJ-XXX" pattern
            project_key = None
            import re
            key_match = re.search(r'([A-Z]+)-\d+', request.query, re.IGNORECASE)
            if key_match:
                project_key = key_match.group(1).upper()
            
            # Build query variations that match the document format
            # Documents are: "Story: KEY - Title\n\nDescription: ..."
            # So queries should include story context for better matching
            queries_to_try = [
                request.query,  # Original query
                f"Story: {request.query}",  # With Story prefix (matches document format)
                f"Jira story: {request.query}",  # Alternative prefix
                f"Story about {request.query}",  # More descriptive
                f"Story description: {request.query}",  # With description prefix
            ]
            
            # If query looks like it could be a story title, add variations
            # that would match the document structure better
            if len(request.query.split()) > 3:
                # Try with "this story" or "feature" to match document language
                queries_to_try.extend([
                    f"This story {request.query}",
                    f"Feature: {request.query}",
                    f"Capability: {request.query}",
                ])
            
            # Always try common project keys - they often work when full queries don't
            # This helps catch stories when semantic search fails for long queries
            common_project_keys = ['PLAT', 'PRDT', 'PORCH']
            for key in common_project_keys:
                if key not in queries_to_try:
                    queries_to_try.append(key)
            
            # If we found a project key, also try searching with just the project key
            # This helps when full title doesn't match but project key does
            if project_key and project_key not in queries_to_try:
                queries_to_try.append(project_key)
                queries_to_try.append(f"{project_key} {request.query}")  # Project + query
            
            # If query is long, also try simplified versions (extract key words)
            if len(request.query.split()) > 5:
                # Extract key words - be less aggressive with filtering
                import re
                # Remove special chars and split
                clean_query = re.sub(r'[()\-]', ' ', request.query)
                words = [w.strip() for w in clean_query.split() if len(w.strip()) > 2]
                # Only filter out very common stop words, keep most words
                skip_words = {'the', 'and', 'or', 'by', 'for', 'with', 'from', 'this', 'that'}
                meaningful_words = [w for w in words if w.lower() not in skip_words and not (w.isdigit() and len(w) <= 2)]
                
                if meaningful_words:
                    # Try different combinations - include more variations
                    # Full meaningful words
                    queries_to_try.append(' '.join(meaningful_words))
                    # First 6 words (more context)
                    if len(meaningful_words) > 6:
                        queries_to_try.append(' '.join(meaningful_words[:6]))
                    # Last 6 words (often the most descriptive)
                    if len(meaningful_words) > 6:
                        queries_to_try.append(' '.join(meaningful_words[-6:]))
                    # Middle section (skip codes at start)
                    if len(meaningful_words) > 8:
                        queries_to_try.append(' '.join(meaningful_words[2:8]))
                    
                    # Add keyword expansion - try singular/plural forms and related terms
                    # This helps match documents that use different word forms
                    expanded_queries = []
                    for word in meaningful_words[:5]:  # Expand first 5 words
                        word_lower = word.lower()
                        # Add plural/singular variations
                        if word_lower.endswith('s') and len(word_lower) > 3:
                            expanded_queries.append(word_lower[:-1])  # Remove 's'
                        elif not word_lower.endswith('s'):
                            expanded_queries.append(word_lower + 's')  # Add 's'
                        expanded_queries.append(word_lower)
                    
                    if expanded_queries:
                        # Try query with expanded terms
                        queries_to_try.append(' '.join(expanded_queries[:8]))
            
            # Search with all query variations and combine results
            # Use dict to track best similarity per key
            results_by_key = {}
            
            logger.info(f"Trying {len(queries_to_try)} query variations: {queries_to_try[:3]}...")
            
            for query_variant in queries_to_try:
                # Use reasonable top_k - balance between coverage and performance
                # For short queries like "PLAT", use higher top_k since they work well
                # For long queries, also search broadly to find matches
                if len(query_variant.split()) <= 2:
                    # Short queries (like "PLAT") - search very broadly
                    top_k = 1500
                else:
                    # Long queries - also search broadly to ensure we find relevant matches
                    top_k = 1000
                
                variant_results = await store.retrieve_similar(
                    collection_name="jira_issues",
                    query_text=query_variant,
                    top_k=top_k,
                    min_similarity_override=0.0  # No threshold - get all results, we'll filter by Story type
                )
                logger.debug(f"Query variant '{query_variant[:50]}...' returned {len(variant_results)} results")
                # Deduplicate by keeping the result with HIGHEST similarity per key
                for result in variant_results:
                    key = result.get('metadata', {}).get('story_key', '')
                    if key:
                        similarity = result.get('similarity', 0.0)
                        # Keep result with highest similarity
                        if key not in results_by_key or similarity > results_by_key[key].get('similarity', 0.0):
                            results_by_key[key] = result
                            # Log if we found the story
                            if '13541' in key:
                                logger.info(f"✅ Found story with query variant: '{query_variant[:50]}...' (similarity={similarity:.4f})")
            
            # Convert dict to list
            all_results = list(results_by_key.values())
            
            logger.info(f"Combined {len(all_results)} unique results from {len(queries_to_try)} query variations")
            
            # Sort by similarity (best matches first)
            all_results.sort(key=lambda x: x.get('similarity', 0), reverse=True)
            
            # Check if the story is in the results
            plat13541_found = any('13541' in r.get('metadata', {}).get('story_key', '') for r in all_results)
            if plat13541_found:
                for r in all_results:
                    if '13541' in r.get('metadata', {}).get('story_key', ''):
                        logger.info(f"Story found at position {all_results.index(r)+1} with similarity {r.get('similarity', 0):.4f}")
                        break
            
            results = all_results[:request.max_results * 2]
        
        # Filter for Story issue type only and sort by last_modified DESC
        story_results = []
        for result in results:
            metadata = result.get("metadata", {})
            issue_type = metadata.get("issue_type", "").strip()
            
            # Only include Stories (case-insensitive)
            if issue_type.lower() == "story":
                # Get the updated date - use last_modified, fallback to timestamp, then created
                updated_date = (
                    metadata.get("last_modified") or 
                    metadata.get("timestamp") or 
                    metadata.get("created") or 
                    ""
                )
                
                # Extract description from the RAG document
                # Format is "Story: PROJ-XXX - Title\n\nDescription..."
                full_document = result.get("document", "")
                description = "No description available"
                if full_document:
                    # Split by double newline to separate title from description
                    parts = full_document.split("\n\n", 1)
                    if len(parts) > 1 and parts[1].strip():
                        full_description = parts[1].strip()
                        # Truncate for UI display (150 chars for preview)
                        description = full_description[:150] + ("..." if len(full_description) > 150 else "")
                
                # Get similarity score for sorting
                similarity = result.get('similarity', 0.0)
                
                story_results.append({
                    "key": metadata.get("story_key", ""),
                    "title": metadata.get("summary", "No title"),
                    "summary": metadata.get("summary", "No title"),
                    "description": description,  # Truncated for UI
                    "url": f"{settings.atlassian_base_url}/browse/{metadata.get('story_key', '')}",
                    "created": metadata.get("timestamp", ""),
                    "updated": updated_date,
                    "status": metadata.get("status", "Unknown"),
                    "_similarity": similarity,  # Internal field for sorting
                })
        
        # Sort by semantic similarity FIRST (most relevant), then by updated date (newest first)
        # Parse dates for proper sorting
        from datetime import datetime
        def parse_date(date_str):
            if not date_str:
                return datetime.min
            try:
                # Handle ISO format dates with timezone
                return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            except:
                return datetime.min
        
        # Primary sort: similarity (descending - highest first)
        # Secondary sort: updated date (descending - newest first)
        story_results.sort(
            key=lambda x: (
                -x.get("_similarity", 0.0),  # Negative for descending (higher similarity first)
                -parse_date(x.get("updated", "")).timestamp()  # Negative for descending (newer first)
            )
        )
        
        # Remove internal sorting field before returning
        for story in story_results:
            story.pop("_similarity", None)
        
        # Limit to max_results after filtering
        story_results = story_results[:request.max_results]
        
        logger.info(f"Found {len(story_results)} stories (filtered from {len(results)} total results)")
        
        return {
            "status": "success",
            "query": request.query,
            "results_count": len(story_results),
            "results": story_results
        }
    except Exception as e:
        logger.error(f"Failed to search stories: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{issue_key}/context")
async def get_story_context(issue_key: str):
    """
    Fetch comprehensive context for a story including linked issues and related items.

    Args:
        issue_key: Jira issue key (e.g., PROJ-123)

    Returns:
        Complete story context
    """
    logger.info(f"API: Fetching context for story {issue_key}")

    try:
        collector = StoryCollector()
        context = await collector.collect_story_context(issue_key)
        return {
            "main_story": context.main_story.model_dump(),
            "linked_stories": [s.model_dump() for s in context.get("linked_stories", [])],
            "related_bugs": [b.model_dump() for b in context.get("related_bugs", [])],
            "context_graph": context.get("context_graph", {}),
        }
    except Exception as e:
        logger.error(f"Failed to fetch context for {issue_key}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

