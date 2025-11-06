"""
Regression test for PLAT-13541 quality.

This test validates that the specific story PLAT-13541 maintains quality standards.
Run this test regularly to catch regressions.
"""

import pytest
from pathlib import Path
import json

from src.aggregator.story_collector import StoryCollector
from src.ai.story_enricher import StoryEnricher
from src.ai.test_plan_generator import TestPlanGenerator


@pytest.mark.asyncio
async def test_plat_13541_enrichment_quality():
    """Regression test for PLAT-13541 enrichment quality."""
    collector = StoryCollector()
    context = await collector.collect_story_context('PLAT-13541')
    
    enricher = StoryEnricher()
    enriched = await enricher.enrich_story(context.main_story, context)
    
    # Story-specific validations
    assert enriched.story_key == 'PLAT-13541'
    assert len(enriched.feature_narrative) > 1500, \
        f"Narrative should be detailed, got {len(enriched.feature_narrative)} chars"
    assert len(enriched.acceptance_criteria) >= 4, \
        f"Should have 4+ ACs, got {len(enriched.acceptance_criteria)}"
    assert len(enriched.functional_points) >= 6, \
        f"Should have 6+ functional points, got {len(enriched.functional_points)}"
    
    # API story - must have API specs
    assert len(enriched.api_specifications) >= 1, \
        "API story should have extracted API endpoints"
    
    # Verify specific endpoints
    endpoint_paths = [api.endpoint_path for api in enriched.api_specifications]
    assert any('policy-mgmt' in ep for ep in endpoint_paths), \
        f"Should have policy-mgmt endpoint, got {endpoint_paths}"
    
    # Check HTTP methods are captured
    for api in enriched.api_specifications:
        assert api.http_methods, f"Should have HTTP methods for {api.endpoint_path}"
        assert api.http_methods != ["(see story for method)"], \
            f"Should extract actual method, not placeholder for {api.endpoint_path}"


@pytest.mark.asyncio
async def test_plat_13541_test_generation_quality():
    """Regression test for PLAT-13541 test plan quality."""
    # Use cached test plan if available, otherwise generate
    test_plan_path = Path('test_plans/test_plan_PLAT-13541.json')
    
    if not test_plan_path.exists():
        # Generate test plan
        collector = StoryCollector()
        context = await collector.collect_story_context('PLAT-13541')
        
        generator = TestPlanGenerator(use_openai=True)
        test_plan = await generator.generate_test_plan(context)
    else:
        # Load existing
        import json
        with open(test_plan_path) as f:
            plan_data = json.load(f)
        test_plan = plan_data
    
    tests = test_plan.get('test_cases') if isinstance(test_plan, dict) else test_plan.test_cases
    
    # Test count should be appropriate (6-15 for this story complexity)
    assert 6 <= len(tests) <= 15, \
        f"Should have 6-15 tests for this story, got {len(tests)}"
    
    # Frontend/backend balance (UI + API story)
    api_tests = [t for t in tests if 'API' in t.get('tags', [])]
    ui_tests = [t for t in tests if 'UI' in t.get('tags', [])]
    
    assert len(ui_tests) >= 2, \
        f"UI story should have UI tests, got {len(ui_tests)}"
    assert len(api_tests) >= 3, \
        f"API story should have API tests, got {len(api_tests)}"
    
    # API tests must include endpoints
    for test in api_tests[:5]:
        steps = test.get('steps', [])
        has_endpoint = any('/policy-mgmt' in step.get('action', '') or '/api/' in step.get('action', '') 
                          for step in steps)
        assert has_endpoint, \
            f"API test '{test.get('title')}' should include endpoint in steps"
    
    # All tests should map to ACs or functional points
    for test in tests:
        desc = test.get('description', '').lower()
        # Should mention specific features from story
        story_terms = ['application', 'policy', 'list', 'paging', 'link', 'unlink', 'permission', 'audit']
        has_story_term = any(term in desc for term in story_terms)
        assert has_story_term, \
            f"Test '{test.get('title')}' should reference story-specific concepts"


def test_plat_13541_prompt_file_exists():
    """Test that prompt debug file was created."""
    prompt_path = Path('debug_prompts/prompt_PLAT-13541.txt')
    assert prompt_path.exists(), "Prompt debug file should be created"
    
    # Check prompt size
    prompt_text = prompt_path.read_text()
    assert len(prompt_text) > 50000, \
        f"Prompt should be substantial, got {len(prompt_text)} chars"
    assert len(prompt_text) < 200000, \
        f"Prompt should not be too large, got {len(prompt_text)} chars"
    
    # Check key sections present
    assert '--- API SPECIFICATIONS' in prompt_text, "Should have API specifications section"
    assert '--- ACCEPTANCE CRITERIA' in prompt_text, "Should have AC section"
    assert '--- FUNCTIONALITY TO TEST' in prompt_text, "Should have functional points"
    
    # Check truncation
    ellipsis_count = prompt_text.count('...')
    assert ellipsis_count <= 5, \
        f"Should have minimal truncations, found {ellipsis_count}"

