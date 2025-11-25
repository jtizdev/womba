#!/usr/bin/env python3
"""
Script to check if a test plan is stored in RAG.
"""
import asyncio
import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.ai.rag_store import RAGVectorStore
from src.models.test_plan import TestPlan
from loguru import logger

async def check_test_plan(story_key: str):
    """Check if test plan exists in RAG and display details."""
    store = RAGVectorStore()
    
    print(f"\n🔍 Checking RAG for test plan: {story_key}\n")
    print("=" * 80)
    
    # Get test plan from RAG
    test_plan_data = await store.get_test_plan_by_story_key(story_key)
    
    if not test_plan_data:
        print(f"❌ Test plan NOT FOUND in RAG for {story_key}")
        return False
    
    print(f"✅ Test plan FOUND in RAG for {story_key}\n")
    
    # Display basic info
    print("📋 Basic Information:")
    print(f"  Document ID: {test_plan_data.get('id', 'N/A')}")
    print(f"  Has document text: {'Yes' if test_plan_data.get('document') else 'No'}")
    print(f"  Has metadata: {'Yes' if test_plan_data.get('metadata') else 'No'}\n")
    
    # Display metadata
    metadata = test_plan_data.get('metadata', {})
    if metadata:
        print("📊 Metadata:")
        for key, value in metadata.items():
            if key == 'test_plan_json':
                print(f"  {key}: [Present - {len(str(value))} characters]")
            else:
                print(f"  {key}: {value}")
        print()
    
    # Check if test_plan_json exists
    if 'test_plan_json' in metadata:
        print("✅ test_plan_json found in metadata\n")
        
        try:
            # Parse and validate the test plan
            test_plan = TestPlan.model_validate_json(metadata['test_plan_json'])
            
            print("📝 Test Plan Details:")
            print(f"  Story Key: {test_plan.story.key}")
            print(f"  Story Summary: {test_plan.story.summary[:100]}..." if len(test_plan.story.summary) > 100 else f"  Story Summary: {test_plan.story.summary}")
            print(f"  Total Test Cases: {len(test_plan.test_cases)}")
            print(f"  Generated At: {test_plan.metadata.generated_at}")
            print(f"  AI Model: {test_plan.metadata.ai_model}")
            print(f"  Total Test Cases (metadata): {test_plan.metadata.total_test_cases}")
            print(f"  Edge Case Count: {test_plan.metadata.edge_case_count}")
            print(f"  Integration Test Count: {test_plan.metadata.integration_test_count}")
            
            print("\n📋 Test Cases:")
            for idx, tc in enumerate(test_plan.test_cases, 1):
                print(f"  {idx}. {tc.title}")
                print(f"     Type: {tc.test_type.value}, Priority: {tc.priority.value}")
                print(f"     Steps: {len(tc.steps)}")
            
            print("\n✅ Test plan structure is valid!")
            return True
            
        except Exception as e:
            print(f"❌ Failed to parse test_plan_json: {e}")
            logger.exception(e)
            return False
    else:
        print("❌ test_plan_json NOT found in metadata")
        print("   This means the test plan was indexed with an older version of the code.")
        return False

if __name__ == "__main__":
    story_key = sys.argv[1] if len(sys.argv) > 1 else "PLAT-9707"
    result = asyncio.run(check_test_plan(story_key))
    sys.exit(0 if result else 1)

