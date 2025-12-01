"""
Test Plan Quality Validator - validates generated test plans against quality criteria.

Validates:
- Acceptance criteria coverage
- API endpoint accuracy (no invented endpoints)
- Test data quality (no placeholders)
- Naming convention compliance
- Test structure completeness

Outputs a ValidationReport with scores and recommendations.
"""

import re
import json
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass, field, asdict
from datetime import datetime
from loguru import logger

from src.models.test_plan import TestPlan
from src.models.enriched_story import EnrichedStory, APISpec


@dataclass
class ValidationMetric:
    """Single validation metric result."""
    score: float  # 0.0 to 1.0
    passed: int
    failed: int
    total: int
    details: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ValidationReport:
    """Complete validation report for a test plan."""
    story_key: str
    validated_at: str
    
    # Metrics
    ac_coverage: ValidationMetric
    api_accuracy: ValidationMetric
    test_data_quality: ValidationMetric
    naming_compliance: ValidationMetric
    structure_completeness: ValidationMetric
    
    # Overall
    overall_score: float
    recommendations: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "story_key": self.story_key,
            "validated_at": self.validated_at,
            "validation_results": {
                "ac_coverage": self.ac_coverage.to_dict(),
                "api_accuracy": self.api_accuracy.to_dict(),
                "test_data_quality": self.test_data_quality.to_dict(),
                "naming_compliance": self.naming_compliance.to_dict(),
                "structure_completeness": self.structure_completeness.to_dict(),
                "overall_score": self.overall_score
            },
            "recommendations": self.recommendations
        }
    
    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


class TestPlanValidator:
    """
    Validates test plans against quality criteria.
    
    Usage:
        validator = TestPlanValidator()
        report = validator.validate(test_plan, enriched_story)
        print(report.to_json())
    """
    
    # Forbidden title prefixes
    FORBIDDEN_PREFIXES = ["Verify", "Validate", "Test", "Check", "Ensure"]
    
    # Placeholder patterns to detect
    PLACEHOLDER_PATTERNS = [
        r'<[^>]+>',           # <token>, <value>
        r'\bTODO\b',          # TODO
        r'\bFIXME\b',         # FIXME
        r'\bnew-\w+-id\b',    # new-policy-id, new-user-id
        r'\bplaceholder\b',   # placeholder
        r'\bexample\b',       # example (in test data)
        r'"\s*"',             # empty strings
        r': null',            # null values
    ]
    
    def __init__(self):
        """Initialize the validator."""
        self.placeholder_regex = re.compile(
            '|'.join(self.PLACEHOLDER_PATTERNS), 
            re.IGNORECASE
        )
        logger.info("[VALIDATOR] Initialized TestPlanValidator")
    
    def validate(
        self,
        test_plan: TestPlan,
        enriched_story: Optional[EnrichedStory] = None,
        api_specs: Optional[List[APISpec]] = None
    ) -> ValidationReport:
        """
        Validate a test plan and generate a report.
        
        Args:
            test_plan: The generated test plan to validate
            enriched_story: Optional enriched story for AC extraction
            api_specs: Optional list of valid API specifications
            
        Returns:
            ValidationReport with scores and recommendations
        """
        story_key = test_plan.story.key if test_plan.story else "UNKNOWN"
        logger.info(f"[VALIDATOR] Validating test plan for {story_key} ({len(test_plan.test_cases)} tests)")
        
        # Extract acceptance criteria
        acceptance_criteria = self._extract_acceptance_criteria(test_plan, enriched_story)
        
        # Extract valid endpoints
        valid_endpoints = self._extract_valid_endpoints(test_plan, enriched_story, api_specs)
        
        # Run validations
        ac_coverage = self._validate_ac_coverage(test_plan, acceptance_criteria)
        api_accuracy = self._validate_api_accuracy(test_plan, valid_endpoints)
        test_data_quality = self._validate_test_data(test_plan)
        naming_compliance = self._validate_naming(test_plan)
        structure_completeness = self._validate_structure(test_plan)
        
        # Calculate overall score (weighted average)
        weights = {
            'ac_coverage': 0.25,
            'api_accuracy': 0.25,
            'test_data_quality': 0.20,
            'naming_compliance': 0.15,
            'structure_completeness': 0.15
        }
        
        overall_score = (
            ac_coverage.score * weights['ac_coverage'] +
            api_accuracy.score * weights['api_accuracy'] +
            test_data_quality.score * weights['test_data_quality'] +
            naming_compliance.score * weights['naming_compliance'] +
            structure_completeness.score * weights['structure_completeness']
        )
        
        # Generate recommendations
        recommendations = self._generate_recommendations(
            ac_coverage, api_accuracy, test_data_quality, 
            naming_compliance, structure_completeness,
            acceptance_criteria
        )
        
        report = ValidationReport(
            story_key=story_key,
            validated_at=datetime.utcnow().isoformat(),
            ac_coverage=ac_coverage,
            api_accuracy=api_accuracy,
            test_data_quality=test_data_quality,
            naming_compliance=naming_compliance,
            structure_completeness=structure_completeness,
            overall_score=round(overall_score, 3),
            recommendations=recommendations
        )
        
        logger.info(f"[VALIDATOR] Validation complete: overall_score={overall_score:.2f}")
        logger.info(f"[VALIDATOR] Scores: ac={ac_coverage.score:.2f}, api={api_accuracy.score:.2f}, "
                   f"data={test_data_quality.score:.2f}, naming={naming_compliance.score:.2f}, "
                   f"structure={structure_completeness.score:.2f}")
        
        return report
    
    def _extract_acceptance_criteria(
        self,
        test_plan: TestPlan,
        enriched_story: Optional[EnrichedStory]
    ) -> List[str]:
        """Extract acceptance criteria from story."""
        acs = []
        
        # From enriched story
        if enriched_story and enriched_story.acceptance_criteria:
            acs.extend(enriched_story.acceptance_criteria)
            logger.debug(f"[VALIDATOR] Found {len(enriched_story.acceptance_criteria)} ACs from enriched story")
        
        # From test plan story
        if test_plan.story and test_plan.story.acceptance_criteria:
            ac_text = test_plan.story.acceptance_criteria
            # Split by common delimiters
            for line in ac_text.split('\n'):
                line = line.strip()
                if line and len(line) > 10:
                    # Clean up bullet points and numbers
                    line = re.sub(r'^[-*•]\s*', '', line)
                    line = re.sub(r'^\d+\.\s*', '', line)
                    if line and line not in acs:
                        acs.append(line)
        
        logger.info(f"[VALIDATOR] Extracted {len(acs)} acceptance criteria")
        return acs
    
    def _extract_valid_endpoints(
        self,
        test_plan: TestPlan,
        enriched_story: Optional[EnrichedStory],
        api_specs: Optional[List[APISpec]]
    ) -> Set[str]:
        """Extract valid API endpoints from story and specs."""
        endpoints = set()
        
        # From API specs
        if api_specs:
            for spec in api_specs:
                if spec.endpoint_path:
                    endpoints.add(spec.endpoint_path.lower())
        
        # From story description (extract paths)
        if test_plan.story and test_plan.story.description:
            desc = test_plan.story.description
            # Match API paths like /api/v1/something or /policy-mgmt/1.0/policies
            path_pattern = r'/[a-zA-Z0-9_/-]+(?:\{[^}]+\})?'
            matches = re.findall(path_pattern, desc)
            for match in matches:
                endpoints.add(match.lower())
        
        logger.info(f"[VALIDATOR] Found {len(endpoints)} valid API endpoints")
        return endpoints
    
    def _validate_ac_coverage(
        self,
        test_plan: TestPlan,
        acceptance_criteria: List[str]
    ) -> ValidationMetric:
        """Validate that all acceptance criteria have mapped tests."""
        if not acceptance_criteria:
            logger.debug("[VALIDATOR] No acceptance criteria to validate")
            return ValidationMetric(score=1.0, passed=0, failed=0, total=0, 
                                   details=["No acceptance criteria found"])
        
        # Build test content for matching
        test_content = []
        for test in test_plan.test_cases:
            content = f"{test.title} {test.description} {test.expected_result}"
            for step in test.steps:
                content += f" {step.action} {step.expected_result}"
            test_content.append(content.lower())
        
        all_test_content = " ".join(test_content)
        
        # Check each AC
        covered = []
        missing = []
        
        for i, ac in enumerate(acceptance_criteria, 1):
            # Extract key terms from AC
            ac_lower = ac.lower()
            key_terms = [term for term in ac_lower.split() if len(term) > 4]
            
            # Check if any key terms appear in tests
            matches = sum(1 for term in key_terms if term in all_test_content)
            coverage_ratio = matches / len(key_terms) if key_terms else 0
            
            if coverage_ratio >= 0.3:  # At least 30% of key terms match
                covered.append(f"AC #{i}: covered")
            else:
                missing.append(f"AC #{i}: '{ac[:50]}...' - not covered by any test")
        
        score = len(covered) / len(acceptance_criteria) if acceptance_criteria else 1.0
        
        logger.info(f"[VALIDATOR] AC coverage: {len(covered)}/{len(acceptance_criteria)} ({score:.2%})")
        
        return ValidationMetric(
            score=round(score, 3),
            passed=len(covered),
            failed=len(missing),
            total=len(acceptance_criteria),
            details=missing[:5]  # Top 5 missing
        )
    
    def _validate_api_accuracy(
        self,
        test_plan: TestPlan,
        valid_endpoints: Set[str]
    ) -> ValidationMetric:
        """Validate that API tests use only valid endpoints."""
        api_tests = [t for t in test_plan.test_cases if 'API' in t.tags or t.test_type == 'api']
        
        if not api_tests:
            logger.debug("[VALIDATOR] No API tests to validate")
            return ValidationMetric(score=1.0, passed=0, failed=0, total=0,
                                   details=["No API tests found"])
        
        # If no valid endpoints defined, we can't validate
        if not valid_endpoints:
            logger.debug("[VALIDATOR] No valid endpoints to validate against")
            return ValidationMetric(score=0.5, passed=0, failed=0, total=len(api_tests),
                                   details=["No valid endpoints defined in story - cannot validate"])
        
        valid = []
        invented = []
        
        for test in api_tests:
            test_endpoints = set()
            
            # Extract endpoints from steps
            for step in test.steps:
                action = step.action.lower()
                # Match API paths
                path_pattern = r'(?:get|post|put|patch|delete)\s+(/[a-zA-Z0-9_/-]+)'
                matches = re.findall(path_pattern, action, re.IGNORECASE)
                test_endpoints.update(matches)
            
            # Check if endpoints are valid
            for endpoint in test_endpoints:
                endpoint_lower = endpoint.lower()
                # Check for exact match or prefix match
                is_valid = any(
                    endpoint_lower == valid_ep or 
                    endpoint_lower.startswith(valid_ep) or
                    valid_ep.startswith(endpoint_lower)
                    for valid_ep in valid_endpoints
                )
                
                if is_valid:
                    valid.append(f"'{test.title}': {endpoint}")
                else:
                    invented.append(f"'{test.title}': {endpoint} (not in story)")
        
        total = len(valid) + len(invented)
        score = len(valid) / total if total > 0 else 1.0
        
        logger.info(f"[VALIDATOR] API accuracy: {len(valid)}/{total} valid endpoints ({score:.2%})")
        
        return ValidationMetric(
            score=round(score, 3),
            passed=len(valid),
            failed=len(invented),
            total=total,
            details=invented[:5]  # Top 5 invented
        )
    
    def _validate_test_data(self, test_plan: TestPlan) -> ValidationMetric:
        """Validate that test_data fields are properly populated."""
        valid = []
        invalid = []
        
        for test in test_plan.test_cases:
            for step in test.steps:
                test_data = step.test_data or ""
                
                # Check for empty
                if not test_data or test_data.strip() in ['', '{}', 'null', 'None']:
                    invalid.append(f"'{test.title}' step {step.step_number}: empty test_data")
                    continue
                
                # Check for placeholders
                if self.placeholder_regex.search(test_data):
                    match = self.placeholder_regex.search(test_data)
                    invalid.append(f"'{test.title}' step {step.step_number}: placeholder '{match.group()}'")
                    continue
                
                # Check if valid JSON
                try:
                    json.loads(test_data)
                    valid.append(f"'{test.title}' step {step.step_number}: valid")
                except json.JSONDecodeError:
                    # Not JSON but might still be valid text
                    if len(test_data) > 10:
                        valid.append(f"'{test.title}' step {step.step_number}: valid (text)")
                    else:
                        invalid.append(f"'{test.title}' step {step.step_number}: too short")
        
        total = len(valid) + len(invalid)
        score = len(valid) / total if total > 0 else 1.0
        
        logger.info(f"[VALIDATOR] Test data quality: {len(valid)}/{total} valid ({score:.2%})")
        
        return ValidationMetric(
            score=round(score, 3),
            passed=len(valid),
            failed=len(invalid),
            total=total,
            details=invalid[:5]
        )
    
    def _validate_naming(self, test_plan: TestPlan) -> ValidationMetric:
        """Validate test naming conventions."""
        valid = []
        violations = []
        
        for test in test_plan.test_cases:
            title = test.title
            
            # Check for forbidden prefixes
            has_forbidden = False
            for prefix in self.FORBIDDEN_PREFIXES:
                if title.lower().startswith(prefix.lower()):
                    violations.append(f"'{title[:50]}': starts with '{prefix}'")
                    has_forbidden = True
                    break
            
            if not has_forbidden:
                # Check for descriptive title (should describe behavior)
                if len(title) > 20 and not title.lower().startswith(('test', 'happy', 'negative')):
                    valid.append(title)
                else:
                    violations.append(f"'{title[:50]}': too generic or short")
        
        total = len(test_plan.test_cases)
        score = len(valid) / total if total > 0 else 1.0
        
        logger.info(f"[VALIDATOR] Naming compliance: {len(valid)}/{total} valid ({score:.2%})")
        
        return ValidationMetric(
            score=round(score, 3),
            passed=len(valid),
            failed=len(violations),
            total=total,
            details=violations[:5]
        )
    
    def _validate_structure(self, test_plan: TestPlan) -> ValidationMetric:
        """Validate test structure completeness."""
        valid = []
        incomplete = []
        
        for test in test_plan.test_cases:
            issues = []
            
            # Check required fields
            if not test.title:
                issues.append("missing title")
            if not test.description:
                issues.append("missing description")
            if not test.preconditions:
                issues.append("missing preconditions")
            if not test.steps or len(test.steps) < 2:
                issues.append("needs at least 2 steps")
            if not test.expected_result:
                issues.append("missing expected_result")
            if not test.tags:
                issues.append("missing tags")
            
            if issues:
                incomplete.append(f"'{test.title[:30]}': {', '.join(issues)}")
            else:
                valid.append(test.title)
        
        total = len(test_plan.test_cases)
        score = len(valid) / total if total > 0 else 1.0
        
        logger.info(f"[VALIDATOR] Structure completeness: {len(valid)}/{total} valid ({score:.2%})")
        
        return ValidationMetric(
            score=round(score, 3),
            passed=len(valid),
            failed=len(incomplete),
            total=total,
            details=incomplete[:5]
        )
    
    def _generate_recommendations(
        self,
        ac_coverage: ValidationMetric,
        api_accuracy: ValidationMetric,
        test_data_quality: ValidationMetric,
        naming_compliance: ValidationMetric,
        structure_completeness: ValidationMetric,
        acceptance_criteria: List[str]
    ) -> List[str]:
        """Generate actionable recommendations based on validation results."""
        recommendations = []
        
        # AC coverage recommendations
        if ac_coverage.score < 1.0 and ac_coverage.details:
            for detail in ac_coverage.details[:3]:
                recommendations.append(f"Add test for: {detail}")
        
        # API accuracy recommendations
        if api_accuracy.score < 1.0 and api_accuracy.details:
            recommendations.append("Remove invented API endpoints - use only endpoints from story")
            for detail in api_accuracy.details[:2]:
                recommendations.append(f"Fix: {detail}")
        
        # Test data recommendations
        if test_data_quality.score < 0.9 and test_data_quality.details:
            recommendations.append("Replace placeholders with concrete test data")
            for detail in test_data_quality.details[:2]:
                recommendations.append(f"Fix: {detail}")
        
        # Naming recommendations
        if naming_compliance.score < 1.0 and naming_compliance.details:
            recommendations.append("Rename tests to describe behavior (remove 'Verify/Validate' prefixes)")
            for detail in naming_compliance.details[:2]:
                recommendations.append(f"Rename: {detail}")
        
        # Structure recommendations
        if structure_completeness.score < 1.0 and structure_completeness.details:
            recommendations.append("Complete test structure (add missing fields)")
            for detail in structure_completeness.details[:2]:
                recommendations.append(f"Complete: {detail}")
        
        return recommendations[:10]  # Top 10 recommendations


def validate_test_plan(
    test_plan: TestPlan,
    enriched_story: Optional[EnrichedStory] = None,
    output_path: Optional[str] = None
) -> ValidationReport:
    """
    Convenience function to validate a test plan.
    
    Args:
        test_plan: Test plan to validate
        enriched_story: Optional enriched story
        output_path: Optional path to save validation report
        
    Returns:
        ValidationReport
    """
    validator = TestPlanValidator()
    report = validator.validate(test_plan, enriched_story)
    
    if output_path:
        from pathlib import Path
        Path(output_path).write_text(report.to_json())
        logger.info(f"[VALIDATOR] Saved validation report to {output_path}")
    
    return report

