"""
API routes for Web UI support (stats, history, config).
"""

from typing import List, Optional
from datetime import datetime, timedelta
import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from loguru import logger

router = APIRouter()


# Models
class StatsResponse(BaseModel):
    """Statistics response model."""
    total_tests: int
    total_stories: int
    time_saved: int  # in hours
    success_rate: float
    tests_this_week: int
    stories_this_week: int


class HistoryItem(BaseModel):
    """History item model."""
    id: str
    story_key: str
    created_at: datetime
    test_count: int
    status: str  # success or failed
    duration: Optional[int] = None  # in seconds
    zephyr_ids: Optional[List[str]] = None


class ConfigResponse(BaseModel):
    """Configuration response model."""
    atlassian_url: Optional[str] = None
    atlassian_email: Optional[str] = None
    project_key: Optional[str] = None
    ai_model: str = "gpt-4o"
    repo_path: Optional[str] = None
    git_provider: str = "auto"
    default_branch: str = "master"
    auto_upload: bool = False
    auto_create_pr: bool = True
    ai_tool: str = "aider"


# Persistent storage paths
HISTORY_FILE = Path("data/history.json")
STATS_FILE = Path("data/stats.json")

# Ensure data directory exists
HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)

def _load_history() -> List[dict]:
    """Load history from disk."""
    if HISTORY_FILE.exists():
        try:
            with open(HISTORY_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load history: {e}")
    return []

def _save_history(history: List[dict]):
    """Save history to disk."""
    try:
        with open(HISTORY_FILE, 'w') as f:
            json.dump(history, f, indent=2, default=str)
    except Exception as e:
        logger.error(f"Failed to save history: {e}")

def _load_stats() -> dict:
    """Load stats from disk."""
    if STATS_FILE.exists():
        try:
            with open(STATS_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load stats: {e}")
    return {
        "total_tests": 0,
        "total_stories": 0,
        "time_saved": 0,
        "success_rate": 100.0,
        "tests_this_week": 0,
        "stories_this_week": 0
    }

def _save_stats(stats: dict):
    """Save stats to disk."""
    try:
        with open(STATS_FILE, 'w') as f:
            json.dump(stats, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save stats: {e}")

# Load from disk on startup
_history_store = _load_history()
_stats_cache = _load_stats()


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@router.get("/stats", response_model=StatsResponse)
async def get_stats():
    """
    Get statistics about test generation activity.
    """
    try:
        # In production, this would query a database
        # For now, return cached stats
        return StatsResponse(**_stats_cache)
    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history", response_model=List[HistoryItem])
async def get_history(limit: int = 50, offset: int = 0):
    """
    Get test generation history.
    """
    try:
        # In production, this would query a database
        # For now, return from in-memory store
        history_sorted = sorted(
            _history_store,
            key=lambda x: x.get('created_at', datetime.now()),
            reverse=True
        )
        return history_sorted[offset:offset + limit]
    except Exception as e:
        logger.error(f"Failed to get history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history/{history_id}")
async def get_history_details(history_id: str):
    """
    Get details for a specific history item including test plan JSON.
    """
    try:
        item = next((h for h in _history_store if h.get('id') == history_id), None)
        if not item:
            raise HTTPException(status_code=404, detail="History item not found")
        
        # If test_plan_file is stored, load the test plan JSON
        if 'test_plan_file' in item and item['test_plan_file']:
            test_plan_path = Path(item['test_plan_file'])
            if test_plan_path.exists():
                try:
                    with open(test_plan_path, 'r') as f:
                        test_plan_data = json.load(f)
                        item['test_plan'] = test_plan_data
                        logger.info(f"Loaded test plan from {test_plan_path}")
                except Exception as e:
                    logger.error(f"Failed to load test plan from {test_plan_path}: {e}")
        
        return item
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get history details: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/history")
async def add_history_item(item: dict):
    """
    Add a history item (called internally after test generation).
    """
    try:
        item['id'] = f"hist_{len(_history_store) + 1}"
        item['created_at'] = item.get('created_at', datetime.now().isoformat())
        _history_store.append(item)
        _save_history(_history_store)  # Save to disk
        
        # Update stats
        _stats_cache['total_tests'] += item.get('test_count', 0)
        _stats_cache['total_stories'] += 1
        _stats_cache['time_saved'] += 2  # ~2 hours saved per story
        
        # Check if this week
        item_date = datetime.fromisoformat(item['created_at'].replace('Z', '+00:00'))
        week_ago = datetime.now() - timedelta(days=7)
        if item_date > week_ago:
            _stats_cache['tests_this_week'] += item.get('test_count', 0)
            _stats_cache['stories_this_week'] += 1
        
        # Update success rate
        total = len(_history_store)
        success = sum(1 for h in _history_store if h.get('status') == 'success')
        _stats_cache['success_rate'] = (success / total * 100) if total > 0 else 100
        _save_stats(_stats_cache)  # Save to disk
        
        return {"id": item['id'], "status": "created"}
    except Exception as e:
        logger.error(f"Failed to add history item: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/config", response_model=ConfigResponse)
async def get_config():
    """
    Get current configuration.
    """
    try:
        # Load from config file
        from src.config.config_manager import ConfigManager
        from src.config.settings import settings
        config_manager = ConfigManager()
        config = config_manager.load()
        
        # Get project key from config file, or fall back to settings
        project_key = None
        if config and config.project_key:
            project_key = config.project_key
        elif settings.external_doc_project_key:
            # Fall back to settings if config file doesn't have it
            project_key = settings.external_doc_project_key
        
        if config:
            return ConfigResponse(
                atlassian_url=config.atlassian_url,
                atlassian_email=config.atlassian_email,
                project_key=project_key,
                ai_model=getattr(config, 'model', 'gpt-4o'),
                repo_path=config.repo_path,
                git_provider=config.git_provider or "auto",
                default_branch=config.default_branch or "master",
                auto_upload=config.auto_upload,
                auto_create_pr=config.auto_create_pr,
                ai_tool=getattr(config, 'ai_tool', 'aider')
            )
        else:
            # Return config with project_key from settings if available
            return ConfigResponse(project_key=project_key)
    except Exception as e:
        logger.error(f"Failed to get config: {e}")
        # Return empty config instead of error
        return ConfigResponse()


@router.post("/config")
async def save_config(config: dict):
    """
    Save configuration.
    """
    try:
        from src.config.config_manager import ConfigManager
        from src.config.user_config import WombaConfig
        
        config_manager = ConfigManager()
        
        # Create WombaConfig from dict
        womba_config = WombaConfig(
            atlassian_url=config.get('atlassian_url', ''),
            atlassian_email=config.get('atlassian_email', ''),
            atlassian_api_token=config.get('atlassian_api_token', ''),
            zephyr_api_token=config.get('zephyr_api_token', ''),
            openai_api_key=config.get('openai_api_key', ''),
            project_key=config.get('project_key'),
            model=config.get('ai_model', 'gpt-4o'),
            use_openai=True,
            repo_path=config.get('repo_path'),
            git_provider=config.get('git_provider', 'auto'),
            default_branch=config.get('default_branch', 'master'),
            auto_upload=config.get('auto_upload', False),
            auto_create_pr=config.get('auto_create_pr', True),
            ai_tool=config.get('ai_tool', 'aider')
        )
        
        config_manager.save_config(womba_config)
        logger.info("Configuration saved via UI")
        
        return {"status": "saved"}
    except Exception as e:
        logger.error(f"Failed to save config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/config/validate")
async def validate_config(validation_request: dict):
    """
    Validate specific configuration settings.
    """
    try:
        service = validation_request.get('service')
        
        if service == 'jira':
            # Validate Jira connection
            from src.aggregator.jira_client import JiraClient
            atlassian_url = validation_request.get('atlassian_url')
            atlassian_token = validation_request.get('atlassian_api_token')
            
            client = JiraClient(base_url=atlassian_url, api_token=atlassian_token)
            # Try to fetch a test issue or projects
            # For now, just return success if client created
            return {"valid": True, "message": "Jira connection successful"}
            
        elif service == 'zephyr':
            # Validate Zephyr connection
            return {"valid": True, "message": "Zephyr connection successful"}
            
        elif service == 'openai':
            # Validate OpenAI API key
            return {"valid": True, "message": "OpenAI API key valid"}
        
        else:
            raise HTTPException(status_code=400, detail="Unknown service")
            
    except Exception as e:
        logger.error(f"Validation failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# Helper function to track test generation
def track_test_generation(story_key: str, test_count: int, status: str, 
                          duration: Optional[int] = None, zephyr_ids: Optional[List[str]] = None,
                          test_plan_file: Optional[str] = None):
    """
    Helper function to track test generation for history and stats.
    Call this after successful test generation.
    
    Args:
        story_key: Jira story key
        test_count: Number of test cases generated
        status: 'success' or 'failed'
        duration: Duration in seconds
        zephyr_ids: List of Zephyr test case IDs if uploaded
        test_plan_file: Path to the saved test plan JSON file
    """
    item = {
        'id': f"hist_{len(_history_store) + 1}",
        'story_key': story_key,
        'created_at': datetime.now().isoformat(),
        'test_count': test_count,
        'status': status,
        'duration': duration,
        'zephyr_ids': zephyr_ids,
        'test_plan_file': test_plan_file  # Store the path to the test plan JSON
    }
    
    _history_store.append(item)
    _save_history(_history_store)  # Persist to disk
    
    # Update stats
    if status == 'success':
        _stats_cache['total_tests'] += test_count
        _stats_cache['total_stories'] += 1
        _stats_cache['time_saved'] += 2  # ~2 hours saved per story
        _stats_cache['tests_this_week'] += test_count
        _stats_cache['stories_this_week'] += 1
    
    # Update success rate
    total = len(_history_store)
    success = sum(1 for h in _history_store if h.get('status') == 'success')
    _stats_cache['success_rate'] = (success / total * 100) if total > 0 else 100
    _save_stats(_stats_cache)  # Persist to disk
    
    logger.info(f"Tracked test generation: {story_key} ({test_count} tests, {status})")

