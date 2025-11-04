"""
Story collector that aggregates data from multiple sources.
"""

from typing import Dict, List, Optional

from loguru import logger

from src.models.story import JiraStory

from .confluence_client import ConfluenceClient
from .jira_client import JiraClient


class StoryContext(dict):
    """
    Enhanced context object that contains story and all related information.
    Acts as a dict but with typed access.
    """

    def __init__(self, main_story: JiraStory):
        super().__init__()
        self.main_story = main_story
        self["main_story"] = main_story
        self["linked_stories"] = []
        self["confluence_docs"] = []
        self["figma_designs"] = []
        self["related_bugs"] = []
        self["context_graph"] = {}


class StoryCollector:
    """
    Collects and aggregates product story data from multiple sources.
    Builds a comprehensive context graph for AI analysis.
    """

    def __init__(
        self,
        jira_client: Optional[JiraClient] = None,
        confluence_client: Optional[ConfluenceClient] = None,
    ):
        """
        Initialize story collector.

        Args:
            jira_client: Jira client instance (creates new if None)
            confluence_client: Confluence client instance (creates new if None)
        """
        self.jira_client = jira_client or JiraClient()
        self.confluence_client = confluence_client or ConfluenceClient()

    async def collect_story_context(self, issue_key: str, include_subtasks: bool = True) -> StoryContext:
        """
        Collect comprehensive context for a story from all available sources.

        Args:
            issue_key: Jira issue key (e.g., PROJ-123)
            include_subtasks: Whether to include subtasks/engineering tasks

        Returns:
            StoryContext with all aggregated information
        """
        # 1. Fetch main story AND subtasks using SDK (avoids 410 Gone errors)
        main_story, subtasks = await self.jira_client.get_issue_with_subtasks(issue_key)
        logger.info(f"Collecting comprehensive context for story: {issue_key}")
        logger.info(f"Found {len(subtasks)} subtasks via Jira SDK")
        
        context = StoryContext(main_story)
        if include_subtasks and subtasks:
            context["subtasks"] = subtasks
        
        # 1.5 Fetch comments for story and subtasks (developer insights)
        try:
            story_comments = await self.jira_client.get_issue_comments(issue_key)
            context["story_comments"] = story_comments
            logger.info(f"Found {len(story_comments)} comments on main story")
            
            if include_subtasks and subtasks:
                subtask_comments = {}
                for subtask in subtasks:
                    # subtask is a JiraStory object, not a dict
                    subtask_key = subtask.key if hasattr(subtask, 'key') else subtask.get('key')
                    if subtask_key:
                        try:
                            comments = await self.jira_client.get_issue_comments(subtask_key)
                            if comments:
                                subtask_comments[subtask_key] = comments
                        except Exception as e:
                            logger.debug(f"Could not fetch comments for {subtask_key}: {e}")
                
                context["subtask_comments"] = subtask_comments
                total_subtask_comments = sum(len(c) for c in subtask_comments.values())
                logger.info(f"Found {total_subtask_comments} comments across {len(subtask_comments)} subtasks")
        except Exception as e:
            logger.warning(f"Failed to fetch comments: {e}")

        # 2. Fetch linked issues
        linked_stories = []
        try:
            linked_stories = await self.jira_client.get_linked_issues(issue_key)
            context["linked_stories"] = linked_stories
            logger.info(f"Found {len(linked_stories)} linked issues")
        except Exception as e:
            logger.warning(f"Failed to fetch linked issues: {e}")
            context["linked_stories"] = []

        # 3. Fetch related bugs (issues that might be related)
        related_bugs = []
        try:
            related_bugs = await self._fetch_related_bugs(main_story)
            context["related_bugs"] = related_bugs
            logger.info(f"Found {len(related_bugs)} related bugs")
        except Exception as e:
            logger.warning(f"Failed to fetch related bugs: {e}")
            context["related_bugs"] = []

        # 4. Fetch related Confluence documentation (PRD, tech design, etc.)
        try:
            confluence_docs = await self._fetch_confluence_docs(main_story)
            context["confluence_docs"] = confluence_docs
            logger.info(f"Found {len(confluence_docs)} related Confluence pages")
        except Exception as e:
            logger.warning(f"Failed to fetch Confluence docs: {e}")
            context["confluence_docs"] = []

        # 5. Build context graph (relationships between items)
        context["context_graph"] = self._build_context_graph(
            main_story, linked_stories, related_bugs
        )

        # 6. Extract all text content for AI context
        context["full_context_text"] = self._build_full_context_text(context)

        logger.info(f"Successfully collected context for {issue_key}")
        return context

    async def _fetch_related_bugs(self, story: JiraStory) -> List[JiraStory]:
        """
        Fetch bugs that are related to this story based on components, labels, etc.

        Args:
            story: The main story

        Returns:
            List of related bug stories
        """
        # Build JQL to find related bugs
        jql_parts = ['type = Bug']

        # Add component filter if story has components
        if story.components:
            components_str = ", ".join([f'"{c}"' for c in story.components])
            jql_parts.append(f"component in ({components_str})")

        # Add label filter if story has labels
        if story.labels:
            labels_str = ", ".join([f'"{l}"' for l in story.labels])
            jql_parts.append(f"labels in ({labels_str})")

        # Only get recent bugs
        jql_parts.append("created >= -90d")

        jql = " AND ".join(jql_parts)

        try:
            bugs, _ = self.jira_client.search_issues(jql, max_results=20)
            return bugs
        except Exception as e:
            logger.error(f"Error fetching related bugs: {e}")
            return []

    async def _fetch_subtasks(self, parent_key: str) -> List[JiraStory]:
        """
        Fetch subtasks and engineering tasks for a story.
        
        These provide implementation details that can inform test scenarios.

        Args:
            parent_key: Parent story key

        Returns:
            List of subtask stories
        """
        logger.info(f"Fetching subtasks for {parent_key}")

        # Try multiple JQL queries to find subtasks
        queries = [
            f'parent = {parent_key}',  # Direct subtasks
            f'"Parent Link" = {parent_key}',  # Alternative parent field
            f'issue in childIssuesOf("{parent_key}")',  # Jira function
        ]

        subtasks = []
        for jql in queries:
            try:
                results, _ = self.jira_client.search_issues(jql, max_results=50)
                if results:
                    subtasks.extend(results)
                    logger.info(f"Found {len(results)} subtasks with query: {jql}")
                    break  # Stop after first successful query
            except Exception as e:
                logger.debug(f"Query '{jql}' failed: {e}")
                continue
        
        return subtasks

    async def _fetch_confluence_docs(self, story: JiraStory) -> List[Dict]:
        """
        Fetch Confluence documentation related to this story.

        Args:
            story: The main story

        Returns:
            List of Confluence pages with extracted content
        """
        try:
            # Extract Confluence links from story description
            import re
            import httpx
            confluence_links = []
            if story.description:
                # Find full Confluence page URLs: /wiki/spaces/SPACE/pages/12345
                full_links = re.findall(
                    r'https://[^/]+/wiki/spaces/([^/]+)/pages/([^/#\s]+)(?:/([^#\s]+))?',
                    story.description
                )
                for match in full_links:
                    space_key = match[0]
                    page_id = match[1]
                    confluence_links.append((space_key, page_id))
                
                # Find short Confluence URLs: /wiki/x/ABC123
                short_links = re.findall(
                    r'https://([^/]+)/wiki/x/([a-zA-Z0-9_-]+)',
                    story.description
                )
                for domain, short_id in short_links:
                    # Resolve short URL to get page ID
                    try:
                        short_url = f"https://{domain}/wiki/x/{short_id}"
                        logger.info(f"Resolving short Confluence URL: {short_url}")
                        async with httpx.AsyncClient(follow_redirects=True) as client:
                            response = await client.get(
                                short_url,
                                auth=(self.confluence_client.email, self.confluence_client.api_token),
                                timeout=10.0
                            )
                            # Extract page ID from final URL
                            final_url = str(response.url)
                            page_id_match = re.search(r'/pages/(\d+)', final_url)
                            space_match = re.search(r'/spaces/([^/]+)', final_url)
                            if page_id_match:
                                page_id = page_id_match.group(1)
                                space_key = space_match.group(1) if space_match else "UNKNOWN"
                                confluence_links.append((space_key, page_id))
                                logger.info(f"Resolved {short_url} to page ID: {page_id}")
                    except Exception as e:
                        logger.warning(f"Failed to resolve short URL {short_url}: {e}")
            
            logger.info(f"Found {len(confluence_links)} Confluence links in story description")
            
            # Fetch pages directly by ID
            confluence_docs = []
            for space_key, page_id in confluence_links:
                try:
                    page = await self.confluence_client.get_page(page_id)
                    if page:
                        # Extract content
                        content = self.confluence_client.extract_page_content(page)
                        doc = {
                            "id": page.get("id"),
                            "title": page.get("title"),
                            "space": space_key,
                            "url": f"{self.confluence_client.base_url}/wiki/spaces/{space_key}/pages/{page_id}",
                            "content": content,
                        }
                        confluence_docs.append(doc)
                        logger.info(f"Fetched Confluence page: {doc['title']}")
                except Exception as e:
                    logger.warning(f"Could not fetch Confluence page {page_id}: {e}")
            
            # If no direct links found, fall back to search
            if not confluence_docs:
                logger.info("No direct links found, falling back to search")
                pages = await self.confluence_client.find_related_pages(
                    story.key, labels=story.labels
                )
                
                for page in pages:
                    doc = {
                        "id": page.get("id"),
                        "title": page.get("title"),
                        "space": page.get("space", {}).get("key"),
                        "url": f"{self.confluence_client.base_url}/wiki{page.get('_links', {}).get('webui', '')}",
                        "content": self.confluence_client.extract_page_content(page),
                    }
                    confluence_docs.append(doc)

            return confluence_docs
        except Exception as e:
            logger.error(f"Error fetching Confluence docs: {e}")
            return []

    def _build_context_graph(
        self,
        main_story: JiraStory,
        linked_stories: List[JiraStory],
        related_bugs: List[JiraStory],
    ) -> Dict[str, List[str]]:
        """
        Build a context graph showing relationships between items.

        Args:
            main_story: The main story
            linked_stories: Linked stories
            related_bugs: Related bugs

        Returns:
            Dictionary representing the context graph
        """
        graph = {
            "main": main_story.key,
            "depends_on": [],
            "blocks": [],
            "relates_to": [],
            "fixed_by": [],
            "components": main_story.components,
            "labels": main_story.labels,
        }

        # Categorize linked issues (this is simplified - real implementation
        # would check the link type)
        for story in linked_stories:
            if story.issue_type == "Bug":
                graph["fixed_by"].append(story.key)
            else:
                graph["relates_to"].append(story.key)

        # Add bug references
        for bug in related_bugs:
            if bug.key not in graph["fixed_by"]:
                graph["fixed_by"].append(bug.key)

        return graph

    def _build_full_context_text(self, context: StoryContext) -> str:
        """
        Build a comprehensive text representation of all context.

        This will be fed to the AI for test plan generation.

        Args:
            context: Story context

        Returns:
            Full context as a formatted string
        """
        main_story = context.main_story
        linked_stories = context.get("linked_stories", [])
        related_bugs = context.get("related_bugs", [])
        confluence_docs = context.get("confluence_docs", [])
        subtasks = context.get("subtasks", [])

        sections = []

        # Main story section
        sections.append("=== MAIN STORY ===")
        sections.append(f"Key: {main_story.key}")
        sections.append(f"Summary: {main_story.summary}")
        sections.append(f"Type: {main_story.issue_type}")
        sections.append(f"Priority: {main_story.priority}")
        sections.append(f"Status: {main_story.status}")

        if main_story.description:
            sections.append(f"\nDescription:\n{main_story.description}")

        if main_story.acceptance_criteria:
            sections.append(f"\nAcceptance Criteria:\n{main_story.acceptance_criteria}")

        if main_story.components:
            sections.append(f"\nComponents: {', '.join(main_story.components)}")

        if main_story.labels:
            sections.append(f"Labels: {', '.join(main_story.labels)}")

        # Subtasks/Engineering Tasks section (NEW!)
        if subtasks:
            sections.append("\n=== ENGINEERING TASKS / SUBTASKS ===")
            sections.append("(These implementation details may suggest regression test scenarios)")
            for task in subtasks[:10]:
                sections.append(f"\n{task.key}: {task.summary}")
                sections.append(f"Status: {task.status}")
                if task.description:
                    desc = task.description[:200] + "..." if len(task.description) > 200 else task.description
                    sections.append(f"Details: {desc}")

        # Linked stories section
        if linked_stories:
            sections.append("\n=== LINKED STORIES ===")
            for story in linked_stories:
                sections.append(f"\n{story.key}: {story.summary}")
                sections.append(f"Type: {story.issue_type}, Status: {story.status}")
                if story.description:
                    # Truncate long descriptions
                    desc = story.description[:300] + "..." if len(story.description) > 300 else story.description
                    sections.append(f"Description: {desc}")

        # Related bugs section
        if related_bugs:
            sections.append("\n=== RELATED BUGS ===")
            for bug in related_bugs[:10]:  # Limit to 10 bugs
                sections.append(f"\n{bug.key}: {bug.summary}")
                sections.append(f"Status: {bug.status}, Priority: {bug.priority}")

        # Confluence documentation section (NEW!)
        if confluence_docs:
            sections.append("\n=== RELATED DOCUMENTATION (PRD, TECH DESIGN) ===")
            for doc in confluence_docs[:5]:  # Limit to 5 most relevant pages
                sections.append(f"\n📄 {doc['title']}")
                sections.append(f"URL: {doc['url']}")
                if doc['content']:
                    # Truncate long content
                    content = doc['content'][:1000] + "..." if len(doc['content']) > 1000 else doc['content']
                    sections.append(f"Content:\n{content}")

        return "\n".join(sections)

