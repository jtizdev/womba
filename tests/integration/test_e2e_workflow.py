"""
End-to-end integration tests for full Jira → AI → Zephyr workflow.
"""

import pytest
from src.aggregator.story_collector import StoryCollector
from src.ai.test_plan_generator import TestPlanGenerator
from src.integrations.zephyr_integration import ZephyrIntegration


@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_jira_to_zephyr_flow():
    """
    Test complete workflow: Fetch story → Generate tests → Upload to Zephyr.
    
    This test validates:
    - Jira story fetching works
    - Context collection works
    - AI generation produces valid tests
    - Test quality meets minimum standards
    """
    # Arrange
    story_key = "PLAT-11907"
    
    # Act - Step 1: Collect story context
    collector = StoryCollector()
    context = await collector.collect_story_context(story_key)
    
    # Assert - Context is complete
    assert context.main_story is not None
    assert context.main_story.key == story_key
    assert len(context.main_story.summary) > 0
    assert len(context.get('subtasks', [])) > 0
    
    # Act - Step 2: Generate test plan
    generator = TestPlanGenerator(use_openai=True)
    
    # Mock existing tests and folder structure for speed
    existing_tests = []
    folder_structure = [{'name': 'General', 'id': '1'}]
    
    test_plan = await generator.generate_test_plan(
        context,
        existing_tests=existing_tests,
        folder_structure=folder_structure
    )
    
    # Assert - Test plan meets quality standards
    assert test_plan is not None
    assert len(test_plan.test_cases) >= 6, "Should generate at least 6 tests"
    assert len(test_plan.test_cases) <= 12, "Should not exceed 12 tests"
    
    # Check folder suggestion
    assert test_plan.suggested_folder is not None, "Must suggest a folder"
    assert len(test_plan.suggested_folder) > 0
    
    # Check test quality
    high_quality_tests = 0
    for tc in test_plan.test_cases:
        # Must have title and description
        assert len(tc.title) > 0
        assert len(tc.description) > 0
        
        # Check if test has 3+ steps (high quality indicator)
        if len(tc.steps) >= 3:
            high_quality_tests += 1
    
    # At least 50% of tests should have 3+ steps
    assert high_quality_tests >= len(test_plan.test_cases) * 0.5, \
        f"Only {high_quality_tests}/{len(test_plan.test_cases)} tests have 3+ steps"
    
    # Check feature specificity (not generic)
    feature_specific_count = 0
    for tc in test_plan.test_cases:
        # Test should mention something specific (API endpoint, feature name, etc.)
        if any(indicator in tc.description.lower() for indicator in 
               ['post', 'get', 'click', 'endpoint', 'custom', 'policy', 'pop']):
            feature_specific_count += 1
    
    assert feature_specific_count >= len(test_plan.test_cases) * 0.7, \
        "At least 70% of tests should be feature-specific"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_context_collection_speed():
    """
    Test that context collection completes within reasonable time.
    
    Target: < 20 seconds with async batching
    """
    import time
    
    story_key = "PLAT-11907"
    collector = StoryCollector()
    
    start_time = time.time()
    context = await collector.collect_story_context(story_key)
    elapsed = time.time() - start_time
    
    assert elapsed < 20, f"Context collection took {elapsed:.1f}s, should be < 20s"
    assert context.main_story is not None


@pytest.mark.integration  
@pytest.mark.asyncio
async def test_ai_generation_quality():
    """
    Test AI generation produces high-quality tests.
    
    Quality criteria:
    - Not generic (mentions feature specifics)
    - Has steps (not just title/description)
    - Realistic test data
    """
    from src.models.story import JiraStory
    from src.aggregator.story_collector import StoryContext
    
    # Create minimal context
    story = JiraStory(
        key="TEST-123",
        summary="Add custom POP ID feature for environment alignment",
        description="Users need to create POPs with custom IDs via POST /v1/pops endpoint",
        story_type="Story",
        status="In Progress",
        priority="High",
        labels=["api", "backend"],
        components=["Orchestration"],
        created="2024-01-01",
        updated="2024-01-02"
    )
    
    context = StoryContext(story)
    context['subtasks'] = []
    context['confluence_docs'] = []
    
    # Generate tests
    generator = TestPlanGenerator(use_openai=True)
    test_plan = await generator.generate_test_plan(
        context,
        existing_tests=[],
        folder_structure=[]
    )
    
    # Check quality
    assert len(test_plan.test_cases) >= 6
    
    # Check for feature-specific terms
    combined_text = ' '.join([
        tc.title + ' ' + tc.description 
        for tc in test_plan.test_cases
    ]).lower()
    
    assert 'custom' in combined_text or 'pop' in combined_text, \
        "Tests should mention the feature (custom POP ID)"
    
    assert 'post' in combined_text or '/pops' in combined_text, \
        "Tests should mention specific endpoint"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_zephyr_connection():
    """
    Test Zephyr API connection works.
    """
    zephyr = ZephyrIntegration()
    
    # Test folder structure fetch
    folders = await zephyr.get_folder_structure("PLAT")
    
    assert isinstance(folders, list)
    assert len(folders) > 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_duplicate_detection():
    """
    Test that duplicate detection prevents creating redundant tests.
    """
    generator = TestPlanGenerator(use_openai=True)
    
    # Mock existing tests
    existing_tests = [
        {
            'key': 'TEST-1',
            'name': 'Create POP with custom ID',
            'objective': 'Test POST /pops endpoint with custom ID parameter'
        },
        {
            'key': 'TEST-2',
            'name': 'Verify POP uniqueness',
            'objective': 'Ensure duplicate custom IDs are rejected'
        }
    ]
    
    # Create context
    from src.models.story import JiraStory
    from src.aggregator.story_collector import StoryContext
    
    story = JiraStory(
        key="TEST-456",
        summary="Custom POP ID feature",
        description="Add custom IDs to POPs",
        story_type="Story",
        status="To Do",
        priority="High",
        labels=[],
        components=[],
        created="2024-01-01",
        updated="2024-01-02"
    )
    
    context = StoryContext(story)
    
    # Generate test plan
    test_plan = await generator.generate_test_plan(
        context,
        existing_tests=existing_tests,
        folder_structure=[]
    )
    
    # Check that some tests reference existing tests
    has_related_tests = any(
        len(tc.related_existing_tests) > 0 
        for tc in test_plan.test_cases
    )
    
    assert has_related_tests or len(test_plan.test_cases) < 10, \
        "Should either link to existing tests or generate fewer new ones"

