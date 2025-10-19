#!/usr/bin/env python3
"""
Automate test code generation from test plans.
Generates executable test code in customer's repository and creates PR.
"""

import asyncio
import json
import sys
from pathlib import Path
from loguru import logger

from src.automation.code_generator import TestCodeGenerator
from src.models.test_plan import TestPlan
from src.models.test_case import TestCase, TestStep
from src.models.story import JiraStory


async def main(
    story_key: str,
    repo_path: str,
    framework: str = "auto",
    ai_tool: str = "aider",
    create_pr: bool = True
):
    """
    Generate automated test code from test plan and create PR.

    Args:
        story_key: Jira story key (e.g., PLAT-12991)
        repo_path: Path to customer's automation repository
        framework: Test framework (auto, playwright, cypress, etc.)
        ai_tool: AI tool to use (aider or cursor)
        create_pr: Whether to automatically create PR
    """
    logger.info("=" * 80)
    logger.info(f"🤖 Womba Test Automation - {story_key}")
    logger.info("=" * 80)

    # Step 1: Load test plan from file
    test_plan_file = Path(f"test_plan_{story_key}.json")
    
    if not test_plan_file.exists():
        logger.error(f"Test plan file not found: {test_plan_file}")
        logger.info("Please generate test plan first:")
        logger.info(f"  womba generate {story_key}")
        sys.exit(1)

    logger.info(f"\n📄 Loading test plan from {test_plan_file}...")
    
    try:
        with open(test_plan_file) as f:
            test_plan_data = json.load(f)
        
        # Reconstruct TestPlan object from JSON
        test_plan = _reconstruct_test_plan(test_plan_data)
        logger.info(f"✅ Loaded {len(test_plan.test_cases)} test cases")
        
    except Exception as e:
        logger.error(f"Failed to load test plan: {e}")
        sys.exit(1)

    # Step 2: Initialize code generator
    logger.info(f"\n🔧 Initializing test code generator...")
    logger.info(f"   Repository: {repo_path}")
    logger.info(f"   Framework: {framework}")
    logger.info(f"   AI Tool: {ai_tool}")
    
    try:
        generator = TestCodeGenerator(
            repo_path=repo_path,
            framework=framework,
            ai_tool=ai_tool
        )
    except Exception as e:
        logger.error(f"Failed to initialize generator: {e}")
        sys.exit(1)

    # Step 3: Generate code and create PR
    logger.info(f"\n🚀 Generating test code...")
    logger.info("   This may take 2-5 minutes depending on:")
    logger.info("   - Number of test cases")
    logger.info("   - Repository size")
    logger.info("   - AI tool response time")
    logger.info("")
    
    try:
        result = await generator.generate_code(
            test_plan=test_plan,
            create_pr=create_pr
        )
        
        if not result:
            logger.error("❌ Failed to generate test code")
            sys.exit(1)
        
        logger.info("\n" + "=" * 80)
        
        if create_pr:
            logger.info(f"✅ SUCCESS! Pull Request created:")
            logger.info(f"   {result}")
            logger.info("")
            logger.info("📋 Next steps:")
            logger.info("   1. Review the generated test code")
            logger.info("   2. Run the tests locally")
            logger.info("   3. Approve and merge the PR")
        else:
            logger.info(f"✅ SUCCESS! Code generated on branch:")
            logger.info(f"   {result}")
            logger.info("")
            logger.info("📋 Next steps:")
            logger.info(f"   1. cd {repo_path}")
            logger.info(f"   2. git checkout {result}")
            logger.info("   3. Review and run the tests")
            logger.info("   4. Create PR manually if satisfied")
        
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"\n❌ Automation failed: {e}")
        logger.exception(e)
        sys.exit(1)


def _reconstruct_test_plan(data: dict) -> TestPlan:
    """Reconstruct TestPlan object from JSON data."""
    from src.models.test_plan import TestPlanMetadata
    from src.models.story import PriorityLevel, TestCaseType
    from datetime import datetime
    
    # Reconstruct story
    story_data = data.get("story", {})
    story = JiraStory(
        key=story_data.get("key", ""),
        summary=story_data.get("summary", ""),
        description=story_data.get("description"),
        issue_type=story_data.get("issue_type", "Story"),
        status=story_data.get("status", "Unknown"),
        priority=story_data.get("priority", "Medium"),
        assignee=story_data.get("assignee"),
        reporter=story_data.get("reporter", "unknown@example.com"),
        created=datetime.fromisoformat(story_data.get("created", datetime.utcnow().isoformat())),
        updated=datetime.fromisoformat(story_data.get("updated", datetime.utcnow().isoformat())),
        labels=story_data.get("labels", []),
        components=story_data.get("components", [])
    )
    
    # Reconstruct test cases
    test_cases = []
    for tc_data in data.get("test_cases", []):
        steps = [
            TestStep(
                step_number=step.get("step_number", idx + 1),
                action=step.get("action", ""),
                expected_result=step.get("expected_result", ""),
                test_data=step.get("test_data")
            )
            for idx, step in enumerate(tc_data.get("steps", []))
        ]
        
        test_case = TestCase(
            title=tc_data.get("title", ""),
            description=tc_data.get("description", ""),
            preconditions=tc_data.get("preconditions"),
            steps=steps,
            expected_result=tc_data.get("expected_result", ""),
            priority=PriorityLevel(tc_data.get("priority", "medium")),
            test_type=TestCaseType(tc_data.get("test_type", "functional")),
            tags=tc_data.get("tags", []),
            automation_candidate=tc_data.get("automation_candidate", True),
            risk_level=tc_data.get("risk_level", "medium"),
            estimated_time=tc_data.get("estimated_time")
        )
        test_cases.append(test_case)
    
    # Reconstruct metadata
    metadata = TestPlanMetadata(
        ai_model=data.get("metadata", {}).get("ai_model", "unknown"),
        source_story_key=story.key,
        total_test_cases=len(test_cases)
    )
    
    # Create TestPlan
    test_plan = TestPlan(
        story=story,
        test_cases=test_cases,
        metadata=metadata,
        summary=data.get("summary", ""),
        suggested_folder=data.get("suggested_folder")
    )
    
    return test_plan


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python automate_tests.py <STORY-KEY> <REPO-PATH> [framework] [ai-tool]")
        print("")
        print("Examples:")
        print("  python automate_tests.py PLAT-12991 /path/to/test/repo")
        print("  python automate_tests.py PLAT-12991 /path/to/test/repo playwright aider")
        print("  python automate_tests.py PLAT-12991 /path/to/test/repo auto cursor")
        sys.exit(1)
    
    story_key = sys.argv[1]
    repo_path = sys.argv[2]
    framework = sys.argv[3] if len(sys.argv) > 3 else "auto"
    ai_tool = sys.argv[4] if len(sys.argv) > 4 else "aider"
    
    asyncio.run(main(story_key, repo_path, framework, ai_tool))

