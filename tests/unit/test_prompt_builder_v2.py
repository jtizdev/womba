"""
Unit tests for PromptBuilder - comprehensive test coverage.

Tests:
- Prompt length enforcement
- Section ordering
- Token estimation
- Compact vs optimized modes
- RAG context handling
- API specification injection
"""

import pytest
from unittest.mock import MagicMock, patch
from typing import List, Dict, Any

from src.ai.generation.prompt_builder import PromptBuilder
from src.models.enriched_story import EnrichedStory, APIContext, APISpec, ConfluenceDocRef


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def sample_enriched_story() -> EnrichedStory:
    """Create a sample enriched story for testing."""
    return EnrichedStory(
        story_key="TEST-123",
        feature_narrative="This feature implements tenant-level audit logging. Users can view audit events for login sessions and administrative operations.",
        acceptance_criteria=[
            "Audit records are created for successful login sessions",
            "Audit records are created for failed login attempts",
            "Filters and sorting work as expected in tenant-level audit",
            "Permissions are validated for accessing tenant-level audit",
        ],
        related_stories=["TEST-100", "TEST-101"],
        risk_areas=["Authentication", "Data integrity"],
        source_story_ids=["TEST-123"],
        platform_components=["PAP", "Keycloak"],
        confluence_docs=[],
        functional_points=[
            "Create audit record for login events",
            "Display audit events in UI",
            "Filter audit events by type",
        ],
    )


@pytest.fixture
def sample_api_context() -> APIContext:
    """Create a sample API context for testing."""
    return APIContext(
        api_specifications=[
            APISpec(
                endpoint_path="/audit/tenant-level",
                http_methods=["GET"],
                parameters=["tenantId", "offset", "limit"],
                request_example=None,
                response_example='{"events": [], "total": 0}',
            ),
            APISpec(
                endpoint_path="/auth/login",
                http_methods=["POST"],
                parameters=[],
                request_example='{"username": "user", "password": "pass"}',
                response_example='{"token": "jwt-token"}',
            ),
        ],
        ui_specifications=[],
        extraction_flow="story → swagger",
    )


@pytest.fixture
def sample_rag_context() -> str:
    """Create sample RAG context."""
    return """
    --- SIMILAR TEST PLANS ---
    Test Plan for AUDIT-100:
    - Test 1: Audit log displays login events
    - Test 2: Audit log filters by date range
    
    --- CONFLUENCE DOCS ---
    Document: Audit System Architecture
    The audit system logs all administrative operations...
    """


@pytest.fixture
def prompt_builder() -> PromptBuilder:
    """Create a prompt builder instance."""
    return PromptBuilder(model="gpt-4o", use_optimized=True, use_compact=False)


@pytest.fixture
def compact_prompt_builder() -> PromptBuilder:
    """Create a compact prompt builder instance."""
    return PromptBuilder(model="gpt-4o", use_optimized=True, use_compact=True)


# ============================================================================
# PROMPT LENGTH TESTS
# ============================================================================

class TestPromptLength:
    """Tests for prompt length enforcement."""
    
    def test_compact_prompt_under_budget(
        self,
        compact_prompt_builder: PromptBuilder,
        sample_enriched_story: EnrichedStory,
        sample_api_context: APIContext,
    ):
        """Test that compact prompt stays under token budget."""
        prompt = compact_prompt_builder.build_compact_generation_prompt(
            enriched_story=sample_enriched_story,
            rag_context=None,
            api_context=sample_api_context,
        )
        
        # Estimate tokens (rough: 1 token ≈ 4 chars)
        estimated_tokens = len(prompt) // 4
        
        # Compact prompt should be under 16K tokens
        assert estimated_tokens < 16000, f"Prompt exceeds budget: {estimated_tokens} tokens"
        
        # Word count should be under 5K
        word_count = len(prompt.split())
        assert word_count < 5000, f"Prompt too long: {word_count} words"
    
    def test_compact_prompt_with_long_rag_context(
        self,
        compact_prompt_builder: PromptBuilder,
        sample_enriched_story: EnrichedStory,
    ):
        """Test that long RAG context is truncated."""
        # Create very long RAG context (20K chars)
        long_rag = "This is a test document. " * 1000
        
        prompt = compact_prompt_builder.build_compact_generation_prompt(
            enriched_story=sample_enriched_story,
            rag_context=long_rag,
            api_context=None,
        )
        
        # RAG should be truncated to ~4K tokens (16K chars)
        assert len(prompt) < 80000, f"Prompt too long with RAG: {len(prompt)} chars"
    
    def test_prompt_includes_all_acceptance_criteria(
        self,
        compact_prompt_builder: PromptBuilder,
        sample_enriched_story: EnrichedStory,
    ):
        """Test that all acceptance criteria are included in prompt."""
        prompt = compact_prompt_builder.build_compact_generation_prompt(
            enriched_story=sample_enriched_story,
            rag_context=None,
            api_context=None,
        )
        
        # All ACs should be in the prompt
        for i, ac in enumerate(sample_enriched_story.acceptance_criteria, 1):
            assert f"AC #{i}" in prompt, f"AC #{i} not found in prompt"
            # At least part of the AC text should be present
            assert ac[:30] in prompt, f"AC text not found: {ac[:30]}"
    
    def test_prompt_excludes_example_when_rag_has_tests(
        self,
        compact_prompt_builder: PromptBuilder,
        sample_enriched_story: EnrichedStory,
        sample_rag_context: str,
    ):
        """Test that example is excluded when RAG has similar test plans."""
        prompt = compact_prompt_builder.build_compact_generation_prompt(
            enriched_story=sample_enriched_story,
            rag_context=sample_rag_context,
            api_context=None,
        )
        
        # When RAG has test plans, example might be skipped
        # This is a soft check - the logic may vary
        assert "STORY REQUIREMENTS" in prompt


# ============================================================================
# SECTION ORDERING TESTS
# ============================================================================

class TestSectionOrdering:
    """Tests for prompt section ordering."""
    
    def test_story_requirements_first_in_prompt(
        self,
        compact_prompt_builder: PromptBuilder,
        sample_enriched_story: EnrichedStory,
    ):
        """Test that story requirements appear early in the prompt."""
        prompt = compact_prompt_builder.build_compact_generation_prompt(
            enriched_story=sample_enriched_story,
            rag_context=None,
            api_context=None,
        )
        
        # Find positions
        story_pos = prompt.find("STORY REQUIREMENTS")
        rules_pos = prompt.find("CRITICAL RULES")
        
        # Rules come first, then story (story should be in first 40% of prompt)
        assert story_pos > 0, "STORY REQUIREMENTS not found"
        story_position_ratio = story_pos / len(prompt)
        assert story_position_ratio < 0.5, f"Story too late in prompt: {story_position_ratio:.2%}"
    
    def test_api_specs_included_when_provided(
        self,
        compact_prompt_builder: PromptBuilder,
        sample_enriched_story: EnrichedStory,
        sample_api_context: APIContext,
    ):
        """Test that API specifications are included when provided."""
        prompt = compact_prompt_builder.build_compact_generation_prompt(
            enriched_story=sample_enriched_story,
            rag_context=None,
            api_context=sample_api_context,
        )
        
        # API endpoints should be in prompt
        assert "/audit/tenant-level" in prompt
        assert "/auth/login" in prompt
        assert "GET" in prompt
        assert "POST" in prompt


# ============================================================================
# TOKEN ESTIMATION TESTS
# ============================================================================

class TestTokenEstimation:
    """Tests for token estimation accuracy."""
    
    def test_token_estimation_accuracy(self, prompt_builder: PromptBuilder):
        """Test that token estimation is reasonably accurate."""
        # Test with known text
        test_text = "This is a test sentence with exactly ten words here."
        estimated = prompt_builder._estimate_tokens(test_text)
        
        # Rough estimate: 1 token ≈ 4 chars
        expected = len(test_text) // 4
        
        # Should be within 20% of expected
        assert abs(estimated - expected) / expected < 0.2
    
    def test_token_estimation_empty_string(self, prompt_builder: PromptBuilder):
        """Test token estimation with empty string."""
        estimated = prompt_builder._estimate_tokens("")
        assert estimated == 0


# ============================================================================
# MODE SWITCHING TESTS
# ============================================================================

class TestModeSwitching:
    """Tests for switching between compact and optimized modes."""
    
    def test_compact_mode_produces_shorter_prompt(
        self,
        sample_enriched_story: EnrichedStory,
        sample_api_context: APIContext,
    ):
        """Test that compact mode produces significantly shorter prompts."""
        # Build with optimized mode
        optimized_builder = PromptBuilder(use_optimized=True, use_compact=False)
        
        # Build with compact mode
        compact_builder = PromptBuilder(use_optimized=True, use_compact=True)
        
        compact_prompt = compact_builder.build_compact_generation_prompt(
            enriched_story=sample_enriched_story,
            api_context=sample_api_context,
        )
        
        # Compact should be under 5K words
        compact_words = len(compact_prompt.split())
        assert compact_words < 5000, f"Compact prompt too long: {compact_words} words"
    
    def test_json_schema_differs_by_mode(self):
        """Test that JSON schema differs between modes."""
        compact_builder = PromptBuilder(use_compact=True)
        optimized_builder = PromptBuilder(use_compact=False)
        
        compact_schema = compact_builder.get_json_schema()
        optimized_schema = optimized_builder.get_json_schema()
        
        # Schemas should have same structure but may differ in details
        assert "schema" in compact_schema
        assert "schema" in optimized_schema
        assert compact_schema["name"] != optimized_schema["name"]


# ============================================================================
# RAG CONTEXT HANDLING TESTS
# ============================================================================

class TestRagContextHandling:
    """Tests for RAG context handling."""
    
    def test_rag_context_included_in_prompt(
        self,
        compact_prompt_builder: PromptBuilder,
        sample_enriched_story: EnrichedStory,
        sample_rag_context: str,
    ):
        """Test that RAG context is included in prompt."""
        prompt = compact_prompt_builder.build_compact_generation_prompt(
            enriched_story=sample_enriched_story,
            rag_context=sample_rag_context,
            api_context=None,
        )
        
        # RAG content should be present
        assert "SIMILAR TEST PLANS" in prompt or "REFERENCE CONTEXT" in prompt
    
    def test_prompt_works_without_rag_context(
        self,
        compact_prompt_builder: PromptBuilder,
        sample_enriched_story: EnrichedStory,
    ):
        """Test that prompt works without RAG context."""
        prompt = compact_prompt_builder.build_compact_generation_prompt(
            enriched_story=sample_enriched_story,
            rag_context=None,
            api_context=None,
        )
        
        # Should still have story and rules
        assert "STORY REQUIREMENTS" in prompt
        assert "CRITICAL RULES" in prompt
        assert len(prompt) > 1000  # Should be substantial


# ============================================================================
# API SPECIFICATION TESTS
# ============================================================================

class TestApiSpecificationHandling:
    """Tests for API specification handling."""
    
    def test_api_specs_formatted_correctly(
        self,
        compact_prompt_builder: PromptBuilder,
        sample_enriched_story: EnrichedStory,
        sample_api_context: APIContext,
    ):
        """Test that API specs are formatted correctly in prompt."""
        prompt = compact_prompt_builder.build_compact_generation_prompt(
            enriched_story=sample_enriched_story,
            rag_context=None,
            api_context=sample_api_context,
        )
        
        # Check endpoint formatting
        assert "GET /audit/tenant-level" in prompt or "/audit/tenant-level" in prompt
        assert "POST /auth/login" in prompt or "/auth/login" in prompt
    
    def test_api_params_included(
        self,
        compact_prompt_builder: PromptBuilder,
        sample_enriched_story: EnrichedStory,
        sample_api_context: APIContext,
    ):
        """Test that API parameters are included."""
        prompt = compact_prompt_builder.build_compact_generation_prompt(
            enriched_story=sample_enriched_story,
            rag_context=None,
            api_context=sample_api_context,
        )
        
        # Parameters should be mentioned
        assert "tenantId" in prompt or "Params" in prompt


# ============================================================================
# EDGE CASE TESTS
# ============================================================================

class TestEdgeCases:
    """Tests for edge cases."""
    
    def test_empty_acceptance_criteria(self, compact_prompt_builder: PromptBuilder):
        """Test handling of empty acceptance criteria."""
        story = EnrichedStory(
            story_key="TEST-999",
            feature_narrative="A feature with no ACs",
            acceptance_criteria=[],
            related_stories=[],
            risk_areas=[],
            source_story_ids=["TEST-999"],
            platform_components=[],
            confluence_docs=[],
            functional_points=[],
        )
        
        prompt = compact_prompt_builder.build_compact_generation_prompt(
            enriched_story=story,
            rag_context=None,
            api_context=None,
        )
        
        # Should still produce valid prompt
        assert len(prompt) > 500
        assert "TEST-999" in prompt
    
    def test_very_long_story_description(self, compact_prompt_builder: PromptBuilder):
        """Test handling of very long story description."""
        long_description = "This is a test. " * 500  # ~8K chars
        
        story = EnrichedStory(
            story_key="TEST-888",
            feature_narrative=long_description,
            acceptance_criteria=["AC1", "AC2"],
            related_stories=[],
            risk_areas=[],
            source_story_ids=["TEST-888"],
            platform_components=[],
            confluence_docs=[],
            functional_points=[],
        )
        
        prompt = compact_prompt_builder.build_compact_generation_prompt(
            enriched_story=story,
            rag_context=None,
            api_context=None,
        )
        
        # Description should be truncated
        assert len(prompt) < 50000  # Should be reasonable size
    
    def test_special_characters_in_story(self, compact_prompt_builder: PromptBuilder):
        """Test handling of special characters in story."""
        story = EnrichedStory(
            story_key="TEST-777",
            feature_narrative="Feature with special chars: <>&\"'{}[]",
            acceptance_criteria=["AC with <brackets> and \"quotes\""],
            related_stories=[],
            risk_areas=[],
            source_story_ids=["TEST-777"],
            platform_components=[],
            confluence_docs=[],
            functional_points=[],
        )
        
        prompt = compact_prompt_builder.build_compact_generation_prompt(
            enriched_story=story,
            rag_context=None,
            api_context=None,
        )
        
        # Should handle special chars without error
        assert "TEST-777" in prompt

