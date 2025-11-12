"""
Document processing service for cleaning and preparing documents.
Single Responsibility: Text cleaning, HTML parsing, content extraction.
"""

from typing import Optional
import yaml
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
            # Ensure description is a string, not a PropertyHolder object
            description = str(story.description)
            # Remove object representations like "<jira.resources.PropertyHolder object at 0x...>"
            if description.startswith('<') and 'object at 0x' in description:
                description = ""  # Skip invalid descriptions
            doc_text += f"Description: {description}\n\n"
        
        if hasattr(story, 'acceptance_criteria') and story.acceptance_criteria:
            # Ensure acceptance criteria is a string
            ac = str(story.acceptance_criteria)
            if not ac.startswith('<') or 'object at 0x' not in ac:
                doc_text += f"Acceptance Criteria: {ac}"
        
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
        FULL CONTENT - metadata (URL, title) will be added by prompt builder.
        
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
        
        # Return ONLY the content - prompt builder will add metadata
        # This avoids duplication and makes the content cleaner
        return text

    def build_swagger_document(self, swagger_doc) -> str:
        """
        Build searchable document from Swagger/OpenAPI YAML.
        
        Args:
            swagger_doc: SwaggerDocument object with YAML content
            
        Returns:
            Formatted document text with API details
        """
        sections = []
        
        # Header
        sections.append(f"Service: {swagger_doc.service_name}")
        sections.append(f"Source: {swagger_doc.project_url}")
        sections.append(f"File: {swagger_doc.file_path}")
        sections.append(f"Branch: {swagger_doc.branch}")
        sections.append("")
        
        try:
            # Parse YAML
            spec = yaml.safe_load(swagger_doc.content)
            
            # API Info
            info = spec.get('info', {})
            if info:
                sections.append(f"API Title: {info.get('title', 'N/A')}")
                sections.append(f"Version: {info.get('version', 'N/A')}")
                if info.get('description'):
                    sections.append(f"Description: {info.get('description')}")
                sections.append("")
            
            # Servers
            servers = spec.get('servers', [])
            if servers:
                sections.append("Servers:")
                for server in servers:
                    sections.append(f"  - {server.get('url', 'N/A')}")
                    if server.get('description'):
                        sections.append(f"    {server.get('description')}")
                sections.append("")
            
            # Authentication
            security_schemes = spec.get('components', {}).get('securitySchemes', {})
            if security_schemes:
                sections.append("Authentication:")
                for name, scheme in security_schemes.items():
                    scheme_type = scheme.get('type', 'unknown')
                    sections.append(f"  - {name}: {scheme_type}")
                    if scheme.get('description'):
                        sections.append(f"    {scheme.get('description')}")
                sections.append("")
            
            # Paths/Endpoints
            paths = spec.get('paths', {})
            if paths:
                sections.append(f"Endpoints ({len(paths)} total):")
                sections.append("")
                
                for path, methods in paths.items():
                    for method, details in methods.items():
                        if method in ['get', 'post', 'put', 'patch', 'delete', 'options', 'head']:
                            sections.append(f"  {method.upper()} {path}")
                            
                            # Operation ID and summary
                            if details.get('operationId'):
                                sections.append(f"    Operation: {details['operationId']}")
                            if details.get('summary'):
                                sections.append(f"    Summary: {details['summary']}")
                            if details.get('description'):
                                sections.append(f"    Description: {details['description']}")
                            
                            # Tags
                            if details.get('tags'):
                                sections.append(f"    Tags: {', '.join(details['tags'])}")
                            
                            # Parameters
                            params = details.get('parameters', [])
                            if params:
                                sections.append(f"    Parameters:")
                                for param in params:
                                    param_name = param.get('name', 'unknown')
                                    param_in = param.get('in', 'unknown')
                                    param_required = ' (required)' if param.get('required') else ''
                                    param_type = param.get('schema', {}).get('type', 'unknown')
                                    sections.append(f"      - {param_name} ({param_in}, {param_type}){param_required}")
                                    if param.get('description'):
                                        sections.append(f"        {param.get('description')}")
                            
                            # Request Body
                            request_body = details.get('requestBody', {})
                            if request_body:
                                sections.append(f"    Request Body:")
                                content = request_body.get('content', {})
                                for content_type in content.keys():
                                    sections.append(f"      Content-Type: {content_type}")
                                if request_body.get('description'):
                                    sections.append(f"      {request_body['description']}")
                            
                            # Responses
                            responses = details.get('responses', {})
                            if responses:
                                sections.append(f"    Responses:")
                                for status_code, response in responses.items():
                                    desc = response.get('description', 'No description')
                                    sections.append(f"      {status_code}: {desc}")
                            
                            sections.append("")
            
            # Schemas (if not too many)
            schemas = spec.get('components', {}).get('schemas', {})
            if schemas and len(schemas) <= 20:
                sections.append(f"Data Models ({len(schemas)} schemas):")
                for schema_name, schema_def in schemas.items():
                    sections.append(f"  - {schema_name}")
                    if schema_def.get('description'):
                        sections.append(f"    {schema_def['description']}")
                    # List properties
                    properties = schema_def.get('properties', {})
                    if properties:
                        sections.append(f"    Properties: {', '.join(properties.keys())}")
                sections.append("")
            
        except yaml.YAMLError as e:
            logger.error(f"Failed to parse Swagger YAML for {swagger_doc.service_name}: {e}")
            sections.append("ERROR: Failed to parse YAML content")
            sections.append(f"Raw content preview: {swagger_doc.content[:500]}...")
        except Exception as e:
            logger.error(f"Unexpected error processing Swagger doc for {swagger_doc.service_name}: {e}")
            sections.append("ERROR: Failed to process Swagger document")
        
        return "\n".join(sections)

