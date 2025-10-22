#!/usr/bin/env python3
"""
Manual test script for RAG system with real APIs.
Run this to validate RAG functionality with actual OpenAI and data.

Usage:
    python tests/manual/test_rag_manual.py

Requirements:
    - OPENAI_API_KEY set in environment or .env
    - Configured Womba settings
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from loguru import logger
from src.ai.embedding_service import EmbeddingService
from src.ai.rag_store import RAGVectorStore
from src.ai.context_indexer import ContextIndexer
from src.ai.rag_retriever import RAGRetriever
from src.models.story import JiraStory


def print_header(title: str):
    """Print a formatted header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def print_success(message: str):
    """Print success message."""
    print(f"✅ {message}")


def print_error(message: str):
    """Print error message."""
    print(f"❌ {message}")


def print_info(message: str):
    """Print info message."""
    print(f"ℹ️  {message}")


async def test_embedding_service():
    """Test embedding service with real OpenAI API."""
    print_header("Test 1: Embedding Service")
    
    try:
        service = EmbeddingService()
        print_success("Embedding service initialized")
        
        # Test single embedding
        text = "This is a test document about user authentication"
        embedding = await service.embed_single(text)
        
        assert len(embedding) == 1536, f"Expected 1536 dimensions, got {len(embedding)}"
        assert all(isinstance(x, float) for x in embedding), "All embeddings should be floats"
        print_success(f"Generated embedding with {len(embedding)} dimensions")
        
        # Test batch embeddings
        texts = [
            "User login functionality",
            "Password reset feature",
            "Shopping cart checkout"
        ]
        embeddings = await service.embed_texts(texts)
        
        assert len(embeddings) == 3, f"Expected 3 embeddings, got {len(embeddings)}"
        print_success(f"Generated {len(embeddings)} batch embeddings")
        
        return True
        
    except Exception as e:
        print_error(f"Embedding service test failed: {e}")
        logger.exception("Full traceback:")
        return False


async def test_rag_store():
    """Test RAG vector store."""
    print_header("Test 2: RAG Vector Store")
    
    try:
        store = RAGVectorStore()
        print_success("RAG store initialized")
        
        # Get initial stats
        stats = store.get_all_stats()
        print_info(f"Storage path: {stats['storage_path']}")
        print_info(f"Total documents: {stats['total_documents']}")
        print_info(f"Test plans: {stats['test_plans']['count']}")
        print_info(f"Confluence docs: {stats['confluence_docs']['count']}")
        print_info(f"Jira stories: {stats['jira_stories']['count']}")
        print_info(f"Existing tests: {stats['existing_tests']['count']}")
        
        # Test adding documents to a test collection
        print_info("Testing document addition...")
        test_docs = [
            "Test document about authentication",
            "Test document about authorization",
            "Test document about user management"
        ]
        test_metadata = [
            {"test_id": "1", "type": "auth"},
            {"test_id": "2", "type": "auth"},
            {"test_id": "3", "type": "user"}
        ]
        test_ids = ["manual_test_1", "manual_test_2", "manual_test_3"]
        
        await store.add_documents(
            collection_name="manual_test_collection",
            documents=test_docs,
            metadatas=test_metadata,
            ids=test_ids
        )
        print_success("Added 3 test documents")
        
        # Test retrieval
        print_info("Testing document retrieval...")
        results = await store.retrieve_similar(
            collection_name="manual_test_collection",
            query_text="authentication and authorization",
            top_k=2
        )
        
        assert len(results) > 0, "Should retrieve at least 1 document"
        print_success(f"Retrieved {len(results)} similar documents")
        
        for i, result in enumerate(results, 1):
            print_info(f"  Result {i}: {result['document'][:50]}... (distance: {result['distance']:.4f})")
        
        # Cleanup
        store.clear_collection("manual_test_collection")
        print_info("Cleaned up test collection")
        
        return True
        
    except Exception as e:
        print_error(f"RAG store test failed: {e}")
        logger.exception("Full traceback:")
        return False


async def test_context_indexer():
    """Test context indexer."""
    print_header("Test 3: Context Indexer")
    
    try:
        indexer = ContextIndexer()
        print_success("Context indexer initialized")
        
        # Create test stories
        stories = [
            JiraStory(
                key="MANUAL-1",
                summary="Add user login functionality",
                description="Implement OAuth 2.0 login for users",
                issue_type="Story",
                status="Open",
                priority="High",
                components=["Authentication"]
            ),
            JiraStory(
                key="MANUAL-2",
                summary="Add password reset feature",
                description="Allow users to reset forgotten passwords",
                issue_type="Story",
                status="Open",
                priority="Medium",
                components=["Authentication"]
            )
        ]
        
        # Index stories
        print_info("Indexing 2 test stories...")
        await indexer.index_jira_stories(stories, "MANUAL")
        print_success("Stories indexed successfully")
        
        # Verify indexing
        stats = indexer.store.get_collection_stats(indexer.store.JIRA_STORIES_COLLECTION)
        print_info(f"Jira stories collection now has {stats['count']} documents")
        
        return True
        
    except Exception as e:
        print_error(f"Context indexer test failed: {e}")
        logger.exception("Full traceback:")
        return False


async def test_rag_retriever():
    """Test RAG retriever."""
    print_header("Test 4: RAG Retriever")
    
    try:
        retriever = RAGRetriever()
        print_success("RAG retriever initialized")
        
        # Create query story
        query_story = JiraStory(
            key="MANUAL-QUERY",
            summary="Implement user authentication",
            description="Need to add login capabilities",
            issue_type="Story",
            status="Open",
            priority="High",
            components=["Authentication"]
        )
        
        # Retrieve context
        print_info("Retrieving context for query story...")
        context = await retriever.retrieve_for_story(query_story, "MANUAL")
        
        print_info(f"Retrieved context: {context.get_summary()}")
        
        if context.has_context():
            print_success("Successfully retrieved relevant context")
            
            if context.similar_jira_stories:
                print_info(f"Found {len(context.similar_jira_stories)} similar stories:")
                for result in context.similar_jira_stories[:3]:
                    print_info(f"  - {result['document'][:80]}...")
        else:
            print_info("No context found (database may be empty)")
        
        return True
        
    except Exception as e:
        print_error(f"RAG retriever test failed: {e}")
        logger.exception("Full traceback:")
        return False


async def main():
    """Run all manual tests."""
    print_header("RAG System Manual Test Suite")
    print_info("This will test RAG functionality with real APIs")
    print_info("Make sure OPENAI_API_KEY is configured")
    print()
    
    results = []
    
    # Run tests
    results.append(("Embedding Service", await test_embedding_service()))
    results.append(("RAG Vector Store", await test_rag_store()))
    results.append(("Context Indexer", await test_context_indexer()))
    results.append(("RAG Retriever", await test_rag_retriever()))
    
    # Print summary
    print_header("Test Summary")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print()
    print(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        print_success("All tests passed! RAG system is working correctly.")
        return 0
    else:
        print_error(f"{total - passed} test(s) failed. Please check the errors above.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

