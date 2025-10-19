"""
Framework detection for test automation repositories.
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Optional
from loguru import logger


class FrameworkDetector:
    """Detects test framework and patterns in a repository."""

    FRAMEWORK_INDICATORS = {
        "playwright": [
            "playwright.config",
            "@playwright/test",
            "test.describe",
            "test.step"
        ],
        "cypress": [
            "cypress.config",
            "cypress/",
            "cy.visit",
            "cy.get"
        ],
        "selenium": [
            "selenium",
            "webdriver",
            "WebDriver",
            "driver.find_element"
        ],
        "rest-assured": [
            "rest-assured",
            "RestAssured",
            "given().when().then()",
            "import static io.restassured"
        ],
        "junit": [
            "junit",
            "@Test",
            "org.junit",
            "TestCase"
        ],
        "pytest": [
            "pytest",
            "def test_",
            "import pytest",
            "pytest.fixture"
        ],
        "jest": [
            "jest.config",
            "describe(",
            "it(",
            "expect("
        ]
    }

    def __init__(self, repo_path: str):
        """
        Args:
            repo_path: Path to the test repository
        """
        self.repo_path = Path(repo_path)
        if not self.repo_path.exists():
            raise ValueError(f"Repository path does not exist: {repo_path}")

    def detect_framework(self) -> str:
        """
        Detect the primary test framework used in the repository.

        Returns:
            Framework name (e.g., 'playwright', 'cypress', 'rest-assured')
        """
        logger.info(f"Detecting test framework in {self.repo_path}")

        scores = {framework: 0 for framework in self.FRAMEWORK_INDICATORS}

        # Check package.json, pom.xml, requirements.txt, etc.
        scores = self._check_dependency_files(scores)

        # Check source files
        scores = self._check_source_files(scores)

        # Get framework with highest score
        detected_framework = max(scores, key=scores.get)
        logger.info(f"Detected framework: {detected_framework} (score: {scores[detected_framework]})")

        return detected_framework if scores[detected_framework] > 0 else "unknown"

    def _check_dependency_files(self, scores: Dict[str, int]) -> Dict[str, int]:
        """Check dependency files for framework indicators."""
        # package.json (JavaScript/TypeScript)
        package_json = self.repo_path / "package.json"
        if package_json.exists():
            content = package_json.read_text()
            if "playwright" in content:
                scores["playwright"] += 10
            if "cypress" in content:
                scores["cypress"] += 10
            if "jest" in content:
                scores["jest"] += 5

        # pom.xml (Java/Maven)
        pom_xml = self.repo_path / "pom.xml"
        if pom_xml.exists():
            content = pom_xml.read_text()
            if "rest-assured" in content:
                scores["rest-assured"] += 10
            if "junit" in content:
                scores["junit"] += 10
            if "selenium" in content:
                scores["selenium"] += 5

        # requirements.txt (Python)
        requirements = self.repo_path / "requirements.txt"
        if requirements.exists():
            content = requirements.read_text()
            if "pytest" in content:
                scores["pytest"] += 10
            if "selenium" in content:
                scores["selenium"] += 5
            if "playwright" in content:
                scores["playwright"] += 10

        return scores

    def _check_source_files(self, scores: Dict[str, int]) -> Dict[str, int]:
        """Check source files for framework patterns."""
        # Find test files
        test_extensions = [".js", ".ts", ".py", ".java"]
        test_files = []

        for ext in test_extensions:
            test_files.extend(self.repo_path.rglob(f"*test*{ext}"))
            test_files.extend(self.repo_path.rglob(f"*spec*{ext}"))

        # Check first 10 test files
        for test_file in test_files[:10]:
            try:
                content = test_file.read_text()
                for framework, indicators in self.FRAMEWORK_INDICATORS.items():
                    for indicator in indicators:
                        if indicator in content:
                            scores[framework] += 1
            except Exception as e:
                logger.debug(f"Could not read {test_file}: {e}")

        return scores

    def analyze_patterns(self) -> Dict[str, any]:
        """
        Analyze code patterns in the repository.

        Returns:
            Dictionary with detected patterns:
            - naming_pattern: File naming convention
            - directory_structure: Test directory structure
            - import_patterns: Common imports
            - test_structure: Common test structure patterns
        """
        logger.info("Analyzing code patterns...")

        patterns = {
            "naming_pattern": self._detect_naming_pattern(),
            "directory_structure": self._detect_directory_structure(),
            "import_patterns": self._detect_import_patterns(),
            "test_structure": self._detect_test_structure()
        }

        return patterns

    def _detect_naming_pattern(self) -> str:
        """Detect file naming pattern (e.g., *.test.js, *_test.py)."""
        test_files = list(self.repo_path.rglob("*test*"))
        
        if not test_files:
            return "unknown"

        # Count naming patterns
        patterns = {
            ".test.": 0,
            "_test.": 0,
            "Test.": 0,
            ".spec.": 0
        }

        for file in test_files:
            for pattern in patterns:
                if pattern in file.name:
                    patterns[pattern] += 1

        most_common = max(patterns, key=patterns.get)
        return most_common if patterns[most_common] > 0 else "unknown"

    def _detect_directory_structure(self) -> Dict[str, str]:
        """Detect test directory structure."""
        common_test_dirs = ["tests/", "test/", "spec/", "__tests__/", "e2e/", "integration/"]
        
        found_dirs = []
        for test_dir in common_test_dirs:
            if (self.repo_path / test_dir).exists():
                found_dirs.append(test_dir)

        return {
            "test_directories": found_dirs,
            "structure_type": "colocated" if not found_dirs else "separate"
        }

    def _detect_import_patterns(self) -> List[str]:
        """Detect common import patterns."""
        imports = set()
        test_files = list(self.repo_path.rglob("*test*"))[:10]

        for file in test_files:
            try:
                content = file.read_text()
                # Extract imports (simplified)
                import_matches = re.findall(r'^import .+$', content, re.MULTILINE)
                imports.update(import_matches[:5])  # Keep top 5 imports per file
            except Exception:
                pass

        return list(imports)[:20]  # Return top 20 most common

    def _detect_test_structure(self) -> str:
        """Detect common test structure pattern."""
        # This is a simplified version
        # In production, you'd use AST parsing
        return "describe/it"  # or "class-based", "function-based", etc.

