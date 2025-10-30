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
from src.config.settings import settings


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
    should_index_plainid = (
        settings.plainid_doc_index_enabled and 
        (settings.plainid_doc_base_url or settings.plainid_doc_urls)
    )
    if should_index_plainid:
        print("  4. PlainID platform documentation (API reference)")
    print("\n⏳ This may take 5-15 minutes for large projects...\n")
    
    indexer = ContextIndexer()
    
    # Index all three types
    tests_count = await fetch_and_index_zephyr_tests(project_key, indexer)
    stories_count = await fetch_and_index_jira_stories(project_key, indexer)
    docs_count = await fetch_and_index_confluence_docs(project_key, indexer)
    external_count = 0
    if should_index_plainid:
        print("\n📥 [4/4] Fetching PlainID documentation...")
        external_count = await indexer.index_external_docs()
        if external_count:
            print(f"✅ Indexed {external_count} PlainID documentation pages")
        else:
            print("⚠️  No PlainID documentation indexed (check base_url/config)")
    
    return {
        'tests': tests_count,
        'stories': stories_count,
        'docs': docs_count,
        'external_docs': external_count,
        'total': tests_count + stories_count + docs_count + external_count
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
    for collection_name in ['test_plans', 'confluence_docs', 'jira_stories', 'existing_tests', 'external_docs']:
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


def view_rag_documents(
    collection: str,
    limit: Optional[int] = 10,
    project_key: Optional[str] = None,
    show_full: bool = False
) -> None:
    """
    View documents from a RAG collection.
    
    Args:
        collection: Collection name (test_plans, confluence_docs, jira_stories, existing_tests)
        limit: Number of documents to show (default: 10)
        project_key: Optional project key filter
        show_full: If True, show full document content (default: first 500 chars)
    """
    store = RAGVectorStore()
    
    # Validate collection name
    valid_collections = [
        store.TEST_PLANS_COLLECTION,
        store.CONFLUENCE_DOCS_COLLECTION,
        store.JIRA_STORIES_COLLECTION,
        store.EXISTING_TESTS_COLLECTION,
        store.EXTERNAL_DOCS_COLLECTION,
    ]
    
    if collection not in valid_collections:
        print(f"❌ Invalid collection: {collection}")
        print(f"Valid options: {', '.join(valid_collections)}")
        return
    
    # Build metadata filter
    metadata_filter = None
    if project_key:
        metadata_filter = {"project_key": project_key}
    
    # Get documents
    print(f"\n🔍 Fetching documents from '{collection}'...")
    if project_key:
        print(f"   Filter: project_key = {project_key}")
    if limit:
        print(f"   Limit: {limit}")
    
    documents = store.get_all_documents(
        collection_name=collection,
        limit=limit,
        metadata_filter=metadata_filter
    )
    
    if not documents:
        print(f"\n⚠️  No documents found in '{collection}'")
        return
    
    print(f"\n📄 Found {len(documents)} document(s):\n")
    print("=" * 80)
    
    for i, doc in enumerate(documents, 1):
        # Display metadata
        metadata = doc.get('metadata', {})
        
        if collection == store.TEST_PLANS_COLLECTION:
            print(f"\n[{i}] Test Plan:")
            print(f"    Story: {metadata.get('story_key', 'N/A')}")
            print(f"    Summary: {metadata.get('summary', 'N/A')[:100]}")
            print(f"    Test Cases: {metadata.get('test_count', 'N/A')}")
            
        elif collection == store.CONFLUENCE_DOCS_COLLECTION:
            print(f"\n[{i}] Confluence Document:")
            print(f"    Title: {metadata.get('title', 'N/A')}")
            print(f"    Space: {metadata.get('space', 'N/A')}")
            if metadata.get('url'):
                print(f"    URL: {metadata.get('url', 'N/A')}")
                
        elif collection == store.JIRA_STORIES_COLLECTION:
            story_key = metadata.get('story_key', 'N/A')
            print(f"\n[{i}] Jira Story:")
            print(f"    Key: {story_key}")
            print(f"    Summary: {metadata.get('summary', 'N/A')[:100]}")
            print(f"    Type: {metadata.get('issue_type', 'N/A')}")
            print(f"    Status: {metadata.get('status', 'N/A')}")
            
        elif collection == store.EXISTING_TESTS_COLLECTION:
            print(f"\n[{i}] Existing Test:")
            print(f"    Key: {metadata.get('test_key', 'N/A')}")
            print(f"    Name: {metadata.get('test_name', 'N/A')}")
            print(f"    Status: {metadata.get('status', 'N/A')}")
            print(f"    Priority: {metadata.get('priority', 'N/A')}")
        elif collection == store.EXTERNAL_DOCS_COLLECTION:
            print(f"\n[{i}] External Doc:")
            print(f"    Title: {metadata.get('title', 'N/A')}")
            print(f"    Source: {metadata.get('source', 'N/A')}")
            if metadata.get('source_url'):
                print(f"    URL: {metadata.get('source_url')}")
        
        # Display document content
        doc_text = doc.get('document', '')
        
        if show_full:
            print(f"\n    Content (FULL):")
            print("    " + "-" * 76)
            # Show full content with proper indentation
            for line in doc_text.split('\n'):
                print(f"    {line}")
        else:
            # Show preview
            preview = doc_text[:500] if len(doc_text) > 500 else doc_text
            print(f"\n    Content Preview (first 500 chars):")
            print("    " + "-" * 76)
            print(f"    {preview}")
            if len(doc_text) > 500:
                print(f"    ... [{len(doc_text) - 500} more characters - use --full to see all]")
        
        print("    " + "-" * 76)
    
    print("\n" + "=" * 80)
    print(f"\n💡 To see full content, use --full flag")
    print(f"💡 To filter by project, use --project-key PROJECT_KEY")
    print(f"💡 To see more documents, use --limit N")

