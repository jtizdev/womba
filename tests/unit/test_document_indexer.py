import pytest
from unittest.mock import AsyncMock, MagicMock

from src.ai.indexing.document_indexer import DocumentIndexer


@pytest.mark.asyncio
async def test_index_external_docs_normalizes_metadata():
    indexer = DocumentIndexer()
    indexer.store = MagicMock()
    indexer.store.add_documents = AsyncMock()

    documents = ["Doc"]
    metadatas = [{"doc_hash": "abc123", "has_json_examples": True, "count": 3}]
    ids = ["plainid_abc"]

    await indexer.index_external_docs(documents, metadatas, ids)

    args = indexer.store.add_documents.await_args
    passed_meta = args.kwargs['metadatas']
    assert all(isinstance(value, str) for meta in passed_meta for value in meta.values())


@pytest.mark.asyncio
async def test_index_existing_tests_normalizes_metadata():
    indexer = DocumentIndexer()
    indexer.store = MagicMock()
    indexer.store.add_documents = AsyncMock()

    documents = ["Test"]
    metadatas = [{"test_key": "T-1", "priority": 1, "timestamp": "2024-01-01T00:00:00Z"}]
    ids = ["id"]

    await indexer.index_existing_tests(documents, metadatas, ids)

    args = indexer.store.add_documents.await_args
    passed_meta = args.kwargs['metadatas']
    assert all(isinstance(value, str) for meta in passed_meta for value in meta.values())
