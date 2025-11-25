#!/usr/bin/env python3
"""
Script to list all test plans stored in RAG.
"""
import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.ai.rag_store import RAGVectorStore
from loguru import logger

async def list_all_test_plans():
    """List all test plans in RAG."""
    store = RAGVectorStore()
    
    print("\n🔍 Listing all test plans in RAG\n")
    print("=" * 80)
    
    try:
        collection = store.get_or_create_collection(store.TEST_PLANS_COLLECTION)
        
        # Get all documents
        results = collection.get(limit=1000)  # Get up to 1000 test plans
        
        if not results or not results.get('ids') or len(results['ids']) == 0:
            print("❌ No test plans found in RAG")
            return
        
        print(f"✅ Found {len(results['ids'])} test plan(s) in RAG\n")
        
        # Display each test plan
        for idx, doc_id in enumerate(results['ids'], 1):
            metadata = results['metadatas'][idx - 1] if results.get('metadatas') else {}
            document = results['documents'][idx - 1] if results.get('documents') else ''
            
            print(f"{idx}. Document ID: {doc_id}")
            print(f"   Story Key: {metadata.get('story_key', 'N/A')}")
            print(f"   Project Key: {metadata.get('project_key', 'N/A')}")
            print(f"   Has test_plan_json: {'Yes' if 'test_plan_json' in metadata else 'No'}")
            if 'test_plan_json' in metadata:
                import json
                try:
                    tp_json = json.loads(metadata['test_plan_json'])
                    test_count = len(tp_json.get('test_cases', []))
                    print(f"   Test Cases: {test_count}")
                except:
                    pass
            print(f"   Document length: {len(document)} characters")
            print()
        
    except Exception as e:
        print(f"❌ Error listing test plans: {e}")
        logger.exception(e)

if __name__ == "__main__":
    asyncio.run(list_all_test_plans())

