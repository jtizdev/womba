"""
API routes for story management.
"""

from fastapi import APIRouter, HTTPException
from loguru import logger

from src.aggregator.jira_client import JiraClient
from src.aggregator.story_collector import StoryCollector
from src.models.story import JiraStory

router = APIRouter()


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

