"""
Document processing service for cleaning and preparing documents.
Single Responsibility: Text cleaning, HTML parsing, content extraction.
"""

from typing import Optional
from loguru import logger
from src.infrastructure.html_parser import HTMLParser
from src.models.test_plan import TestPlan


class DocumentProcessor:
    """
    Processes and cleans documents before indexing.
    Features:
    - HTML to text conversion
    - Title extraction
    - Test plan formatting
    """

    def __init__(self):
        """Initialize document processor with HTML parser."""
        self.html_parser = HTMLParser()

    def strip_html_tags(self, html: str) -> str:
        """
        Convert HTML to readable text.
        
        Args:
            html: HTML content
            
        Returns:
            Clean text content
        """
        return self.html_parser.strip_html_tags(html)

    def extract_title(self, html: str, fallback: str = "Untitled") -> str:
        """
        Extract title from HTML.
        
        Args:
            html: HTML content
            fallback: Fallback title if extraction fails
            
        Returns:
            Extracted title
        """
        return self.html_parser.extract_title(html, fallback)

    def build_test_plan_document(self, test_plan: TestPlan) -> str:
        """
        Build a searchable document from a test plan.
        
        Args:
            test_plan: Test plan to convert
            
        Returns:
            Formatted document text with complete details
        """
        sections = []
        
        # Story context
        sections.append(f"Story: {test_plan.story.key} - {test_plan.story.summary}")
        sections.append(f"Components: {', '.join(test_plan.story.components or [])}")
        sections.append(f"\nSummary: {test_plan.summary}")
        
        # Test cases - INDEX ALL with FULL details
        sections.append(f"\n{len(test_plan.test_cases)} Test Cases:")
        for i, tc in enumerate(test_plan.test_cases, 1):
            sections.append(f"\n{i}. {tc.title}")
            sections.append(f"   Type: {tc.test_type}, Priority: {tc.priority}, Risk: {tc.risk_level}")
            sections.append(f"   Description: {tc.description}")
            
            if tc.preconditions:
                sections.append(f"   Preconditions: {tc.preconditions}")
            
            if tc.steps:
                sections.append(f"   Steps ({len(tc.steps)} total):")
                for step in tc.steps:
                    sections.append(f"      Step {step.step_number}: {step.action}")
                    sections.append(f"         Expected: {step.expected_result}")
                    if step.test_data:
                        sections.append(f"         Test Data: {step.test_data}")
            
            if tc.expected_result:
                sections.append(f"   Expected Result: {tc.expected_result}")
            
            if tc.tags:
                sections.append(f"   Tags: {', '.join(tc.tags)}")
        
        return "\n".join(sections)

    def build_confluence_document(self, doc_dict: dict) -> str:
        """
        Build document text from Confluence doc.
        
        Args:
            doc_dict: Confluence document dictionary
            
        Returns:
            Formatted document text
        """
        title = doc_dict.get('title', 'Unknown')
        content = doc_dict.get('content', '')
        return f"Title: {title}\n\n{content}"

    def build_jira_story_document(self, story) -> str:
        """
        Build document text from Jira story.
        
        Args:
            story: JiraStory object
            
        Returns:
            Formatted document text
        """
        doc_text = f"Story: {story.key} - {story.summary}\n\n"
        
        if story.description:
            doc_text += f"Description: {story.description}\n\n"
        
        if hasattr(story, 'acceptance_criteria') and story.acceptance_criteria:
            doc_text += f"Acceptance Criteria: {story.acceptance_criteria}"
        
        return doc_text

    def build_test_case_document(self, test: dict) -> str:
        """
        Build document text from existing test case.
        
        Args:
            test: Test case dictionary
            
        Returns:
            Formatted document text
        """
        doc_text = f"Test: {test.get('name', 'Unknown')}\n\n"
        
        if test.get('objective'):
            doc_text += f"Objective: {test.get('objective', '')}\n\n"
        
        if test.get('precondition'):
            doc_text += f"Precondition: {test.get('precondition', '')}\n\n"
        
        if test.get('testScript'):
            script = test.get('testScript', {})
            if isinstance(script, dict) and script.get('steps'):
                doc_text += "Steps:\n"
                for step in script.get('steps', []):
                    if isinstance(step, dict):
                        doc_text += f"  - {step.get('description', '')}\n"
                        if step.get('expectedResult'):
                            doc_text += f"    Expected: {step.get('expectedResult')}\n"
        
        return doc_text

    def build_external_doc_document(self, url: str, title: str, html: str) -> Optional[str]:
        """
        Build document text from external documentation.
        
        Args:
            url: Source URL
            title: Document title
            html: HTML content
            
        Returns:
            Formatted document text or None if no content
        """
        text = self.strip_html_tags(html)
        if not text:
            logger.warning(f"No textual content extracted from {url}")
            return None
        
        return f"Source: {url}\nTitle: {title}\n\nContent:\n{text}"

