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
        # DEBUG logging removed for performance (was being called thousands of times)
        
        # Handle Jira SDK PropertyHolder objects
        # PropertyHolder wraps the actual data - access via iteration or dict-like methods
        if adf_content is None:
            return ""
        
        # Try to unwrap PropertyHolder (Jira SDK object that wraps dict data)
        try:
            # Check if it's a PropertyHolder or other Jira SDK object
            class_name = adf_content.__class__.__name__
            if class_name == 'PropertyHolder' or (hasattr(adf_content, '__getitem__') and not isinstance(adf_content, (str, list, dict))):
                # Try multiple unwrapping strategies for PropertyHolder
                unwrapped = None
                
                # Strategy 1: Try .raw attribute
                if hasattr(adf_content, 'raw'):
                    unwrapped = adf_content.raw
                    if unwrapped:
                        logger.debug(f"Unwrapped PropertyHolder via .raw")
                        adf_content = unwrapped
                
                # Strategy 2: Try direct dict conversion
                if not unwrapped:
                    try:
                        unwrapped = dict(adf_content)
                        if unwrapped:
                            logger.debug(f"Unwrapped PropertyHolder via dict()")
                            adf_content = unwrapped
                    except:
                        pass
                
                # Strategy 3: Try common attributes
                if not unwrapped:
                    for attr in ['value', 'content', '_value', '_raw', 'data', '_data']:
                        if hasattr(adf_content, attr):
                            val = getattr(adf_content, attr)
                            if val is not None and val != adf_content:
                                unwrapped = val
                                logger.debug(f"Unwrapped PropertyHolder via .{attr}")
                                adf_content = unwrapped
                                break
                
                # Strategy 4: Try iterating over items
                if not unwrapped:
                    try:
                        items_list = list(adf_content.items()) if hasattr(adf_content, 'items') else list(adf_content)
                        if items_list and isinstance(items_list[0], tuple):
                            # It's dict-like
                            unwrapped = dict(items_list)
                            logger.debug(f"Unwrapped PropertyHolder via .items()")
                        elif items_list:
                            # It's list-like
                            unwrapped = items_list
                            logger.debug(f"Unwrapped PropertyHolder via iteration (got list)")
                        adf_content = unwrapped
                    except:
                        pass
                
                if not unwrapped:
                    logger.debug(f"Could not unwrap PropertyHolder {class_name}")
        except Exception as e:
            logger.debug(f"PropertyHolder unwrap attempt failed: {e}")

        if isinstance(adf_content, str):
            return adf_content
        
        # We can handle dict or list (ADF may be a dict or a list of nodes)
        if not isinstance(adf_content, (dict, list)):
            # Last resort: stringify (will give object repr if unwrap failed)
            result = str(adf_content) if adf_content else ""
            # If it's an object repr, return empty instead
            if result.startswith('<') and 'object at 0x' in result:
                logger.warning(f"Failed to extract text from PropertyHolder - got object repr: {result[:80]}")
                return ""
            return result
        
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
            else:
                # Fallback for unexpected scalar values
                if isinstance(node, str):
                    text_parts.append(node)
        
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
        
        # Extract description - try renderedFields first (HTML), fallback to ADF
        description = ""
        if hasattr(issue, 'renderedFields') and hasattr(issue.renderedFields, 'description'):
            # renderedFields.description is HTML string (when expand='renderedFields' is used)
            description_html = issue.renderedFields.description
            if description_html and isinstance(description_html, str):
                import re
                # Strip HTML tags to get plain text
                description = re.sub(r'<[^>]+>', '', description_html)
                description = description.replace('&nbsp;', ' ').replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')
        
        # Fallback to ADF if renderedFields didn't work
        if not description:
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
        
        # Extract custom fields and convert Jira objects to serializable types
        custom_fields = {}
        for field_name in dir(issue.fields):
            if field_name.startswith('customfield_') and not field_name.startswith('_'):
                field_value = getattr(issue.fields, field_name, None)
                if field_value is not None:
                    # Convert Jira objects to serializable types
                    custom_fields[field_name] = self._serialize_custom_field_value(field_value)
        
        # Try to find acceptance criteria
        acceptance_criteria = self._extract_acceptance_criteria_from_sdk(issue.fields, description)
        
        # Extract fix versions
        fix_versions = []
        if hasattr(issue.fields, 'fixVersions') and issue.fields.fixVersions:
            fix_versions = [v.name for v in issue.fields.fixVersions if hasattr(v, 'name')]
        
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
            fix_versions=fix_versions,
            acceptance_criteria=acceptance_criteria,
            linked_issues=linked_issues,
            attachments=attachments,
            custom_fields=custom_fields,
        )

    def _serialize_custom_field_value(self, value: Any) -> Any:
        """
        Convert Jira objects to serializable types.
        
        Args:
            value: Jira field value (may be CustomFieldOption, list, dict, etc.)
            
        Returns:
            Serializable value (str, dict, list, or primitive type)
        """
        # Handle None
        if value is None:
            return None
        
        # Handle primitive types
        if isinstance(value, (str, int, float, bool)):
            return value
        
        # Handle lists
        if isinstance(value, (list, tuple)):
            return [self._serialize_custom_field_value(item) for item in value]
        
        # Handle dicts
        if isinstance(value, dict):
            return {k: self._serialize_custom_field_value(v) for k, v in value.items()}
        
        # Handle Jira CustomFieldOption objects
        if hasattr(value, '__class__') and 'CustomFieldOption' in str(value.__class__):
            # Extract useful attributes from CustomFieldOption
            result = {}
            if hasattr(value, 'value'):
                result['value'] = str(value.value)
            if hasattr(value, 'id'):
                result['id'] = str(value.id)
            if hasattr(value, 'self'):
                result['self'] = str(value.self)
            return result if result else str(value)
        
        # Handle other Jira objects with attributes
        if hasattr(value, '__dict__'):
            result = {}
            for key, val in value.__dict__.items():
                if not key.startswith('_'):
                    result[key] = self._serialize_custom_field_value(val)
            return result if result else str(value)
        
        # Fallback: convert to string
        return str(value)

    def _extract_acceptance_criteria_from_sdk(self, fields, description: str) -> Optional[str]:
        """
        Try to extract acceptance criteria from SDK fields.
        
        Args:
            fields: SDK issue fields object
            description: Issue description
            
        Returns:
            Acceptance criteria string or None
        """
        # Try renderedFields first (easier to parse)
        if hasattr(fields, '__dict__') and 'renderedFields' in fields.__dict__:
            rendered = fields.__dict__['renderedFields']
            if rendered and hasattr(rendered, 'customfield_10100'):
                ac_rendered = getattr(rendered, 'customfield_10100', None)
                if ac_rendered and isinstance(ac_rendered, str) and len(ac_rendered) > 10:
                    import re
                    # Strip HTML
                    ac_clean = re.sub(r'<[^>]+>', '', ac_rendered)
                    ac_clean = ac_clean.replace('&nbsp;', ' ').replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')
                    if ac_clean and not ac_clean.startswith('<'):
                        return ac_clean.strip()
        
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
                    # Handle PropertyHolder
                    ac_text = self._extract_text_from_adf(ac_value)
                    # If we got garbage (object repr or very short), skip
                    if ac_text and len(ac_text) > 10 and not ac_text.startswith('<') and 'object at 0x' not in ac_text:
                        return ac_text

        # Try to find AC in description (case-insensitive)
        if description and "acceptance criteria" in description.lower():
            import re
            # Find "Acceptance Criteria" section (case-insensitive)
            ac_pattern = re.compile(r'acceptance\s+criteria[:\s]*\n*(.*?)(?=\n\n[A-Z]|\n\n\n|$)', re.IGNORECASE | re.DOTALL)
            match = ac_pattern.search(description)
            if match:
                ac_text = match.group(1).strip()
                if ac_text and len(ac_text) > 5:
                    return ac_text
            
            # Fallback: simple split
            desc_lower_idx = description.lower().find("acceptance criteria")
            if desc_lower_idx >= 0:
                after_ac = description[desc_lower_idx + len("acceptance criteria"):]
                # Skip past any colons/dashes/newlines
                after_ac = after_ac.lstrip(':-\n ')
                # Take until next major section or end
                lines = after_ac.split('\n')
                ac_lines = []
                for line in lines[:20]:  # Max 20 lines
                    if not line.strip():
                        continue
                    # Stop if we hit another section header
                    if re.match(r'^[A-Z][a-z]+(\s+[A-Z][a-z]+)*:?\s*$', line.strip()):
                        break
                    ac_lines.append(line)
                if ac_lines:
                    return '\n'.join(ac_lines).strip()

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
            issue = jira.issue(issue_key, expand='subtasks,renderedFields', fields='*all')
            main_story = self._parse_sdk_issue(issue)
            
            subtasks = []
            if hasattr(issue.fields, 'subtasks') and issue.fields.subtasks:
                logger.info(f"Found {len(issue.fields.subtasks)} subtasks for {issue_key}")
                for subtask in issue.fields.subtasks:
                    try:
                        # Fetch subtask with full data including renderedFields
                        full_subtask = jira.issue(subtask.key, expand='renderedFields', fields='*all')
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
            raise ValueError("Jira client not configured")
        
        try:
            issue = jira.issue(issue_key, expand='renderedFields', fields='*all')
            return self._parse_sdk_issue(issue)
        except Exception as e:
            logger.error(f"Error fetching issue with SDK: {e}")
            # Re-raise so caller can handle appropriately (404 vs 500)
            raise

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
                            # Fetch linked issue with full data including rendered fields
                            full_linked = jira.issue(linked_issue.key, expand='renderedFields', fields='*all')
                            story = self._parse_sdk_issue(full_linked)
                            linked_stories.append(story)
                        except Exception as e:
                            logger.warning(f"Could not fetch linked issue {linked_issue.key}: {e}")
            
            return linked_stories
        except Exception as e:
            logger.error(f"Error fetching linked issues with SDK: {e}")
            return []

    def search_all_issues(self, jql: str) -> List[JiraStory]:
        """
        Search for ALL issues using JQL with automatic pagination.
        
        Uses SDK's enhanced_search_issues() with auto-pagination.
        NO artificial limits - fetches the actual count whatever it is.
        
        Args:
            jql: JQL query string
            
        Returns:
            List of ALL JiraStory objects matching the query
        """
        jira = self._get_jira_sdk_client()
        if not jira:
            return []
        
        try:
            logger.info(f"Fetching ALL issues for JQL: '{jql}'")
            
            all_stories = []
            
            # Use enhanced_search_issues with maxResults=False for full auto-pagination
            # It will fetch all matching issues automatically
            logger.info("  Using enhanced_search_issues with maxResults=False for full pagination")
            issues = jira.enhanced_search_issues(
                jql_str=jql,
                maxResults=False,
                fields='*all',
                expand='renderedFields'
            )
            
            if not issues:
                logger.warning("  No issues returned")
                return []
            
            for idx, issue in enumerate(issues, start=1):
                try:
                    story = self._parse_sdk_issue(issue)
                    all_stories.append(story)
                except Exception as parse_error:
                    logger.warning(f"  Failed to parse issue {getattr(issue, 'key', 'UNKNOWN')}: {parse_error}")
                    continue
                
                if idx % 500 == 0:
                    logger.info(f"  📊 Progress: {idx} issues processed so far...")
            
            logger.info(f"🎉 FINAL COUNT: {len(all_stories)} issues fetched successfully")
            return all_stories
            
        except Exception as e:
            logger.error(f"Error searching all Jira issues: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return []
    
    def search_issues(self, jql: str, max_results: int = 50, start_at: int = 0) -> tuple[List[JiraStory], int]:
        """
        Search for issues using JQL with manual pagination.
        
        For fetching ALL issues, use search_all_issues() instead.
        
        Args:
            jql: JQL query string
            max_results: Number of results to return per page
            start_at: Starting index for pagination
            
        Returns:
            Tuple of (list of JiraStory objects, total count)
        """
        jira = self._get_jira_sdk_client()
        if not jira:
            return [], 0
        
        try:
            logger.info(f"Searching Jira issues: JQL='{jql}' startAt={start_at} maxResults={max_results}")
            
            # Use SDK's native search_issues - makes ONE efficient API call
            issues = jira.search_issues(
                jql_str=jql,
                startAt=start_at,
                maxResults=max_results,
                expand='renderedFields',
                fields='*all'
            )
            
            # Parse issues
            stories = [self._parse_sdk_issue(issue) for issue in issues]
            
            # The SDK returns a ResultList with total attribute
            if hasattr(issues, 'total'):
                total = issues.total
            else:
                total = start_at + len(issues) if len(issues) < max_results else 999999
            
            logger.info(f"✅ Fetched {len(stories)} stories (startAt={start_at}, total={total})")
            return stories, total
            
        except Exception as e:
            logger.error(f"Error searching Jira: {e}")
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

        # Extract custom fields and convert Jira objects to serializable types
        custom_fields = {}
        for field_key, field_value in fields.items():
            if field_key.startswith("customfield_") and field_value is not None:
                custom_fields[field_key] = self._serialize_custom_field_value(field_value)

        # Try to find acceptance criteria in common custom field names or description
        acceptance_criteria = self._extract_acceptance_criteria(fields, description)
        
        # Extract fix versions
        fix_versions = [v.get("name", "") for v in fields.get("fixVersions", []) if v.get("name")]

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
            fix_versions=fix_versions,
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

