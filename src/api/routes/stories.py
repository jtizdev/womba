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
        
        # Search the jira_issues collection for story-type issues
        results = await store.retrieve_similar(
            collection_name="jira_issues",
            query_text=request.query,
            top_k=request.max_results * 2  # Get more to filter for stories
        )
        
        # Filter for Story issue type only and sort by last_modified DESC
        story_results = []
        for result in results:
            metadata = result.get("metadata", {})
            issue_type = metadata.get("issue_type", "").strip().lower()
            
            # Only include Stories (accept "story", "stories", etc)
            if "story" in issue_type or issue_type == "story":
                # Get the updated date - use last_modified, fallback to timestamp
                updated_date = metadata.get("last_modified") or metadata.get("timestamp") or ""
                
                story_results.append({
                    "key": metadata.get("story_key", ""),
                    "title": metadata.get("summary", "No title"),
                    "summary": metadata.get("summary", "No title"),
                    "description": result.get("document", "No description available"),
                    "url": f"https://plainid.atlassian.net/browse/{metadata.get('story_key', '')}",
                    "created": metadata.get("timestamp", ""),
                    "updated": updated_date,
                    "status": metadata.get("status", "Unknown"),
                })
        
        # Sort by last_modified DESC (newest first)
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
        
        story_results.sort(
            key=lambda x: parse_date(x.get("updated", "")),
            reverse=True
        )
        
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

