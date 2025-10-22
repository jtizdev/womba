"""
RAG CLI command handlers.
Separate module to keep CLI clean and maintainable.
"""

import asyncio
from typing import Optional
from loguru import logger

from src.ai.context_indexer import ContextIndexer
from src.ai.rag_store import RAGVectorStore
from src.integrations.zephyr_integration import ZephyrIntegration
from src.aggregator.jira_client import JiraClient
from src.aggregator.confluence_client import ConfluenceClient
from src.aggregator.story_collector import StoryCollector
from src.models.story import JiraStory


async def fetch_and_index_zephyr_tests(
    project_key: str,
    indexer: ContextIndexer
) -> int:
    """
    Fetch and index all Zephyr tests for a project.
    
    Returns:
        Number of tests indexed
    """
    print("📥 [1/3] Fetching existing tests from Zephyr...")
    
    zephyr = ZephyrIntegration()
    tests = await zephyr.get_test_cases_for_project(project_key, max_results=None)
    print(f"Found {len(tests)} existing tests")
    
    if tests:
        print("📊 Indexing existing tests...")
        await indexer.index_existing_tests(tests, project_key)
        print("✅ Indexed existing tests")
        return len(tests)
    else:
        print("⚠️  No tests found to index")
        return 0


async def fetch_and_index_jira_stories(
    project_key: str,
    indexer: ContextIndexer
) -> int:
    """
    Fetch and index all Jira stories for a project.
    
    Returns:
        Number of stories indexed
    """
    print("\n📥 [2/3] Fetching Jira stories from project...")
    
    try:
        jira_client = JiraClient()
        all_stories = []
        start_at = 0
        max_results = 100
        
        while True:
            jql = f"project = {project_key} AND type in (Story, Task, Bug) ORDER BY created DESC"
            result = await jira_client.search_issues(jql, max_results=max_results, start_at=start_at)
            
            # Result is now a List[JiraStory] from the async method
            if not result:
                break
            
            # Add stories to list
            all_stories.extend(result)
            
            # Check if there are more results
            if len(result) < max_results:
                break
            
            start_at += max_results
            print(f"  Fetched {len(all_stories)} stories so far...")
        
        print(f"Found {len(all_stories)} Jira stories")
        
        if all_stories:
            print("📊 Indexing Jira stories...")
            await indexer.index_jira_stories(all_stories, project_key)
            print("✅ Indexed Jira stories")
            return len(all_stories)
        else:
            print("⚠️  No Jira stories found to index")
            return 0
            
    except Exception as e:
        print(f"⚠️  Failed to index Jira stories: {e}")
        logger.error(f"Jira story indexing failed: {e}")
        return 0


async def fetch_and_index_confluence_docs(
    project_key: str,
    indexer: ContextIndexer
) -> int:
    """
    Fetch and index all Confluence docs for a project space.
    Uses proper CQL and pagination.
    
    Returns:
        Number of docs indexed
    """
    print("\n📥 [3/3] Fetching Confluence docs from project spaces...")
    
    try:
        confluence = ConfluenceClient()
        all_docs = []
        
        # Try multiple space patterns (project key and common variations)
        space_patterns = [
            project_key,  # Exact match (e.g., PLAT)
            f"{project_key}*",  # Wildcard (e.g., PLAT*)
        ]
        
        # Also try common documentation spaces
        common_spaces = ["PROD", "TECH", "ENG", "DOC"]
        
        # Build CQL query for project-related spaces
        spaces_to_search = [project_key] + common_spaces
        cql = f"type=page AND space IN ({','.join(spaces_to_search)}) ORDER BY lastModified DESC"
        
        print(f"Searching spaces: {', '.join(spaces_to_search)}")
        
        try:
            start = 0
            limit = 100
            total_fetched = 0
            
            while True:
                # Use the enhanced search_pages with pagination
                result = await confluence.search_pages(cql, limit=limit, start=start)
                
                # Result should be a list of pages
                if not result:
                    break
                
                pages = result if isinstance(result, list) else result.get('results', [])
                if not pages:
                    break
                
                for page in pages:
                    doc = {
                        'id': page.get('id', ''),
                        'title': page.get('title', ''),
                        'content': page.get('body', {}).get('storage', {}).get('value', ''),
                        'space': page.get('space', {}).get('key', '') if isinstance(page.get('space'), dict) else str(page.get('space', '')),
                        'url': page.get('_links', {}).get('webui', '')
                    }
                    all_docs.append(doc)
                
                total_fetched += len(pages)
                
                # Check if there are more results
                if len(pages) < limit:
                    break
                
                start += limit
                print(f"  Fetched {total_fetched} Confluence pages so far...")
            
            print(f"Found {len(all_docs)} Confluence docs")
            
            if all_docs:
                print("📊 Indexing Confluence docs...")
                await indexer.index_confluence_docs(all_docs, project_key)
                print("✅ Indexed Confluence docs")
                return len(all_docs)
            else:
                print(f"⚠️  No Confluence docs found in spaces: {', '.join(spaces_to_search)}")
                print("💡 Confluence docs will be indexed per-story when you run 'womba index STORY-KEY'")
                return 0
                
        except Exception as e:
            print(f"⚠️  Could not search Confluence spaces: {e}")
            logger.error(f"Confluence search error: {e}")
            print("💡 Confluence docs will be indexed per-story when you run 'womba index STORY-KEY'")
            return 0
            
    except Exception as e:
        print(f"⚠️  Failed to index Confluence docs: {e}")
        logger.error(f"Confluence indexing failed: {e}")
        return 0


async def index_all_data(project_key: str) -> dict:
    """
    Index all available data for a project.
    
    Args:
        project_key: Jira project key
        
    Returns:
        Dictionary with counts of indexed items
    """
    print(f"\n🔄 Starting comprehensive indexing for project {project_key}...")
    print("This will index:")
    print("  1. All existing Zephyr tests")
    print("  2. All Jira stories from the project")
    print("  3. All Confluence docs from project space")
    print("\n⏳ This may take 5-15 minutes for large projects...\n")
    
    indexer = ContextIndexer()
    
    # Index all three types
    tests_count = await fetch_and_index_zephyr_tests(project_key, indexer)
    stories_count = await fetch_and_index_jira_stories(project_key, indexer)
    docs_count = await fetch_and_index_confluence_docs(project_key, indexer)
    
    return {
        'tests': tests_count,
        'stories': stories_count,
        'docs': docs_count,
        'total': tests_count + stories_count + docs_count
    }


async def index_story_context(story_key: str) -> None:
    """
    Index context for a specific story.
    
    Args:
        story_key: Jira story key
    """
    print(f"\n📊 Indexing context for story {story_key}...")
    
    # Collect story context
    collector = StoryCollector()
    context = await collector.collect_story_context(story_key)
    
    # Index the context
    indexer = ContextIndexer()
    project_key = story_key.split('-')[0]
    await indexer.index_story_context(context, project_key)
    
    print(f"✅ Successfully indexed {story_key}")
    print("💡 This story's context is now available for RAG retrieval")


def show_rag_stats() -> None:
    """Display RAG database statistics."""
    store = RAGVectorStore()
    stats = store.get_all_stats()
    
    print("\n" + "=" * 60)
    print("📊 RAG Database Statistics")
    print("=" * 60)
    print(f"\n📁 Storage Path: {stats['storage_path']}")
    print(f"📈 Total Documents: {stats['total_documents']}")
    print("\nCollections:")
    for collection_name in ['test_plans', 'confluence_docs', 'jira_stories', 'existing_tests']:
        collection_stats = stats.get(collection_name, {})
        count = collection_stats.get('count', 0)
        status = "✓" if collection_stats.get('exists') else "✗"
        print(f"  {status} {collection_name}: {count} documents")
    print("=" * 60 + "\n")


def clear_rag_database(confirm: bool = False) -> None:
    """
    Clear RAG database.
    
    Args:
        confirm: If True, skip confirmation prompt
    """
    print("\n⚠️  WARNING: This will delete all RAG data!")
    if not confirm:
        response = input("Are you sure? (yes/no): ").strip().lower()
        if response != 'yes':
            print("❌ Cancelled")
            return
    
    store = RAGVectorStore()
    store.clear_all_collections()
    print("✅ RAG database cleared")

