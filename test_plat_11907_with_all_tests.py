#!/usr/bin/env python3
"""
Enhanced test generation script that uses ALL Zephyr tests (7000+) for better context.

Usage:
    python3 test_plat_11907_with_all_tests.py
"""

import asyncio
import json
from pathlib import Path

from loguru import logger
from src.aggregator.story_collector import StoryCollector
from src.ai.test_plan_generator import TestPlanGenerator
from src.integrations.zephyr_integration import ZephyrIntegration


async def test_story_key(story_key: str):
    """Test comprehensive test generation for a story with ALL Zephyr context."""
    
    logger.info("=" * 80)
    logger.info(f"🚀 Womba Enhanced Test - Using ALL {story_key} Zephyr Tests")
    logger.info("=" * 80)
    
    # Step 1: Collect story context
    logger.info(f"\n📊 Step 1: Collecting comprehensive context...")
    collector = StoryCollector()
    context = await collector.collect_story_context(story_key, include_subtasks=True)
    
    logger.info(f"✅ Context collected!")
    logger.info(f"   Linked stories: {len(context.get('linked_stories', []))}")
    logger.info(f"   Subtasks/Tasks: {len(context.get('subtasks', []))}")
    logger.info(f"   Related bugs: {len(context.get('related_bugs', []))}")
    logger.info(f"   Confluence docs: {len(context.get('confluence_docs', []))}")
    
    # Step 2: Fetch ALL existing tests from Zephyr (7000+!)
    logger.info(f"\n🗂️  Step 2: Fetching ALL existing tests from Zephyr...")
    logger.info("   (This may take 2-3 minutes for 7000+ tests...)")
    
    zephyr = ZephyrIntegration()
    project_key = story_key.split('-')[0]
    
    # Step 2: Fetch existing tests from Zephyr
    # Option A: Use scalable search (best for 100k+ tests)
    # existing_tests = await zephyr.get_relevant_tests_for_story(project_key, story_key, max_results=100)
    
    # Option B: Fetch recent tests (current approach, good for up to 10k tests)
    existing_tests = await zephyr.get_test_cases_for_project(project_key, max_results=1000, use_cache=True)
    logger.info(f"✅ Found {len(existing_tests)} existing test cases in Zephyr")
    
    # Step 3: Get folder structure
    folder_structure = await zephyr.get_folder_structure(project_key)
    logger.info(f"✅ Found {len(folder_structure)} test folders")
    
    # Step 4: Generate test plan with ALL context
    logger.info(f"\n🤖 Step 3: Generating test plan with AI...")
    logger.info("   Using context from:")
    logger.info(f"   - Story + {len(context.get('subtasks', []))} subtasks")
    logger.info(f"   - {len(context.get('confluence_docs', []))} Confluence docs")
    logger.info(f"   - {len(existing_tests)} existing Zephyr tests")
    logger.info(f"   - {len(folder_structure)} Zephyr folders")
    
    generator = TestPlanGenerator(use_openai=True)
    test_plan = await generator.generate_test_plan(
        context=context,
        existing_tests=existing_tests[:1000],  # Use top 1000 most relevant
        folder_structure=folder_structure
    )
    
    logger.info("✅ Test plan generated successfully!")
    
    # Step 5: Display results
    logger.info("\n📋 Test Plan Summary:")
    logger.info(f"   {test_plan.summary}")
    
    logger.info("\n📊 Statistics:")
    logger.info(f"   Total test cases: {len(test_plan.test_cases)}")
    
    # Save to JSON
    output_file = f"test_plan_{story_key}_enhanced.json"
    test_plan_dict = {
        "story": {
            "key": test_plan.story.key,
            "summary": test_plan.story.summary,
            "description": test_plan.story.description,
            "status": test_plan.story.status,
            "priority": test_plan.story.priority
        },
        "summary": test_plan.summary,
        "test_cases": [
            {
                "title": tc.title,
                "description": tc.description,
                "preconditions": tc.preconditions,
                "steps": [
                    {
                        "step_number": step.step_number,
                        "action": step.action,
                        "expected_result": step.expected_result,
                        "test_data": step.test_data
                    }
                    for step in tc.steps
                ],
                "expected_result": tc.expected_result,
                "priority": tc.priority,
                "test_type": tc.test_type,
                "tags": tc.tags,
                "automation_candidate": tc.automation_candidate,
                "estimated_time": tc.estimated_time,
                "risk_level": tc.risk_level,
                "related_existing_tests": tc.related_existing_tests
            }
            for tc in test_plan.test_cases
        ],
        "suggested_folder": test_plan.suggested_folder
    }
    
    with open(output_file, 'w') as f:
        json.dump(test_plan_dict, f, indent=2)
    
    logger.info(f"\n💾 Full test plan saved to: {output_file}")
    logger.info(f"   Suggested folder: {test_plan.suggested_folder}")
    
    logger.info("\n" + "=" * 80)
    logger.info("✅ Enhanced test generation completed successfully!")
    logger.info("=" * 80)
    
    logger.info("\n📤 Next steps:")
    logger.info(f"   1. Review the generated test plan")
    logger.info(f"   2. Upload to Zephyr: python3 upload_to_zephyr.py {story_key}")


if __name__ == "__main__":
    asyncio.run(test_story_key("PLAT-11907"))

