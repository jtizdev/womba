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
from src.models.enriched_story import EnrichedStory


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
        
        # Extract summary (handle if it's a dict)
        summary = test_plan_data.get("summary", "")
        if isinstance(summary, dict):
            summary = summary.get("summary") or summary.get("text") or str(summary)
        summary = str(summary) if summary else ""
        
        # Build test plan
        test_plan = TestPlan(
            story=main_story,
            test_cases=test_cases,
            metadata=metadata,
            summary=summary,
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

    def validate_test_cases(self, test_plan: TestPlan, enriched_story: Optional[EnrichedStory] = None) -> List[str]:
        """
        Validate generated test cases for quality issues with stricter criteria.
        
        Checks for:
        - Missing or null test_data
        - Placeholder patterns
        - Generic test names
        - Empty descriptions
        - API test requirements (if story has API specs)
        - UI test navigation detail
        - Test naming patterns (no "Verify" prefix)
        
        Args:
            test_plan: TestPlan to validate
            enriched_story: Optional EnrichedStory to check for API specifications
            
        Returns:
            List of validation warnings
        """
        warnings = []
        
        # Check if story has API specifications
        # NOTE: API specs are now in APIContext, not EnrichedStory
        has_api_specs = False
        api_endpoints = []
        # Enriched story no longer contains API specs - they're built separately
        # This validation now just checks test structure
        
        # Count API and UI tests
        api_tests = []
        ui_tests = []
        
        for tc in test_plan.test_cases:
            # Check test name quality (NO "Verify" prefix)
            if tc.title.startswith(("Verify", "Validate", "Test", "Check")):
                warnings.append(f"Test '{tc.title}' should NOT start with 'Verify/Validate/Test/Check' - use business-focused naming")
            
            if any(generic in tc.title.lower() for generic in ["happy path", "test case", "basic test"]):
                warnings.append(f"Test '{tc.title}' has generic naming")
            
            # Check if test title contains HTTP status codes (should be in steps, not title)
            if any(code in tc.title for code in ["200", "400", "404", "500", "403", "401"]):
                warnings.append(f"Test '{tc.title}' contains HTTP status code in title - status codes should be in test steps, not titles")
            
            # Check description
            if not tc.description or len(tc.description) < 20:
                warnings.append(f"Test '{tc.title}' has insufficient description")
            
            # Classify test type based on tags and steps
            is_api_test = "API" in (tc.tags or [])
            is_ui_test = "UI" in (tc.tags or [])
            
            if is_api_test:
                api_tests.append(tc)
            if is_ui_test:
                ui_tests.append(tc)
            
            # Check steps
            for step in tc.steps:
                step_dict = step if isinstance(step, dict) else step.model_dump() if hasattr(step, 'model_dump') else {}
                step_action = step_dict.get('action', '')
                step_data = step_dict.get('test_data', '')
                step_number = step_dict.get('step_number', '?')
                
                # Check for null or empty test_data
                if step_data is None or (isinstance(step_data, str) and not step_data.strip()):
                    warnings.append(f"Test '{tc.title}' step {step_number} missing test_data")
                
                # Check for placeholder patterns
                placeholders = ['<', '>', 'Bearer ', 'placeholder', 'TODO', 'FIXME', '<token>', '<value>']
                if any(placeholder in str(step_data) for placeholder in placeholders):
                    warnings.append(f"Test '{tc.title}' step {step_number} contains placeholder")
                
                # API test validation
                if is_api_test:
                    # Check if API test has HTTP method and endpoint (only for API call steps, not validation steps)
                    is_api_call_step = any(method in step_action for method in ["GET ", "POST ", "PATCH ", "PUT ", "DELETE "])
                    is_validation_step = any(word in step_action.lower() for word in ["validate", "check", "verify", "confirm"])
                    
                    if is_api_call_step:
                        # This step makes an API call - must have endpoint
                        has_endpoint = "/" in step_action and any(char in step_action for char in ["/policy-mgmt", "/api/", "/orchestrator", "/internal-assets"])
                        if not has_endpoint:
                            warnings.append(f"API test '{tc.title}' step {step_number} missing endpoint path")
                    elif step_number == 1 and not is_validation_step:
                        # First step must be an API call (unless it's a validation step)
                        warnings.append(f"API test '{tc.title}' step {step_number} missing HTTP method (GET/POST/PATCH/DELETE) - first step must make an API call")
                    
                    # Check for UI navigation in API test (should not have)
                    if any(nav in step_action for nav in ["Navigate to", "Click", "Select"]):
                        warnings.append(f"API test '{tc.title}' step {step_number} contains UI navigation - API tests should only have HTTP calls")
                
                # UI test validation
                if is_ui_test:
                    # Check if UI test has detailed navigation (only first step needs navigation)
                    is_navigation_step = "Navigate to" in step_action or "→" in step_action
                    is_verification_step = any(word in step_action.lower() for word in ["check", "verify", "confirm", "validate"])
                    
                    if step_number == 1:
                        # First step must have navigation
                        has_workspace = any(ws in step_action for ws in ["Authorization Workspace", "Identity Workspace", "Orchestration Workspace", "Administration Workspace"])
                        if not is_navigation_step:
                            warnings.append(f"UI test '{tc.title}' step {step_number} missing navigation path - should include 'Navigate to Workspace → Menu → Item'")
                        elif not has_workspace:
                            warnings.append(f"UI test '{tc.title}' step {step_number} navigation should specify workspace (e.g., 'Authorization Workspace')")
                    # Note: Step 2+ can be verification steps, so we don't require navigation
                    
                    # Check for API endpoints in UI test (should not have)
                    if any(endpoint in step_action for endpoint in ["GET /", "POST /", "PATCH /", "PUT /", "DELETE /"]):
                        warnings.append(f"UI test '{tc.title}' step {step_number} contains API endpoint - UI tests should only have navigation steps")
        
        # API test coverage validation
        if has_api_specs:
            if len(api_tests) == 0:
                warnings.append(f"CRITICAL: Story has {len(api_endpoints)} API endpoint(s) but generated 0 API tests. Must generate at least 1 API test per endpoint.")
            else:
                # Check if we have tests for all endpoints
                covered_endpoints = set()
                for api_test in api_tests:
                    for step in api_test.steps:
                        step_dict = step if isinstance(step, dict) else step.model_dump() if hasattr(step, 'model_dump') else {}
                        step_action = step_dict.get('action', '')
                        for endpoint in api_endpoints:
                            if endpoint in step_action or endpoint.split('/')[-1] in step_action:
                                covered_endpoints.add(endpoint)
                
                missing_endpoints = set(api_endpoints) - covered_endpoints
                if missing_endpoints:
                    warnings.append(f"Story has {len(missing_endpoints)} API endpoint(s) without tests: {', '.join(list(missing_endpoints)[:3])}")
        
        # Log warnings
        if warnings:
            logger.warning(f"Found {len(warnings)} validation issues:")
            for warning in warnings[:10]:  # Log first 10
                logger.warning(f"  - {warning}")
            if len(warnings) > 10:
                logger.warning(f"  ... and {len(warnings) - 10} more")
        else:
            logger.info("✓ All tests passed validation")
        
        return warnings

