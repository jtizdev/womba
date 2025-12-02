"""
Coverage Plan models for two-stage test generation.

Stage 1 (Analysis) outputs a CoveragePlan that Stage 2 (Generation) uses
to ensure complete and intelligent test coverage.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class PatternMatch:
    """
    A pattern detected in an acceptance criterion.
    
    Patterns:
    - DIFFERENT_X: AC mentions "different/multiple/various X" → test with 2+ X values
    - SPECIFIC_USER: AC mentions specific user type (root, admin, guest) → test with that user
    - NAMED_FEATURE: AC mentions feature name (compare, filter, sort) → test that feature
    - HIDDEN_VISIBLE: PRD mentions hidden/visible elements → verify visibility
    """
    ac_number: int
    pattern_type: str  # DIFFERENT_X, SPECIFIC_USER, NAMED_FEATURE, HIDDEN_VISIBLE
    matched_text: str  # The actual text that matched (e.g., "different IDP")
    requirement: str   # What this means for testing (e.g., "Test with 2+ IDPs")
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "ac_number": self.ac_number,
            "pattern_type": self.pattern_type,
            "matched_text": self.matched_text,
            "requirement": self.requirement
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PatternMatch":
        return cls(
            ac_number=data.get("ac_number", 0),
            pattern_type=data.get("pattern_type", ""),
            matched_text=data.get("matched_text", ""),
            requirement=data.get("requirement", "")
        )


@dataclass
class PRDRequirement:
    """
    A requirement extracted from PRD/Confluence documentation.
    
    These are often missed if only focusing on ACs - things like:
    - "Parent Name field should be hidden"
    - "Button should be disabled when X"
    - "Compare changes feature available"
    """
    source: str        # "PRD", "Confluence", "Story Description"
    requirement: str   # The actual requirement text
    test_needed: str   # What test is needed to verify this
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "requirement": self.requirement,
            "test_needed": self.test_needed
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PRDRequirement":
        return cls(
            source=data.get("source", ""),
            requirement=data.get("requirement", ""),
            test_needed=data.get("test_needed", "")
        )


@dataclass
class APICoverage:
    """
    An API endpoint that needs test coverage.
    
    Extracted from Swagger docs, story description, or GitLab MCP.
    """
    endpoint: str      # e.g., "GET /audit/logs"
    source: str        # "swagger", "story", "gitlab_mcp"
    must_test: bool    # Whether this endpoint must be explicitly tested
    description: Optional[str] = None  # What this endpoint does
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "endpoint": self.endpoint,
            "source": self.source,
            "must_test": self.must_test,
            "description": self.description
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "APICoverage":
        return cls(
            endpoint=data.get("endpoint", ""),
            source=data.get("source", ""),
            must_test=data.get("must_test", True),
            description=data.get("description")
        )


@dataclass
class ExistingTestOverlap:
    """
    An existing test that overlaps with what we might generate.
    
    Used to avoid creating duplicate tests.
    """
    existing_test_name: str
    skip_reason: str  # Why we should skip creating a similar test
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "existing_test_name": self.existing_test_name,
            "skip_reason": self.skip_reason
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExistingTestOverlap":
        return cls(
            existing_test_name=data.get("existing_test_name", ""),
            skip_reason=data.get("skip_reason", "")
        )


@dataclass
class PlannedTest:
    """
    A test idea from the coverage plan.
    
    This is the output of Stage 1 analysis - each planned test
    should become a real test case in Stage 2.
    """
    test_idea: str                          # Brief description of the test
    covers_acs: List[int] = field(default_factory=list)  # AC numbers covered
    covers_patterns: List[str] = field(default_factory=list)  # Pattern types covered
    covers_prd: bool = False                # Whether this covers a PRD requirement
    api_endpoints: List[str] = field(default_factory=list)  # API endpoints tested
    priority: str = "high"                  # critical, high, medium, low
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_idea": self.test_idea,
            "covers_acs": self.covers_acs,
            "covers_patterns": self.covers_patterns,
            "covers_prd": self.covers_prd,
            "api_endpoints": self.api_endpoints,
            "priority": self.priority
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlannedTest":
        return cls(
            test_idea=data.get("test_idea", ""),
            covers_acs=data.get("covers_acs", []),
            covers_patterns=data.get("covers_patterns", []),
            covers_prd=data.get("covers_prd", False),
            api_endpoints=data.get("api_endpoints", []),
            priority=data.get("priority", "high")
        )


@dataclass
class CoveragePlan:
    """
    The complete coverage plan output from Stage 1 analysis.
    
    This structured plan ensures Stage 2 generates tests that:
    - Cover all detected patterns (DIFFERENT_X, SPECIFIC_USER, etc.)
    - Include PRD requirements (hidden fields, UI behavior)
    - Test all relevant API endpoints
    - Avoid duplicating existing tests
    - Follow the planned test structure
    """
    story_key: str
    story_title: str
    
    # Analysis results
    pattern_matches: List[PatternMatch] = field(default_factory=list)
    prd_requirements: List[PRDRequirement] = field(default_factory=list)
    api_coverage: List[APICoverage] = field(default_factory=list)
    existing_test_overlap: List[ExistingTestOverlap] = field(default_factory=list)
    
    # Planned tests
    test_plan: List[PlannedTest] = field(default_factory=list)
    
    # Analysis reasoning
    analysis_reasoning: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "story_key": self.story_key,
            "story_title": self.story_title,
            "pattern_matches": [p.to_dict() for p in self.pattern_matches],
            "prd_requirements": [p.to_dict() for p in self.prd_requirements],
            "api_coverage": [a.to_dict() for a in self.api_coverage],
            "existing_test_overlap": [e.to_dict() for e in self.existing_test_overlap],
            "test_plan": [t.to_dict() for t in self.test_plan],
            "analysis_reasoning": self.analysis_reasoning
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CoveragePlan":
        return cls(
            story_key=data.get("story_key", ""),
            story_title=data.get("story_title", ""),
            pattern_matches=[PatternMatch.from_dict(p) for p in data.get("pattern_matches", [])],
            prd_requirements=[PRDRequirement.from_dict(p) for p in data.get("prd_requirements", [])],
            api_coverage=[APICoverage.from_dict(a) for a in data.get("api_coverage", [])],
            existing_test_overlap=[ExistingTestOverlap.from_dict(e) for e in data.get("existing_test_overlap", [])],
            test_plan=[PlannedTest.from_dict(t) for t in data.get("test_plan", [])],
            analysis_reasoning=data.get("analysis_reasoning", "")
        )
    
    def get_uncovered_patterns(self, generated_tests: List[Dict]) -> List[PatternMatch]:
        """Find patterns that aren't covered by generated tests."""
        covered_patterns = set()
        for test in generated_tests:
            # Check test title/description for pattern coverage
            test_text = f"{test.get('title', '')} {test.get('description', '')}".lower()
            for pattern in self.pattern_matches:
                if pattern.matched_text.lower() in test_text:
                    covered_patterns.add(pattern.pattern_type)
        
        return [p for p in self.pattern_matches if p.pattern_type not in covered_patterns]
    
    def get_uncovered_prd_requirements(self, generated_tests: List[Dict]) -> List[PRDRequirement]:
        """Find PRD requirements that aren't covered by generated tests."""
        uncovered = []
        for prd in self.prd_requirements:
            covered = False
            for test in generated_tests:
                test_text = f"{test.get('title', '')} {test.get('description', '')}".lower()
                if any(word in test_text for word in prd.requirement.lower().split()[:3]):
                    covered = True
                    break
            if not covered:
                uncovered.append(prd)
        return uncovered
    
    def get_summary(self) -> str:
        """Get a human-readable summary of the coverage plan."""
        return (
            f"Coverage Plan for {self.story_key}:\n"
            f"  - {len(self.pattern_matches)} patterns detected\n"
            f"  - {len(self.prd_requirements)} PRD requirements\n"
            f"  - {len(self.api_coverage)} API endpoints\n"
            f"  - {len(self.existing_test_overlap)} existing test overlaps\n"
            f"  - {len(self.test_plan)} planned tests"
        )

