"""
GitLab fallback endpoint extractor using MCP for discovering endpoints from codebase.
Used when no endpoints are found via normal Swagger/RAG extraction.

Uses mcp-remote with OAuth authentication via MCP Python client library.
"""

import re
import json
import yaml
import subprocess
import asyncio
from pathlib import Path
from typing import List, Optional, Dict, Any
from loguru import logger

from src.models.enriched_story import APISpec
from src.config.settings import settings
from src.ai.generation.ai_client_factory import AIClientFactory


class GitLabMCPClient:
    """
    Client wrapper for GitLab MCP using mcp-remote with OAuth.
    
    Uses MCP Python client library to communicate with mcp-remote subprocess.
    mcp-remote handles OAuth authentication automatically (browser opens on first use).
    """
    
    def __init__(self):
        """Initialize GitLab MCP client with mcp-remote."""
        self.mcp_available = False
        self.mcp_process = None
        self.oauth_cache_dir = None
        
        # First, check if mcp package is installed and accessible
        try:
            import mcp
            import mcp.client.stdio  # Test if submodule is accessible
        except ImportError as e:
            logger.error(f"MCP package not properly installed: {e}")
            logger.error("Install with: pip install 'mcp>=1.21.2'")
            return
        
        try:
            from mcp.client.stdio import stdio_client, StdioServerParameters
            from mcp.client.session import ClientSession
            
            # Set up OAuth cache directory (configurable for K8s)
            if settings.mcp_oauth_cache_dir:
                self.oauth_cache_dir = Path(settings.mcp_oauth_cache_dir)
            else:
                self.oauth_cache_dir = Path.home() / ".mcp-auth"
            self.oauth_cache_dir.mkdir(parents=True, exist_ok=True)
            
            # Check if mcp-remote is available
            try:
                result = subprocess.run(
                    ["which", "mcp-remote"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    mcp_remote_path = result.stdout.strip()
                    logger.debug(f"mcp-remote found at: {mcp_remote_path}")
                else:
                    # Try npx as fallback
                    result = subprocess.run(
                        ["which", "npx"],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if result.returncode != 0:
                        logger.warning("Neither mcp-remote nor npx found")
                        self.mcp_available = False
                        return
                    mcp_remote_path = "npx"
                
                self.mcp_remote_path = mcp_remote_path
                self.mcp_endpoint = "https://gitlab.com/api/v4/mcp"
                
                logger.info(f"GitLab MCP client initialized (OAuth cache: {self.oauth_cache_dir})")
                logger.info("Using mcp-remote with OAuth authentication")
                logger.info("Browser will open for OAuth login on first use")
                self.mcp_available = True
                
            except Exception as e:
                logger.warning(f"Failed to check for mcp-remote: {e}")
                self.mcp_available = False
                
        except Exception as e:
            logger.error(f"MCP initialization failed: {e}")
            logger.error(f"  Full error: {type(e).__name__}: {e}")
            self.mcp_available = False
    
    async def semantic_code_search(
        self,
        project_id: str,
        semantic_query: str,
        directory_path: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Perform semantic code search using GitLab MCP via mcp-remote.
        
        Args:
            project_id: GitLab project ID or path
            semantic_query: Natural language query about the code
            directory_path: Optional directory to scope search
            limit: Maximum number of results
            
        Returns:
            List of code search results with file paths and content
        """
        if not self.mcp_available:
            logger.warning("MCP not available for semantic code search")
            return []
        
        try:
            from mcp.client.stdio import stdio_client, StdioServerParameters
            from mcp.client.session import ClientSession
            
            logger.debug(f"Semantic code search via GitLab MCP: {semantic_query} in {project_id}")
            
            # Build mcp-remote command
            if self.mcp_remote_path == "npx":
                cmd = ["npx", "-y", "mcp-remote", self.mcp_endpoint]
            else:
                cmd = [self.mcp_remote_path, self.mcp_endpoint]
            
            logger.info(f"Connecting to GitLab MCP via: {' '.join(cmd[:3])}...")
            logger.info("If browser opens, please authorize OAuth login!")
            
            # Build StdioServerParameters
            if self.mcp_remote_path == "npx":
                server_params = StdioServerParameters(
                    command="npx",
                    args=["-y", "mcp-remote", self.mcp_endpoint]
                )
            else:
                server_params = StdioServerParameters(
                    command=self.mcp_remote_path,
                    args=[self.mcp_endpoint]
                )
            
            # Use MCP stdio client to communicate with mcp-remote
            async with stdio_client(server_params) as streams:
                if not streams:
                    logger.error("Failed to establish stdio connection")
                    return []
                
                read, write = streams
                async with ClientSession(read, write) as session:
                    try:
                        # Initialize the session
                        await session.initialize()
                        logger.debug("MCP session initialized")
                        
                        # List available tools
                        try:
                            tools = await session.list_tools()
                            logger.debug(f"Available MCP tools: {[t.name for t in tools.tools]}")
                        except Exception as e:
                            logger.warning(f"Could not list tools: {e}")
                        
                        # Call semantic_code_search tool
                        logger.info("Calling semantic_code_search tool via MCP...")
                        
                        # Build parameters (only include directory_path if provided)
                        params = {
                            "project_id": project_id,
                            "semantic_query": semantic_query,
                            "limit": limit
                        }
                        if directory_path:
                            params["directory_path"] = directory_path
                        
                        result = await session.call_tool(
                            "semantic_code_search",
                            params
                        )
                        
                        logger.debug(f"MCP tool call completed, parsing results...")
                        
                        # Parse results
                        if result.content:
                            results = []
                            for item in result.content:
                                if hasattr(item, 'text'):
                                    text = item.text
                                    # Skip error messages
                                    if 'Validation error' in text or 'Error' in text[:50]:
                                        logger.warning(f"MCP returned error: {text}")
                                        continue
                                    
                                    try:
                                        data = json.loads(text)
                                        if isinstance(data, list):
                                            results.extend(data)
                                        else:
                                            results.append(data)
                                    except json.JSONDecodeError:
                                        # If not JSON, treat as plain text content
                                        if 'Validation error' not in text and 'Error' not in text[:50]:
                                            results.append({"content": text})
                                elif hasattr(item, 'content'):
                                    # Handle different content types
                                    content_str = str(item.content)
                                    if 'Validation error' not in content_str and 'Error' not in content_str[:50]:
                                        results.append({"content": content_str})
                            
                            # Filter out error results
                            valid_results = [r for r in results if not any(
                                'Validation error' in str(v) or 'Error' in str(v)[:50] 
                                for v in r.values()
                            )]
                            
                            logger.info(f"MCP semantic search returned {len(valid_results)} valid results (filtered {len(results) - len(valid_results)} errors)")
                            return valid_results
                        else:
                            logger.warning("MCP returned no content")
                            return []
                    except Exception as session_error:
                        logger.error(f"Error in MCP session: {session_error}", exc_info=True)
                        return []
        
        except Exception as e:
            logger.error(f"Error in MCP semantic code search: {e}", exc_info=True)
            return []
    
    async def gitlab_search(
        self,
        scope: str,
        search: str,
        project_id: Optional[str] = None,
        group_id: Optional[str] = None,
        per_page: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Search GitLab using MCP search function via mcp-remote.
        
        Args:
            scope: Search scope (blobs, commits, etc.)
            search: Search query
            project_id: Optional project ID to search within
            group_id: Optional group ID to search within
            per_page: Results per page
            
        Returns:
            List of search results
        """
        if not self.mcp_available:
            logger.warning("MCP not available for GitLab search")
            return []
        
        try:
            from mcp.client.stdio import stdio_client, StdioServerParameters
            from mcp.client.session import ClientSession
            
            logger.debug(f"GitLab search via MCP: {search} (scope: {scope})")
            
            # Build StdioServerParameters
            if self.mcp_remote_path == "npx":
                server_params = StdioServerParameters(
                    command="npx",
                    args=["-y", "mcp-remote", self.mcp_endpoint]
                )
            else:
                server_params = StdioServerParameters(
                    command=self.mcp_remote_path,
                    args=[self.mcp_endpoint]
                )
            
            # Use MCP stdio client
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    
                    # Call gitlab_search tool
                    # Build parameters based on scope (different scopes support different parameters)
                    params = {
                        "scope": scope,
                        "search": search,
                        "per_page": per_page
                    }
                    
                    # Only add project_id or group_id if provided and supported by scope
                    # merge_requests scope doesn't support group_id in some GitLab versions
                    if project_id:
                        params["project_id"] = project_id
                    elif group_id and scope not in ["merge_requests", "issues"]:
                        # Only add group_id for scopes that support it
                        params["group_id"] = group_id
                    
                    result = await session.call_tool("gitlab_search", params)
                    
                    # Parse results
                    if result.content:
                        results = []
                        for item in result.content:
                            if hasattr(item, 'text'):
                                try:
                                    data = json.loads(item.text)
                                    if isinstance(data, list):
                                        results.extend(data)
                                    else:
                                        results.append(data)
                                except json.JSONDecodeError:
                                    results.append({"content": item.text})
                        return results
                    else:
                        return []
        
        except Exception as e:
            logger.error(f"Error in MCP GitLab search: {e}", exc_info=True)
            return []


class GitLabFallbackExtractor:
    """
    Extracts API endpoints from GitLab codebases using MCP as a fallback mechanism.
    
    When normal endpoint extraction finds no results, this class:
    1. Uses AI to identify relevant services
    2. Uses GitLab MCP semantic search to find endpoint-related code
    3. Extracts endpoints from found code files
    """
    
    def __init__(self):
        """Initialize GitLab fallback extractor."""
        if not settings.gitlab_fallback_enabled:
            logger.info("GitLab fallback is disabled in settings")
            return
        
        try:
            self.mcp_client = GitLabMCPClient()
        except Exception as e:
            logger.warning(f"GitLab MCP client not available: {e}")
            self.mcp_client = None
        
        self.max_services = settings.gitlab_fallback_max_services
        self.max_apis = settings.enrichment_max_apis
    
    async def _find_branches_for_story(
        self,
        story_key: str
    ) -> List[Dict[str, Any]]:
        """
        Find branches matching the story key pattern.
        
        Convention: ALL stories have branches with the story key in the name
        (e.g., "PLAT-13541", "feature/PLAT-13541", "bugfix/PLAT-13541")
        
        Args:
            story_key: Story key (e.g., "PLAT-13541")
            
        Returns:
            List of branch/project information
        """
        if not self.mcp_client or not self.mcp_client.mcp_available:
            return []
        
        logger.info(f"Searching for branches matching story key: {story_key}")
        
        try:
            group_id = settings.gitlab_group_path
            
            # Search for merge requests containing the story key
            # This is the most reliable way to find branches for a story
            mr_results = []
            try:
                # Try with group_id first
                mr_results = await self.mcp_client.gitlab_search(
                    scope="merge_requests",
                    search=story_key,
                    group_id=group_id,
                    per_page=30
                )
                logger.info(f"Found {len(mr_results)} merge requests for {story_key}")
            except Exception as e:
                logger.debug(f"MR search with group_id failed: {e}, trying without group_id")
                try:
                    # Try without group_id (global search)
                    mr_results = await self.mcp_client.gitlab_search(
                        scope="merge_requests",
                        search=story_key,
                        per_page=30
                    )
                    logger.info(f"Found {len(mr_results)} merge requests (global search)")
                except Exception as e2:
                    logger.warning(f"MR search failed completely: {e2}")
                    mr_results = []
            
            # Also search for the story key in code (to find which projects it's in)
            code_results = []
            try:
                code_results = await self.mcp_client.gitlab_search(
                    scope="blobs",
                    search=story_key,
                    group_id=group_id,
                    per_page=30
                )
                logger.info(f"Found {len(code_results)} code files containing {story_key}")
            except Exception as e:
                logger.warning(f"Blob search failed: {e}")
                code_results = []
            
            # Extract unique project IDs from results
            projects = {}
            
            # Process merge requests first (most reliable)
            for result in mr_results:
                if isinstance(result, dict):
                    project_id = result.get('project_id') or result.get('source_project_id')
                    source_branch = result.get('source_branch', '')
                    target_branch = result.get('target_branch', '')
                    
                    if project_id and project_id not in projects:
                        projects[project_id] = {
                            'project_id': project_id,
                            'source_branch': source_branch,
                            'target_branch': target_branch,
                            'ref': source_branch or target_branch or 'master',
                            'mr_title': result.get('title', ''),
                        }
                        logger.debug(f"Found project {project_id} via MR: {result.get('title', 'N/A')}")
            
            # Process code results
            for result in code_results:
                if isinstance(result, dict):
                    # Extract project ID and other metadata
                    project_id = result.get('project_id')
                    if project_id and project_id not in projects:
                        projects[project_id] = {
                            'project_id': project_id,
                            'path': result.get('path', ''),
                            'filename': result.get('filename', result.get('path', '')),
                            'ref': result.get('ref', 'master'),
                        }
            
            logger.info(f"Found {len(projects)} projects with branches/code for {story_key}")
            for proj_id, proj_info in list(projects.items())[:5]:
                logger.debug(f"  - Project {proj_id}: {proj_info.get('filename', 'N/A')}")
            
            return list(projects.values())
            
        except Exception as e:
            logger.warning(f"Error finding branches for {story_key}: {e}")
            return []
    
    async def extract_from_codebase(
        self,
        story_key: str,
        story_text: str,
        project_key: str
    ) -> List[APISpec]:
        """
        Extract endpoints from GitLab codebase using MCP as fallback.
        
        Args:
            story_key: Story key (e.g., "PLAT-13541")
            story_text: Combined story text for analysis
            project_key: Project key (e.g., "PLAT")
            
        Returns:
            List of APISpec objects
        """
        if not settings.gitlab_fallback_enabled:
            logger.debug("GitLab fallback is disabled")
            return []
        
        if not self.mcp_client or not self.mcp_client.mcp_available:
            logger.error("GitLab MCP client not available - CRITICAL: MCP must be working for endpoint extraction")
            logger.error("Ensure 'mcp' package is installed: pip install 'mcp>=1.21.2'")
            logger.error("Ensure 'mcp-remote' is installed: npm install -g mcp-remote")
            return []
        
        logger.info(f"Starting GitLab MCP fallback extraction for {story_key}")
        logger.info("⚠️  Browser may open for OAuth login - please authorize!")
        
        try:
            # 1. Find branches/repos matching the story key (convention: story key in branch name)
            branches = await self._find_branches_for_story(story_key)
            
            if branches:
                logger.info(f"✅ Found {len(branches)} projects with {story_key} branches/code")
                for branch_info in branches:
                    logger.info(f"   - Project {branch_info.get('project_id')}: {branch_info.get('source_branch', branch_info.get('ref', 'N/A'))}")
            else:
                logger.warning(f"⚠️  No branches found for {story_key} - will search group-wide")
            
            # 2. Use AI to generate intelligent semantic queries based on story content
            # CRITICAL: Use full story text to understand what endpoint is being created
            ai_queries = await self._generate_ai_endpoint_search_queries(story_text, story_key)
            logger.info(f"Generated {len(ai_queries)} AI-powered search queries")
            logger.info(f"Sample queries: {ai_queries[:3]}")
            
            # 3. Search in found repos FIRST (most likely to have the code)
            search_results = []
            
            if branches:
                logger.info(f"🔍 Searching within {len(branches)} projects found for {story_key}")
                for branch_info in branches[:self.max_services]:
                    project_id = branch_info.get('project_id')
                    if not project_id:
                        continue
                    
                    logger.info(f"   Searching project {project_id}...")
                    
                    # Use MORE AI queries per project (top 10 instead of 5)
                    for query in ai_queries[:10]:  # Increased from 5 to 10
                        try:
                            results = await self.mcp_client.semantic_code_search(
                                project_id=str(project_id),
                                semantic_query=query,
                                limit=20  # Increased from 15 to 20
                            )
                            if results:
                                logger.info(f"      ✅ Found {len(results)} results with query: '{query[:60]}...'")
                                search_results.extend(results)
                        except Exception as e:
                            logger.debug(f"      Error searching project {project_id}: {e}")
                            continue
            
            # 4. Also search group-wide MORE AGGRESSIVELY
            # Use semantic code search (better than blob search) for group-wide
            logger.info(f"🔍 Group-wide semantic search (found {len(search_results)} results so far)")
            group_id = settings.gitlab_group_path
            
            # Try semantic code search first (more accurate)
            for query in ai_queries[:15]:  # Increased from 10 to 15
                try:
                    # Try semantic code search if we have a project ID from branches
                    if branches and branches[0].get('project_id'):
                        # Use the first project as reference for group-wide semantic search
                        results = await self.mcp_client.semantic_code_search(
                            project_id=str(branches[0]['project_id']),
                            semantic_query=query,
                            limit=20
                        )
                        if results:
                            logger.info(f"   ✅ Found {len(results)} semantic results with query: '{query[:60]}...'")
                            search_results.extend(results)
                except Exception as e:
                    logger.debug(f"   Error in semantic search with '{query[:30]}...': {e}")
                    # Fallback to blob search
                    try:
                        blob_results = await self.mcp_client.gitlab_search(
                            scope="blobs",
                            search=query,
                            group_id=group_id,
                            per_page=20  # Increased from 15
                        )
                        if blob_results:
                            logger.info(f"   ✅ Found {len(blob_results)} blobs with query: '{query[:60]}...'")
                            search_results.extend(blob_results)
                    except Exception as e2:
                        logger.debug(f"   Error in blob search: {e2}")
                        continue
            
            if not search_results:
                logger.error(f"❌ NO CODE FOUND via MCP search for {story_key}")
                logger.error("   This means the endpoint might not exist yet or search queries need improvement")
                return []
            
            logger.info(f"✅ Found {len(search_results)} total code search results")
            
            # 5. Extract endpoints from search results using intelligent parsing
            api_specs = self._extract_endpoints_from_search_results(search_results)
            
            # Limit to max_apis
            api_specs = api_specs[:self.max_apis]
            
            if api_specs:
                logger.info(f"✅ GitLab MCP extracted {len(api_specs)} API specifications")
                for spec in api_specs:
                    logger.info(f"   - {' '.join(spec.http_methods)} {spec.endpoint_path}")
            else:
                logger.warning(f"⚠️  Found {len(search_results)} code results but extracted 0 endpoints")
                logger.warning("   This might mean the parsing logic needs improvement")
            
            return api_specs
            
        except Exception as e:
            logger.error(f"Error in GitLab MCP fallback extraction: {e}", exc_info=True)
            return []
    
    async def _generate_ai_endpoint_search_queries(
        self,
        story_text: str,
        story_key: str
    ) -> List[str]:
        """
        Use AI to generate intelligent semantic search queries for finding endpoints/DTOs.
        
        This is the KEY method - uses AI to understand what endpoints/DTOs to look for
        based on the story content. Focuses on finding the EXACT endpoint being created.
        """
        try:
            client, model, use_openai = AIClientFactory.create_client(
                use_openai=True,
                model="gpt-4o-mini"
            )
            
            # Get full story context (not just snippet) to understand what endpoint is being created
            story_snippet = story_text[:2000]  # More context for better understanding
            
            prompt = f"""You are analyzing a Jira story to find the EXACT API endpoint being created or modified.

Story Key: {story_key}
Full Story Context:
{story_snippet}

CRITICAL: The story describes creating or modifying a specific API endpoint. Your job is to generate semantic search queries that will find THIS EXACT ENDPOINT in the codebase.

Analyze the story to determine:
1. What HTTP method is needed? (GET, POST, PATCH, DELETE)
2. What resource/entity is being accessed? (e.g., "policies", "applications")
3. What action is being performed? (e.g., "fetch by application", "list by application", "get policies for application")
4. What path pattern should it follow? (Look for examples in the story like "/policy-mgmt/dynamic-group/.../policies")

Based on the story, generate 15-20 HIGHLY SPECIFIC semantic search queries that target:
- The exact endpoint pattern (e.g., "GET policies by application", "PolicyController getPoliciesByApplication")
- Controller methods implementing this feature (e.g., "@GetMapping application policies", "PolicyController application")
- Route definitions matching the pattern (e.g., "/policy-mgmt/application", "/policy-mgmt/policies application")
- DTOs used by this endpoint (e.g., "PolicyDto application", "ApplicationPolicyRequest")
- Service methods (e.g., "fetchPoliciesByApplication", "getPoliciesForApplication")

IMPORTANT:
- Include queries with the story key: "{story_key} endpoint", "{story_key} PolicyController"
- Include queries matching the pattern shown in story examples (e.g., if story shows "/policy-mgmt/dynamic-group/.../policies", search for "/policy-mgmt/application/.../policies")
- Use Java Spring annotations: "@GetMapping", "@PostMapping", "@RequestMapping"
- Use controller naming: "PolicyController", "ApplicationController"
- Be VERY specific about the relationship (e.g., "policies by application", "policies for application", "application policies")

Return ONLY a JSON array of query strings:
[
  "GET /policy-mgmt/application policies endpoint",
  "PolicyController @GetMapping application policies",
  "fetchPoliciesByApplication method",
  "GET policies by application ID",
  "{story_key} PolicyController application",
  "/policy-mgmt/application/policies route",
  ...
]

Be extremely specific and technical. These queries will search actual code."""

            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,  # Lower temperature for more focused queries
                max_tokens=800  # Increased from 500 to allow more queries
            )
            
            content = response.choices[0].message.content or ""
            
            # Extract JSON array
            import json
            json_start = content.find('[')
            json_end = content.rfind(']') + 1
            if json_start != -1 and json_end > json_start:
                queries = json.loads(content[json_start:json_end])
                logger.info(f"AI generated {len(queries)} semantic search queries")
                # Return more queries (up to 20) for better coverage
                return queries[:20]
            else:
                # Fallback: parse lines if JSON fails
                lines = [line.strip().strip('"').strip("'") for line in content.split('\n') 
                        if line.strip() and not line.strip().startswith('[') and not line.strip().startswith(']')]
                return lines[:20]
                
        except Exception as e:
            logger.warning(f"AI query generation failed: {e}, using fallback queries")
            # Fallback to rule-based queries
            return await self._generate_service_search_queries(story_text, story_key)
    
    async def _generate_service_search_queries(
        self,
        story_text: str,
        story_key: str
    ) -> List[str]:
        """
        Generate intelligent search queries using AI and pattern analysis.
        
        Generates both:
        1. Semantic queries (AI-powered, based on story content)
        2. Specific patterns (story key, entity names, technical terms)
        """
        queries = []
        
        # Always include story key-based queries (convention: story key in branch/code)
        queries.append(f"{story_key} API endpoint")
        queries.append(f"{story_key} DTO class")
        queries.append(f"{story_key} route definition")
        
        # Extract key entities from story text for specific pattern queries
        # Look for common patterns like "policy", "application", "user", etc.
        entity_patterns = [
            r'\b(policy|policies)\b',
            r'\b(application|app)\b',
            r'\b(user|users)\b',
            r'\b(permission|permissions)\b',
            r'\b(resource|resources)\b',
            r'\b(role|roles)\b',
            r'\b(group|groups)\b',
            r'\b(tenant|tenants)\b',
        ]
        
        entities = set()
        for pattern in entity_patterns:
            matches = re.findall(pattern, story_text, re.IGNORECASE)
            for match in matches:
                entities.add(match.lower())
        
        # Generate entity-specific queries
        for entity in list(entities)[:3]:  # Limit to top 3 entities
            queries.append(f"{entity} DTO {story_key}")
            queries.append(f"{entity} endpoint {story_key}")
        
        # Try AI-powered semantic query generation
        try:
            ai_queries = await self._generate_ai_semantic_queries(story_text, story_key, list(entities))
            queries.extend(ai_queries)
        except Exception as e:
            logger.debug(f"AI query generation failed, using rule-based only: {e}")
        
        # Add generic technical queries
        feature_terms = []
        if re.search(r'(create|add|new|implement).*endpoint', story_text, re.IGNORECASE):
            feature_terms.append("API endpoint")
        if re.search(r'(route|router|path)', story_text, re.IGNORECASE):
            feature_terms.append("route definition")
        if re.search(r'(dto|data.*transfer|request|response)', story_text, re.IGNORECASE):
            feature_terms.append("DTO class definition")
        
        for term in feature_terms:
            queries.append(f"{story_key} {term}")
        
        # Deduplicate while preserving order
        seen = set()
        unique_queries = []
        for q in queries:
            q_lower = q.lower()
            if q_lower not in seen:
                seen.add(q_lower)
                unique_queries.append(q)
        
        logger.debug(f"Generated {len(unique_queries)} search queries for {story_key}")
        return unique_queries[:10]  # Limit to 10 queries
    
    async def _generate_ai_semantic_queries(
        self,
        story_text: str,
        story_key: str,
        entities: List[str]
    ) -> List[str]:
        """
        Use AI to generate semantic search queries based on story content.
        
        Args:
            story_text: Story summary and description
            story_key: Story key (e.g., "PLAT-13541")
            entities: Extracted entities (e.g., ["policy", "application"])
            
        Returns:
            List of AI-generated semantic queries
        """
        try:
            client, model, use_openai = AIClientFactory.create_client(
                use_openai=True,
                model="gpt-4o-mini"  # Fast, cheap model for query generation
            )
            
            entities_str = ", ".join(entities) if entities else "N/A"
            story_snippet = ' '.join(story_text.split()[:200])  # Limit context
            
            prompt = f"""Analyze this story and generate 3-5 semantic search queries to find relevant API endpoints and DTOs in a codebase.

Story Key: {story_key}
Story Content: {story_snippet}
Key Entities: {entities_str}

Generate queries that would help find:
1. API endpoint definitions (routes, controllers)
2. DTO/model class definitions with fields
3. Request/response schemas

Return ONLY a JSON array of query strings, no other text:
["query 1", "query 2", "query 3"]

Focus on semantic meaning, not exact text matching."""

            if use_openai:
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": "You generate semantic search queries for code search. Return only JSON arrays."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3,
                    max_tokens=200
                )
                result_text = response.choices[0].message.content
            else:
                from anthropic import Anthropic
                response = client.messages.create(
                    model=model,
                    max_tokens=200,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3
                )
                result_text = response.content[0].text
            
            # Parse JSON response
            result_text = result_text.strip()
            if result_text.startswith('```'):
                # Remove code fence
                result_text = re.sub(r'```json?\s*|\s*```', '', result_text)
            
            queries = json.loads(result_text)
            if isinstance(queries, list):
                logger.debug(f"AI generated {len(queries)} semantic queries")
                return queries[:5]
            else:
                logger.warning(f"AI returned non-list: {type(queries)}")
                return []
                
        except Exception as e:
            logger.debug(f"AI semantic query generation failed: {e}")
            return []
    
    async def _search_codebase_via_mcp(
        self,
        story_key: str,
        story_text: str,
        service_queries: List[str],
        branches: List[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search GitLab codebase using MCP semantic search.
        
        Multi-stage search:
        1. Search in found branches/projects (if available)
        2. Fall back to group-wide search if no branches found
        """
        all_results = []
        
        group_id = settings.gitlab_group_path
        
        search_queries = [
            f"API endpoint for {story_key}",
            f"route definition {story_key}",
            f"OpenAPI specification {story_key}",
            f"REST API {story_key}",
        ]
        search_queries.extend(service_queries)
        
        # If we have specific branches/projects, search within them first
        if branches:
            logger.info(f"Searching within {len(branches)} projects found for {story_key}")
            for branch_info in branches[:self.max_services]:
                project_id = branch_info.get('project_id')
                if not project_id:
                    continue
                
                logger.debug(f"Searching in project {project_id}")
                
                for query in search_queries[:3]:  # Limit queries per project
                    try:
                        results = await self.mcp_client.semantic_code_search(
                            project_id=str(project_id),  # Use numeric ID
                            semantic_query=query,
                            limit=10
                        )
                        all_results.extend(results)
                    except Exception as e:
                        logger.debug(f"Error searching project {project_id} with '{query}': {e}")
                        continue
        
        # Also do group-wide blob search with feature-specific queries
        logger.info("Performing group-wide blob search")
        
        # Add feature-specific search queries based on story content
        feature_queries = []
        if 'policy' in story_text.lower() and 'application' in story_text.lower():
            feature_queries.extend([
                "PolicyController @GetMapping",
                "PolicyController @PostMapping",
                "@RequestMapping policy",
                "fetchLinkedPolicies application",
                "policy application endpoint",
                "PolicyDto application",
                "GET policy-mgmt policies application",
                "class PolicyDto",
                "interface PolicyDto"
            ])
        
        # Combine with existing queries
        all_search_queries = search_queries[:5] + feature_queries
        
        for query in all_search_queries:
            try:
                blob_results = await self.mcp_client.gitlab_search(
                    scope="blobs",
                    search=query,
                    group_id=group_id,
                    per_page=10
                )
                
                all_results.extend(blob_results)
                
            except Exception as e:
                logger.warning(f"Error searching with query '{query}': {e}")
                continue
        
        # Deduplicate results
        seen = set()
        unique_results = []
        for result in all_results:
            result_id = result.get('file_path') or result.get('path') or str(result)
            if result_id not in seen:
                seen.add(result_id)
                unique_results.append(result)
        
        return unique_results
    
    def _extract_endpoints_from_search_results(
        self,
        search_results: List[Dict[str, Any]]
    ) -> List[APISpec]:
        """
        Extract endpoints from MCP search results.
        
        MCP blob search returns snippets, not full files.
        We aggregate snippets by file path to get more complete content.
        """
        api_specs = []
        seen_endpoints = set()
        
        # Aggregate snippets by file path
        file_contents = {}
        logger.debug(f"Processing {len(search_results)} search results")
        
        for i, result in enumerate(search_results):
            # Get content from result
            content = result.get('content') or result.get('text') or result.get('data') or ''
            
            if not content:
                continue
            
            # Semantic search results come as numbered lists: "1. path/to/file\n   code..."
            # Parse this format
            import re
            
            # Split by numbered list items (e.g., "1. ", "2. ", etc.)
            items = re.split(r'\n(\d+)\.\s+', content)
            
            if len(items) > 1:
                # We have numbered list format
                for j in range(1, len(items), 2):  # Skip first empty item, then pairs of (number, content)
                    if j + 1 < len(items):
                        file_path = items[j + 1].split('\n')[0].strip()  # First line is path
                        code_content = '\n'.join(items[j + 1].split('\n')[1:])  # Rest is code
                        
                        if file_path and code_content:
                            if file_path not in file_contents:
                                file_contents[file_path] = {
                                    'path': file_path,
                                    'snippets': [],
                                    'project_id': result.get('project_id')
                                }
                            file_contents[file_path]['snippets'].append(code_content)
                            logger.debug(f"Parsed semantic result: {file_path} ({len(code_content)} chars)")
            else:
                # Not numbered list format - try to extract file path from content
                # Look for common patterns like "path/to/file" at start of lines
                lines = content.split('\n')
                file_path = None
                code_start = 0
                
                for line_idx, line in enumerate(lines[:10]):  # Check first 10 lines
                    # Look for file path patterns
                    if re.match(r'^[\w\-./]+\.(java|py|ts|js|yaml|yml|json)', line.strip()):
                        file_path = line.strip()
                        code_start = line_idx + 1
                        break
                
                if file_path:
                    code_content = '\n'.join(lines[code_start:])
                    if file_path not in file_contents:
                        file_contents[file_path] = {
                            'path': file_path,
                            'snippets': [],
                            'project_id': result.get('project_id')
                        }
                    file_contents[file_path]['snippets'].append(code_content)
                else:
                    # Fallback: use content as-is with a generic path
                    logger.debug(f"Could not extract file path from result {i}, using generic path")
                    generic_path = f"semantic_result_{i}.txt"
                    if generic_path not in file_contents:
                        file_contents[generic_path] = {
                            'path': generic_path,
                            'snippets': [],
                            'project_id': result.get('project_id')
                        }
                    file_contents[generic_path]['snippets'].append(content)
        
        logger.debug(f"Aggregated {len(file_contents)} unique files from {len(search_results)} search results")
        
        # Extract endpoints from aggregated content
        for file_path, file_data in file_contents.items():
            try:
                # Combine all snippets for this file
                combined_content = '\n'.join(file_data['snippets'])
                
                # Parse based on file type
                if any(ext in file_path.lower() for ext in ['.yaml', '.yml', '.json']):
                    specs = self._parse_openapi_file(combined_content, file_path)
                elif any(ext in file_path.lower() for ext in ['.py', '.ts', '.js', '.java']):
                    specs = self._parse_route_file(combined_content, file_path)
                else:
                    specs = self._parse_route_file(combined_content, file_path)
                
                for spec in specs:
                    endpoint_key = f"{spec.endpoint_path}:{','.join(sorted(spec.http_methods))}"
                    if endpoint_key not in seen_endpoints:
                        api_specs.append(spec)
                        seen_endpoints.add(endpoint_key)
                        logger.debug(f"Extracted endpoint: {spec.http_methods} {spec.endpoint_path} from {file_path}")
                
            except Exception as e:
                logger.warning(f"Error extracting endpoints from {file_path}: {e}")
                continue
        
        # Extract DTOs and add examples to specs
        api_specs = self._enhance_specs_with_dtos(api_specs, search_results)
        
        return api_specs
    
    def _enhance_specs_with_dtos(
        self,
        api_specs: List[APISpec],
        search_results: List[Dict[str, Any]]
    ) -> List[APISpec]:
        """
        Enhance API specifications with DTO definitions and example payloads.
        
        Args:
            api_specs: List of API specifications
            search_results: MCP search results containing code
            
        Returns:
            Enhanced API specifications with DTO info and examples
        """
        # Extract all DTO definitions from search results
        dto_definitions = self._extract_dto_definitions(search_results)
        
        if not dto_definitions:
            logger.debug("No DTO definitions found in search results")
            return api_specs
        
        logger.info(f"Found {len(dto_definitions)} DTO definitions")
        
        # Match DTOs to endpoints and generate examples
        for spec in api_specs:
            # Try to find matching DTOs based on endpoint path
            endpoint_name = spec.endpoint_path.split('/')[-1] if '/' in spec.endpoint_path else spec.endpoint_path
            
            # Look for DTOs that match the endpoint name
            matching_dtos = {}
            for dto_name, dto_def in dto_definitions.items():
                dto_lower = dto_name.lower()
                endpoint_lower = endpoint_name.lower()
                
                # Match if DTO name contains endpoint name or vice versa
                if endpoint_lower in dto_lower or dto_lower in endpoint_lower:
                    matching_dtos[dto_name] = dto_def
            
            if matching_dtos:
                # Generate example request/response from DTOs
                spec.dto_definitions = matching_dtos
                
                # Generate example payloads
                request_example, response_example = self._generate_example_payloads(
                    matching_dtos,
                    spec.http_methods
                )
                
                if request_example:
                    spec.request_example = request_example
                if response_example:
                    spec.response_example = response_example
                
                logger.debug(f"Enhanced {spec.endpoint_path} with {len(matching_dtos)} DTOs")
        
        return api_specs
    
    def _extract_dto_definitions(
        self,
        search_results: List[Dict[str, Any]]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Extract DTO/model class definitions from code search results.
        
        Args:
            search_results: MCP search results containing code
            
        Returns:
            Dict mapping DTO names to their field definitions
        """
        dto_definitions = {}
        
        for result in search_results:
            try:
                content = result.get('content') or result.get('text') or result.get('code', '')
                file_path = result.get('file_path') or result.get('path') or ''
                
                if not content:
                    continue
                
                # Look for DTO/model class definitions
                # Python: class XyzDTO:
                python_class_pattern = r'class\s+(\w+(?:DTO|Request|Response|Entity|Model))\s*(?:\([^)]*\))?:\s*\n((?:\s+\w+.*\n)+)'
                
                # TypeScript/JavaScript: interface XyzDTO { ... }
                ts_interface_pattern = r'(?:interface|type)\s+(\w+(?:DTO|Request|Response|Entity|Model))\s*\{([^}]+)\}'
                
                # Java: public class XyzDTO { ... }
                java_class_pattern = r'(?:public|private)?\s*class\s+(\w+(?:DTO|Request|Response|Entity|Model))\s*\{([^}]+)\}'
                
                # Try Python pattern
                for match in re.finditer(python_class_pattern, content, re.MULTILINE):
                    dto_name = match.group(1)
                    dto_body = match.group(2)
                    fields = self._parse_python_dto_fields(dto_body)
                    if fields:
                        dto_definitions[dto_name] = fields
                        logger.debug(f"Found Python DTO: {dto_name} with {len(fields)} fields")
                
                # Try TypeScript/JavaScript pattern
                for match in re.finditer(ts_interface_pattern, content, re.DOTALL):
                    dto_name = match.group(1)
                    dto_body = match.group(2)
                    fields = self._parse_typescript_dto_fields(dto_body)
                    if fields:
                        dto_definitions[dto_name] = fields
                        logger.debug(f"Found TypeScript DTO: {dto_name} with {len(fields)} fields")
                
                # Try Java pattern
                for match in re.finditer(java_class_pattern, content, re.DOTALL):
                    dto_name = match.group(1)
                    dto_body = match.group(2)
                    fields = self._parse_java_dto_fields(dto_body)
                    if fields:
                        dto_definitions[dto_name] = fields
                        logger.debug(f"Found Java DTO: {dto_name} with {len(fields)} fields")
                
            except Exception as e:
                logger.debug(f"Error extracting DTOs from result: {e}")
                continue
        
        return dto_definitions
    
    def _parse_python_dto_fields(self, dto_body: str) -> Dict[str, Any]:
        """Parse Python DTO fields from class body."""
        fields = {}
        
        # Look for field definitions: field_name: type = ...
        field_pattern = r'(\w+)\s*:\s*([^=\n]+)(?:\s*=\s*[^#\n]+)?(?:\s*#\s*(.+))?'
        
        for match in re.finditer(field_pattern, dto_body):
            field_name = match.group(1)
            field_type = match.group(2).strip()
            field_desc = match.group(3).strip() if match.group(3) else ""
            
            # Skip special fields
            if field_name.startswith('_') or field_name in ['pass', 'return']:
                continue
            
            fields[field_name] = {
                'type': field_type,
                'description': field_desc,
                'required': 'Optional' not in field_type
            }
        
        return fields
    
    def _parse_typescript_dto_fields(self, dto_body: str) -> Dict[str, Any]:
        """Parse TypeScript/JavaScript DTO fields from interface body."""
        fields = {}
        
        # Look for field definitions: fieldName: type; or fieldName?: type;
        field_pattern = r'(\w+)(\?)?:\s*([^;,\n]+)'
        
        for match in re.finditer(field_pattern, dto_body):
            field_name = match.group(1)
            is_optional = match.group(2) == '?'
            field_type = match.group(3).strip()
            
            fields[field_name] = {
                'type': field_type,
                'required': not is_optional
            }
        
        return fields
    
    def _parse_java_dto_fields(self, dto_body: str) -> Dict[str, Any]:
        """Parse Java DTO fields from class body."""
        fields = {}
        
        # Look for field definitions: private Type fieldName;
        field_pattern = r'(?:private|public|protected)?\s+([A-Z]\w+(?:<[^>]+>)?)\s+(\w+)\s*;'
        
        for match in re.finditer(field_pattern, dto_body):
            field_type = match.group(1)
            field_name = match.group(2)
            
            fields[field_name] = {
                'type': field_type,
                'required': True  # Java fields are typically required unless marked @Nullable
            }
        
        return fields
    
    def _generate_example_payloads(
        self,
        dto_definitions: Dict[str, Dict[str, Any]],
        http_methods: List[str]
    ) -> tuple[Optional[str], Optional[str]]:
        """
        Generate example request and response payloads from DTO definitions.
        
        Args:
            dto_definitions: DTO field definitions
            http_methods: HTTP methods for the endpoint
            
        Returns:
            Tuple of (request_example, response_example) as JSON strings
        """
        request_example = None
        response_example = None
        
        # Find request and response DTOs
        request_dto = None
        response_dto = None
        
        for dto_name, dto_fields in dto_definitions.items():
            dto_lower = dto_name.lower()
            if 'request' in dto_lower or 'input' in dto_lower:
                request_dto = dto_fields
            elif 'response' in dto_lower or 'output' in dto_lower or 'result' in dto_lower:
                response_dto = dto_fields
        
        # If no explicit request/response, use first DTO for both
        if not request_dto and not response_dto and dto_definitions:
            first_dto = list(dto_definitions.values())[0]
            if 'POST' in http_methods or 'PUT' in http_methods or 'PATCH' in http_methods:
                request_dto = first_dto
            response_dto = first_dto
        
        # Generate request example
        if request_dto:
            request_obj = {}
            for field_name, field_info in request_dto.items():
                field_type = field_info.get('type', 'string').lower()
                
                # Generate example value based on type
                if 'string' in field_type or 'str' in field_type:
                    request_obj[field_name] = f"example-{field_name}"
                elif 'int' in field_type or 'number' in field_type:
                    request_obj[field_name] = 123
                elif 'bool' in field_type:
                    request_obj[field_name] = True
                elif 'list' in field_type or 'array' in field_type:
                    request_obj[field_name] = []
                else:
                    request_obj[field_name] = f"example-{field_name}"
            
            request_example = json.dumps(request_obj, indent=2)
        
        # Generate response example
        if response_dto:
            response_obj = {}
            for field_name, field_info in response_dto.items():
                field_type = field_info.get('type', 'string').lower()
                
                if 'string' in field_type or 'str' in field_type:
                    response_obj[field_name] = f"example-{field_name}"
                elif 'int' in field_type or 'number' in field_type:
                    response_obj[field_name] = 123
                elif 'bool' in field_type:
                    response_obj[field_name] = True
                elif 'list' in field_type or 'array' in field_type:
                    response_obj[field_name] = []
                else:
                    response_obj[field_name] = f"example-{field_name}"
            
            response_example = json.dumps(response_obj, indent=2)
        
        return request_example, response_example
    
    def _parse_openapi_file(self, content: str, file_path: str) -> List[APISpec]:
        """Parse OpenAPI YAML/JSON file and extract endpoints."""
        specs = []
        
        try:
            if content.strip().startswith('{'):
                spec = json.loads(content)
            else:
                spec = yaml.safe_load(content)
            
            if not spec or 'paths' not in spec:
                return specs
            
            paths = spec.get('paths', {})
            for path, methods in paths.items():
                if not isinstance(methods, dict):
                    continue
                
                http_methods = []
                for method in ['get', 'post', 'put', 'patch', 'delete', 'head', 'options']:
                    if method in methods:
                        http_methods.append(method.upper())
                
                if not http_methods:
                    continue
                
                parameters = []
                for method in http_methods:
                    method_spec = methods.get(method.lower(), {})
                    params = method_spec.get('parameters', [])
                    for param in params:
                        param_name = param.get('name', '')
                        param_in = param.get('in', '')
                        if param_name:
                            parameters.append(f"{param_name} ({param_in})")
                
                service_name = file_path.split('/')[0] if '/' in file_path else 'unknown'
                
                specs.append(APISpec(
                    endpoint_path=path,
                    http_methods=http_methods,
                    parameters=list(set(parameters)) if parameters else [],
                    service_name=service_name
                ))
        
        except (yaml.YAMLError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to parse OpenAPI file: {e}")
        except Exception as e:
            logger.warning(f"Error parsing OpenAPI file: {e}")
        
        return specs
    
    def _infer_service_name(self, file_path: str, content: str) -> str:
        """
        Infer service name from file path and content.
        Works for any service following PlainID conventions.
        """
        file_path_lower = file_path.lower()
        
        # Check for known service patterns in file path
        # e.g., "policy/controller", "envmgmt/route", "app-mgmt/service"
        path_parts = file_path_lower.split('/')
        
        for part in path_parts:
            if 'policy' in part:
                return 'policy-mgmt'
            elif 'envmgmt' in part or 'env' in part:
                return 'envmgmt'
            elif 'application' in part or 'app' in part:
                return 'app-mgmt'
            elif 'role' in part:
                return 'role-mgmt'
            elif 'user' in part:
                return 'user-mgmt'
            elif 'entitlement' in part:
                return 'entitlement-mgmt'
        
        # Try to extract from @RequestMapping annotation
        request_mapping_match = re.search(r'@RequestMapping\s*\(\s*["\']([^/"][^"\']*)', content)
        if request_mapping_match:
            base_path = request_mapping_match.group(1)
            # Extract service name from base path (e.g., "policy-mgmt" from "/policy-mgmt/1.0/...")
            if '/' in base_path:
                service = base_path.split('/')[0].rstrip('-')
                if service:
                    return service
        
        # Default: extract first meaningful part from path
        if '/' in file_path:
            return file_path.split('/')[0]
        
        return 'unknown'
    
    def _parse_route_file(self, content: str, file_path: str) -> List[APISpec]:
        """Parse route definition file (FastAPI, Flask, Express, Java Spring, etc.)."""
        specs = []
        
        # Determine service name from file path
        service_name = self._infer_service_name(file_path, content)
        
        # Java Spring annotations
        spring_pattern = r'@(GetMapping|PostMapping|PutMapping|PatchMapping|DeleteMapping)\s*(?:\(\s*["\']([^"\']*)["\'])?'
        
        for match in re.finditer(spring_pattern, content):
            annotation = match.group(1)
            path = match.group(2) or ""
            
            # Extract method from annotation name
            method = annotation.replace('Mapping', '').upper()
            
            # Build full path (need to find @RequestMapping on class if exists)
            base_path = ""
            request_mapping_match = re.search(r'@RequestMapping\s*\(\s*["\']([^"\']+)["\']', content)
            if request_mapping_match:
                base_path = request_mapping_match.group(1)
            
            full_path = f"{base_path}/{path}".replace('//', '/').rstrip('/')
            if not full_path.startswith('/'):
                full_path = '/' + full_path
            
            # If no base path found in @RequestMapping, infer from service name
            if not base_path and service_name and service_name != 'unknown':
                # Standard PlainID pattern: /service-name/1.0/resource
                # Resource name is typically the service without "-mgmt"
                resource_name = service_name.replace('-mgmt', '')
                full_path = f"/{service_name}/1.0/{resource_name}{full_path}"
            
            # Extract path parameters
            parameters = []
            param_matches = re.findall(r'\{(\w+)\}', full_path)
            for param in param_matches:
                parameters.append(f"{param} (path)")
            
            # Look for @PathVariable annotations near this endpoint
            # Search for method signature after this annotation
            method_start = match.end()
            method_signature = content[method_start:method_start+500]
            path_vars = re.findall(r'@PathVariable\s*(?:\(["\'](\w+)["\']\))?\s*\w+\s+(\w+)', method_signature)
            for path_var in path_vars:
                param_name = path_var[0] or path_var[1]
                if param_name and f"{param_name} (path)" not in parameters:
                    parameters.append(f"{param_name} (path)")
            
            # Look for @RequestParam annotations
            request_params = re.findall(r'@RequestParam\s*(?:\([^)]*name\s*=\s*["\'](\w+)["\'][^)]*\))?\s*\w+\s+(\w+)', method_signature)
            for req_param in request_params:
                param_name = req_param[0] or req_param[1]
                if param_name:
                    parameters.append(f"{param_name} (query)")
            
            specs.append(APISpec(
                endpoint_path=full_path,
                http_methods=[method],
                parameters=parameters,
                service_name=service_name
            ))
        
        # Python FastAPI routes
        fastapi_pattern = r'@router\.(get|post|put|patch|delete|head|options)\s*\(\s*["\']([^"\']+)["\']'
        flask_pattern = r'@app\.route\s*\(\s*["\']([^"\']+)["\'][^)]*\)'
        flask_methods_pattern = r'methods\s*=\s*\[([^\]]+)\]'
        express_pattern = r'(?:router|app)\.(get|post|put|patch|delete|head|options)\s*\(\s*["\']([^"\']+)["\']'
        
        # FastAPI routes
        for match in re.finditer(fastapi_pattern, content, re.IGNORECASE):
            method = match.group(1).upper()
            path = match.group(2)
            if not path.startswith('/'):
                path = '/' + path
            
            parameters = []
            param_matches = re.findall(r'\{(\w+)\}', path)
            for param in param_matches:
                parameters.append(f"{param} (path)")
            
            specs.append(APISpec(
                endpoint_path=path,
                http_methods=[method],
                parameters=parameters,
                service_name=service_name
            ))
        
        # Flask routes
        for match in re.finditer(flask_pattern, content, re.IGNORECASE):
            path = match.group(1)
            if not path.startswith('/'):
                path = '/' + path
            
            methods = ['GET']
            methods_match = re.search(flask_methods_pattern, match.group(0), re.IGNORECASE)
            if methods_match:
                methods_str = methods_match.group(1)
                methods = [m.strip().strip('"\'') for m in methods_str.split(',')]
                methods = [m.upper() for m in methods if m]
            
            parameters = []
            param_matches = re.findall(r'<(\w+)>', path)
            for param in param_matches:
                parameters.append(f"{param} (path)")
            
            specs.append(APISpec(
                endpoint_path=path,
                http_methods=methods,
                parameters=parameters,
                service_name=service_name
            ))
        
        # JavaScript/TypeScript: Look for API endpoint URLs in strings/template literals
        # Pattern: "/policy-mgmt/1.0/application/${applicationID}/search" or any service endpoint
        # Match common PlainID service patterns: /service-name/version/resource
        js_url_patterns = [
            r'["\'](/(?:policy|app|env|identity|orchestrator|internal-assets|runtime)[^"\']+)["\']',  # String literals with service names
            r'`(/(?:policy|app|env|identity|orchestrator|internal-assets|runtime)[^`]+)`',  # Template literals
            r'url:\s*["\'](/(?:policy|app|env|identity|orchestrator|internal-assets|runtime)[^"\']+)["\']',  # url: "/..."
            r'endpoint:\s*["\'](/(?:policy|app|env|identity|orchestrator|internal-assets|runtime)[^"\']+)["\']',  # endpoint: "/..."
            r'ajaxV2\([^)]*url:\s*["\'](/(?:policy|app|env|identity|orchestrator|internal-assets|runtime)[^"\']+)["\']',  # ajaxV2 calls
        ]
        
        for pattern in js_url_patterns:
            for match in re.finditer(pattern, content):
                path = match.group(1)
                # Replace template variables like ${applicationID} with {applicationID}
                path = re.sub(r'\$\{(\w+)\}', r'{\1}', path)
                
                # Infer HTTP method from context (look for ajax, fetch, axios, etc.)
                method = 'GET'  # Default
                context_start = max(0, match.start() - 100)
                context_end = min(len(content), match.end() + 100)
                context = content[context_start:context_end].lower()
                
                if 'post' in context or 'create' in context:
                    method = 'POST'
                elif 'put' in context or 'update' in context:
                    method = 'PUT'
                elif 'delete' in context or 'remove' in context:
                    method = 'DELETE'
                elif 'patch' in context:
                    method = 'PATCH'
                
                # Extract path parameters
                parameters = []
                param_matches = re.findall(r'\{(\w+)\}', path)
                for param in param_matches:
                    parameters.append(f"{param} (path)")
                
                # Check if this endpoint already exists
                if not any(spec.endpoint_path == path for spec in specs):
                    specs.append(APISpec(
                        endpoint_path=path,
                        http_methods=[method],
                        parameters=parameters,
                        service_name=service_name
                    ))
                    logger.debug(f"Extracted JS/TS endpoint: {method} {path}")
        
        # Express routes
        for match in re.finditer(express_pattern, content, re.IGNORECASE):
            method = match.group(1).upper()
            path = match.group(2)
            if not path.startswith('/'):
                path = '/' + path
            
            parameters = []
            param_matches = re.findall(r':(\w+)', path)
            for param in param_matches:
                parameters.append(f"{param} (path)")
            
            specs.append(APISpec(
                endpoint_path=path,
                http_methods=[method],
                parameters=parameters,
                service_name=service_name
            ))
        
        return specs
    
    async def _analyze_codebase_for_tests(
        self,
        endpoint: APISpec,
        story_key: str,
        story_text: str
    ) -> Dict[str, Any]:
        """
        Analyze codebase to find test patterns and examples for a given endpoint.
        
        Uses MCP semantic code search with AI-generated queries to find:
        - Test files for similar endpoints
        - Test patterns and scenarios
        - Request/response examples
        
        Returns supplementary test scenarios and code examples (not primary requirements).
        """
        if not self.mcp_client or not self.mcp_client.mcp_available:
            logger.debug("MCP not available for codebase test analysis")
            return {}
        
        logger.info(f"Analyzing codebase for test patterns: {endpoint.endpoint_path}")
        
        results = {
            "suggested_test_scenarios": [],
            "code_examples": {},
            "similar_endpoints": []
        }
        
        try:
            # Generate AI-powered semantic queries for finding test patterns
            semantic_queries = await self._generate_test_search_queries(
                endpoint=endpoint,
                story_key=story_key,
                story_text=story_text
            )
            
            logger.info(f"Generated {len(semantic_queries)} semantic search queries for test patterns")
            
            # Use MCP semantic code search to find test files and patterns
            all_test_results = []
            
            # First, try to find projects related to this endpoint
            path_parts = endpoint.endpoint_path.strip('/').split('/')
            service_name = path_parts[0] if path_parts else None
            
            # Search for projects in the group that might contain tests
            projects_to_search = []
            try:
                # Try to find projects related to the service
                project_results = await self.mcp_client.gitlab_search(
                    scope="projects",
                    search=f"{service_name}",
                    group_id=settings.gitlab_group_path,
                    per_page=5
                )
                for proj in project_results:
                    proj_id = proj.get("id") or proj.get("project_id")
                    if proj_id:
                        projects_to_search.append(str(proj_id))
            except Exception as e:
                logger.debug(f"Could not find projects for {service_name}: {e}")
            
            # If no specific projects found, use group-wide blob search
            if not projects_to_search:
                logger.info("No specific projects found, using group-wide blob search")
                for query in semantic_queries[:5]:
                    try:
                        logger.debug(f"Searching for: {query}")
                        blob_results = await self.mcp_client.gitlab_search(
                            scope="blobs",
                            search=f"{query} file:*Test.java OR file:*test.ts OR file:*_test.py",
                            group_id=settings.gitlab_group_path,
                            per_page=10
                        )
                        if blob_results:
                            logger.debug(f"Found {len(blob_results)} blob results for query: {query[:50]}...")
                            all_test_results.extend(blob_results)
                    except Exception as e:
                        logger.warning(f"Blob search failed for '{query}': {e}")
                        continue
            else:
                # Use semantic code search within found projects
                logger.info(f"Searching in {len(projects_to_search)} projects using semantic search")
                for project_id in projects_to_search[:3]:  # Limit to 3 projects
                    for query in semantic_queries[:3]:  # Limit queries per project
                        try:
                            logger.debug(f"Semantic search in project {project_id}: {query}")
                            search_results = await self.mcp_client.semantic_code_search(
                                project_id=project_id,
                                semantic_query=query,
                                limit=10
                            )
                            
                            if search_results:
                                logger.debug(f"Found {len(search_results)} results for query: {query[:50]}...")
                                all_test_results.extend(search_results)
                        except Exception as e:
                            logger.warning(f"Semantic search failed in project {project_id} for '{query}': {e}")
                            continue
            
            logger.info(f"Total test-related code snippets found: {len(all_test_results)}")
            
            if all_test_results:
                # Extract test patterns using AI understanding
                test_patterns = await self._extract_test_patterns_with_ai(
                    code_results=all_test_results,
                    endpoint=endpoint,
                    story_key=story_key
                )
                
                results["suggested_test_scenarios"] = test_patterns.get("scenarios", [])
                results["code_examples"] = test_patterns.get("examples", {})
                
                # Extract similar endpoints from code
                for result in all_test_results[:10]:
                    content = result.get("content") or result.get("text") or ""
                    if content:
                        import re
                        # Look for endpoint patterns in code
                        endpoint_matches = re.findall(
                            r'["\'](/(?:policy|app|env|identity|orchestrator|internal-assets|runtime)[^"\']+)["\']',
                            content
                        )
                        for match in endpoint_matches[:2]:
                            if match != endpoint.endpoint_path and match not in results["similar_endpoints"]:
                                results["similar_endpoints"].append(match)
            
            logger.info(f"Codebase analysis complete: {len(results['suggested_test_scenarios'])} scenarios, {len(results['code_examples'])} examples, {len(results['similar_endpoints'])} similar endpoints")
            
        except Exception as e:
            logger.warning(f"Codebase test analysis failed: {e}", exc_info=True)
        
        return results
    
    async def _generate_test_search_queries(
        self,
        endpoint: APISpec,
        story_key: str,
        story_text: str
    ) -> List[str]:
        """Use AI to generate semantic search queries for finding test patterns."""
        try:
            client, model, use_openai = AIClientFactory.create_client(
                use_openai=True,
                model="gpt-4o-mini"
            )
            
            story_snippet = ' '.join(story_text.split()[:300])
            endpoint_info = f"{' '.join(endpoint.http_methods)} {endpoint.endpoint_path}"
            
            prompt = f"""Generate semantic search queries to find test patterns and examples for this API endpoint.

Story: {story_key}
Endpoint: {endpoint_info}
Story Context: {story_snippet[:500]}

Generate 8-10 specific semantic search queries that will help find:
1. Test files that test similar endpoints (Java @Test, TypeScript it(), Python test_)
2. Test scenarios for similar functionality
3. Request/response examples in test code
4. Error handling test patterns
5. Edge case test patterns

Focus on:
- Test method patterns (e.g., "test application search endpoint", "test policy by application")
- Similar endpoint tests (e.g., "test GET endpoint with filter", "test search with pagination")
- Error scenarios (e.g., "test invalid application ID", "test unauthorized access")
- Edge cases (e.g., "test empty results", "test pagination")

Return ONLY a JSON array of query strings:
[
  "test application search endpoint with filters",
  "test GET endpoint pagination",
  "test invalid application ID error handling",
  ...
]"""

            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=500
            )
            
            content = response.choices[0].message.content or ""
            
            # Extract JSON array
            import json
            json_start = content.find('[')
            json_end = content.rfind(']') + 1
            if json_start != -1 and json_end > json_start:
                queries = json.loads(content[json_start:json_end])
                logger.info(f"AI generated {len(queries)} test search queries")
                return queries[:10]
            else:
                # Fallback: parse lines
                lines = [line.strip().strip('"').strip("'") for line in content.split('\n') 
                        if line.strip() and not line.strip().startswith('[') and not line.strip().startswith(']')]
                return lines[:10]
                
        except Exception as e:
            logger.warning(f"AI query generation failed: {e}, using fallback queries")
            # Fallback queries
            path_parts = endpoint.endpoint_path.strip('/').split('/')
            service_name = path_parts[0] if path_parts else None
            resource_name = path_parts[2] if len(path_parts) > 2 else None
            return [
                f"test {service_name} {resource_name} endpoint",
                f"test {endpoint.endpoint_path}",
                f"test GET endpoint with filters",
                f"test {resource_name} search pagination"
            ]
    
    async def _extract_test_patterns_with_ai(
        self,
        code_results: List[Dict[str, Any]],
        endpoint: APISpec,
        story_key: str
    ) -> Dict[str, Any]:
        """Use AI to extract test patterns and scenarios from code snippets."""
        try:
            # Combine code snippets (limit to avoid token limits)
            combined_code = []
            for result in code_results[:20]:  # Limit to 20 results
                content = result.get("content") or result.get("text") or ""
                if content:
                    # Truncate each snippet to 500 chars
                    combined_code.append(content[:500])
            
            if not combined_code:
                return {"scenarios": [], "examples": {}}
            
            code_text = "\n\n---\n\n".join(combined_code[:10])  # Limit to 10 snippets
            
            client, model, use_openai = AIClientFactory.create_client(
                use_openai=True,
                model="gpt-4o-mini"
            )
            
            prompt = f"""Analyze these test code snippets and extract test scenarios and examples.

Endpoint being tested: {' '.join(endpoint.http_methods)} {endpoint.endpoint_path}
Story: {story_key}

Code snippets from test files:
{code_text[:4000]}

Extract:
1. Test scenarios (what is being tested - e.g., "Test pagination with offset and limit", "Test error handling for invalid ID")
2. Request examples (JSON request bodies used in tests)
3. Response examples (JSON response bodies expected in tests)

CRITICAL RULES:
- DO NOT include generic scenarios like "Test response structure" or "Test valid response" - response validation is IMPLICIT in all tests
- DO NOT include scenarios that just check HTTP status codes - all tests validate both status AND response body
- Focus on SPECIFIC behaviors: error conditions, edge cases, filtering, pagination, data transformations
- Each scenario should test a DISTINCT behavior or condition
- Avoid redundancy - if a scenario is implied by another, exclude it

Return ONLY a JSON object:
{{
  "scenarios": [
    "Test scenario 1 (specific behavior)",
    "Test scenario 2 (specific edge case)",
    ...
  ],
  "examples": {{
    "request": "{{...}}",
    "response": "{{...}}"
  }}
}}

Focus on scenarios that would be useful for testing similar endpoints. Be specific and avoid generic/redundant scenarios."""

            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=1000
            )
            
            content = response.choices[0].message.content or ""
            
            # Extract JSON
            import json
            json_start = content.find('{')
            json_end = content.rfind('}') + 1
            if json_start != -1 and json_end > json_start:
                patterns = json.loads(content[json_start:json_end])
                scenarios = patterns.get('scenarios', [])
                
                # Filter out redundant/generic scenarios
                filtered_scenarios = self._filter_redundant_scenarios(scenarios)
                
                if len(filtered_scenarios) < len(scenarios):
                    logger.info(f"Filtered {len(scenarios) - len(filtered_scenarios)} redundant scenarios")
                
                patterns['scenarios'] = filtered_scenarios
                logger.info(f"AI extracted {len(filtered_scenarios)} test scenarios from code (after filtering)")
                return patterns
            else:
                logger.warning("AI response did not contain valid JSON")
                return {"scenarios": [], "examples": {}}
                
        except Exception as e:
            logger.warning(f"AI test pattern extraction failed: {e}")
            # Fallback to regex-based extraction
            return self._extract_test_patterns_from_files(code_results)
    
    def _filter_redundant_scenarios(self, scenarios: List[str]) -> List[str]:
        """
        Filter out redundant/generic test scenarios.
        
        Removes scenarios that:
        - Just check response structure/format (implicit in all tests)
        - Just check HTTP status codes (implicit in all tests)
        - Are too generic/vague
        """
        if not scenarios:
            return []
        
        # Patterns that indicate redundant scenarios
        redundant_patterns = [
            r'response structure',
            r'response format',
            r'valid response',
            r'correct response',
            r'response body',
            r'status code',
            r'http status',
            r'200 status',
            r'successful response',
            r'valid request',
            r'correct request',
            r'request format',
            r'request structure',
        ]
        
        import re
        filtered = []
        
        for scenario in scenarios:
            scenario_lower = scenario.lower()
            
            # Check if scenario matches redundant patterns
            is_redundant = False
            for pattern in redundant_patterns:
                if re.search(pattern, scenario_lower):
                    is_redundant = True
                    logger.debug(f"Filtered redundant scenario: {scenario}")
                    break
            
            # Also filter very generic scenarios (too short or vague)
            if not is_redundant:
                # Check if scenario is too generic (less than 30 chars or just "test X")
                if len(scenario) < 30 and 'test' in scenario_lower and scenario_lower.count(' ') < 4:
                    # Might be too generic, but allow if it has specific keywords
                    specific_keywords = ['error', 'invalid', 'empty', 'null', 'pagination', 'filter', 'edge', 'case']
                    if not any(keyword in scenario_lower for keyword in specific_keywords):
                        is_redundant = True
                        logger.debug(f"Filtered generic scenario: {scenario}")
            
            if not is_redundant:
                filtered.append(scenario)
        
        return filtered
    
    def _extract_test_patterns_from_files(self, test_files: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Extract test patterns from test file content.
        
        Returns:
            Dict with scenarios and examples
        """
        scenarios = []
        examples = {}
        
        for test_file in test_files:
            content = test_file.get("content") or test_file.get("text") or ""
            if not content:
                continue
            
            # Extract test method names (Java, TypeScript, Python patterns)
            import re
            
            # Java: @Test public void testMethodName()
            java_tests = re.findall(r'@Test\s+.*?\s+void\s+(\w+)\s*\(', content, re.IGNORECASE)
            # TypeScript: it('test description', ...)
            ts_tests = re.findall(r"it\(['\"]([^'\"]+)['\"]", content)
            # Python: def test_method_name()
            py_tests = re.findall(r'def\s+(test_\w+)\s*\(', content)
            
            all_test_names = java_tests + ts_tests + py_tests
            
            for test_name in all_test_names:
                # Convert test names to readable scenarios
                scenario = self._test_name_to_scenario(test_name)
                if scenario and scenario not in scenarios:
                    scenarios.append(scenario)
            
            # Extract request/response examples
            # Look for JSON examples in code
            json_examples = re.findall(r'\{[^{}]*"(?:applicationId|policyId|id)"[^{}]*\}', content)
            if json_examples:
                examples["request"] = json_examples[0] if json_examples else None
        
        return {
            "scenarios": scenarios[:10],  # Limit to 10 scenarios
            "examples": examples
        }
    
    def _test_name_to_scenario(self, test_name: str) -> Optional[str]:
        """Convert test method name to readable test scenario."""
        # Remove common prefixes
        name = test_name.replace("test_", "").replace("test", "")
        
        # Convert camelCase/snake_case to readable text
        import re
        words = re.findall(r'[A-Z]?[a-z]+|[A-Z]+(?=[A-Z]|$)', name) or name.split('_')
        
        if not words:
            return None
        
        # Build readable scenario
        scenario = " ".join(word.lower() for word in words if word)
        
        # Add context based on keywords
        if "invalid" in scenario or "error" in scenario:
            return f"Handle invalid input: {scenario}"
        elif "empty" in scenario or "null" in scenario:
            return f"Handle empty/null data: {scenario}"
        elif "unauthorized" in scenario or "permission" in scenario:
            return f"Handle authorization: {scenario}"
        elif "pagination" in scenario or "page" in scenario:
            return f"Test pagination: {scenario}"
        else:
            return f"Test {scenario}"
    
    def _extract_examples_from_code(self, code_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract request/response examples from code."""
        examples = {}
        
        import re
        import json
        
        for result in code_results:
            content = result.get("content") or result.get("text") or ""
            if not content:
                continue
            
            # Look for JSON objects that might be request/response examples
            # Pattern: { "field": "value", ... }
            json_pattern = r'\{[^{}]*(?:"applicationId"|"policyId"|"id"|"data"|"meta")[^{}]*\}'
            matches = re.findall(json_pattern, content)
            
            for match in matches[:2]:  # Limit to 2 per result
                try:
                    # Try to parse as JSON
                    parsed = json.loads(match)
                    if "request" not in examples and ("applicationId" in match or "policyId" in match):
                        examples["request"] = match
                    elif "response" not in examples and ("data" in match or "meta" in match):
                        examples["response"] = match
                except:
                    pass
        
        return examples
