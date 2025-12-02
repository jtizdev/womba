"""
Coverage Validator for Two-Stage Test Generation.

Validates that generated tests cover all:
- Pattern matches (DIFFERENT_X, SPECIFIC_USER, NAMED_FEATURE, HIDDEN_VISIBLE)
- PRD requirements
- API endpoints
- Planned tests from coverage plan

If validation fails, provides specific gaps for re-prompting.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from loguru import logger

from src.models.coverage_plan import CoveragePlan, PatternMatch, PRDRequirement, APICoverage
from src.models.test_plan import TestPlan


@dataclass
class ValidationGap:
    """A gap in test coverage."""
    gap_type: str  # "pattern", "prd", "api", "planned_test"
    description: str
    severity: str  # "critical", "high", "medium"
    source_item: Any  # The PatternMatch, PRDRequirement, etc. that's not covered
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "gap_type": self.gap_type,
            "description": self.description,
            "severity": self.severity
        }


@dataclass
class ValidationResult:
    """Result of coverage validation."""
    is_valid: bool
    gaps: List[ValidationGap] = field(default_factory=list)
    coverage_score: float = 0.0  # 0-100%
    pattern_coverage: float = 0.0
    prd_coverage: float = 0.0
    api_coverage: float = 0.0
    planned_test_coverage: float = 0.0
    
    def get_summary(self) -> str:
        return (
            f"Coverage: {self.coverage_score:.1f}% "
            f"(patterns: {self.pattern_coverage:.1f}%, "
            f"PRD: {self.prd_coverage:.1f}%, "
            f"API: {self.api_coverage:.1f}%, "
            f"planned: {self.planned_test_coverage:.1f}%)"
        )
    
    def get_reprompt_instructions(self) -> str:
        """Generate instructions for re-prompting to fill gaps."""
        if not self.gaps:
            return ""
        
        lines = ["The following coverage gaps were detected. Please add tests for:"]
        
        for gap in self.gaps:
            if gap.severity == "critical":
                lines.append(f"  ⚠️ CRITICAL: {gap.description}")
            elif gap.severity == "high":
                lines.append(f"  ❗ HIGH: {gap.description}")
            else:
                lines.append(f"  📋 {gap.description}")
        
        return "\n".join(lines)


class CoverageValidator:
    """
    Validates test coverage against a coverage plan.
    
    Checks:
    1. Pattern coverage - all DIFFERENT_X, SPECIFIC_USER, etc. patterns covered
    2. PRD coverage - all PRD requirements verified
    3. API coverage - all must-test endpoints included
    4. Planned test coverage - all planned tests created
    """
    
    def validate(
        self,
        coverage_plan: CoveragePlan,
        test_plan: TestPlan
    ) -> ValidationResult:
        """
        Validate test plan against coverage plan.
        
        Args:
            coverage_plan: The analysis output from Stage 1
            test_plan: The generated test plan from Stage 2
            
        Returns:
            ValidationResult with gaps and coverage scores
        """
        gaps = []
        
        # Build combined test text for searching
        test_texts = []
        for test in test_plan.test_cases:
            text = f"{test.title} {test.description}".lower()
            # Include step actions too
            for step in test.steps:
                text += f" {step.action}".lower()
            test_texts.append(text)
        
        combined_text = " ".join(test_texts)
        
        # 1. Check pattern coverage
        pattern_gaps = self._check_pattern_coverage(
            coverage_plan.pattern_matches,
            combined_text
        )
        gaps.extend(pattern_gaps)
        
        # 2. Check PRD coverage
        prd_gaps = self._check_prd_coverage(
            coverage_plan.prd_requirements,
            combined_text
        )
        gaps.extend(prd_gaps)
        
        # 3. Check API coverage
        api_gaps = self._check_api_coverage(
            coverage_plan.api_coverage,
            combined_text
        )
        gaps.extend(api_gaps)
        
        # 4. Check planned test coverage
        planned_gaps = self._check_planned_test_coverage(
            coverage_plan.test_plan,
            test_texts
        )
        gaps.extend(planned_gaps)
        
        # Calculate coverage scores
        total_patterns = len(coverage_plan.pattern_matches)
        total_prd = len(coverage_plan.prd_requirements)
        total_api = len([a for a in coverage_plan.api_coverage if a.must_test])
        total_planned = len(coverage_plan.test_plan)
        
        pattern_covered = total_patterns - len([g for g in gaps if g.gap_type == "pattern"])
        prd_covered = total_prd - len([g for g in gaps if g.gap_type == "prd"])
        api_covered = total_api - len([g for g in gaps if g.gap_type == "api"])
        planned_covered = total_planned - len([g for g in gaps if g.gap_type == "planned_test"])
        
        pattern_coverage = (pattern_covered / total_patterns * 100) if total_patterns > 0 else 100
        prd_coverage = (prd_covered / total_prd * 100) if total_prd > 0 else 100
        api_coverage = (api_covered / total_api * 100) if total_api > 0 else 100
        planned_coverage = (planned_covered / total_planned * 100) if total_planned > 0 else 100
        
        # Overall coverage (weighted)
        weights = {
            "pattern": 0.35,
            "prd": 0.25,
            "api": 0.20,
            "planned": 0.20
        }
        
        overall_coverage = (
            pattern_coverage * weights["pattern"] +
            prd_coverage * weights["prd"] +
            api_coverage * weights["api"] +
            planned_coverage * weights["planned"]
        )
        
        result = ValidationResult(
            is_valid=len(gaps) == 0,
            gaps=gaps,
            coverage_score=overall_coverage,
            pattern_coverage=pattern_coverage,
            prd_coverage=prd_coverage,
            api_coverage=api_coverage,
            planned_test_coverage=planned_coverage
        )
        
        logger.info(f"[VALIDATOR] {result.get_summary()}")
        if gaps:
            logger.warning(f"[VALIDATOR] Found {len(gaps)} coverage gaps")
            for gap in gaps[:5]:  # Log first 5
                logger.warning(f"[VALIDATOR]   - {gap.gap_type}: {gap.description}")
        
        return result
    
    def _check_pattern_coverage(
        self,
        patterns: List[PatternMatch],
        combined_text: str
    ) -> List[ValidationGap]:
        """Check if all patterns are covered in tests."""
        gaps = []
        
        for pattern in patterns:
            # Check if the matched text appears in any test
            matched_text_lower = pattern.matched_text.lower()
            
            # For DIFFERENT_X, check if multiple values are tested
            if pattern.pattern_type == "DIFFERENT_X":
                # Look for variations (e.g., "keycloak" and "okta" for "different IDP")
                if matched_text_lower not in combined_text:
                    gaps.append(ValidationGap(
                        gap_type="pattern",
                        description=f"Pattern {pattern.pattern_type}: '{pattern.matched_text}' not tested with multiple values",
                        severity="critical",
                        source_item=pattern
                    ))
            
            elif pattern.pattern_type == "SPECIFIC_USER":
                # Look for the specific user type
                if matched_text_lower not in combined_text:
                    gaps.append(ValidationGap(
                        gap_type="pattern",
                        description=f"Pattern {pattern.pattern_type}: '{pattern.matched_text}' user type not tested",
                        severity="high",
                        source_item=pattern
                    ))
            
            elif pattern.pattern_type == "NAMED_FEATURE":
                # Look for the feature name
                if matched_text_lower not in combined_text:
                    gaps.append(ValidationGap(
                        gap_type="pattern",
                        description=f"Pattern {pattern.pattern_type}: '{pattern.matched_text}' feature not tested",
                        severity="high",
                        source_item=pattern
                    ))
            
            elif pattern.pattern_type == "HIDDEN_VISIBLE":
                # Look for visibility-related keywords
                visibility_keywords = ["hidden", "visible", "disabled", "enabled", "not visible", "not shown"]
                if not any(kw in combined_text for kw in visibility_keywords):
                    gaps.append(ValidationGap(
                        gap_type="pattern",
                        description=f"Pattern {pattern.pattern_type}: '{pattern.matched_text}' visibility not verified",
                        severity="medium",
                        source_item=pattern
                    ))
        
        return gaps
    
    def _check_prd_coverage(
        self,
        prd_requirements: List[PRDRequirement],
        combined_text: str
    ) -> List[ValidationGap]:
        """Check if all PRD requirements are covered."""
        gaps = []
        
        for prd in prd_requirements:
            # Extract key words from requirement
            requirement_words = prd.requirement.lower().split()
            key_words = [w for w in requirement_words if len(w) > 3][:4]  # First 4 significant words
            
            # Check if any key words appear in tests
            matches = sum(1 for word in key_words if word in combined_text)
            
            if matches < len(key_words) / 2:  # Less than half of key words found
                gaps.append(ValidationGap(
                    gap_type="prd",
                    description=f"PRD requirement not covered: '{prd.requirement[:50]}...'",
                    severity="high",
                    source_item=prd
                ))
        
        return gaps
    
    def _check_api_coverage(
        self,
        api_coverage: List[APICoverage],
        combined_text: str
    ) -> List[ValidationGap]:
        """Check if all must-test API endpoints are covered."""
        gaps = []
        
        for api in api_coverage:
            if not api.must_test:
                continue
            
            # Extract endpoint path
            endpoint_lower = api.endpoint.lower()
            
            # Check if endpoint appears in any test
            if endpoint_lower not in combined_text:
                # Also check for partial matches (e.g., "/audit" in "/audit/logs")
                path_parts = endpoint_lower.replace("get ", "").replace("post ", "").replace("put ", "").replace("delete ", "").split("/")
                significant_parts = [p for p in path_parts if p and len(p) > 2]
                
                matches = sum(1 for part in significant_parts if part in combined_text)
                
                if matches < len(significant_parts) / 2:
                    gaps.append(ValidationGap(
                        gap_type="api",
                        description=f"API endpoint not tested: {api.endpoint}",
                        severity="high",
                        source_item=api
                    ))
        
        return gaps
    
    def _check_planned_test_coverage(
        self,
        planned_tests: List[Dict],
        test_texts: List[str]
    ) -> List[ValidationGap]:
        """Check if all planned tests were created."""
        gaps = []
        
        for planned in planned_tests:
            test_idea = planned.test_idea if hasattr(planned, 'test_idea') else planned.get('test_idea', '')
            idea_words = test_idea.lower().split()
            key_words = [w for w in idea_words if len(w) > 3][:5]  # First 5 significant words
            
            # Check if any generated test matches this planned test
            found = False
            for test_text in test_texts:
                matches = sum(1 for word in key_words if word in test_text)
                if matches >= len(key_words) / 2:  # At least half of key words match
                    found = True
                    break
            
            if not found:
                gaps.append(ValidationGap(
                    gap_type="planned_test",
                    description=f"Planned test not created: '{test_idea[:50]}...'",
                    severity="high",
                    source_item=planned
                ))
        
        return gaps


def validate_test_coverage(
    coverage_plan: CoveragePlan,
    test_plan: TestPlan
) -> ValidationResult:
    """
    Convenience function to validate test coverage.
    
    Args:
        coverage_plan: The analysis output from Stage 1
        test_plan: The generated test plan from Stage 2
        
    Returns:
        ValidationResult with gaps and coverage scores
    """
    validator = CoverageValidator()
    return validator.validate(coverage_plan, test_plan)

