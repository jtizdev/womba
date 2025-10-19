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


async def test_story_key(story_key: str, auto_upload: bool = False):
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
    
    # Step 2.5: Filter to top 50 most relevant tests (40% AI speedup) ⚡
    from src.utils.text_processor import extract_keywords, calculate_text_similarity
    
    logger.info("🔍 Filtering to top 50 most relevant tests...")
    story_text = f"{context.main_story.summary} {context.main_story.description}"
    
    # Score each test by relevance
    scored_tests = []
    for test in existing_tests:
        test_text = f"{test.get('name', '')} {test.get('objective', '') or ''}"
        similarity = calculate_text_similarity(story_text, test_text)
        scored_tests.append((similarity, test))
    
    # Sort by score and take top 50
    scored_tests.sort(reverse=True, key=lambda x: x[0])
    relevant_tests = [test for score, test in scored_tests[:50] if score > 0]
    
    logger.info(f"✅ Filtered to {len(relevant_tests)} most relevant tests (from {len(existing_tests)})")
    
    # Step 3: Get folder structure
    folder_structure = await zephyr.get_folder_structure(project_key)
    logger.info(f"✅ Found {len(folder_structure)} test folders")
    
    # Step 4: Generate test plan with FILTERED context (40% faster)
    logger.info(f"\n🤖 Step 3: Generating test plan with AI...")
    logger.info("   Using context from:")
    logger.info(f"   - Story + {len(context.get('subtasks', []))} subtasks")
    logger.info(f"   - {len(context.get('confluence_docs', []))} Confluence docs")
    logger.info(f"   - {len(relevant_tests)} relevant Zephyr tests (filtered from {len(existing_tests)})")
    logger.info(f"   - {len(folder_structure)} Zephyr folders")
    
    generator = TestPlanGenerator(use_openai=True)
    test_plan = await generator.generate_test_plan(
        context=context,
        existing_tests=relevant_tests,  # Use only top 50 relevant tests ⚡
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
    
    # Interactive upload prompt (unless auto_upload is True)
    if not auto_upload:
        print("\n")
        print("=" * 80)
        print(f"📋 Generated {len(test_plan.test_cases)} test cases for {story_key}")
        print("=" * 80)
        print("")
        
        # Show brief summary of test cases
        for i, tc in enumerate(test_plan.test_cases, 1):
            priority_icon = {
                "critical": "🔴",
                "high": "🟠",
                "medium": "🟡",
                "low": "⚪"
            }.get(str(tc.priority), "⚪")
            
            type_icon = {
                "functional": "⚙️",
                "integration": "🔗",
                "negative": "❌",
                "regression": "🔄",
                "ui": "🖥️",
                "api": "📡"
            }.get(str(tc.test_type), "✅")
            
            print(f"{i}. {priority_icon} {type_icon} {tc.title}")
            print(f"   Priority: {tc.priority} | Type: {tc.test_type} | Steps: {len(tc.steps)}")
        
        print("")
        print("=" * 80)
        upload_choice = input("📤 Upload these test cases to Zephyr? (y/n): ").lower().strip()
        
        if upload_choice in ['y', 'yes']:
            print("\n🚀 Uploading to Zephyr...")
            print("This may take 30-60 seconds...")
            print("")
            
            # Upload to Zephyr
            try:
                from upload_to_zephyr import upload_test_plan
                
                result = await upload_test_plan(
                    test_plan_file=output_file,
                    project_key=project_key,
                    story_key=story_key,
                    dry_run=False
                )
                
                print("")
                print("=" * 80)
                print("✅ Successfully uploaded to Zephyr!")
                print("=" * 80)
                print(f"📊 Uploaded test cases:")
                
                if 'zephyr_ids' in result:
                    for i, zephyr_id in enumerate(result['zephyr_ids'], 1):
                        print(f"   {i}. {zephyr_id}")
                
                print("")
                print(f"🔗 View in Zephyr: https://plainid.atlassian.net/browse/{story_key}")
                print("")
                
            except Exception as e:
                logger.error(f"Failed to upload to Zephyr: {e}")
                print(f"\n❌ Upload failed: {e}")
                print(f"\nYou can upload manually later with:")
                print(f"   womba upload {story_key}")
        else:
            print("\n⏭️  Skipping upload. You can upload later with:")
            print(f"   womba upload {story_key}")
            print("")
    else:
        # Auto-upload mode (from CLI --upload flag)
        logger.info("\n📤 Auto-uploading to Zephyr...")
        try:
            from upload_to_zephyr import upload_test_plan
            
            result = await upload_test_plan(
                test_plan_file=output_file,
                project_key=project_key,
                story_key=story_key,
                dry_run=False
            )
            
            logger.info("✅ Successfully uploaded to Zephyr!")
            if 'zephyr_ids' in result:
                logger.info(f"   Zephyr IDs: {', '.join(result['zephyr_ids'])}")
        except Exception as e:
            logger.error(f"Failed to upload to Zephyr: {e}")


if __name__ == "__main__":
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Generate AI-powered test plan for a Jira story"
    )
    parser.add_argument('story_key', help='Jira story key (e.g., PLAT-12991)')
    parser.add_argument(
        '--yes', '-y',
        action='store_true',
        help='Auto-upload to Zephyr without prompting'
    )
    
    args = parser.parse_args()
    
    asyncio.run(test_story_key(args.story_key, auto_upload=args.yes))

