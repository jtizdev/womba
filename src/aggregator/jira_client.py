"""
Jira client for fetching stories and issues.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx
from loguru import logger

from src.core.atlassian_client import AtlassianClient
from src.models.story import JiraStory


class JiraClient(AtlassianClient):
    """Client for interacting with Jira API."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        email: Optional[str] = None,
        api_token: Optional[str] = None,
    ):
        """
        Initialize Jira client.

        Args:
            base_url: Jira base URL (defaults to settings)
            email: Jira user email (defaults to settings)
            api_token: Jira API token (defaults to settings)
        """
        super().__init__(base_url=base_url, email=email, api_token=api_token)

    def _extract_text_from_adf(self, adf_content: Any) -> str:
        """
        Extract plain text and URLs from Atlassian Document Format (ADF) JSON.
        Handles text nodes, link marks, and inlineCard nodes (for Confluence links).
        
        Args:
            adf_content: ADF content (dict or str)
            
        Returns:
            Plain text extracted from ADF with URLs included
        """
        logger.debug(f"Extracting text from ADF (type: {type(adf_content).__name__})")
        
        if isinstance(adf_content, str):
            return adf_content
        
        if not isinstance(adf_content, dict):
            return str(adf_content) if adf_content else ""
        
        text_parts = []
        
        def extract_recursive(node):
            if isinstance(node, dict):
                node_type = node.get('type')
                
                # Extract text node
                if node_type == 'text':
                    text = node.get('text', '')
                    if text:
                        text_parts.append(text)
                    
                    # If this text node has link marks, also add the URL
                    if 'marks' in node:
                        for mark in node.get('marks', []):
                            if mark.get('type') == 'link':
                                href = mark.get('attrs', {}).get('href', '')
                                if href:
                                    # Add the URL right after the link text
                                    text_parts.append(f' [{href}] ')
                
                # Extract inlineCard nodes (Confluence/Jira links) - CRITICAL FOR CONFLUENCE!
                elif node_type == 'inlineCard':
                    url = node.get('attrs', {}).get('url', '')
                    if url:
                        logger.info(f"Found inlineCard URL: {url}")
                        text_parts.append(f' {url} ')
                
                # Add newlines for paragraphs
                if node_type == 'paragraph':
                    text_parts.append('\n')
                
                # Recurse into content
                if 'content' in node:
                    for child in node['content']:
                        extract_recursive(child)
                        
            elif isinstance(node, list):
                for item in node:
                    extract_recursive(item)
        
        extract_recursive(adf_content)
        return ' '.join(text_parts)
    
    async def get_issue_comments(self, issue_key: str) -> List[Dict]:
        """Fetch all comments for a Jira issue using SDK."""
        jira = self._get_jira_sdk_client()
        if not jira:
            return []
        
        try:
            issue = jira.issue(issue_key, expand='comments')
            comments = []
            
            if hasattr(issue.fields, 'comment') and issue.fields.comment:
                for comment in issue.fields.comment.comments:
                    comments.append({
                        'author': comment.author.displayName if comment.author else 'Unknown',
                        'body': self._extract_text_from_adf(comment.body) if comment.body else '',
                        'created': comment.created
                    })
            
            logger.info(f"Found {len(comments)} comments for {issue_key}")
            return comments
        except Exception as e:
            logger.error(f"Error fetching comments with SDK: {e}")
            return []

    def _get_jira_sdk_client(self):
        """Get Jira SDK client instance."""
        try:
            from jira import JIRA
            return JIRA(
                server=self.base_url,
                basic_auth=(self.email, self.api_token),
                options={'rest_api_version': '3'}
            )
        except ImportError:
            logger.warning("Jira SDK not installed. Install with: pip install jira")
            return None


    def _parse_sdk_issue(self, issue) -> JiraStory:
        """
        Parse Jira SDK Issue object into JiraStory model.
        
        Args:
            issue: Jira SDK Issue object
            
        Returns:
            JiraStory object
        """
        # Extract basic fields from SDK Issue object
        key = issue.key
        summary = issue.fields.summary or ""
        
        # Extract description (handle ADF format)
        description_raw = issue.fields.description
        description = self._extract_text_from_adf(description_raw) if description_raw else ""
        
        # Extract issue type, status, priority
        issue_type = issue.fields.issuetype.name if issue.fields.issuetype else "Unknown"
        status = issue.fields.status.name if issue.fields.status else "Unknown"
        priority = issue.fields.priority.name if issue.fields.priority else "Medium"
        
        # Extract people (SDK User objects have displayName, not emailAddress)
        assignee = issue.fields.assignee.displayName if issue.fields.assignee else None
        reporter = issue.fields.reporter.displayName if issue.fields.reporter else "Unknown"
        
        # Extract dates
        created = self._parse_datetime(issue.fields.created)
        updated = self._parse_datetime(issue.fields.updated)
        
        # Extract arrays
        labels = list(issue.fields.labels) if issue.fields.labels else []
        components = [c.name for c in issue.fields.components] if issue.fields.components else []
        
        # Extract attachments
        attachments = [att.content for att in issue.fields.attachment] if issue.fields.attachment else []
        
        # Extract linked issues
        linked_issues = []
        if hasattr(issue.fields, 'issuelinks') and issue.fields.issuelinks:
            for link in issue.fields.issuelinks:
                if hasattr(link, 'inwardIssue') and link.inwardIssue:
                    linked_issues.append(link.inwardIssue.key)
                elif hasattr(link, 'outwardIssue') and link.outwardIssue:
                    linked_issues.append(link.outwardIssue.key)
        
        # Extract custom fields
        custom_fields = {}
        for field_name in dir(issue.fields):
            if field_name.startswith('customfield_') and not field_name.startswith('_'):
                field_value = getattr(issue.fields, field_name, None)
                if field_value is not None:
                    custom_fields[field_name] = field_value
        
        # Try to find acceptance criteria
        acceptance_criteria = self._extract_acceptance_criteria_from_sdk(issue.fields, description)
        
        return JiraStory(
            key=key,
            summary=summary,
            description=description,
            issue_type=issue_type,
            status=status,
            priority=priority,
            assignee=assignee,
            reporter=reporter,
            created=created,
            updated=updated,
            labels=labels,
            components=components,
            acceptance_criteria=acceptance_criteria,
            linked_issues=linked_issues,
            attachments=attachments,
            custom_fields=custom_fields,
        )

    def _extract_acceptance_criteria_from_sdk(self, fields, description: str) -> Optional[str]:
        """
        Try to extract acceptance criteria from SDK fields.
        
        Args:
            fields: SDK issue fields object
            description: Issue description
            
        Returns:
            Acceptance criteria string or None
        """
        # Check common custom field names for acceptance criteria
        ac_field_names = [
            "customfield_10100",  # Common AC field
            "customfield_10200",
            "Acceptance Criteria",
        ]

        for field_name in ac_field_names:
            if hasattr(fields, field_name):
                ac_value = getattr(fields, field_name)
                if ac_value:
                    if isinstance(ac_value, str):
                        return ac_value
                    elif isinstance(ac_value, dict):
                        return self._extract_text_from_adf(ac_value)

        # Try to find AC in description
        if description and "acceptance criteria" in description.lower():
            parts = description.lower().split("acceptance criteria")
            if len(parts) > 1:
                # Get the part after "acceptance criteria"
                ac_part = parts[1].split("\n\n")[0]  # Until next paragraph
                return ac_part.strip()

        return None

    async def get_issue_with_subtasks(self, issue_key: str) -> tuple[JiraStory, List[JiraStory]]:
        """
        Fetch issue and its subtasks using Jira SDK (more reliable than REST API).
        
        Args:
            issue_key: Jira issue key
            
        Returns:
            Tuple of (main_story, subtasks)
        """
        jira = self._get_jira_sdk_client()
        if not jira:
            # Fallback to REST API
            main_story = await self.get_issue(issue_key)
            return main_story, []
        
        try:
            issue = jira.issue(issue_key, expand='subtasks')
            main_story = self._parse_sdk_issue(issue)
            
            subtasks = []
            if hasattr(issue.fields, 'subtasks') and issue.fields.subtasks:
                logger.info(f"Found {len(issue.fields.subtasks)} subtasks for {issue_key}")
                for subtask in issue.fields.subtasks:
                    try:
                        # Fetch subtask with full data
                        full_subtask = jira.issue(subtask.key)
                        subtasks.append(self._parse_sdk_issue(full_subtask))
                    except Exception as e:
                        logger.warning(f"Could not fetch subtask {subtask.key}: {e}")
            
            return main_story, subtasks
            
        except Exception as e:
            logger.error(f"Error fetching with SDK: {e}")
            # Fallback to REST API
            main_story = await self.get_issue(issue_key)
            return main_story, []

    async def get_issue(self, issue_key: str) -> JiraStory:
        """Fetch a single Jira issue by key using SDK."""
        jira = self._get_jira_sdk_client()
        if not jira:
            return None
        
        try:
            issue = jira.issue(issue_key)
            return self._parse_sdk_issue(issue)
        except Exception as e:
            logger.error(f"Error fetching issue with SDK: {e}")
            return None

    async def get_linked_issues(self, issue_key: str) -> List[JiraStory]:
        """Fetch all issues linked to the given issue using SDK."""
        jira = self._get_jira_sdk_client()
        if not jira:
            return []
        
        try:
            issue = jira.issue(issue_key, expand='issuelinks')
            linked_stories = []
            
            if hasattr(issue.fields, 'issuelinks') and issue.fields.issuelinks:
                for link in issue.fields.issuelinks:
                    linked_issue = None
                    if hasattr(link, 'inwardIssue') and link.inwardIssue:
                        linked_issue = link.inwardIssue
                    elif hasattr(link, 'outwardIssue') and link.outwardIssue:
                        linked_issue = link.outwardIssue
                    
                    if linked_issue:
                        try:
                            # Fetch linked issue with full data
                            full_linked = jira.issue(linked_issue.key)
                            story = self._parse_sdk_issue(full_linked)
                            linked_stories.append(story)
                        except Exception as e:
                            logger.warning(f"Could not fetch linked issue {linked_issue.key}: {e}")
            
            return linked_stories
        except Exception as e:
            logger.error(f"Error fetching linked issues with SDK: {e}")
            return []

    async def search_issues(self, jql: str, max_results: int = 50, start_at: int = 0) -> tuple[List[JiraStory], int]:
        """
        Search for issues using JQL with SDK.
        
        Returns:
            Tuple of (list of JiraStory objects, total count)
        """
        jira = self._get_jira_sdk_client()
        if not jira:
            return [], 0
        
        try:
            logger.info(f"Searching Jira issues with SDK JQL: {jql} (startAt={start_at}, maxResults={max_results})")
            # Use enhanced_search_issues for Jira Cloud (old search is deprecated)
            # CRITICAL: Must pass startAt parameter, otherwise returns same results forever!
            # The SDK's search_issues returns an object with .total attribute
            issues = jira.search_issues(jql, maxResults=max_results, startAt=start_at)
            
            # Get total count from the result object
            total = getattr(issues, 'total', len(issues) if issues else 0)
            stories = [self._parse_sdk_issue(issue) for issue in issues]
            
            logger.debug(f"Found {len(stories)} issues (total: {total})")
            return stories, total
        except Exception as e:
            # If old method fails, we still return empty (don't want infinite loop!)
            logger.error(f"Error searching with SDK: {e}")
            return [], 0


    def _parse_issue(self, issue_data: Dict[str, Any]) -> JiraStory:
        """
        Parse raw Jira issue data into JiraStory model.

        Args:
            issue_data: Raw issue data from Jira API

        Returns:
            JiraStory object
        """
        fields = issue_data.get("fields", {})

        # Extract basic fields
        key = issue_data.get("key", "")
        summary = fields.get("summary", "")
        # Extract description (handle ADF format)
        description_raw = fields.get("description")
        description = self._extract_text_from_adf(description_raw)

        # Handle new Atlassian Document Format (ADF) for description
        if isinstance(description, dict):
            description = self._extract_text_from_adf(description)

        issue_type = fields.get("issuetype", {}).get("name", "Unknown")
        status = fields.get("status", {}).get("name", "Unknown")
        priority = fields.get("priority", {}).get("name", "Medium")

        # Extract people
        assignee_data = fields.get("assignee")
        assignee = assignee_data.get("emailAddress") if assignee_data else None

        reporter_data = fields.get("reporter", {})
        reporter = reporter_data.get("emailAddress", "unknown@example.com")

        # Extract dates
        created = self._parse_datetime(fields.get("created"))
        updated = self._parse_datetime(fields.get("updated"))

        # Extract arrays
        labels = fields.get("labels", [])
        components = [c.get("name", "") for c in fields.get("components", [])]

        # Extract attachments
        attachments = [
            att.get("content", "") for att in fields.get("attachment", [])
        ]

        # Extract linked issues
        issuelinks = fields.get("issuelinks", [])
        linked_issues = []
        for link in issuelinks:
            linked_issue = link.get("inwardIssue") or link.get("outwardIssue")
            if linked_issue:
                linked_issues.append(linked_issue.get("key", ""))

        # Extract custom fields
        custom_fields = {}
        for field_key, field_value in fields.items():
            if field_key.startswith("customfield_") and field_value is not None:
                custom_fields[field_key] = field_value

        # Try to find acceptance criteria in common custom field names or description
        acceptance_criteria = self._extract_acceptance_criteria(fields, description)

        return JiraStory(
            key=key,
            summary=summary,
            description=description,
            issue_type=issue_type,
            status=status,
            priority=priority,
            assignee=assignee,
            reporter=reporter,
            created=created,
            updated=updated,
            labels=labels,
            components=components,
            acceptance_criteria=acceptance_criteria,
            linked_issues=linked_issues,
            attachments=attachments,
            custom_fields=custom_fields,
        )


    def _parse_datetime(self, date_str: Optional[str]) -> datetime:
        """Parse Jira datetime string."""
        if not date_str:
            return datetime.utcnow()
        try:
            # Jira uses ISO 8601 format
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except Exception:
            return datetime.utcnow()

    def _extract_acceptance_criteria(
        self, fields: Dict[str, Any], description: str
    ) -> Optional[str]:
        """
        Try to extract acceptance criteria from various sources.

        Args:
            fields: Issue fields
            description: Issue description

        Returns:
            Acceptance criteria string or None
        """
        # Check common custom field names for acceptance criteria
        ac_field_names = [
            "customfield_10100",  # Common AC field
            "customfield_10200",
            "Acceptance Criteria",
        ]

        for field_name in ac_field_names:
            ac_value = fields.get(field_name)
            if ac_value:
                if isinstance(ac_value, str):
                    return ac_value
                elif isinstance(ac_value, dict):
                    return self._extract_text_from_adf(ac_value)

        # Try to find AC in description
        if description and "acceptance criteria" in description.lower():
            parts = description.lower().split("acceptance criteria")
            if len(parts) > 1:
                # Get the part after "acceptance criteria"
                ac_part = parts[1].split("\n\n")[0]  # Until next paragraph
                return ac_part.strip()

        return None

