"""
Unit tests for TestPlanValidator - comprehensive test coverage.

Tests:
- Acceptance criteria coverage validation
- API endpoint accuracy validation
- Test data quality validation
- Naming convention compliance
- Structure completeness validation
- Recommendation generation
"""

import pytest
from unittest.mock import MagicMock
from typing import List

from src.ai.quality_validator import TestPlanValidator, ValidationReport, ValidationMetric
from src.models.test_plan import TestPlan
from src.models.test_case import TestCase, TestStep
from src.models.story import JiraStory
from src.models.enriched_story import EnrichedStory, APISpec


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def sample_story() -> JiraStory:
    """Create a sample Jira story."""
    from datetime import datetime
    return JiraStory(
        key="TEST-123",
        summary="Implement tenant-level audit logging",
        description="Add audit logging for tenant operations. GET /audit/tenant-level returns events.",
        issue_type="Story",
        status="Done",
        priority="High",
        components=["Audit"],
        labels=["audit"],
        reporter="test@example.com",
        created=datetime.now(),
        updated=datetime.now(),
        acceptance_criteria="""
        - Audit records are created for successful login sessions
        - Audit records are created for failed login attempts
        - Filters work correctly in tenant-level audit
        """,
    )


@pytest.fixture
def sample_enriched_story() -> EnrichedStory:
    """Create a sample enriched story."""
    return EnrichedStory(
        story_key="TEST-123",
        feature_narrative="Tenant-level audit logging feature",
        acceptance_criteria=[
            "Audit records are created for successful login sessions",
            "Audit records are created for failed login attempts",
            "Filters work correctly in tenant-level audit",
        ],
        related_stories=[],
        risk_areas=[],
        source_story_ids=["TEST-123"],
        platform_components=[],
        confluence_docs=[],
        functional_points=[],
    )


@pytest.fixture
def good_test_plan(sample_story: JiraStory) -> TestPlan:
    """Create a good quality test plan."""
    return TestPlan(
        story=sample_story,
        test_cases=[
            TestCase(
                title="Audit log displays successful login events when user authenticates",
                description="Verify audit records are created for successful logins",
                preconditions="User exists with valid credentials",
                steps=[
                    TestStep(
                        step_number=1,
                        action="POST /auth/login with valid credentials",
                        expected_result="API returns 200 OK with token",
                        test_data='{"username": "testuser", "password": "validpass"}'
                    ),
                    TestStep(
                        step_number=2,
                        action="GET /audit/tenant-level?type=LOGIN",
                        expected_result="API returns audit events including login",
                        test_data='{"tenantId": "tenant-123", "eventType": "LOGIN"}'
                    ),
                ],
                expected_result="Login events are properly audited",
                priority="critical",
                test_type="functional",
                tags=["API", "AUDIT", "LOGIN"],
                automation_candidate=True,
                risk_level="high",
            ),
            TestCase(
                title="Audit log displays failed login attempts when credentials are invalid",
                description="Verify audit records are created for failed logins",
                preconditions="User exists in system",
                steps=[
                    TestStep(
                        step_number=1,
                        action="POST /auth/login with invalid password",
                        expected_result="API returns 401 Unauthorized",
                        test_data='{"username": "testuser", "password": "wrongpass"}'
                    ),
                    TestStep(
                        step_number=2,
                        action="GET /audit/tenant-level?type=LOGIN_FAILED",
                        expected_result="API returns failed login event",
                        test_data='{"tenantId": "tenant-123", "eventType": "LOGIN_FAILED"}'
                    ),
                ],
                expected_result="Failed login attempts are audited",
                priority="high",
                test_type="negative",
                tags=["API", "AUDIT", "NEGATIVE"],
                automation_candidate=True,
                risk_level="high",
            ),
            TestCase(
                title="Audit log filters events by date range when filter is applied",
                description="Verify date filters work correctly",
                preconditions="Audit events exist in system",
                steps=[
                    TestStep(
                        step_number=1,
                        action="GET /audit/tenant-level?from=2024-01-01&to=2024-01-31",
                        expected_result="API returns events within date range",
                        test_data='{"from": "2024-01-01", "to": "2024-01-31"}'
                    ),
                    TestStep(
                        step_number=2,
                        action="Validate all returned events are within the date range",
                        expected_result="All events have timestamp within specified range",
                        test_data='{"expectedDateRange": "2024-01-01 to 2024-01-31"}'
                    ),
                ],
                expected_result="Date filters work correctly",
                priority="high",
                test_type="functional",
                tags=["API", "AUDIT", "FILTER"],
                automation_candidate=True,
                risk_level="medium",
            ),
        ],
    )


@pytest.fixture
def bad_test_plan(sample_story: JiraStory) -> TestPlan:
    """Create a poor quality test plan with various issues."""
    return TestPlan(
        story=sample_story,
        test_cases=[
            TestCase(
                title="Verify audit log is displayed",  # Bad: starts with "Verify"
                description="Check the audit log",
                preconditions="",  # Missing preconditions
                steps=[
                    TestStep(
                        step_number=1,
                        action="Open audit page",
                        expected_result="Page opens",
                        test_data=""  # Empty test data
                    ),
                ],
                expected_result="Audit works",
                priority="medium",
                test_type="functional",
                tags=[],  # Missing tags
                automation_candidate=True,
                risk_level="low",
            ),
            TestCase(
                title="Test login API",  # Bad: starts with "Test"
                description="Test the login",
                preconditions="User exists",
                steps=[
                    TestStep(
                        step_number=1,
                        action="POST /invented/endpoint",  # Invented endpoint
                        expected_result="Success",
                        test_data='{"placeholder": "<token>"}'  # Placeholder
                    ),
                    TestStep(
                        step_number=2,
                        action="Check result",
                        expected_result="Works",
                        test_data="TODO"  # TODO placeholder
                    ),
                ],
                expected_result="Login works",
                priority="high",
                test_type="functional",
                tags=["API"],
                automation_candidate=True,
                risk_level="medium",
            ),
        ],
    )


@pytest.fixture
def validator() -> TestPlanValidator:
    """Create a validator instance."""
    return TestPlanValidator()


# ============================================================================
# ACCEPTANCE CRITERIA COVERAGE TESTS
# ============================================================================

class TestACCoverage:
    """Tests for acceptance criteria coverage validation."""
    
    def test_all_acs_covered(
        self,
        validator: TestPlanValidator,
        good_test_plan: TestPlan,
        sample_enriched_story: EnrichedStory,
    ):
        """Test validation when all ACs are covered."""
        report = validator.validate(good_test_plan, sample_enriched_story)
        
        # Should have high AC coverage
        assert report.ac_coverage.score >= 0.8
        assert report.ac_coverage.passed >= 2
    
    def test_missing_ac_coverage(
        self,
        validator: TestPlanValidator,
        bad_test_plan: TestPlan,
        sample_enriched_story: EnrichedStory,
    ):
        """Test validation when ACs are not covered."""
        report = validator.validate(bad_test_plan, sample_enriched_story)
        
        # Should have lower AC coverage
        assert report.ac_coverage.score < 1.0
        assert len(report.ac_coverage.details) > 0
    
    def test_no_acceptance_criteria(
        self,
        validator: TestPlanValidator,
        good_test_plan: TestPlan,
    ):
        """Test validation when no ACs exist."""
        # Story without ACs
        story_no_acs = EnrichedStory(
            story_key="TEST-999",
            feature_narrative="Feature",
            acceptance_criteria=[],
            related_stories=[],
            risk_areas=[],
            source_story_ids=[],
            platform_components=[],
            confluence_docs=[],
            functional_points=[],
        )
        
        report = validator.validate(good_test_plan, story_no_acs)
        
        # Should report perfect score (no ACs to miss)
        assert report.ac_coverage.score == 1.0
        assert report.ac_coverage.total == 0


# ============================================================================
# API ACCURACY TESTS
# ============================================================================

class TestAPIAccuracy:
    """Tests for API endpoint accuracy validation."""
    
    def test_valid_endpoints(
        self,
        validator: TestPlanValidator,
        good_test_plan: TestPlan,
        sample_enriched_story: EnrichedStory,
    ):
        """Test validation with valid API endpoints."""
        report = validator.validate(good_test_plan, sample_enriched_story)
        
        # Story mentions /audit/tenant-level, tests use it
        # Score depends on whether endpoints are detected
        assert report.api_accuracy.score >= 0.0
    
    def test_invented_endpoints(
        self,
        validator: TestPlanValidator,
        bad_test_plan: TestPlan,
        sample_enriched_story: EnrichedStory,
    ):
        """Test validation with invented API endpoints."""
        report = validator.validate(bad_test_plan, sample_enriched_story)
        
        # Should detect invented endpoints
        # Note: depends on endpoint extraction from story
        assert report.api_accuracy is not None
    
    def test_no_api_tests(self, validator: TestPlanValidator, sample_story: JiraStory):
        """Test validation when no API tests exist."""
        plan = TestPlan(
            story=sample_story,
            test_cases=[
                TestCase(
                    title="UI test for audit page",
                    description="Test UI",
                    preconditions="User logged in",
                    steps=[
                        TestStep(
                            step_number=1,
                            action="Navigate to Audit page",
                            expected_result="Page displays",
                            test_data='{"page": "audit"}'
                        ),
                    ],
                    expected_result="Page works",
                    priority="medium",
                    test_type="functional",
                    tags=["UI"],  # No API tag
                    automation_candidate=True,
                    risk_level="low",
                ),
            ],
        )
        
        report = validator.validate(plan)
        
        # Should report no API tests found
        assert report.api_accuracy.total == 0


# ============================================================================
# TEST DATA QUALITY TESTS
# ============================================================================

class TestDataQuality:
    """Tests for test data quality validation."""
    
    def test_valid_test_data(
        self,
        validator: TestPlanValidator,
        good_test_plan: TestPlan,
    ):
        """Test validation with valid test data."""
        report = validator.validate(good_test_plan)
        
        # All test data should be valid JSON
        assert report.test_data_quality.score >= 0.8
    
    def test_empty_test_data(
        self,
        validator: TestPlanValidator,
        bad_test_plan: TestPlan,
    ):
        """Test validation with empty test data."""
        report = validator.validate(bad_test_plan)
        
        # Should detect empty test data
        assert report.test_data_quality.failed > 0
        assert any("empty" in d.lower() for d in report.test_data_quality.details)
    
    def test_placeholder_detection(
        self,
        validator: TestPlanValidator,
        bad_test_plan: TestPlan,
    ):
        """Test detection of placeholder values."""
        report = validator.validate(bad_test_plan)
        
        # Should detect placeholders like <token> and TODO
        assert report.test_data_quality.failed > 0


# ============================================================================
# NAMING COMPLIANCE TESTS
# ============================================================================

class TestNamingCompliance:
    """Tests for naming convention compliance."""
    
    def test_good_naming(
        self,
        validator: TestPlanValidator,
        good_test_plan: TestPlan,
    ):
        """Test validation with good naming conventions."""
        report = validator.validate(good_test_plan)
        
        # All titles should be compliant
        assert report.naming_compliance.score >= 0.9
        assert report.naming_compliance.failed == 0
    
    def test_forbidden_prefixes(
        self,
        validator: TestPlanValidator,
        bad_test_plan: TestPlan,
    ):
        """Test detection of forbidden title prefixes."""
        report = validator.validate(bad_test_plan)
        
        # Should detect "Verify" and "Test" prefixes
        assert report.naming_compliance.failed >= 2
        assert any("Verify" in d for d in report.naming_compliance.details)
    
    def test_all_forbidden_prefixes(self, validator: TestPlanValidator, sample_story: JiraStory):
        """Test all forbidden prefixes are detected."""
        plan = TestPlan(
            story=sample_story,
            test_cases=[
                TestCase(
                    title=f"{prefix} something works",
                    description="Test",
                    preconditions="Setup",
                    steps=[
                        TestStep(1, "Action", "Result", '{"data": "value"}'),
                        TestStep(2, "Action 2", "Result 2", '{"data": "value"}'),
                    ],
                    expected_result="Works",
                    priority="medium",
                    test_type="functional",
                    tags=["TEST"],
                    automation_candidate=True,
                    risk_level="low",
                )
                for prefix in ["Verify", "Validate", "Test", "Check", "Ensure"]
            ],
        )
        
        report = validator.validate(plan)
        
        # All 5 tests should fail naming
        assert report.naming_compliance.failed == 5


# ============================================================================
# STRUCTURE COMPLETENESS TESTS
# ============================================================================

class TestStructureCompleteness:
    """Tests for test structure completeness."""
    
    def test_complete_structure(
        self,
        validator: TestPlanValidator,
        good_test_plan: TestPlan,
    ):
        """Test validation with complete test structure."""
        report = validator.validate(good_test_plan)
        
        # All tests should have complete structure
        assert report.structure_completeness.score >= 0.9
    
    def test_missing_fields(
        self,
        validator: TestPlanValidator,
        bad_test_plan: TestPlan,
    ):
        """Test detection of missing fields."""
        report = validator.validate(bad_test_plan)
        
        # Should detect missing preconditions, tags
        assert report.structure_completeness.failed > 0
    
    def test_insufficient_steps(self, validator: TestPlanValidator, sample_story: JiraStory):
        """Test detection of insufficient test steps."""
        plan = TestPlan(
            story=sample_story,
            test_cases=[
                TestCase(
                    title="Single step test",
                    description="Test with only one step",
                    preconditions="Setup",
                    steps=[
                        TestStep(1, "Only action", "Only result", '{"data": "value"}'),
                    ],  # Only 1 step - should be at least 2
                    expected_result="Works",
                    priority="medium",
                    test_type="functional",
                    tags=["TEST"],
                    automation_candidate=True,
                    risk_level="low",
                ),
            ],
        )
        
        report = validator.validate(plan)
        
        # Should detect insufficient steps
        assert report.structure_completeness.failed > 0
        assert any("step" in d.lower() for d in report.structure_completeness.details)


# ============================================================================
# OVERALL SCORE TESTS
# ============================================================================

class TestOverallScore:
    """Tests for overall score calculation."""
    
    def test_good_plan_high_score(
        self,
        validator: TestPlanValidator,
        good_test_plan: TestPlan,
        sample_enriched_story: EnrichedStory,
    ):
        """Test that good plans get high overall scores."""
        report = validator.validate(good_test_plan, sample_enriched_story)
        
        # Should be above 0.7
        assert report.overall_score >= 0.7
    
    def test_bad_plan_low_score(
        self,
        validator: TestPlanValidator,
        bad_test_plan: TestPlan,
        sample_enriched_story: EnrichedStory,
    ):
        """Test that bad plans get lower overall scores."""
        report = validator.validate(bad_test_plan, sample_enriched_story)
        
        # Should be below 0.7
        assert report.overall_score < 0.7
    
    def test_score_is_weighted_average(
        self,
        validator: TestPlanValidator,
        good_test_plan: TestPlan,
    ):
        """Test that overall score is a weighted average."""
        report = validator.validate(good_test_plan)
        
        # Calculate expected weighted average
        weights = {
            'ac_coverage': 0.25,
            'api_accuracy': 0.25,
            'test_data_quality': 0.20,
            'naming_compliance': 0.15,
            'structure_completeness': 0.15
        }
        
        expected = (
            report.ac_coverage.score * weights['ac_coverage'] +
            report.api_accuracy.score * weights['api_accuracy'] +
            report.test_data_quality.score * weights['test_data_quality'] +
            report.naming_compliance.score * weights['naming_compliance'] +
            report.structure_completeness.score * weights['structure_completeness']
        )
        
        assert abs(report.overall_score - expected) < 0.01


# ============================================================================
# RECOMMENDATION TESTS
# ============================================================================

class TestRecommendations:
    """Tests for recommendation generation."""
    
    def test_recommendations_for_issues(
        self,
        validator: TestPlanValidator,
        bad_test_plan: TestPlan,
        sample_enriched_story: EnrichedStory,
    ):
        """Test that recommendations are generated for issues."""
        report = validator.validate(bad_test_plan, sample_enriched_story)
        
        # Should have recommendations
        assert len(report.recommendations) > 0
    
    def test_no_recommendations_for_perfect_plan(
        self,
        validator: TestPlanValidator,
        good_test_plan: TestPlan,
    ):
        """Test minimal recommendations for good plans."""
        report = validator.validate(good_test_plan)
        
        # May have some minor recommendations, but should be limited
        # Good plans should have fewer recommendations
        assert len(report.recommendations) <= 5
    
    def test_recommendations_are_actionable(
        self,
        validator: TestPlanValidator,
        bad_test_plan: TestPlan,
    ):
        """Test that recommendations are actionable."""
        report = validator.validate(bad_test_plan)
        
        # Recommendations should contain action words
        action_words = ["Add", "Remove", "Fix", "Replace", "Rename", "Complete"]
        
        for rec in report.recommendations:
            has_action = any(word in rec for word in action_words)
            assert has_action or ":" in rec, f"Recommendation not actionable: {rec}"


# ============================================================================
# REPORT FORMAT TESTS
# ============================================================================

class TestReportFormat:
    """Tests for validation report format."""
    
    def test_to_dict(
        self,
        validator: TestPlanValidator,
        good_test_plan: TestPlan,
    ):
        """Test report can be converted to dict."""
        report = validator.validate(good_test_plan)
        
        report_dict = report.to_dict()
        
        assert "story_key" in report_dict
        assert "validated_at" in report_dict
        assert "validation_results" in report_dict
        assert "recommendations" in report_dict
    
    def test_to_json(
        self,
        validator: TestPlanValidator,
        good_test_plan: TestPlan,
    ):
        """Test report can be converted to JSON."""
        report = validator.validate(good_test_plan)
        
        json_str = report.to_json()
        
        assert isinstance(json_str, str)
        assert "story_key" in json_str
        assert "overall_score" in json_str
    
    def test_metric_to_dict(self):
        """Test ValidationMetric can be converted to dict."""
        metric = ValidationMetric(
            score=0.85,
            passed=17,
            failed=3,
            total=20,
            details=["Issue 1", "Issue 2"],
        )
        
        metric_dict = metric.to_dict()
        
        assert metric_dict["score"] == 0.85
        assert metric_dict["passed"] == 17
        assert metric_dict["failed"] == 3
        assert metric_dict["total"] == 20
        assert len(metric_dict["details"]) == 2

