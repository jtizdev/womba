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
        
        try:
            from mcp.client.stdio import stdio_client, StdioServerParameters
            from mcp.client.session import ClientSession
            
            # Set up OAuth cache directory
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
                
        except ImportError:
            logger.warning("MCP Python library not available. Install with: pip install mcp")
            self.mcp_available = False
        except Exception as e:
            logger.warning(f"Failed to initialize MCP client: {e}")
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
                        result = await session.call_tool(
                            "semantic_code_search",
                            {
                                "project_id": project_id,
                                "semantic_query": semantic_query,
                                "directory_path": directory_path,
                                "limit": limit
                            }
                        )
                        
                        logger.debug(f"MCP tool call completed, parsing results...")
                        
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
                                elif hasattr(item, 'content'):
                                    # Handle different content types
                                    results.append({"content": str(item.content)})
                            logger.info(f"MCP semantic search returned {len(results)} results")
                            return results
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
            # Note: MR search doesn't support group_id, so we search globally
            # and filter by group later if needed
            try:
                mr_results = await self.mcp_client.gitlab_search(
                    scope="merge_requests",
                    search=story_key,
                    group_id=group_id,  # Try with group_id
                    per_page=20
                )
            except Exception as e:
                logger.debug(f"MR search with group_id failed: {e}, trying without group_id")
                mr_results = []
            
            # Also search for the story key in code (to find which projects it's in)
            code_results = await self.mcp_client.gitlab_search(
                scope="blobs",
                search=story_key,
                group_id=group_id,
                per_page=20
            )
            
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
            logger.warning("GitLab MCP client not available for fallback extraction")
            return []
        
        logger.info(f"Starting GitLab MCP fallback extraction for {story_key}")
        logger.info("⚠️  Browser may open for OAuth login - please authorize!")
        
        try:
            # 1. Find branches matching the story key (convention: story key in branch name)
            branches = await self._find_branches_for_story(story_key)
            
            if not branches:
                logger.warning(f"No branches found for {story_key} - trying generic search")
            else:
                logger.info(f"Found {len(branches)} projects with {story_key} branches/code")
            
            # 2. Use AI to identify which services might be relevant
            service_queries = await self._generate_service_search_queries(story_text, story_key)
            
            # 3. Search across GitLab group for relevant code using MCP semantic search
            search_results = await self._search_codebase_via_mcp(
                story_key=story_key,
                story_text=story_text,
                service_queries=service_queries,
                branches=branches
            )
            
            if not search_results:
                logger.warning("No code found via MCP search")
                return []
            
            logger.info(f"Found {len(search_results)} code search results")
            
            # 3. Extract endpoints from search results
            api_specs = self._extract_endpoints_from_search_results(search_results)
            
            # Limit to max_apis
            api_specs = api_specs[:self.max_apis]
            
            logger.info(f"GitLab MCP fallback extracted {len(api_specs)} API specifications")
            return api_specs
            
        except Exception as e:
            logger.error(f"Error in GitLab MCP fallback extraction: {e}", exc_info=True)
            return []
    
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
        for result in search_results:
            file_path = result.get('file_path') or result.get('path') or result.get('filename', '')
            if not file_path:
                continue
            
            # Get content from various possible fields
            content = result.get('content') or result.get('text') or result.get('data') or result.get('code', '')
            if not content:
                continue
            
            # Aggregate content for this file
            if file_path not in file_contents:
                file_contents[file_path] = {
                    'path': file_path,
                    'snippets': [],
                    'project_id': result.get('project_id')
                }
            file_contents[file_path]['snippets'].append(content)
        
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
