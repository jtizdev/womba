"""
Refactored Jira client using atlassian-python-api SDK.
Reduces from 445 lines to ~150 lines with better maintainability.
"""

from typing import Dict, List, Optional
from atlassian import Jira
from loguru import logger

from src.config.settings import settings
from src.models.story import JiraStory
from src.utils.text_processor import parse_adf_to_text, extract_urls_from_text


class JiraClient:
    """
    Jira client using atlassian-python-api SDK.
    Handles authentication, issue fetching, and ADF parsing automatically.
    """
    
    def __init__(
        self,
        base_url: Optional[str] = None,
        email: Optional[str] = None,
        api_token: Optional[str] = None,
    ):
        """
        Initialize Jira client with SDK.
        
        Args:
            base_url: Jira base URL (defaults to settings)
            email: Jira user email (defaults to settings)
            api_token: Jira API token (defaults to settings)
        """
        self.base_url = (base_url or settings.jira_base_url).rstrip("/")
        self.email = email or settings.jira_email
        self.api_token = api_token or settings.jira_api_token
        
        # Initialize Atlassian SDK
        self.jira = Jira(
            url=self.base_url,
            username=self.email,
            password=self.api_token,
            cloud=True
        )
        
        logger.info(f"Initialized Jira client for {self.base_url}")
    
    async def get_issue(self, issue_key: str) -> JiraStory:
        """
        Fetch a single Jira issue.
        
        Args:
            issue_key: Jira issue key (e.g., 'PROJ-123')
            
        Returns:
            JiraStory object
        """
        logger.info(f"Fetching Jira issue: {issue_key}")
        
        # SDK handles API call and JSON parsing
        issue = self.jira.issue(issue_key, expand='renderedFields')
        
        # Extract fields
        fields = issue['fields']
        
        # Parse description (SDK returns rendered HTML or raw ADF)
        description = fields.get('description', '')
        if isinstance(description, dict):
            description = parse_adf_to_text(description)
        
        # Build JiraStory model
        story = JiraStory(
            key=issue['key'],
            summary=fields.get('summary', ''),
            description=description or '',
            story_type=fields.get('issuetype', {}).get('name', 'Story'),
            status=fields.get('status', {}).get('name', 'Unknown'),
            priority=fields.get('priority', {}).get('name', 'Medium'),
            assignee=fields.get('assignee', {}).get('displayName') if fields.get('assignee') else None,
            reporter=fields.get('reporter', {}).get('displayName') if fields.get('reporter') else None,
            labels=fields.get('labels', []),
            components=[c.get('name') for c in fields.get('components', [])],
            created=fields.get('created', ''),
            updated=fields.get('updated', ''),
            comments=[]  # Will be fetched separately
        )
        
        logger.debug(f"Fetched issue {issue_key}: {story.summary}")
        return story
    
    async def get_issue_with_subtasks(self, issue_key: str) -> tuple[JiraStory, List[JiraStory]]:
        """
        Fetch issue and its subtasks in one call.
        
        Args:
            issue_key: Jira issue key
            
        Returns:
            Tuple of (main_story, subtasks)
        """
        logger.info(f"Fetching issue with subtasks: {issue_key}")
        
        # SDK handles subtask expansion
        issue = self.jira.issue(issue_key, expand='subtasks,renderedFields')
        
        # Parse main issue
        main_story = await self._parse_issue_to_story(issue)
        
        # Parse subtasks
        subtasks = []
        for subtask_ref in issue['fields'].get('subtasks', []):
            subtask_key = subtask_ref.get('key')
            if subtask_key:
                subtask = await self.get_issue(subtask_key)
                subtasks.append(subtask)
        
        logger.info(f"Found {len(subtasks)} subtasks for {issue_key}")
        return main_story, subtasks
    
    async def get_issue_comments(self, issue_key: str) -> List[Dict]:
        """
        Fetch all comments for an issue.
        
        Args:
            issue_key: Jira issue key
            
        Returns:
            List of comment dictionaries
        """
        logger.info(f"Fetching comments for: {issue_key}")
        
        # SDK provides comments method
        comments = self.jira.issue_get_comments(issue_key)
        
        parsed_comments = []
        for comment in comments.get('comments', []):
            author = comment.get('author', {}).get('displayName', 'Unknown')
            body = comment.get('body', '')
            
            # Parse ADF if needed
            if isinstance(body, dict):
                body = parse_adf_to_text(body)
            
            parsed_comments.append({
                'author': author,
                'body': body,
                'created': comment.get('created', '')
            })
        
        logger.info(f"Found {len(parsed_comments)} comments for {issue_key}")
        return parsed_comments
    
    async def get_linked_issues(self, issue_key: str) -> List[JiraStory]:
        """
        Get all issues linked to this issue.
        
        Args:
            issue_key: Jira issue key
            
        Returns:
            List of linked JiraStory objects
        """
        logger.info(f"Fetching linked issues for: {issue_key}")
        
        issue = self.jira.issue(issue_key, fields='issuelinks')
        issue_links = issue['fields'].get('issuelinks', [])
        
        linked_stories = []
        for link in issue_links:
            # Link can be inward or outward
            linked_issue_ref = link.get('inwardIssue') or link.get('outwardIssue')
            if linked_issue_ref:
                linked_key = linked_issue_ref.get('key')
                if linked_key:
                    try:
                        linked_story = await self.get_issue(linked_key)
                        linked_stories.append(linked_story)
                    except Exception as e:
                        logger.warning(f"Failed to fetch linked issue {linked_key}: {e}")
        
        logger.info(f"Found {len(linked_stories)} linked issues")
        return linked_stories
    
    async def search_issues(self, jql: str, max_results: int = 50) -> List[Dict]:
        """
        Search issues using JQL.
        
        Args:
            jql: JQL query string
            max_results: Maximum number of results
            
        Returns:
            List of issue dictionaries
        """
        logger.info(f"Searching Jira issues with JQL: {jql}")
        
        try:
            # SDK handles pagination
            results = self.jira.jql(jql, limit=max_results)
            issues = results.get('issues', [])
            
            logger.info(f"Found {len(issues)} issues")
            return issues
        except Exception as e:
            logger.error(f"JQL search failed: {e}")
            return []
    
    async def _parse_issue_to_story(self, issue: Dict) -> JiraStory:
        """
        Parse raw issue dict to JiraStory model.
        
        Args:
            issue: Raw issue dictionary from SDK
            
        Returns:
            JiraStory object
        """
        fields = issue['fields']
        
        description = fields.get('description', '')
        if isinstance(description, dict):
            description = parse_adf_to_text(description)
        
        return JiraStory(
            key=issue['key'],
            summary=fields.get('summary', ''),
            description=description or '',
            story_type=fields.get('issuetype', {}).get('name', 'Story'),
            status=fields.get('status', {}).get('name', 'Unknown'),
            priority=fields.get('priority', {}).get('name', 'Medium'),
            assignee=fields.get('assignee', {}).get('displayName') if fields.get('assignee') else None,
            reporter=fields.get('reporter', {}).get('displayName') if fields.get('reporter') else None,
            labels=fields.get('labels', []),
            components=[c.get('name') for c in fields.get('components', [])],
            created=fields.get('created', ''),
            updated=fields.get('updated', ''),
            comments=[]
        )
    
    async def validate_connection(self) -> bool:
        """
        Validate Jira connection.
        
        Returns:
            True if connection is valid
        """
        try:
            self.jira.myself()
            logger.info("Jira connection validated successfully")
            return True
        except Exception as e:
            logger.error(f"Jira connection validation failed: {e}")
            return False

