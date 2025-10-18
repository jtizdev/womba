"""
Test quality scoring system to measure test specificity and relevance.
"""

from typing import List
from loguru import logger

from src.models.test_case import TestCase
from src.models.story import JiraStory
from src.utils.text_processor import extract_keywords, calculate_text_similarity


class TestQualityScorer:
    """
    Scores test cases based on specificity, completeness, and relevance.
    
    Score breakdown (0-100):
    - Feature name mentioned: 30 points
    - Has 3+ steps: 20 points
    - Uses specific indicators (endpoints, UI elements): 25 points
    - Has realistic test data: 25 points
    """
    
    def __init__(self):
        self.min_passing_score = 60.0
    
    def score_test_case(self, test_case: TestCase, story: JiraStory) -> float:
        """
        Score a single test case for quality.
        
        Args:
            test_case: Test case to score
            story: Related Jira story
            
        Returns:
            Score between 0-100
        """
        score = 0.0
        
        # 1. Feature name mentioned (30 points)
        feature_score = self._score_feature_specificity(test_case, story)
        score += feature_score
        
        # 2. Has 3+ detailed steps (20 points)
        steps_score = self._score_step_completeness(test_case)
        score += steps_score
        
        # 3. Uses specific indicators (25 points)
        indicator_score = self._score_specific_indicators(test_case)
        score += indicator_score
        
        # 4. Has realistic test data (25 points)
        data_score = self._score_test_data(test_case)
        score += data_score
        
        logger.debug(
            f"Test '{test_case.title}' scored {score:.1f} "
            f"(feature:{feature_score:.1f}, steps:{steps_score:.1f}, "
            f"indicators:{indicator_score:.1f}, data:{data_score:.1f})"
        )
        
        return score
    
    def score_test_plan(
        self, 
        test_cases: List[TestCase], 
        story: JiraStory
    ) -> dict:
        """
        Score entire test plan.
        
        Args:
            test_cases: List of test cases
            story: Related Jira story
            
        Returns:
            Dictionary with scoring details
        """
        scores = [self.score_test_case(tc, story) for tc in test_cases]
        
        avg_score = sum(scores) / len(scores) if scores else 0.0
        passing_tests = sum(1 for s in scores if s >= self.min_passing_score)
        
        result = {
            "average_score": avg_score,
            "min_score": min(scores) if scores else 0.0,
            "max_score": max(scores) if scores else 0.0,
            "passing_tests": passing_tests,
            "total_tests": len(test_cases),
            "pass_rate": passing_tests / len(test_cases) if test_cases else 0.0,
            "individual_scores": scores
        }
        
        logger.info(
            f"Test plan quality: {avg_score:.1f}/100 "
            f"({passing_tests}/{len(test_cases)} passing)"
        )
        
        return result
    
    def _score_feature_specificity(self, test_case: TestCase, story: JiraStory) -> float:
        """
        Score whether test mentions the specific feature (30 points).
        """
        # Extract feature name from story
        feature_keywords = extract_keywords(story.summary, min_length=4)
        
        # Check if test mentions feature
        test_text = f"{test_case.title} {test_case.description}".lower()
        
        matches = sum(1 for kw in feature_keywords if kw in test_text)
        
        if matches >= 2:
            return 30.0  # Mentions multiple feature keywords
        elif matches == 1:
            return 20.0  # Mentions one keyword
        
        # Check for similarity as fallback
        similarity = calculate_text_similarity(
            story.summary,
            test_case.title + " " + test_case.description
        )
        
        return similarity * 30.0
    
    def _score_step_completeness(self, test_case: TestCase) -> float:
        """
        Score based on number and quality of steps (20 points).
        """
        step_count = len(test_case.steps)
        
        if step_count >= 5:
            return 20.0
        elif step_count >= 3:
            return 15.0
        elif step_count >= 2:
            return 10.0
        elif step_count >= 1:
            return 5.0
        
        return 0.0
    
    def _score_specific_indicators(self, test_case: TestCase) -> float:
        """
        Score based on use of specific indicators (25 points).
        
        Indicators:
        - API: POST, GET, PUT, DELETE, /endpoint
        - UI: Click, Verify, Navigate, Button, Tab, Screen
        - Data: Expect, Assert, Check, Confirm
        """
        indicators = {
            'api': ['post', 'get', 'put', 'delete', 'patch', 'endpoint', 'api', '/v1/', 'http'],
            'ui': ['click', 'verify', 'navigate', 'button', 'tab', 'screen', 'dialog', 'menu'],
            'validation': ['expect', 'assert', 'check', 'confirm', 'validate', 'ensure']
        }
        
        test_text = f"{test_case.title} {test_case.description}".lower()
        
        # Add step text
        for step in test_case.steps:
            test_text += f" {step.action} {step.expected_result}".lower()
        
        score = 0.0
        found_categories = set()
        
        for category, keywords in indicators.items():
            if any(kw in test_text for kw in keywords):
                found_categories.add(category)
        
        # Award points based on categories found
        if len(found_categories) >= 2:
            score = 25.0  # Uses multiple types of indicators
        elif len(found_categories) == 1:
            score = 15.0  # Uses one type
        
        return score
    
    def _score_test_data(self, test_case: TestCase) -> float:
        """
        Score based on presence of realistic test data (25 points).
        """
        has_data = False
        
        # Check steps for test data
        for step in test_case.steps:
            if step.test_data and len(str(step.test_data)) > 0:
                has_data = True
                break
        
        if has_data:
            return 25.0
        
        # Check for inline data in descriptions
        inline_indicators = [
            '{', '}',  # JSON
            'id:', 'name:', 'type:',  # Key-value pairs
            '=',  # Assignments
            '"', "'"  # Strings
        ]
        
        test_text = f"{test_case.description}"
        for step in test_case.steps:
            test_text += f" {step.action}"
        
        if any(ind in test_text for ind in inline_indicators):
            return 15.0  # Has some inline data
        
        return 0.0
    
    def is_test_acceptable(self, test_case: TestCase, story: JiraStory) -> bool:
        """
        Check if test meets minimum quality threshold.
        
        Args:
            test_case: Test case to evaluate
            story: Related story
            
        Returns:
            True if test passes quality check
        """
        score = self.score_test_case(test_case, story)
        return score >= self.min_passing_score
    
    def filter_low_quality_tests(
        self,
        test_cases: List[TestCase],
        story: JiraStory
    ) -> List[TestCase]:
        """
        Filter out low-quality tests.
        
        Args:
            test_cases: List of test cases
            story: Related story
            
        Returns:
            List of high-quality tests only
        """
        filtered = [
            tc for tc in test_cases
            if self.is_test_acceptable(tc, story)
        ]
        
        removed = len(test_cases) - len(filtered)
        if removed > 0:
            logger.warning(f"Filtered out {removed} low-quality tests")
        
        return filtered

