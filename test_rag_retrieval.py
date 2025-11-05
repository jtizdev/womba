#!/usr/bin/env python3
"""
Test script to inspect RAG retrieval quality and similarity scores.
Shows what documents are retrieved and their similarity scores.
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from loguru import logger
from src.aggregator.story_collector import StoryCollector
from src.ai.rag_retriever import RAGRetriever
from src.config.settings import settings


async def test_rag_retrieval(story_key: str):
    """Test RAG retrieval for a specific story and show detailed results."""
    
    print("=" * 80)
    print(f"RAG RETRIEVAL TEST FOR: {story_key}")
    print("=" * 80)
    print()
    
    # Collect story context
    print(f"1. Collecting story context for {story_key}...")
    collector = StoryCollector()
    context = await collector.collect_story_context(story_key)
    story = context.main_story
    
    print(f"   Story: {story.summary}")
    print()
    
    # Retrieve RAG context
    print(f"2. Retrieving RAG context...")
    print(f"   Configuration:")
    print(f"   - Min similarity threshold: {settings.rag_min_similarity}")
    print(f"   - Top-K tests: {settings.rag_top_k_tests}")
    print(f"   - Top-K docs: {settings.rag_top_k_docs}")
    print(f"   - Top-K stories: {settings.rag_top_k_stories}")
    print(f"   - Top-K existing: {settings.rag_top_k_existing}")
    print()
    
    retriever = RAGRetriever()
    retrieved = await retriever.retrieve_for_story(story, project_key=story.key.split('-')[0])
    
    print(f"3. RETRIEVAL RESULTS:")
    print("=" * 80)
    
    # Test Plans
    print(f"\n📋 TEST PLANS ({len(retrieved.similar_test_plans)} retrieved)")
    print("-" * 80)
    if retrieved.similar_test_plans:
        for i, doc in enumerate(retrieved.similar_test_plans, 1):
            similarity = doc.get('similarity', 1 - doc.get('distance', 0))
            metadata = doc.get('metadata', {})
            story_key = metadata.get('story_key', 'N/A')
            preview = doc.get('document', '')[:150]
            print(f"{i}. Similarity: {similarity:.3f} | Story: {story_key}")
            print(f"   Preview: {preview}...")
    else:
        print("   No test plans retrieved")
    
    # Confluence Docs
    print(f"\n📚 CONFLUENCE DOCS ({len(retrieved.similar_confluence_docs)} retrieved)")
    print("-" * 80)
    if retrieved.similar_confluence_docs:
        for i, doc in enumerate(retrieved.similar_confluence_docs, 1):
            similarity = doc.get('similarity', 1 - doc.get('distance', 0))
            metadata = doc.get('metadata', {})
            title = metadata.get('title', 'N/A')
            preview = doc.get('document', '')[:150]
            print(f"{i}. Similarity: {similarity:.3f} | Title: {title}")
            print(f"   Preview: {preview}...")
    else:
        print("   No Confluence docs retrieved")
    
    # Jira Stories
    print(f"\n📝 JIRA STORIES ({len(retrieved.similar_jira_stories)} retrieved)")
    print("-" * 80)
    if retrieved.similar_jira_stories:
        for i, doc in enumerate(retrieved.similar_jira_stories, 1):
            similarity = doc.get('similarity', 1 - doc.get('distance', 0))
            metadata = doc.get('metadata', {})
            story_key = metadata.get('story_key', 'N/A')
            preview = doc.get('document', '')[:150]
            print(f"{i}. Similarity: {similarity:.3f} | Story: {story_key}")
            print(f"   Preview: {preview}...")
    else:
        print("   No Jira stories retrieved")
    
    # Existing Tests
    print(f"\n✅ EXISTING TESTS ({len(retrieved.similar_existing_tests)} retrieved)")
    print("-" * 80)
    if retrieved.similar_existing_tests:
        for i, doc in enumerate(retrieved.similar_existing_tests, 1):
            similarity = doc.get('similarity', 1 - doc.get('distance', 0))
            metadata = doc.get('metadata', {})
            test_name = metadata.get('test_name', 'N/A')
            preview = doc.get('document', '')[:150]
            print(f"{i}. Similarity: {similarity:.3f} | Test: {test_name}")
            print(f"   Preview: {preview}...")
    else:
        print("   No existing tests retrieved")
    
    # External Docs (PlainID API)
    print(f"\n🔗 EXTERNAL DOCS ({len(retrieved.similar_external_docs)} retrieved)")
    print("-" * 80)
    if retrieved.similar_external_docs:
        for i, doc in enumerate(retrieved.similar_external_docs, 1):
            similarity = doc.get('similarity', 1 - doc.get('distance', 0))
            metadata = doc.get('metadata', {})
            title = metadata.get('title', 'N/A')
            url = metadata.get('source_url', 'N/A')
            preview = doc.get('document', '')[:150]
            print(f"{i}. Similarity: {similarity:.3f} | Title: {title}")
            print(f"   URL: {url}")
            print(f"   Preview: {preview}...")
    else:
        print("   No external docs retrieved")
    
    # Summary Statistics
    print("\n" + "=" * 80)
    print("SUMMARY STATISTICS")
    print("=" * 80)
    
    all_results = (
        retrieved.similar_test_plans +
        retrieved.similar_confluence_docs +
        retrieved.similar_jira_stories +
        retrieved.similar_existing_tests +
        retrieved.similar_external_docs
    )
    
    if all_results:
        similarities = [doc.get('similarity', 1 - doc.get('distance', 0)) for doc in all_results]
        avg_similarity = sum(similarities) / len(similarities)
        max_similarity = max(similarities)
        min_similarity = min(similarities)
        
        print(f"Total documents retrieved: {len(all_results)}")
        print(f"Average similarity: {avg_similarity:.3f}")
        print(f"Max similarity: {max_similarity:.3f}")
        print(f"Min similarity: {min_similarity:.3f}")
        print(f"Threshold: {settings.rag_min_similarity}")
        
        # Quality assessment
        print()
        if avg_similarity >= 0.7:
            print("✅ GOOD: High average similarity - retrieval quality is excellent")
        elif avg_similarity >= 0.6:
            print("⚠️  OKAY: Moderate average similarity - retrieval quality is acceptable")
        else:
            print("❌ POOR: Low average similarity - consider improving query or embeddings")
        
        below_threshold = sum(1 for s in similarities if s < settings.rag_min_similarity)
        if below_threshold > 0:
            print(f"⚠️  Warning: {below_threshold} documents below threshold were filtered out")
    else:
        print("❌ No documents retrieved - check if RAG is indexed")
    
    print("=" * 80)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_rag_retrieval.py <STORY_KEY>")
        print("Example: python test_rag_retrieval.py PLAT-15474")
        sys.exit(1)
    
    story_key = sys.argv[1]
    asyncio.run(test_rag_retrieval(story_key))
