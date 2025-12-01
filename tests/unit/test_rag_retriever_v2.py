"""
Unit tests for RAG Retriever - comprehensive test coverage.

Tests:
- Similarity threshold filtering
- Keyword re-ranking
- Document deduplication
- Long document summarization
- Collection retrieval
- Optimization pipeline
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from typing import List, Dict, Any

from src.ai.rag_retriever import RAGRetriever, RetrievedContext
from src.models.story import JiraStory


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def sample_story() -> JiraStory:
    """Create a sample Jira story for testing."""
    return JiraStory(
        key="TEST-123",
        summary="Implement tenant-level audit logging",
        description="Add audit logging for tenant-level operations including login events and administrative actions.",
        issue_type="Story",
        status="In Progress",
        priority="High",
        components=["PAP", "Audit"],
        labels=["audit", "security", "tenant"],
        acceptance_criteria="Audit records are created for login sessions",
        linked_issues=["TEST-100"],
    )


@pytest.fixture
def sample_docs() -> List[Dict[str, Any]]:
    """Create sample documents for testing."""
    return [
        {
            "document": "This is a highly relevant document about audit logging and tenant management.",
            "metadata": {"title": "Audit Guide", "source_type": "confluence_docs"},
            "distance": 0.15,  # High similarity (1 - 0.15 = 0.85)
            "similarity": 0.85,
        },
        {
            "document": "This document is about something completely unrelated to the query.",
            "metadata": {"title": "Unrelated Doc", "source_type": "confluence_docs"},
            "distance": 0.45,  # Low similarity (1 - 0.45 = 0.55)
            "similarity": 0.55,
        },
        {
            "document": "Another relevant document discussing audit events and logging mechanisms.",
            "metadata": {"title": "Logging Best Practices", "source_type": "confluence_docs"},
            "distance": 0.20,  # Good similarity (1 - 0.20 = 0.80)
            "similarity": 0.80,
        },
        {
            "document": "This is a duplicate of the audit logging document with minor differences.",
            "metadata": {"title": "Audit Guide Copy", "source_type": "confluence_docs"},
            "distance": 0.16,  # High similarity
            "similarity": 0.84,
        },
    ]


@pytest.fixture
def long_doc() -> Dict[str, Any]:
    """Create a long document for summarization testing."""
    long_text = "This is a test document about audit logging. " * 200  # ~10K chars
    return {
        "document": long_text,
        "metadata": {"title": "Long Doc"},
        "distance": 0.10,
        "similarity": 0.90,
    }


@pytest.fixture
def rag_retriever() -> RAGRetriever:
    """Create a RAG retriever instance."""
    with patch('src.ai.rag_retriever.RAGVectorStore'):
        retriever = RAGRetriever()
        return retriever


# ============================================================================
# SIMILARITY FILTERING TESTS
# ============================================================================

class TestSimilarityFiltering:
    """Tests for similarity threshold filtering."""
    
    def test_filter_by_similarity_removes_low_scores(
        self,
        rag_retriever: RAGRetriever,
        sample_docs: List[Dict[str, Any]],
    ):
        """Test that low similarity docs are filtered out."""
        # Default threshold is 0.75
        filtered = rag_retriever.filter_by_similarity(sample_docs)
        
        # Should keep only docs with similarity >= 0.75
        assert len(filtered) == 3  # 0.85, 0.80, 0.84 pass; 0.55 fails
        
        for doc in filtered:
            assert doc.get('similarity', 0) >= 0.75
    
    def test_filter_by_similarity_custom_threshold(
        self,
        rag_retriever: RAGRetriever,
        sample_docs: List[Dict[str, Any]],
    ):
        """Test filtering with custom threshold."""
        # Use higher threshold
        filtered = rag_retriever.filter_by_similarity(sample_docs, min_similarity=0.82)
        
        # Should keep only docs with similarity >= 0.82
        assert len(filtered) == 2  # 0.85 and 0.84 pass
    
    def test_filter_by_similarity_empty_list(self, rag_retriever: RAGRetriever):
        """Test filtering with empty document list."""
        filtered = rag_retriever.filter_by_similarity([])
        assert filtered == []
    
    def test_filter_by_similarity_all_pass(self, rag_retriever: RAGRetriever):
        """Test when all docs pass the threshold."""
        high_sim_docs = [
            {"document": "Doc 1", "similarity": 0.95},
            {"document": "Doc 2", "similarity": 0.90},
            {"document": "Doc 3", "similarity": 0.85},
        ]
        
        filtered = rag_retriever.filter_by_similarity(high_sim_docs)
        assert len(filtered) == 3
    
    def test_filter_by_similarity_none_pass(self, rag_retriever: RAGRetriever):
        """Test when no docs pass the threshold."""
        low_sim_docs = [
            {"document": "Doc 1", "similarity": 0.50},
            {"document": "Doc 2", "similarity": 0.60},
        ]
        
        filtered = rag_retriever.filter_by_similarity(low_sim_docs)
        assert len(filtered) == 0


# ============================================================================
# KEYWORD RE-RANKING TESTS
# ============================================================================

class TestKeywordReranking:
    """Tests for keyword-based re-ranking."""
    
    def test_rerank_by_keywords_boosts_relevant(
        self,
        rag_retriever: RAGRetriever,
    ):
        """Test that keyword matching boosts document scores."""
        docs = [
            {"document": "Document about cats and dogs", "similarity": 0.80},
            {"document": "Document about audit logging and security", "similarity": 0.75},
            {"document": "Document about random topics", "similarity": 0.85},
        ]
        
        keywords = ["audit", "logging", "security"]
        
        reranked = rag_retriever.rerank_by_keywords(docs, keywords)
        
        # Doc with matching keywords should be boosted to top
        assert "audit" in reranked[0]["document"].lower()
    
    def test_rerank_by_keywords_empty_keywords(
        self,
        rag_retriever: RAGRetriever,
        sample_docs: List[Dict[str, Any]],
    ):
        """Test re-ranking with empty keyword list."""
        original_order = [d["document"] for d in sample_docs]
        reranked = rag_retriever.rerank_by_keywords(sample_docs, [])
        
        # Order should be unchanged
        assert [d["document"] for d in reranked] == original_order
    
    def test_rerank_by_keywords_preserves_docs(
        self,
        rag_retriever: RAGRetriever,
        sample_docs: List[Dict[str, Any]],
    ):
        """Test that re-ranking preserves all documents."""
        keywords = ["audit", "logging"]
        reranked = rag_retriever.rerank_by_keywords(sample_docs, keywords)
        
        assert len(reranked) == len(sample_docs)


# ============================================================================
# DEDUPLICATION TESTS
# ============================================================================

class TestDeduplication:
    """Tests for document deduplication."""
    
    def test_deduplicate_removes_similar_docs(self, rag_retriever: RAGRetriever):
        """Test that near-duplicate documents are removed."""
        docs = [
            {"document": "This is a document about audit logging for tenants."},
            {"document": "This is a document about audit logging for tenants."},  # Exact duplicate
            {"document": "Completely different document about something else."},
        ]
        
        unique = rag_retriever.deduplicate_docs(docs)
        
        # Should remove exact duplicate
        assert len(unique) == 2
    
    def test_deduplicate_keeps_different_docs(self, rag_retriever: RAGRetriever):
        """Test that different documents are kept."""
        docs = [
            {"document": "Document about audit logging and security features."},
            {"document": "Document about user authentication and sessions."},
            {"document": "Document about API endpoints and REST services."},
        ]
        
        unique = rag_retriever.deduplicate_docs(docs)
        
        # All should be kept (different content)
        assert len(unique) == 3
    
    def test_deduplicate_empty_list(self, rag_retriever: RAGRetriever):
        """Test deduplication with empty list."""
        unique = rag_retriever.deduplicate_docs([])
        assert unique == []
    
    def test_deduplicate_single_doc(self, rag_retriever: RAGRetriever):
        """Test deduplication with single document."""
        docs = [{"document": "Single document"}]
        unique = rag_retriever.deduplicate_docs(docs)
        assert len(unique) == 1


# ============================================================================
# DOCUMENT SUMMARIZATION TESTS
# ============================================================================

class TestDocumentSummarization:
    """Tests for long document summarization."""
    
    def test_summarize_long_docs_truncates(
        self,
        rag_retriever: RAGRetriever,
        long_doc: Dict[str, Any],
    ):
        """Test that long documents are truncated."""
        docs = [long_doc]
        summarized = rag_retriever._summarize_long_docs(docs)
        
        # Should be truncated
        assert len(summarized[0]["document"]) < len(long_doc["document"])
        assert len(summarized[0]["document"]) <= rag_retriever.max_doc_chars + 100  # Allow some buffer
        assert summarized[0].get("was_summarized", False) is True
    
    def test_summarize_short_docs_unchanged(self, rag_retriever: RAGRetriever):
        """Test that short documents are unchanged."""
        short_doc = {"document": "This is a short document."}
        summarized = rag_retriever._summarize_long_docs([short_doc])
        
        assert summarized[0]["document"] == short_doc["document"]
        assert summarized[0].get("was_summarized") is None or summarized[0].get("was_summarized") is False
    
    def test_summarize_ends_at_sentence_boundary(
        self,
        rag_retriever: RAGRetriever,
    ):
        """Test that summarization tries to end at sentence boundary."""
        # Create doc that will be truncated
        doc = {"document": "First sentence. " * 300 + "Last sentence."}
        summarized = rag_retriever._summarize_long_docs([doc])
        
        # Should end with period or truncation marker
        text = summarized[0]["document"]
        assert text.rstrip().endswith('.') or text.endswith(']')


# ============================================================================
# KEYWORD EXTRACTION TESTS
# ============================================================================

class TestKeywordExtraction:
    """Tests for keyword extraction from stories."""
    
    def test_extract_keywords_from_story(
        self,
        rag_retriever: RAGRetriever,
        sample_story: JiraStory,
    ):
        """Test keyword extraction from story."""
        keywords = rag_retriever.extract_keywords(sample_story)
        
        # Should extract meaningful keywords
        assert len(keywords) > 0
        assert len(keywords) <= 15  # Max 15 keywords
        
        # Should include words from summary
        assert any("audit" in kw.lower() for kw in keywords)
    
    def test_extract_keywords_includes_components(
        self,
        rag_retriever: RAGRetriever,
        sample_story: JiraStory,
    ):
        """Test that component names are included in keywords."""
        keywords = rag_retriever.extract_keywords(sample_story)
        
        # Components should be in keywords
        assert any("pap" in kw.lower() for kw in keywords)
    
    def test_extract_keywords_includes_labels(
        self,
        rag_retriever: RAGRetriever,
        sample_story: JiraStory,
    ):
        """Test that labels are included in keywords."""
        keywords = rag_retriever.extract_keywords(sample_story)
        
        # Labels should be in keywords
        assert any(kw in ["audit", "security", "tenant"] for kw in keywords)


# ============================================================================
# OPTIMIZATION PIPELINE TESTS
# ============================================================================

class TestOptimizationPipeline:
    """Tests for the full optimization pipeline."""
    
    def test_optimize_docs_applies_all_steps(
        self,
        rag_retriever: RAGRetriever,
        sample_docs: List[Dict[str, Any]],
    ):
        """Test that optimization applies all steps."""
        keywords = ["audit", "logging"]
        
        optimized = rag_retriever._optimize_docs(
            docs=sample_docs,
            keywords=keywords,
            max_docs=2,
            collection_name="test_collection"
        )
        
        # Should return limited number of docs
        assert len(optimized) <= 2
        
        # All should pass similarity threshold
        for doc in optimized:
            assert doc.get('similarity', 0) >= rag_retriever.min_similarity
    
    def test_optimize_docs_empty_input(self, rag_retriever: RAGRetriever):
        """Test optimization with empty input."""
        optimized = rag_retriever._optimize_docs(
            docs=[],
            keywords=["test"],
            max_docs=5,
            collection_name="test"
        )
        
        assert optimized == []
    
    def test_optimize_docs_respects_max_docs(
        self,
        rag_retriever: RAGRetriever,
    ):
        """Test that max_docs limit is respected."""
        # Create many high-quality docs
        docs = [
            {"document": f"Document {i} about audit logging", "similarity": 0.90}
            for i in range(10)
        ]
        
        optimized = rag_retriever._optimize_docs(
            docs=docs,
            keywords=["audit"],
            max_docs=3,
            collection_name="test"
        )
        
        assert len(optimized) <= 3


# ============================================================================
# RETRIEVED CONTEXT TESTS
# ============================================================================

class TestRetrievedContext:
    """Tests for RetrievedContext dataclass."""
    
    def test_has_context_true(self):
        """Test has_context returns True when context exists."""
        context = RetrievedContext(
            similar_test_plans=[{"document": "test"}],
            similar_confluence_docs=[],
            similar_jira_stories=[],
            similar_existing_tests=[],
        )
        
        assert context.has_context() is True
    
    def test_has_context_false(self):
        """Test has_context returns False when no context."""
        context = RetrievedContext(
            similar_test_plans=[],
            similar_confluence_docs=[],
            similar_jira_stories=[],
            similar_existing_tests=[],
        )
        
        assert context.has_context() is False
    
    def test_get_summary(self):
        """Test summary generation."""
        context = RetrievedContext(
            similar_test_plans=[{"doc": "1"}, {"doc": "2"}],
            similar_confluence_docs=[{"doc": "1"}],
            similar_jira_stories=[],
            similar_existing_tests=[{"doc": "1"}, {"doc": "2"}, {"doc": "3"}],
        )
        
        summary = context.get_summary()
        
        assert "2 test plans" in summary
        assert "1 docs" in summary
        assert "3 existing tests" in summary


# ============================================================================
# TEXT SIMILARITY TESTS
# ============================================================================

class TestTextSimilarity:
    """Tests for text similarity calculation."""
    
    def test_text_similarity_identical(self, rag_retriever: RAGRetriever):
        """Test similarity of identical texts."""
        text = "This is a test document"
        similarity = rag_retriever._text_similarity(text, text)
        
        assert similarity == 1.0
    
    def test_text_similarity_different(self, rag_retriever: RAGRetriever):
        """Test similarity of different texts."""
        text1 = "This is about cats and dogs"
        text2 = "This is about cars and planes"
        
        similarity = rag_retriever._text_similarity(text1, text2)
        
        # Should have some overlap ("This is about")
        assert 0 < similarity < 1
    
    def test_text_similarity_empty(self, rag_retriever: RAGRetriever):
        """Test similarity with empty text."""
        similarity = rag_retriever._text_similarity("", "some text")
        assert similarity == 0.0
        
        similarity = rag_retriever._text_similarity("some text", "")
        assert similarity == 0.0

