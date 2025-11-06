"""
Unit tests for story enricher.

Tests narrative generation and functional point extraction.
"""

import pytest
from src.ai.story_enricher import StoryEnricher
from src.models.story import JiraStory
from src.aggregator.story_collector import StoryContext
from datetime import datetime


def test_narrative_includes_full_description():
    """Test that narrative includes full description without truncation."""
    # Create story with long description
    long_description = "This is a detailed description. " * 100  # ~3200 chars
    
    story = JiraStory(
        key='TEST-123',
        summary='Test Feature',
        description=long_description,
        issue_type='Story',
        status='Open',
        priority='High',
        reporter='test@example.com',
        created=datetime.utcnow(),
        updated=datetime.utcnow()
    )
    
    context = StoryContext(story)
    enricher = StoryEnricher()
    
    narrative = enricher._synthesize_narrative(
        main_story=story,
        linked_stories=[],
        story_context=context,
        plainid_components=[]
    )
    
    # Should include full description, not truncated to 800 chars
    assert len(narrative) > 2500, \
        f"Narrative should include full description, got {len(narrative)} chars"
    assert long_description[:1000] in narrative, \
        "Narrative should contain the full description text"


@pytest.mark.asyncio 
async def test_all_subtasks_in_narrative():
    """Test that narrative includes all subtasks without '... and X more' truncation."""
    # Create story
    story = JiraStory(
        key='TEST-123',
        summary='Large Feature',
        description='Feature with many subtasks',
        issue_type='Story',
        status='Open',
        priority='High',
        reporter='test@example.com',
        created=datetime.utcnow(),
        updated=datetime.utcnow()
    )
    
    # Create 40 subtasks
    subtasks = []
    for i in range(40):
        subtask = JiraStory(
            key=f'TEST-SUB-{i}',
            summary=f'Subtask {i}: Implement feature component {i}',
            description=f'Details for subtask {i}',
            issue_type='Sub-task',
            status='Open',
            priority='Medium',
            reporter='test@example.com',
            created=datetime.utcnow(),
            updated=datetime.utcnow()
        )
        subtasks.append(subtask)
    
    context = StoryContext(story)
    context['subtasks'] = subtasks
    
    enricher = StoryEnricher()
    narrative = enricher._synthesize_narrative(
        main_story=story,
        linked_stories=[],
        story_context=context,
        plainid_components=[]
    )
    
    # Should include all 40 subtasks
    assert '... and' not in narrative or 'more tasks' not in narrative, \
        "Should not truncate subtasks with '... and X more'"
    
    # Count how many subtasks are mentioned
    subtask_count = sum(1 for i in range(40) if f'Subtask {i}' in narrative)
    assert subtask_count == 40, \
        f"Should include all 40 subtasks, found {subtask_count}"


def test_functional_points_from_subtasks():
    """Test that functional points are derived from subtasks."""
    story = JiraStory(
        key='TEST-123',
        summary='Feature',
        description='Implement new capabilities',
        issue_type='Story',
        status='Open',
        priority='High',
        reporter='test@example.com',
        created=datetime.utcnow(),
        updated=datetime.utcnow()
    )
    
    subtasks = [
        JiraStory(
            key='TEST-1',
            summary='Implement user authentication',
            description='Add OAuth2 support',
            issue_type='Sub-task',
            status='Open',
            priority='Medium',
            reporter='test@example.com',
            created=datetime.utcnow(),
            updated=datetime.utcnow()
        ),
        JiraStory(
            key='TEST-2',
            summary='Create policy validation API',
            description='POST /api/policies/validate endpoint',
            issue_type='Sub-task',
            status='Open',
            priority='Medium',
            reporter='test@example.com',
            created=datetime.utcnow(),
            updated=datetime.utcnow()
        ),
    ]
    
    enricher = StoryEnricher()
    points = enricher._derive_functional_points(story, [], subtasks)
    
    # Should include subtasks as functional points
    assert len(points) >= 2, f"Should derive points from subtasks, got {len(points)}"
    assert any('authentication' in p.lower() for p in points), \
        "Should include authentication from subtask"
    assert any('validation' in p.lower() or 'api' in p.lower() for p in points), \
        "Should include API validation from subtask"


def test_plainid_component_extraction():
    """Test that PlainID components are correctly identified."""
    story = JiraStory(
        key='TEST-123',
        summary='PAP policy management enhancement',
        description='''
        This feature enhances the Policy Administration Point (PAP) interface.
        It integrates with the PDP for policy decisions and uses POPs for storage.
        Authorization happens in the Authorization Workspace.
        ''',
        issue_type='Story',
        status='Open',
        priority='High',
        reporter='test@example.com',
        created=datetime.utcnow(),
        updated=datetime.utcnow(),
        components=['PAP']
    )
    
    enricher = StoryEnricher()
    components = enricher._extract_plainid_components([story])
    
    # Should identify PlainID components
    assert 'PAP' in components or 'Policy Administration Point' in components
    assert len(components) >= 2, f"Should find multiple components, got {components}"

