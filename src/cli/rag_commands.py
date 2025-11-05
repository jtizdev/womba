"""
RAG CLI command handlers.
Separate module to keep CLI clean and maintainable.
"""

from datetime import datetime
import asyncio
from typing import Optional, List
from loguru import logger

from src.ai.context_indexer import ContextIndexer
from src.ai.rag_store import RAGVectorStore
from src.integrations.zephyr_integration import ZephyrIntegration
from src.aggregator.jira_client import JiraClient
from src.aggregator.confluence_client import ConfluenceClient
from src.aggregator.story_collector import StoryCollector
from src.models.story import JiraStory
from src.cli.rag_refresh import RAGRefreshManager


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
    Uses batch indexing to handle large numbers of stories efficiently.
    
    Returns:
        Number of stories indexed
    """
    print("\n📥 [2/3] Fetching Jira stories from project...")
    
    try:
        jira_client = JiraClient()
        jql = f"project = {project_key} AND type in (Story, Task, Bug) ORDER BY created DESC"
        
        # Use the new search_all_issues method - handles pagination internally
        all_stories = jira_client.search_all_issues(jql)
        
        print(f"Found {len(all_stories)} Jira issues")
        
        if all_stories:
            print(f"📊 Indexing {len(all_stories)} Jira stories in batches of 500...")
            
            # Index in batches to prevent memory issues
            batch_size = 500
            total_indexed = 0
            
            for i in range(0, len(all_stories), batch_size):
                batch = all_stories[i:i + batch_size]
                batch_num = (i // batch_size) + 1
                total_batches = (len(all_stories) + batch_size - 1) // batch_size
                
                print(f"  Indexing batch {batch_num}/{total_batches} ({len(batch)} stories)...")
                await indexer.index_jira_stories(batch, project_key)
                total_indexed += len(batch)
                print(f"  ✅ Batch {batch_num}/{total_batches} indexed ({total_indexed}/{len(all_stories)} total)")
            
            print(f"✅ Successfully indexed all {total_indexed} Jira stories")
            return total_indexed
        else:
            print("⚠️  No Jira stories found to index")
            return 0
            
    except Exception as e:
        print(f"⚠️  Failed to index Jira stories: {e}")
        logger.error(f"Jira story indexing failed: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return 0


async def fetch_and_index_confluence_docs(
    project_key: str,
    indexer: ContextIndexer
) -> int:
    """
    Fetch ALL Confluence pages using the client's built-in search_all_pages.
    
    Returns:
        Number of docs indexed
    """
    print("\n📥 [3/3] Fetching ALL Confluence pages...")
    
    try:
        confluence = ConfluenceClient()
        cql = 'type=page ORDER BY lastModified DESC'
        
        # Use search_all_pages - it handles pagination internally
        pages = await confluence.search_all_pages(cql, limit=250)
        
        # Convert to doc format
        all_docs = []
        for page in pages:
            space_key = page.get('space', {}).get('key', '') if isinstance(page.get('space'), dict) else str(page.get('space', ''))
            version_info = page.get('version', {})
            last_modified = version_info.get('when') if version_info else None
            
            doc = {
                'id': page.get('id', ''),
                'title': page.get('title', ''),
                'content': page.get('body', {}).get('storage', {}).get('value', ''),
                'space': space_key,
                'url': page.get('_links', {}).get('webui', ''),
                'last_modified': last_modified
            }
            all_docs.append(doc)
        
        # Report
        spaces_found = set(doc.get('space', '') for doc in all_docs if doc.get('space'))
        print(f"\n📊 FINAL COUNT: {len(all_docs)} Confluence pages")
        if spaces_found:
            print(f"   Spaces: {', '.join(sorted(spaces_found))}")
        
        if all_docs:
            print("📊 Indexing Confluence docs...")
            await indexer.index_confluence_docs(all_docs, project_key)
            print("✅ Indexed Confluence docs")
            return len(all_docs)
        else:
            print("⚠️  No Confluence pages found")
            return 0
            
    except Exception as e:
        print(f"⚠️  Failed to index Confluence docs: {e}")
        logger.error(f"Confluence indexing failed: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return 0


async def index_all_data(
    project_key: str,
    *,
    refresh_manager: Optional[RAGRefreshManager] = None,
    refresh_hours: Optional[float] = None,
    force: bool = False
) -> dict:
    """
    Index all available data for a project with comprehensive logging.
    
    Args:
        project_key: Jira project key
        
    Returns:
        Dictionary with counts of indexed items
    """
    import time
    
    start_time = datetime.now()
    start_datetime = start_time.strftime("%Y-%m-%d %H:%M:%S")
    
    print("\n" + "=" * 70)
    print(f"🚀 STARTING INDEX-ALL FOR PROJECT: {project_key}")
    print(f"⏰ Start Time: {start_datetime}")
    print("=" * 70)
    print("\nThis will index:")
    print("  1. All existing Zephyr tests")
    print("  2. All Jira stories from the project (Stories, Tasks, Bugs)")
    print("  3. All Confluence docs from project spaces")
    print("  4. PlainID developer portal documentation")
    print("  5. GitLab Swagger/OpenAPI documentation")
    print("\n⏳ Estimated time: 5-15 minutes for large projects...")
    print("=" * 70 + "\n")
    
    indexer = ContextIndexer()
    manager = refresh_manager or RAGRefreshManager()
    
    # Track results
    results = {
        'tests': 0,
        'stories': 0,
        'docs': 0,
        'external_docs': 0,
        'swagger_docs': 0
    }
    
    # Phase 1: Zephyr Tests
    print("\n📋 [1/4] PHASE 1: Fetching and indexing Zephyr tests...")
    phase_start = time.time()
    try:
        results['tests'] = await fetch_and_index_zephyr_tests(project_key, indexer)
        phase_duration = time.time() - phase_start
        print(f"✅ Phase 1 complete in {phase_duration:.1f}s: {results['tests']} tests indexed\n")
    except Exception as e:
        logger.error(f"Phase 1 failed: {e}")
        print(f"❌ Phase 1 failed: {e}\n")
    
    # Phase 2: Jira Stories
    print("\n📝 [2/4] PHASE 2: Fetching and indexing Jira stories...")
    phase_start = time.time()
    try:
        results['stories'] = await fetch_and_index_jira_stories(project_key, indexer)
        phase_duration = time.time() - phase_start
        print(f"✅ Phase 2 complete in {phase_duration:.1f}s: {results['stories']} stories indexed\n")
    except Exception as e:
        logger.error(f"Phase 2 failed: {e}")
        print(f"❌ Phase 2 failed: {e}\n")
    
    # Phase 3: Confluence Docs
    print("\n📚 [3/4] PHASE 3: Fetching and indexing Confluence documentation...")
    phase_start = time.time()
    try:
        results['docs'] = await fetch_and_index_confluence_docs(project_key, indexer)
        phase_duration = time.time() - phase_start
        print(f"✅ Phase 3 complete in {phase_duration:.1f}s: {results['docs']} docs indexed\n")
    except Exception as e:
        logger.error(f"Phase 3 failed: {e}")
        print(f"❌ Phase 3 failed: {e}\n")
    
    # Phase 4: External Docs (PlainID)
    print("\n🌐 [4/5] PHASE 4: Fetching and indexing PlainID documentation...")
    phase_start = time.time()
    try:
        results['external_docs'] = await indexer.index_external_docs()
        phase_duration = time.time() - phase_start
        print(f"✅ Phase 4 complete in {phase_duration:.1f}s: {results['external_docs']} external docs indexed\n")
    except Exception as e:
        logger.error(f"Phase 4 failed: {e}")
        print(f"❌ Phase 4 failed: {e}\n")
    
    # Phase 5: GitLab Swagger Docs
    print("\n🔧 [5/5] PHASE 5: Fetching and indexing GitLab Swagger documentation...")
    phase_start = time.time()
    try:
        results['swagger_docs'] = await indexer.index_gitlab_swagger_docs()
        phase_duration = time.time() - phase_start
        print(f"✅ Phase 5 complete in {phase_duration:.1f}s: {results['swagger_docs']} swagger docs indexed\n")
    except Exception as e:
        logger.error(f"Phase 5 failed: {e}")
        print(f"❌ Phase 5 failed: {e}\n")
    
    # Final summary
    total_duration = datetime.now() - start_time
    total_seconds = total_duration.total_seconds()
    end_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    results['total'] = sum(results.values())
    
    print("\n" + "=" * 70)
    print("🎉 INDEX-ALL COMPLETE!")
    print("=" * 70)
    print(f"⏰ Start Time:    {start_datetime}")
    print(f"⏰ End Time:      {end_datetime}")
    print(f"⏱️  Total Duration: {total_seconds:.1f} seconds ({total_seconds/60:.1f} minutes)")
    print("\n📊 SUMMARY:")
    print(f"  ✓ Zephyr Tests:       {results['tests']:,} documents")
    print(f"  ✓ Jira Stories:       {results['stories']:,} documents")
    print(f"  ✓ Confluence Docs:    {results['docs']:,} documents")
    print(f"  ✓ External Docs:      {results['external_docs']:,} documents")
    print(f"  ✓ Swagger Docs:       {results['swagger_docs']:,} documents")
    print(f"  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"  🎯 TOTAL INDEXED:     {results['total']:,} documents")
    print("=" * 70 + "\n")
    
    manager.record_refresh(project_key, ['index_all', 'tests', 'stories', 'docs', 'external_docs', 'swagger_docs'])
    return results


async def index_specific_sources(
    sources: list[str],
    project_key: str,
    refresh_manager: Optional[RAGRefreshManager] = None
) -> dict:
    """Index only the requested data sources."""
    valid_sources = {
        'zephyr': 'tests',
        'jira': 'stories',
        'confluence': 'docs',
        'plainid': 'external_docs',
        'external': 'external_docs',
        'gitlab': 'swagger_docs',
        'swagger': 'swagger_docs'
    }

    normalized_sources = []
    for source in sources:
        key = source.lower()
        if key not in valid_sources:
            raise ValueError(f"Unknown source '{source}'. Valid options: {', '.join(sorted(valid_sources))}")
        normalized_sources.append(key)

    print("\n" + "=" * 70)
    print("🎯 TARGETED INDEXING")
    print("=" * 70)
    print(f"Sources: {', '.join(normalized_sources)}")
    print(f"Project: {project_key}")
    print("=" * 70 + "\n")

    indexer = ContextIndexer()
    results = {
        'tests': 0,
        'stories': 0,
        'docs': 0,
        'external_docs': 0,
        'swagger_docs': 0
    }

    manager = refresh_manager or RAGRefreshManager()
    canonical_to_record = set()

    if 'zephyr' in normalized_sources:
        results['tests'] = await fetch_and_index_zephyr_tests(project_key, indexer)
        canonical_to_record.add('tests')

    if 'jira' in normalized_sources:
        results['stories'] = await fetch_and_index_jira_stories(project_key, indexer)
        canonical_to_record.add('stories')

    if 'confluence' in normalized_sources:
        results['docs'] = await fetch_and_index_confluence_docs(project_key, indexer)
        canonical_to_record.add('docs')

    if any(src in normalized_sources for src in ('plainid', 'external')):
        print("\n🌐 Fetching and indexing PlainID documentation...")
        try:
            results['external_docs'] = await indexer.index_external_docs()
            print(f"✅ Indexed {results['external_docs']} external docs")
        except Exception as exc:
            logger.error(f"External documentation indexing failed: {exc}")
            print(f"⚠️  External documentation indexing failed: {exc}")
        canonical_to_record.add('external_docs')
    
    if any(src in normalized_sources for src in ('gitlab', 'swagger')):
        print("\n🔧 Fetching and indexing GitLab Swagger documentation...")
        try:
            results['swagger_docs'] = await indexer.index_gitlab_swagger_docs()
            print(f"✅ Indexed {results['swagger_docs']} swagger docs")
        except Exception as exc:
            logger.error(f"GitLab Swagger indexing failed: {exc}")
            print(f"⚠️  GitLab Swagger indexing failed: {exc}")
        canonical_to_record.add('swagger_docs')

    if canonical_to_record:
        manager.record_refresh(project_key, canonical_to_record)

    print("\n" + "=" * 70)
    print("✅ TARGETED INDEXING COMPLETE")
    print("=" * 70)
    print(f"📊 Results: tests={results['tests']}, stories={results['stories']}, docs={results['docs']}, external={results['external_docs']}, swagger={results['swagger_docs']}")
    print("=" * 70 + "\n")

    return results


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
    limit: int = 10,
    project_key: Optional[str] = None,
    show_full: bool = False
) -> None:
    """
    View documents in a RAG collection.
    
    Args:
        collection: Collection name to view
        limit: Number of documents to show
        project_key: Filter by project key
        show_full: Show full document content
    """
    store = RAGVectorStore()
    
    print(f"\n📚 Viewing {collection} (limit: {limit})")
    if project_key:
        print(f"   Filtered by project: {project_key}")
    print("=" * 60)
    
    try:
        # Get collection stats first
        stats = store.get_all_stats()
        collection_stats = stats.get(collection, {})
        
        if not collection_stats.get('exists'):
            print(f"❌ Collection '{collection}' does not exist")
            print("\nAvailable collections:")
            for name, stat in stats.items():
                if isinstance(stat, dict) and stat.get('exists'):
                    print(f"  - {name}: {stat.get('count', 0)} documents")
            return
        
        total_count = collection_stats.get('count', 0)
        print(f"Total documents in {collection}: {total_count}\n")
        
        # Query the collection
        # Note: ChromaDB's get() doesn't support filtering by metadata directly in a simple way
        # We'll get all and filter in Python if needed
        collection_obj = store.chroma_client.get_collection(name=collection)
        
        # Get documents with limit
        results = collection_obj.get(
            limit=limit,
            include=['documents', 'metadatas']
        )
        
        if not results['ids']:
            print("No documents found")
            return
        
        # Display documents
        for i, (doc_id, doc, metadata) in enumerate(zip(results['ids'], results['documents'], results['metadatas']), 1):
            # Filter by project_key if specified
            if project_key and metadata.get('project_key') != project_key:
                continue
                
            print(f"\n📄 Document {i}/{len(results['ids'])}")
            print(f"   ID: {doc_id}")
            if metadata:
                for key, value in metadata.items():
                    print(f"   {key}: {value}")
            
            if show_full:
                print(f"\n   Content:\n   {doc}\n")
            else:
                preview = doc[:200] + "..." if len(doc) > 200 else doc
                print(f"   Preview: {preview}\n")
            print("-" * 60)
        
        print(f"\n✅ Displayed {min(limit, len(results['ids']))} documents")
        
    except Exception as e:
        logger.error(f"Failed to view RAG documents: {e}")
        print(f"❌ Error viewing documents: {e}")

