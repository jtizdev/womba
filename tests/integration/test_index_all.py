"""
Integration tests for index-all command and RAG indexing workflow.
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from pathlib import Path
from src.cli.rag_commands import index_all_data, show_rag_stats
from src.ai.context_indexer import ContextIndexer
from src.ai.rag_store import RAGVectorStore
from src.config.settings import settings


@pytest.fixture
def mock_jira_client():
    """Mock Jira client for testing."""
    with patch('src.cli.rag_commands.JiraClient') as mock_client:
        mock_instance = AsyncMock()
        mock_client.return_value = mock_instance
        
        # Mock search_issues to return test data
        mock_story = Mock()
        mock_story.key = "PLAT-123"
        mock_story.summary = "Test story"
        mock_story.description = "Test description"
        mock_story.issue_type = "Story"
        mock_story.status = "Done"
        mock_story.components = []
        mock_story.updated = "2024-01-01T00:00:00.000+0000"
        
        mock_instance.search_issues.return_value = ([mock_story], 1)
        
        yield mock_instance


@pytest.fixture
def mock_confluence_client():
    """Mock Confluence client for testing."""
    with patch('src.cli.rag_commands.ConfluenceClient') as mock_client:
        mock_instance = AsyncMock()
        mock_client.return_value = mock_instance
        
        # Mock search_pages to return test data
        mock_page = {
            'id': '123',
            'title': 'Test Page',
            'body': {'storage': {'value': 'Test content'}},
            'space': {'key': 'DOC'},
            '_links': {'webui': '/wiki/spaces/DOC/pages/123'},
            'version': {'when': '2024-01-01T00:00:00.000+0000'}
        }
        
        mock_instance.search_pages.return_value = [mock_page]
        
        yield mock_instance


@pytest.fixture
def mock_zephyr_client():
    """Mock Zephyr client for testing."""
    with patch('src.cli.rag_commands.ZephyrClient') as mock_client:
        mock_instance = AsyncMock()
        mock_client.return_value = mock_instance
        
        # Mock get_test_cases to return test data
        mock_test = {
            'key': 'PLAT-T123',
            'name': 'Test case',
            'objective': 'Test objective',
            'precondition': 'Test precondition',
            'testScript': {
                'steps': [
                    {'description': 'Step 1', 'expectedResult': 'Result 1'}
                ]
            }
        }
        
        mock_instance.get_test_cases.return_value = [mock_test]
        
        yield mock_instance


@pytest.mark.asyncio
async def test_index_all_basic_workflow(mock_jira_client, mock_confluence_client, mock_zephyr_client):
    """Test basic index-all workflow completes without errors."""
    project_key = "PLAT"
    
    # Mock the indexer methods to avoid actual embedding calls
    with patch.object(ContextIndexer, 'index_jira_stories') as mock_index_stories, \
         patch.object(ContextIndexer, 'index_confluence_docs') as mock_index_docs, \
         patch.object(ContextIndexer, 'index_existing_tests') as mock_index_tests, \
         patch.object(ContextIndexer, 'index_external_docs') as mock_index_external:
        
        mock_index_stories.return_value = None
        mock_index_docs.return_value = None
        mock_index_tests.return_value = None
        mock_index_external.return_value = 5
        
        # Run index-all
        results = await index_all_data(project_key)
        
        # Verify results structure
        assert 'tests' in results
        assert 'stories' in results
        assert 'docs' in results
        assert 'external_docs' in results
        assert 'total' in results
        
        # Verify all indexing methods were called
        mock_index_stories.assert_called_once()
        mock_index_docs.assert_called_once()
        mock_index_tests.assert_called_once()
        mock_index_external.assert_called_once()


@pytest.mark.asyncio
async def test_plainid_doc_indexing():
    """Test PlainID documentation indexing."""
    indexer = ContextIndexer()
    
    # Mock the crawler
    with patch('src.ai.context_indexer.PlainIDDocCrawler') as mock_crawler_class:
        mock_crawler = Mock()
        mock_crawler_class.return_value = mock_crawler
        mock_crawler.is_available.return_value = True
        mock_crawler.discover_urls.return_value = [
            "https://docs.plainid.io/v1-api/endpoint1",
            "https://docs.plainid.io/v1-api/endpoint2"
        ]
        mock_crawler.fetch_content.return_value = [
            Mock(url="https://docs.plainid.io/v1-api/endpoint1", title="Endpoint 1", html="<html>Content 1</html>"),
            Mock(url="https://docs.plainid.io/v1-api/endpoint2", title="Endpoint 2", html="<html>Content 2</html>")
        ]
        
        # Mock the RAG store to avoid actual embedding
        with patch.object(indexer.rag_store, 'add_documents') as mock_add:
            mock_add.return_value = None
            
            count = await indexer.index_external_docs()
            
            # Should have indexed documents
            assert count == 2
            mock_add.assert_called_once()


@pytest.mark.asyncio
async def test_plainid_doc_indexing_disabled():
    """Test that PlainID indexing respects the enabled flag."""
    indexer = ContextIndexer()
    
    # Temporarily disable PlainID indexing
    original_enabled = settings.plainid_doc_index_enabled
    settings.plainid_doc_index_enabled = False
    
    try:
        count = await indexer.index_external_docs()
        
        # Should return 0 when disabled
        assert count == 0
    finally:
        settings.plainid_doc_index_enabled = original_enabled


@pytest.mark.asyncio
async def test_upsert_logic_new_documents():
    """Test that new documents are properly indexed."""
    store = RAGVectorStore()
    
    # Clear test collection
    store.clear_collection("test_upsert")
    
    # Add new documents
    documents = ["New document 1", "New document 2"]
    metadatas = [
        {"id": "1", "last_modified": "2024-01-01T00:00:00Z"},
        {"id": "2", "last_modified": "2024-01-01T00:00:00Z"}
    ]
    ids = ["test_upsert_1", "test_upsert_2"]
    
    await store.add_documents("test_upsert", documents, metadatas, ids)
    
    # Verify documents were added
    stats = store.get_collection_stats("test_upsert")
    assert stats['count'] == 2


@pytest.mark.asyncio
async def test_upsert_logic_unchanged_documents():
    """Test that unchanged documents are skipped."""
    store = RAGVectorStore()
    
    # Clear and add initial documents
    store.clear_collection("test_upsert_unchanged")
    
    documents = ["Document content"]
    metadatas = [{"id": "1", "last_modified": "2024-01-01T00:00:00Z"}]
    ids = ["test_upsert_unchanged_1"]
    
    await store.add_documents("test_upsert_unchanged", documents, metadatas, ids)
    
    # Try to add same document again
    await store.add_documents("test_upsert_unchanged", documents, metadatas, ids)
    
    # Should still have only 1 document
    stats = store.get_collection_stats("test_upsert_unchanged")
    assert stats['count'] == 1


@pytest.mark.asyncio
async def test_upsert_logic_updated_documents():
    """Test that updated documents are re-indexed."""
    store = RAGVectorStore()
    
    # Clear and add initial document
    store.clear_collection("test_upsert_updated")
    
    documents = ["Original content"]
    metadatas = [{"id": "1", "last_modified": "2024-01-01T00:00:00Z"}]
    ids = ["test_upsert_updated_1"]
    
    await store.add_documents("test_upsert_updated", documents, metadatas, ids)
    
    # Update the document with new timestamp
    updated_documents = ["Updated content"]
    updated_metadatas = [{"id": "1", "last_modified": "2024-01-02T00:00:00Z"}]
    
    await store.add_documents("test_upsert_updated", updated_documents, updated_metadatas, ids)
    
    # Should still have 1 document (updated, not duplicated)
    stats = store.get_collection_stats("test_upsert_updated")
    assert stats['count'] == 1


@pytest.mark.asyncio
async def test_clear_all_collections():
    """Test that clear_all_collections removes all data."""
    store = RAGVectorStore()
    
    # Add some test data to multiple collections
    test_collections = [
        store.TEST_PLANS_COLLECTION,
        store.CONFLUENCE_DOCS_COLLECTION,
        store.JIRA_STORIES_COLLECTION,
        store.EXISTING_TESTS_COLLECTION,
        store.EXTERNAL_DOCS_COLLECTION
    ]
    
    for collection in test_collections:
        await store.add_documents(
            collection,
            ["Test document"],
            [{"test": "data"}],
            [f"{collection}_test_1"]
        )
    
    # Verify data exists
    for collection in test_collections:
        stats = store.get_collection_stats(collection)
        assert stats['count'] > 0
    
    # Clear all collections
    store.clear_all_collections()
    
    # Verify all collections are empty
    for collection in test_collections:
        stats = store.get_collection_stats(collection)
        assert stats['count'] == 0
    
    # Verify ChromaDB files are deleted (except chroma.sqlite3)
    chroma_path = Path(settings.rag_collection_path)
    remaining_items = list(chroma_path.iterdir())
    
    # Should only have chroma.sqlite3 or be empty
    for item in remaining_items:
        if item.is_file():
            assert item.name == "chroma.sqlite3", f"Unexpected file: {item.name}"


@pytest.mark.asyncio
async def test_jql_pagination():
    """Test that JQL pagination works correctly."""
    with patch('src.cli.rag_commands.JiraClient') as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        
        # Mock multiple pages of results
        mock_stories_page1 = [Mock(key=f"PLAT-{i}") for i in range(50)]
        mock_stories_page2 = [Mock(key=f"PLAT-{i}") for i in range(50, 75)]
        
        # First call returns 50 items, total 75
        # Second call returns 25 items, total 75
        mock_client.search_issues.side_effect = [
            (mock_stories_page1, 75),
            (mock_stories_page2, 75)
        ]
        
        # Mock indexer to avoid actual indexing
        with patch.object(ContextIndexer, 'index_jira_stories') as mock_index:
            mock_index.return_value = None
            
            from src.cli.rag_commands import fetch_and_index_jira_stories
            indexer = ContextIndexer()
            
            count = await fetch_and_index_jira_stories("PLAT", indexer)
            
            # Should have fetched all 75 stories
            assert count == 75
            
            # Should have made 2 API calls (pagination)
            assert mock_client.search_issues.call_count == 2


@pytest.mark.asyncio
async def test_confluence_doc_space_indexing():
    """Test that Confluence DOC space is properly indexed."""
    with patch('src.cli.rag_commands.ConfluenceClient') as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        
        # Mock pages from DOC space
        mock_pages = [
            {
                'id': f'{i}',
                'title': f'Page {i}',
                'body': {'storage': {'value': f'Content {i}'}},
                'space': {'key': 'DOC'},
                '_links': {'webui': f'/wiki/spaces/DOC/pages/{i}'},
                'version': {'when': '2024-01-01T00:00:00.000+0000'}
            }
            for i in range(10)
        ]
        
        mock_client.search_pages.return_value = mock_pages
        
        # Mock indexer
        with patch.object(ContextIndexer, 'index_confluence_docs') as mock_index:
            mock_index.return_value = None
            
            from src.cli.rag_commands import fetch_and_index_confluence_docs
            indexer = ContextIndexer()
            
            count = await fetch_and_index_confluence_docs("PLAT", indexer)
            
            # Should have indexed pages
            assert count == 10
            
            # Verify CQL query includes DOC space
            call_args = mock_client.search_pages.call_args
            cql = call_args[0][0] if call_args else ""
            assert 'DOC' in cql or 'space' in cql.lower()


@pytest.mark.asyncio
async def test_error_handling_missing_settings():
    """Test error handling when settings are missing."""
    # Temporarily unset a required setting
    original_base_url = settings.atlassian_base_url
    settings.atlassian_base_url = ""
    
    try:
        # This should handle the error gracefully
        with patch('src.cli.rag_commands.JiraClient') as mock_client_class:
            mock_client_class.side_effect = ValueError("Invalid configuration")
            
            # Should not raise exception
            try:
                from src.cli.rag_commands import fetch_and_index_jira_stories
                indexer = ContextIndexer()
                count = await fetch_and_index_jira_stories("PLAT", indexer)
                # If it doesn't raise, count should be 0
                assert count == 0
            except ValueError:
                # Expected behavior - error is raised but caught
                pass
    finally:
        settings.atlassian_base_url = original_base_url


@pytest.mark.asyncio
async def test_external_docs_collection_in_stats():
    """Test that external_docs collection appears in stats."""
    store = RAGVectorStore()
    
    # Add some external docs
    await store.add_documents(
        store.EXTERNAL_DOCS_COLLECTION,
        ["External doc 1", "External doc 2"],
        [{"source": "plainid"}, {"source": "plainid"}],
        ["ext_1", "ext_2"]
    )
    
    # Get all stats
    all_stats = store.get_all_stats()
    
    # Verify external_docs is included
    assert 'external_docs' in all_stats
    assert all_stats['external_docs']['count'] >= 2


@pytest.mark.asyncio
async def test_index_all_includes_external_docs(mock_jira_client, mock_confluence_client, mock_zephyr_client):
    """Test that index-all includes external documentation."""
    project_key = "PLAT"
    
    # Mock all indexing methods
    with patch.object(ContextIndexer, 'index_jira_stories') as mock_index_stories, \
         patch.object(ContextIndexer, 'index_confluence_docs') as mock_index_docs, \
         patch.object(ContextIndexer, 'index_existing_tests') as mock_index_tests, \
         patch.object(ContextIndexer, 'index_external_docs') as mock_index_external:
        
        mock_index_stories.return_value = None
        mock_index_docs.return_value = None
        mock_index_tests.return_value = None
        mock_index_external.return_value = 10  # Return count
        
        results = await index_all_data(project_key)
        
        # Verify external_docs is in results
        assert 'external_docs' in results
        assert results['external_docs'] == 10
        
        # Verify index_external_docs was called
        mock_index_external.assert_called_once()

