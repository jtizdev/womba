#!/usr/bin/env python3
"""Test script to verify PlainID docs are included in RAG context."""

import asyncio
from src.aggregator.story_collector import StoryCollector
from src.ai.rag_retriever import RAGRetriever
from src.ai.test_plan_generator import TestPlanGenerator

async def main():
    print("=" * 80)
    print("Testing PlainID Documentation Integration")
    print("=" * 80)
    
    # Fetch a story
    story_key = "PLAT-16263"
    print(f"\n1. Fetching story {story_key}...")
    collector = StoryCollector()
    context = await collector.collect_story_context(story_key)
    
    # Retrieve RAG context
    print(f"\n2. Retrieving RAG context...")
    retriever = RAGRetriever()
    retrieved_context = await retriever.retrieve_for_story(
        story=context.main_story,
        project_key="PLAT"
    )
    
    print(f"\n3. RAG Retrieval Results:")
    print(f"   - Test plans: {len(retrieved_context.similar_test_plans)}")
    print(f"   - Confluence docs: {len(retrieved_context.similar_confluence_docs)}")
    print(f"   - Jira stories: {len(retrieved_context.similar_jira_stories)}")
    print(f"   - Existing tests: {len(retrieved_context.similar_existing_tests)}")
    print(f"   - External docs (PlainID): {len(retrieved_context.similar_external_docs)}")
    
    # Build RAG context section
    print(f"\n4. Building RAG context section...")
    generator = TestPlanGenerator()
    rag_section = generator._build_rag_context(retrieved_context)
    
    # Check if PlainID docs are included
    has_plainid = "PLAINID API DOCUMENTATION" in rag_section
    has_endpoint_info = "/api/" in rag_section or "POST" in rag_section or "GET" in rag_section
    
    print(f"\n5. Verification:")
    print(f"   ✓ PlainID section header present: {has_plainid}")
    print(f"   ✓ API endpoint info present: {has_endpoint_info}")
    
    if has_plainid:
        # Extract PlainID section
        start = rag_section.find("PLAINID API DOCUMENTATION")
        end = rag_section.find("=" * 80, start + 100)
        plainid_section = rag_section[start:end] if end > start else rag_section[start:start+2000]
        
        print(f"\n6. PlainID Section Preview (first 1500 chars):")
        print("-" * 80)
        print(plainid_section[:1500])
        print("-" * 80)
    else:
        print(f"\n❌ ERROR: PlainID section NOT found in RAG context!")
        print(f"\nRAG section preview:")
        print(rag_section[:1000])
    
    print(f"\n" + "=" * 80)
    if has_plainid and has_endpoint_info:
        print("✅ SUCCESS: PlainID documentation IS included in prompts!")
    else:
        print("❌ FAILURE: PlainID documentation NOT properly integrated!")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(main())

