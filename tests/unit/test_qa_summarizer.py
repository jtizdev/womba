"""
Unit tests for QA summarizer.

Tests that PRD content is summarized without excessive truncation.
"""

import pytest
from src.ai.qa_summarizer import summarize_for_qa, _collect_priority_lines


def test_summarize_for_qa_no_excessive_truncation():
    """Test that summarizer uses most of the available space without excessive truncation."""
    # Create a large PRD-like content (10KB)
    prd_content = """
    Summary: This is a comprehensive product requirements document.
    
    Problem Statement: Users face challenges with authorization management.
    The current system is fragmented and lacks visibility.
    
    Solution: We will implement a new interface that provides comprehensive views.
    
    Requirements:
    - Must support policy visualization
    - Must display synchronization status
    - Must enable reconciliation operations
    - Must handle large datasets
    - Must provide drag-and-drop functionality
    - Must support zoom and pan controls
    """ * 50  # Repeat to make it ~10KB
    
    summary = summarize_for_qa(story_summary=None, content=prd_content, max_chars=8000)
    
    # Should produce substantial summary (overview + bullets, not full 8K)
    assert len(summary) > 1500, f"Should produce substantial summary, got {len(summary)} chars"
    assert len(summary) <= 8100, f"Should respect max limit, got {len(summary)} chars"
    
    # Should include requirements
    assert 'requirement' in summary.lower() or 'must' in summary.lower()
    assert 'support' in summary.lower() or 'enable' in summary.lower()


def test_functional_points_derivation():
    """Test that functional points are extracted from description without URLs."""
    from src.ai.story_enricher import StoryEnricher
    from src.models.story import JiraStory
    from datetime import datetime
    
    description = """
    Feature Overview:
    Introducing Vendor compare view into policy 360.
    
    Capabilities:
    - Enable reconciliation operations
    - Support drag and drop for ordering
    - Implement zoom and pinch controls
    - Display policy synchronization status
    - Show vendor policy details
    
    Recording links:
    Share link: https://zoom.us/rec/share/ABC123
    
    More features:
    - Validate with large datasets
    - Update POP details via UI
    """
    
    story = JiraStory(
        key='TEST-123',
        summary='Vendor Compare View',
        description=description,
        issue_type='Story',
        status='Open',
        priority='High',
        reporter='test@example.com',
        created=datetime.utcnow(),
        updated=datetime.utcnow()
    )
    
    enricher = StoryEnricher()
    points = enricher._derive_functional_points(story, [], [])
    
    # Should extract functional points
    assert len(points) > 5, f"Should extract multiple points, got {len(points)}"
    
    # Should not include zoom recording links
    for point in points:
        assert 'zoom.us/rec' not in point.lower(), f"Should not include recording links: {point}"
        assert 'share link' not in point.lower(), f"Should not include share links: {point}"
    
    # Should include actual features
    features_found = sum(1 for p in points if any(
        term in p.lower() for term in ['reconciliation', 'drag', 'zoom', 'pinch', 'display', 'validate']
    ))
    assert features_found >= 3, f"Should find actual features, found {features_found}"


def test_collect_priority_lines():
    """Test that priority line collection finds requirement-oriented content."""
    content = """
    This is a general paragraph about the feature.
    
    Requirements:
    - System must validate user input
    - API should return 200 status code
    - Users must be able to create policies
    - Error handling is required for failures
    
    General notes that aren't requirements.
    """
    
    lines = _collect_priority_lines(content, limit=10)
    
    # Should find requirement lines
    assert len(lines) >= 3, f"Should find requirement lines, got {len(lines)}"
    
    # Should prioritize lines with must/should/required
    requirement_lines = [l for l in lines if any(
        word in l.lower() for word in ['must', 'should', 'required', 'validate', 'error']
    )]
    assert len(requirement_lines) >= 2, f"Should find requirement-oriented lines"

