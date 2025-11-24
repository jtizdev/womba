"""
Integration tests for RAG enrichment quality.

Validates that:
- Confluence docs are indexed without truncation
- RAG retrieval works correctly  
- Prompts include RAG content
- Enrichment has zero truncations
- Acceptance criteria extracted correctly
"""

import pytest
import asyncio
from pathlib import Path

from src.ai.rag_store import RAGVectorStore
from src.ai.context_indexer import ContextIndexer
from src.ai.story_enricher import StoryEnricher
from src.aggregator.story_collector import StoryCollector, StoryContext
from src.models.story import JiraStory
from datetime import datetime


@pytest.mark.asyncio
async def test_confluence_indexing_no_truncation():
    """Test that Confluence docs are indexed with full content, no truncation."""
    # Create a sample Confluence doc
    sample_doc = {
        'id': 'test_page_123',
        'title': 'Test PRD Document',
        'content': 'This is a test PRD with requirements. ' * 100,  # 4000+ chars
        'space': 'TEST',
        'url': '/spaces/TEST/pages/123',
        'last_modified': '2025-11-06T00:00:00Z'
    }
    
    # Index it
    indexer = ContextIndexer()
    await indexer.index_confluence_docs([sample_doc], project_key='TEST')
    
    # Retrieve from RAG
    store = RAGVectorStore()
    results = await store.retrieve_similar(
        collection_name='confluence_docs',
        query_text='Test PRD requirements',
        top_k=1,
        metadata_filter={'project_key': 'TEST'}
    )
    
    assert len(results) > 0, "Should retrieve the indexed doc"
    
    retrieved_content = results[0].get('document', '')
    assert len(retrieved_content) > 100, f"Content should not be empty, got {len(retrieved_content)} chars"
    assert 'requirements' in retrieved_content.lower(), "Should contain actual content"
    assert len(retrieved_content) > 3000, f"Should have substantial content, got {len(retrieved_content)} chars"


@pytest.mark.asyncio
async def test_rag_retrieval_for_story():
    """Test that RAG retrieves docs for a story with good similarity."""
    from src.ai.rag_retriever import RAGRetriever
    from src.models.story import JiraStory
    
    # Create a story about Policy 360
    story = JiraStory(
        key='TEST-123',
        summary='Policy 360 Vendor Compare improvements',
        description='Enhance the vendor compare view for policy management',
        issue_type='Story',
        status='Open',
        priority='High',
        reporter='test@example.com',
        created=datetime.utcnow(),
        updated=datetime.utcnow()
    )
    
    retriever = RAGRetriever()
    context = await retriever.retrieve_for_story(story, project_key='PLAT')
    
    # Should retrieve Confluence docs
    assert context.similar_confluence_docs is not None, "Should attempt to retrieve Confluence docs"
    assert len(context.similar_confluence_docs) > 0, "Should retrieve at least 1 doc for Policy 360 topic"
    
    # Check similarity scores
    for doc in context.similar_confluence_docs[:3]:
        similarity = 1 - doc.get('distance', 1.0)
        assert similarity > 0.3, f"Similarity should be reasonable, got {similarity}"


@pytest.mark.asyncio
async def test_prompt_includes_rag_content():
    """Test that generated prompts include RAG content when available."""
    from src.ai.test_plan_generator import TestPlanGenerator
    from src.aggregator.story_collector import StoryCollector
    
    # Collect context for a real story
    collector = StoryCollector()
    context = await collector.collect_story_context('PROJ-15596')
    
    # Generate with RAG enabled
    generator = TestPlanGenerator(use_openai=True)
    
    # Build prompt (don't call AI)
    rag_context = await generator._retrieve_rag_context(
        context.main_story,
        context,
        use_rag=True
    )
    
    assert rag_context is not None, "Should retrieve RAG context"
    assert len(rag_context) > 1000, f"RAG context should be substantial, got {len(rag_context)} chars"
    assert "COMPANY DOCUMENTATION" in rag_context or "RETRIEVED CONTEXT" in rag_context
    assert "Policy" in rag_context, "Should contain policy-related content"


@pytest.mark.asyncio
async def test_enrichment_no_truncation():
    """Test that enrichment includes all subtasks without truncation."""
    collector = StoryCollector()
    context = await collector.collect_story_context('PROJ-15596')
    
    enricher = StoryEnricher()
    enriched = await enricher.enrich_story(context.main_story, context)
    
    # Check narrative includes all subtasks
    subtasks = context.get('subtasks', [])
    assert len(subtasks) == 36, f"Test story should have 36 subtasks, got {len(subtasks)}"
    
    # Check narrative doesn't have truncation marker
    assert '... and' not in enriched.feature_narrative or 'more tasks' not in enriched.feature_narrative, \
        "Narrative should not truncate subtasks"
    
    # Check narrative is substantial
    assert len(enriched.feature_narrative) > 2000, \
        f"Narrative should be detailed, got {len(enriched.feature_narrative)} chars"
    
    # Check functional points derived
    assert len(enriched.functional_points) > 15, \
        f"Should derive many functional points, got {len(enriched.functional_points)}"


@pytest.mark.asyncio
async def test_acceptance_criteria_extraction():
    """Test that acceptance criteria are extracted correctly, not corrupted."""
    collector = StoryCollector()
    context = await collector.collect_story_context('PROJ-15596')
    
    story = context.main_story
    
    # Should have real acceptance criteria, not field ID
    assert story.acceptance_criteria is not None, "Should have AC"
    assert len(story.acceptance_criteria) > 50, \
        f"AC should be substantial text, got {len(story.acceptance_criteria)} chars"
    assert 'customfield' not in story.acceptance_criteria.lower(), \
        "Should not contain field ID garbage"
    assert 'behavior validated' in story.acceptance_criteria or 'validation' in story.acceptance_criteria.lower(), \
        "Should contain actual acceptance criteria text"


def test_rag_database_not_empty():
    """Test that RAG database has been populated."""
    store = RAGVectorStore()
    
    # Check confluence_docs collection
    confluence_collection = store.get_or_create_collection('confluence_docs')
    confluence_count = confluence_collection.count()
    
    assert confluence_count > 100, \
        f"Should have indexed many Confluence docs, got {confluence_count}"


@pytest.mark.asyncio
async def test_prd_content_quality_in_enrichment():
    """Test that PRD content in enrichment is meaningful, not just URLs."""
    collector = StoryCollector()
    context = await collector.collect_story_context('PROJ-15596')
    
    enricher = StoryEnricher()
    enriched = await enricher.enrich_story(context.main_story, context)
    
    # Should have Confluence docs
    assert len(enriched.confluence_docs) > 0, "Should have PRD/Confluence docs"
    
    prd = enriched.confluence_docs[0]
    assert prd.title is not None, "Should have title"
    assert prd.url is not None, "Should have URL"
    
    # Critical: Should have QA summary with real content
    if prd.qa_summary:
        assert len(prd.qa_summary) > 500, \
            f"PRD QA summary should be substantial, got {len(prd.qa_summary)} chars"
        assert 'policy' in prd.qa_summary.lower(), "Should mention policy concepts"
        assert 'requirement' in prd.qa_summary.lower() or 'feature' in prd.qa_summary.lower(), \
            "Should include requirements or features"

