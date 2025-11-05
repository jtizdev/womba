"""
Response parser for AI-generated test plans.
Single Responsibility: Parsing AI responses into TestPlan objects.

Enhanced with:
- Reasoning extraction (chain-of-thought)
- Structured JSON parsing
- Support for both OpenAI and Claude formats
- Stricter validation
"""

import json
import re
from typing import List, Dict, Optional, Tuple
from loguru import logger

from src.models.test_plan import TestPlan, TestPlanMetadata
from src.models.test_case import TestCase, TestStep


class ResponseParser:
    """
    Parses AI responses into structured TestPlan objects.
    Features:
    - JSON extraction from AI responses
    - TestPlan object construction
    - Folder suggestion extraction
    """

    def parse_ai_response(self, response_text: str) -> Tuple[dict, Optional[str]]:
        """
        Parse AI response text into structured data and extract reasoning.
        
        Handles both:
        - OpenAI: Direct JSON (structured output)
        - Claude: JSON wrapped in XML tags
        
        Args:
            response_text: Raw response from AI
            
        Returns:
            Tuple of (parsed dictionary, reasoning text)
            
        Raises:
            ValueError: If response cannot be parsed
        """
        reasoning = None
        
        # Try Claude format first (JSON wrapped in <json> tags)
        if "<json>" in response_text and "</json>" in response_text:
            logger.debug("Detected Claude format (XML-wrapped JSON)")
            json_start = response_text.find("<json>") + 6
            json_end = response_text.find("</json>")
            json_text = response_text[json_start:json_end].strip()
        else:
            # OpenAI format (direct JSON)
            logger.debug("Detected OpenAI format (direct JSON)")
            json_start = response_text.find("{")
            json_end = response_text.rfind("}") + 1
            
            if json_start == -1 or json_end == 0:
                raise ValueError("No JSON found in AI response")
            
            json_text = response_text[json_start:json_end]

        try:
            data = json.loads(json_text)
            
            # Extract reasoning if present
            reasoning = data.get("reasoning")
            if reasoning:
                logger.info(f"Extracted reasoning: {len(reasoning)} chars")
            
            return data, reasoning
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {e}")
            logger.error(f"Response text preview: {json_text[:500]}")
            raise ValueError(f"Invalid JSON in AI response: {e}")

    def build_test_plan(
        self,
        main_story: any,
        test_plan_data: dict,
        ai_model: str,
        folder_structure: Optional[List[Dict]] = None,
        reasoning: Optional[str] = None,
        validation_check: Optional[Dict] = None
    ) -> TestPlan:
        """
        Build TestPlan object from parsed AI data with reasoning.
        
        Args:
            main_story: The main Jira story
            test_plan_data: Parsed test plan data from AI
            ai_model: AI model used
            folder_structure: Optional folder structure for fallback
            reasoning: Optional reasoning/analysis from AI
            validation_check: Optional self-validation results from AI
            
        Returns:
            TestPlan object
        """
        # Extract test cases
        test_cases = []
        for tc_data in test_plan_data.get("test_cases", []):
            # Parse steps
            steps = [
                TestStep(
                    step_number=step.get("step_number", idx + 1),
                    action=step.get("action", ""),
                    expected_result=step.get("expected_result", ""),
                    test_data=step.get("test_data"),
                )
                for idx, step in enumerate(tc_data.get("steps", []))
            ]

            # Create test case
            test_case = TestCase(
                title=tc_data.get("title", "Untitled Test"),
                description=tc_data.get("description", ""),
                preconditions=tc_data.get("preconditions"),
                steps=steps,
                expected_result=tc_data.get("expected_result", ""),
                priority=tc_data.get("priority", "medium"),
                test_type=tc_data.get("test_type", "functional"),
                tags=tc_data.get("tags", []),
                automation_candidate=tc_data.get("automation_candidate", True),
                risk_level=tc_data.get("risk_level", "medium"),
            )
            test_cases.append(test_case)

        # Count test types
        edge_case_count = sum(
            1 for tc in test_cases if tc.test_type == "edge_case" or "edge" in tc.tags
        )
        integration_test_count = sum(
            1 for tc in test_cases if tc.test_type == "integration"
        )
        
        # Extract validation issues if present
        validation_issues = []
        if validation_check:
            if not validation_check.get("all_tests_specific", True):
                validation_issues.append("Some tests may not be feature-specific")
            if not validation_check.get("no_placeholders", True):
                validation_issues.append("Placeholder data detected in tests")
            if not validation_check.get("terminology_matched", True):
                validation_issues.append("Terminology may not match company docs")

        # Build metadata with reasoning
        metadata = TestPlanMetadata(
            ai_model=ai_model,
            source_story_key=main_story.key,
            total_test_cases=len(test_cases),
            edge_case_count=edge_case_count,
            integration_test_count=integration_test_count,
            confidence_score=0.9,
            ai_reasoning=reasoning,
            validation_issues=validation_issues if validation_issues else None
        )

        # Extract suggested folder
        suggested_folder = test_plan_data.get("suggested_folder")
        
        # FALLBACK: If AI didn't suggest folder, extract dynamically from story
        if not suggested_folder and folder_structure:
            suggested_folder = self.extract_folder_from_story(main_story, folder_structure)
            logger.warning(f"AI didn't suggest folder, using dynamic fallback: {suggested_folder}")
        
        # Build test plan
        test_plan = TestPlan(
            story=main_story,
            test_cases=test_cases,
            metadata=metadata,
            summary=test_plan_data.get("summary", ""),
            coverage_analysis=test_plan_data.get("coverage_analysis"),
            risk_assessment=test_plan_data.get("risk_assessment"),
            dependencies=test_plan_data.get("dependencies", []),
            estimated_execution_time=test_plan_data.get("estimated_execution_time"),
            suggested_folder=suggested_folder,
        )

        return test_plan

    def extract_folder_from_story(
        self,
        main_story: any,
        folder_structure: List[Dict]
    ) -> str:
        """
        Dynamically extract folder from story by analyzing:
        1. Story component/labels
        2. Story summary keywords
        3. Existing folder structure
        
        Args:
            main_story: The main Jira story
            folder_structure: List of folders from Zephyr
            
        Returns:
            Suggested folder path
        """
        summary_lower = main_story.summary.lower()
        description_lower = (main_story.description or "").lower()
        combined_text = f"{summary_lower} {description_lower}"
        
        # Extract all folder names from structure
        folder_names = []
        for folder in folder_structure:
            folder_names.append(folder.get('name', ''))
            if folder.get('folders'):
                for subfolder in folder['folders']:
                    folder_names.append(f"{folder.get('name')}/{subfolder.get('name')}")
        
        # Score each folder based on keyword matches
        folder_scores = {}
        for folder_name in folder_names:
            if not folder_name:
                continue
            
            folder_lower = folder_name.lower()
            score = 0
            
            # Check for keyword matches
            folder_keywords = folder_lower.replace('/', ' ').split()
            for keyword in folder_keywords:
                if len(keyword) > 3:  # Ignore short words
                    if keyword in combined_text:
                        score += 2  # Strong match
                    elif any(keyword in word for word in combined_text.split()):
                        score += 1  # Partial match
            
            if score > 0:
                folder_scores[folder_name] = score
        
        # Return folder with highest score
        if folder_scores:
            best_folder = max(folder_scores, key=folder_scores.get)
            logger.info(f"Dynamic folder selection: {best_folder} (score: {folder_scores[best_folder]})")
            return best_folder
        
        # Last resort: extract component from summary or use General
        component_match = re.search(r'\(([A-Z][A-Za-z\s]+)\)', main_story.summary)
        if component_match:
            component = component_match.group(1).strip()
            return f"{component}/Feature Tests"
        
        # Check for common patterns in first part of summary
        parts = main_story.summary.split('-')
        if len(parts) > 1:
            potential_component = parts[0].strip()
            if len(potential_component) < 20:  # Likely a component name
                return f"{potential_component}/Feature Tests"
        
        return "General/Automated Tests"

    def validate_test_cases(self, test_plan: TestPlan) -> List[str]:
        """
        Validate generated test cases for quality issues with stricter criteria.
        
        Checks for:
        - Missing or null test_data
        - Placeholder patterns
        - Generic test names
        - Empty descriptions
        
        Args:
            test_plan: TestPlan to validate
            
        Returns:
            List of validation warnings
        """
        warnings = []
        
        for tc in test_plan.test_cases:
            # Check test name quality
            if not tc.title.startswith("Verify"):
                warnings.append(f"Test '{tc.title}' should start with 'Verify'")
            
            if any(generic in tc.title.lower() for generic in ["happy path", "test case", "basic test"]):
                warnings.append(f"Test '{tc.title}' has generic naming")
            
            # Check description
            if not tc.description or len(tc.description) < 20:
                warnings.append(f"Test '{tc.title}' has insufficient description")
            
            # Check steps
            for step in tc.steps:
                step_data = step.get('test_data', '') if isinstance(step, dict) else getattr(step, 'test_data', '')
                step_number = step.get('step_number', '?') if isinstance(step, dict) else getattr(step, 'step_number', '?')
                
                # Check for null or empty test_data
                if step_data is None or (isinstance(step_data, str) and not step_data.strip()):
                    warnings.append(f"Test '{tc.title}' step {step_number} missing test_data")
                
                # Check for placeholder patterns
                placeholders = ['<', '>', 'Bearer ', 'placeholder', 'TODO', 'FIXME', '<token>', '<value>']
                if any(placeholder in str(step_data) for placeholder in placeholders):
                    warnings.append(f"Test '{tc.title}' step {step_number} contains placeholder")
        
        # Log warnings
        if warnings:
            logger.warning(f"Found {len(warnings)} validation issues:")
            for warning in warnings[:5]:  # Log first 5
                logger.warning(f"  - {warning}")
            if len(warnings) > 5:
                logger.warning(f"  ... and {len(warnings) - 5} more")
        else:
            logger.info("✓ All tests passed validation")
        
        return warnings

