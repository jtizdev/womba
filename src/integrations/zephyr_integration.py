"""
Zephyr Scale integration for uploading test cases.
"""

from typing import Dict, List, Optional
from collections import defaultdict

import httpx
from loguru import logger

from src.config.settings import settings
from src.models.test_case import TestCase
from src.models.test_plan import TestPlan


class ZephyrIntegration:
    """
    Integration with Zephyr Scale API for test case management.
    """

    # Class-level cache for test cases (defined outside __init__)
    _test_cache: Dict = {}
    _cache_timestamp: Optional[float] = None
    CACHE_TTL = 30 * 60  # 30 minutes cache (extended from 10 min for better performance)

    def __init__(
        self, api_key: Optional[str] = None, base_url: Optional[str] = None
    ):
        """
        Initialize Zephyr integration.

        Args:
            api_key: Zephyr API key (defaults to settings)
            base_url: Zephyr base URL (defaults to settings)
        """
        self.api_key = api_key or settings.zephyr_api_token
        self.base_url = (base_url or settings.zephyr_base_url).rstrip("/")
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def upload_test_plan(
        self, test_plan: TestPlan, project_key: str, folder_id: Optional[str] = None, folder_path: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Upload entire test plan to Zephyr Scale.

        Args:
            test_plan: TestPlan object to upload
            project_key: Jira project key
            folder_id: Optional folder ID to organize tests

        Returns:
            Dictionary mapping local test case titles to Zephyr test case keys

        Raises:
            httpx.HTTPError: If API calls fail
        """
        logger.info(
            f"Uploading test plan with {len(test_plan.test_cases)} test cases to Zephyr"
        )

        result = {}

        if folder_path and not folder_id:
            try:
                folder_id = await self.ensure_folder(project_key, folder_path)
                logger.info(f"Resolved folder path '{folder_path}' to ID {folder_id}")
            except Exception as exc:
                logger.error(f"Failed to ensure folder '{folder_path}': {exc}")
                raise

        for test_case in test_plan.test_cases:
            try:
                zephyr_key = await self.create_test_case(
                    test_case=test_case,
                    project_key=project_key,
                    folder_id=folder_id,
                    story_key=test_plan.story.key,
                )
                result[test_case.title] = zephyr_key
                logger.info(f"Created test case: {zephyr_key}")
            except Exception as e:
                logger.error(f"Failed to create test case '{test_case.title}': {e}")
                result[test_case.title] = f"ERROR: {str(e)}"

        logger.info(
            f"Successfully uploaded {len([v for v in result.values() if not v.startswith('ERROR')])} out of {len(test_plan.test_cases)} test cases"
        )
        return result

    async def create_test_case(
        self,
        test_case: TestCase,
        project_key: str,
        folder_id: Optional[str] = None,
        story_key: Optional[str] = None,
    ) -> str:
        """
        Create a single test case in Zephyr Scale.

        Args:
            test_case: TestCase object
            project_key: Jira project key
            folder_id: Optional folder ID
            story_key: Optional Jira story key to link test to

        Returns:
            Created test case key

        Raises:
            httpx.HTTPError: If the request fails
        """
        # Prevent debug tests
        if 'womba' in test_case.title.lower() or 'generated test' in test_case.title.lower():
            raise ValueError(f"Blocked debug test: {test_case.title}")
        
        logger.debug(f"Creating test case: {test_case.title}")

        # Build test case payload
        payload = {
            "projectKey": project_key,
            "name": test_case.title,
            "objective": test_case.description,
            "priority": self._map_priority(test_case.priority),
            "status": "Draft",
        }
        
        # Add estimated time if provided
        if test_case.estimated_time:
            payload["estimatedTime"] = test_case.estimated_time * 60  # Convert to seconds
        
        # Add labels if provided
        if test_case.tags:
            payload["labels"] = test_case.tags

        # Add folder if specified
        if folder_id:
            payload["folderId"] = int(folder_id) if str(folder_id).isdigit() else folder_id

        # Add preconditions
        if test_case.preconditions:
            payload["precondition"] = test_case.preconditions

        # Add REQUIRED custom field: Is Automated (must be a list/array)
        payload["customFields"] = {
            "Is Automated": ["Yes"] if test_case.automation_candidate else ["No"]
        }

        # Step 1: Create the test case (WITHOUT testScript - it doesn't work in creation payload)
        url = f"{self.base_url}/testcases"

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url, headers=self.headers, json=payload, timeout=30.0
            )
            response.raise_for_status()
            data = response.json()

        test_case_key = data.get("key")
        logger.info(f"✅ Test case created: {test_case_key}")
        
        # Step 2: Add steps via separate endpoint (CRITICAL - must be done AFTER creation)
        if test_case.steps and len(test_case.steps) > 0:
            await self._add_test_steps(test_case_key, test_case.steps)

        # Link to story if provided
        if story_key and test_case_key:
            try:
                await self.link_test_to_issue(test_case_key, story_key)
            except Exception as e:
                logger.warning(
                    f"Failed to link test case to story {story_key}: {e}"
                )

        return test_case_key

    async def _add_test_steps(self, test_case_key: str, steps: List) -> None:
        """
        Add test steps to an existing test case.
        
        Zephyr Scale API v2 requires steps to be added AFTER test case creation
        via a separate endpoint: POST /testcases/{key}/teststeps
        
        Args:
            test_case_key: The Zephyr test case key (e.g., 'PLAT-T1234')
            steps: List of TestStep objects
        """
        url = f"{self.base_url}/testcases/{test_case_key}/teststeps"
        
        # Build the steps payload in Zephyr's format
        items = []
        for step in steps:
            items.append({
                "inline": {
                    "description": step.action[:1000] if step.action else "",
                    "testData": step.test_data[:500] if step.test_data else "",
                    "expectedResult": step.expected_result[:1000] if step.expected_result else ""
                }
            })
        
        payload = {
            "mode": "OVERWRITE",  # Replace any existing steps
            "items": items
        }
        
        logger.info(f"Adding {len(items)} steps to {test_case_key}")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload, headers=self.headers)
            response.raise_for_status()
            
        logger.info(f"✅ Added {len(items)} steps to {test_case_key}")

    async def get_test_cases_for_project(
        self, 
        project_key: str, 
        max_results: Optional[int] = 5000,
        use_cache: bool = True,
        search_query: Optional[str] = None
    ) -> List[Dict]:
        """
        Retrieve test cases for a project with pagination, caching, and optional search.

        Args:
            project_key: Jira project key
            max_results: Maximum number of test cases to retrieve (default 5000, None for unlimited)
            use_cache: Use cached results if available (default True)
            search_query: Optional search query to filter by keywords (for scalability)

        Returns:
            List of test cases

        Raises:
            httpx.HTTPError: If the request fails
        """
        import time
        
        # For search queries, create a unique cache key
        cache_key = f"{project_key}_{max_results}_{search_query or 'all'}"
        
        # Return cached if less than CACHE_TTL (30 min) old
        if use_cache and cache_key in ZephyrIntegration._test_cache:
            if ZephyrIntegration._cache_timestamp:
                age = time.time() - ZephyrIntegration._cache_timestamp
                if age < ZephyrIntegration.CACHE_TTL:
                    cached = ZephyrIntegration._test_cache[cache_key]
                    logger.info(f"⚡ Using cached tests ({int(age)}s old, {len(cached)} tests)")
                    return cached
        
        # If search_query is provided, use Zephyr search API for scalability
        if search_query:
            logger.info(f"Searching Zephyr for tests matching: {search_query} (scalable mode)")
            return await self.search_test_cases(project_key, search_query)
        
        if max_results is None:
            logger.info(f"Fetching ALL existing test cases for project: {project_key} (unlimited)")
        else:
            logger.info(f"Fetching existing test cases for project: {project_key} (max: {max_results})")

        all_tests = []
        start_at = 0
        page_size = 100
        
        while max_results is None or len(all_tests) < max_results:
            url = f"{self.base_url}/testcases"
            params = {
                "projectKey": project_key, 
                "maxResults": page_size,
                "startAt": start_at
            }

            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=self.headers, params=params, timeout=30.0)
                response.raise_for_status()
                data = response.json()

            values = data.get("values", [])
            if not values:
                break
                
            all_tests.extend(values)
            
            # Check if there are more results
            if not data.get("isLast", True):
                start_at += page_size
            else:
                break
        
        logger.info(f"Fetched {len(all_tests)} total test cases from Zephyr")
        
        # Cache the results
        import time
        ZephyrIntegration._test_cache[cache_key] = all_tests
        ZephyrIntegration._cache_timestamp = time.time()
        
        return all_tests

    async def get_relevant_tests_for_story(
        self,
        project_key: str,
        story_summary: str,
        max_results: int = 100
    ) -> List[Dict]:
        """
        Get ONLY relevant tests using Zephyr search API (scalable to millions).
        
        This method extracts keywords from the story and searches only for relevant tests,
        making it scalable even with 500k+ tests.
        
        Args:
            project_key: Jira project key
            story_summary: Story title/summary to extract keywords from
            max_results: Maximum relevant tests to return (default 100)
            
        Returns:
            List of relevant test cases
        """
        # Extract meaningful keywords from story
        keywords = self._extract_keywords(story_summary)
        
        if not keywords:
            logger.warning("No keywords extracted, falling back to recent tests")
            return await self.get_test_cases_for_project(project_key, max_results=100)
        
        # Build search query
        query = " OR ".join(keywords[:5])  # Use top 5 keywords
        
        logger.info(f"Searching Zephyr with keywords: {keywords[:5]}")
        logger.info(f"Search query: {query}")
        
        try:
            # Use existing search API (indexed, fast)
            results = await self.search_test_cases(project_key, query)
            logger.info(f"Found {len(results)} relevant tests via search")
            return results[:max_results]
        except Exception as e:
            logger.warning(f"Search failed: {e}, falling back to recent tests")
            return await self.get_test_cases_for_project(project_key, max_results=100)
    
    def _extract_keywords(self, text: str) -> List[str]:
        """
        Extract meaningful keywords from text for search.
        
        Args:
            text: Text to extract keywords from
            
        Returns:
            List of keywords (nouns, feature names)
        """
        # Common stop words to ignore
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'with', 'by', 'from', 'up', 'about', 'into', 'through', 'during',
            'before', 'after', 'above', 'below', 'between', 'under', 'again',
            'further', 'then', 'once', 'here', 'there', 'when', 'where', 'why',
            'how', 'all', 'both', 'each', 'few', 'more', 'most', 'other', 'some',
            'such', 'no', 'nor', 'not', 'only', 'own', 'same', 'so', 'than',
            'too', 'very', 'can', 'will', 'just', 'should', 'now', 'is', 'are',
            'was', 'were', 'been', 'being', 'have', 'has', 'had', 'do', 'does',
            'did', 'get', 'add', 'create', 'update', 'delete', 'test', 'verify'
        }
        
        # Split and clean
        words = text.lower().split()
        
        # Filter: length > 3, not a stop word, alphanumeric
        keywords = [
            w for w in words 
            if len(w) > 3 and w not in stop_words and w.isalnum()
        ]
        
        # Remove duplicates while preserving order
        seen = set()
        unique_keywords = []
        for kw in keywords:
            if kw not in seen:
                seen.add(kw)
                unique_keywords.append(kw)
        
        return unique_keywords[:10]  # Return top 10

    async def search_test_cases(
        self, project_key: str, query: str
    ) -> List[Dict]:
        """
        Search for test cases matching a query.

        Args:
            project_key: Jira project key
            query: Search query string

        Returns:
            List of matching test cases
        """
        logger.info(f"Searching test cases in {project_key} for: {query}")

        url = f"{self.base_url}/testcases/search"
        params = {"projectKey": project_key, "query": query}

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self.headers, params=params, timeout=30.0)
            response.raise_for_status()
            data = response.json()

        return data.get("values", [])

    async def get_folder_structure(self, project_key: str) -> List[Dict]:
        """
        Get test case folder structure for a project.

        Args:
            project_key: Jira project key

        Returns:
            List of folders with hierarchy

        Raises:
            httpx.HTTPError: If the request fails
        """
        logger.info(f"Fetching folder structure for project: {project_key}")

        url = f"{self.base_url}/folders"
        params = {"projectKey": project_key, "folderType": "TEST_CASE"}

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self.headers, params=params, timeout=30.0)
            response.raise_for_status()
            data = response.json()

        return data.get("values", [])

    async def ensure_folder(self, project_key: str, folder_path: str) -> Optional[str]:
        """Ensure the full folder path exists and return the final folder ID."""
        if not folder_path:
            return None

        segments = [seg.strip() for seg in folder_path.split('/') if seg.strip()]
        if not segments:
            return None

        existing = await self.get_folder_structure(project_key)
        flat_folders = self._flatten_folders(existing)
        by_parent: Dict[Optional[str], List[Dict]] = defaultdict(list)
        for folder in flat_folders:
            fid = folder.get('id')
            pid = folder.get('parentId') if folder.get('parentId') is not None else None
            key = str(pid) if pid is not None else None
            by_parent[key].append(folder)

        parent_id: Optional[str] = None
        for segment in segments:
            normalized = segment.lower()
            siblings = by_parent[str(parent_id) if parent_id is not None else None]
            match = None
            for folder in siblings:
                name = folder.get('name', '').strip().lower()
                if name == normalized:
                    match = folder
                    break
            if match:
                parent_id = match.get('id')
                continue

            parent_before = parent_id
            created_id = await self._create_folder(project_key, segment, parent_before)
            new_folder = {
                'id': created_id,
                'name': segment,
                'parentId': parent_before,
                'children': []
            }
            by_parent[str(parent_before) if parent_before is not None else None].append(new_folder)
            by_parent[str(created_id)].extend([])
            parent_id = created_id

        return str(parent_id) if parent_id is not None else None

    async def _create_folder(self, project_key: str, name: str, parent_id: Optional[str] = None) -> str:
        """Create a test case folder and return its ID."""
        payload: Dict[str, object] = {
            "projectKey": project_key,
            "name": name,
            "folderType": "TEST_CASE",
        }
        if parent_id is not None:
            payload["parentId"] = int(parent_id) if str(parent_id).isdigit() else parent_id

        url = f"{self.base_url}/folders"
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=self.headers, json=payload, timeout=30.0)
            response.raise_for_status()
            data = response.json()
        folder_id = data.get("id") or data.get("folderId")
        logger.info(f"Created folder '{name}' (ID: {folder_id})")
        return str(folder_id)

    def _flatten_folders(self, folders: List[Dict]) -> List[Dict]:
        """Flatten folder tree into a list."""
        flat: List[Dict] = []
        stack = list(folders or [])
        while stack:
            folder = stack.pop()
            flat.append(folder)
            children = folder.get('children') or []
            stack.extend(children)
        return flat

    async def link_test_to_issue(self, test_case_key: str, issue_key: str) -> None:
        """
        Link a test case to a Jira issue (for traceability).

        Args:
            test_case_key: Zephyr test case key (e.g., PROJ-T123)
            issue_key: Jira issue key (e.g., PROJ-456)

        Raises:
            httpx.HTTPError: If the request fails
        """
        logger.debug(f"Linking test case {test_case_key} to issue {issue_key}")

        # Zephyr Scale v2 API uses issueId (Jira internal ID), not issueKey
        # We need to get the Jira issue ID first
        from src.config.settings import settings
        import base64
        
        # Get Jira issue to extract its ID
        jira_auth = base64.b64encode(f"{settings.atlassian_email}:{settings.atlassian_api_token}".encode()).decode()
        
        async with httpx.AsyncClient() as client:
            # Get Jira issue details
            jira_response = await client.get(
                f"https://plainid.atlassian.net/rest/api/2/issue/{issue_key}",
                headers={
                    'Authorization': f'Basic {jira_auth}',
                    'Content-Type': 'application/json'
                },
                timeout=30.0
            )
            
            if jira_response.status_code == 200:
                issue_data = jira_response.json()
                issue_id = issue_data.get('id')
                
                # Now link in Zephyr
                url = f"{self.base_url}/testcases/{test_case_key}/links/issues"
                payload = {"issueId": int(issue_id)}
                
                response = await client.post(
                    url, headers=self.headers, json=payload, timeout=30.0
                )
                response.raise_for_status()
                logger.info(f"✅ Linked {test_case_key} to {issue_key}")
            else:
                raise Exception(f"Could not fetch Jira issue {issue_key}: {jira_response.status_code}")

    async def get_test_case(self, test_case_key: str) -> Dict:
        """
        Retrieve a test case from Zephyr.

        Args:
            test_case_key: Zephyr test case key

        Returns:
            Test case data

        Raises:
            httpx.HTTPError: If the request fails
        """
        url = f"{self.base_url}/testcases/{test_case_key}"

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self.headers, timeout=30.0)
            response.raise_for_status()
            return response.json()

    async def create_test_cycle(
        self,
        project_key: str,
        name: str,
        description: Optional[str] = None,
        folder_id: Optional[str] = None,
    ) -> str:
        """
        Create a test cycle in Zephyr.

        Args:
            project_key: Jira project key
            name: Cycle name
            description: Cycle description
            folder_id: Optional folder ID

        Returns:
            Created test cycle key

        Raises:
            httpx.HTTPError: If the request fails
        """
        logger.info(f"Creating test cycle: {name}")

        payload = {
            "projectKey": project_key,
            "name": name,
            "description": description or "",
        }

        if folder_id:
            payload["folderId"] = folder_id

        url = f"{self.base_url}/testcycles"

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url, headers=self.headers, json=payload, timeout=30.0
            )
            response.raise_for_status()
            data = response.json()

        return data.get("key")

    def _map_priority(self, priority: str) -> str:
        """
        Map internal priority to Zephyr priority.

        Args:
            priority: Internal priority level

        Returns:
            Zephyr priority string
        """
        priority_map = {
            "critical": "High",
            "high": "High",
            "medium": "Medium",
            "low": "Low",
        }
        return priority_map.get(priority.lower(), "Medium")

