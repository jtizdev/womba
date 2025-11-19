"""
GitLab fallback endpoint extractor using MCP for discovering endpoints from codebase.
Used when no endpoints are found via normal Swagger/RAG extraction.

NOTE: Uses GitLab MCP functions (not REST API) for codebase search.
The GitLab REST API client is only used for OpenAPI file fetching in RAG indexing.
"""

import re
import json
import yaml
from typing import List, Optional, Set, Dict, Any
from loguru import logger

from src.models.enriched_story import APISpec
from src.config.settings import settings
from src.ai.generation.ai_client_factory import AIClientFactory


class GitLabMCPClient:
    """
    Client wrapper for GitLab MCP functions using direct HTTP calls.
    
    Uses GitLab's MCP REST API endpoint with token authentication.
    No OAuth, no mcp-remote, no Node.js required - just HTTP + token.
    """
    
    def __init__(self):
        """Initialize GitLab MCP client."""
        self.mcp_available = False
        self.base_url = None
        self.token = None
        
        try:
            import httpx
            
            # Get GitLab token and base URL
            gitlab_token = settings.mcp_gitlab_token or settings.gitlab_token
            gitlab_base_url = settings.gitlab_base_url or "https://gitlab.com"
            
            if not gitlab_token:
                logger.warning("GitLab token not configured for MCP")
                self.mcp_available = False
                return
            
            self.token = gitlab_token
            self.base_url = gitlab_base_url.rstrip('/')
            self.mcp_endpoint = f"{self.base_url}/api/v4/mcp"
            
            logger.info(f"GitLab MCP client initialized (endpoint: {self.mcp_endpoint})")
            logger.info("Using direct HTTP calls with token authentication (no OAuth needed)")
            self.mcp_available = True
                
        except ImportError:
            logger.warning("httpx not available for MCP client")
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
        Perform semantic code search using GitLab MCP via direct HTTP calls.
        
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
            import httpx
            
            logger.debug(f"Semantic code search via GitLab MCP: {semantic_query} in {project_id}")
            
            # Call GitLab MCP endpoint directly using JSON-RPC
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Prepare JSON-RPC request
                mcp_request = {
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "params": {
                        "name": "semantic_code_search",
                        "arguments": {
                            "project_id": project_id,
                            "semantic_query": semantic_query,
                            "directory_path": directory_path,
                            "limit": limit
                        }
                    },
                    "id": 1
                }
                
                headers = {
                    "PRIVATE-TOKEN": self.token,
                    "Content-Type": "application/json"
                }
                
                response = await client.post(
                    self.mcp_endpoint,
                    json=mcp_request,
                    headers=headers
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if "result" in result:
                        # Parse MCP response
                        content = result["result"].get("content", [])
                        results = []
                        for item in content:
                            if isinstance(item, dict) and "text" in item:
                                try:
                                    item_data = json.loads(item["text"])
                                    if isinstance(item_data, list):
                                        results.extend(item_data)
                                    else:
                                        results.append(item_data)
                                except json.JSONDecodeError:
                                    results.append({"content": item["text"]})
                        return results
                    elif "error" in result:
                        error = result["error"]
                        logger.warning(f"MCP error: {error.get('message', 'Unknown error')}")
                elif response.status_code == 403:
                    error_data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
                    if "insufficient_scope" in str(error_data):
                        logger.error(
                            "GitLab token lacks 'mcp' scope. "
                            "Create a new token with 'mcp', 'api', and 'read_api' scopes."
                        )
                    else:
                        logger.warning(f"MCP authentication failed: {response.status_code}")
                else:
                    logger.warning(f"MCP request failed: {response.status_code} - {response.text[:200]}")
            
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
        Search GitLab using MCP search function via direct HTTP calls.
        
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
            import httpx
            
            logger.debug(f"GitLab search via MCP: {search} (scope: {scope})")
            
            # Call GitLab MCP endpoint directly using JSON-RPC
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Prepare JSON-RPC request
                mcp_request = {
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "params": {
                        "name": "gitlab_search",
                        "arguments": {
                            "scope": scope,
                            "search": search,
                            "project_id": project_id,
                            "group_id": group_id,
                            "per_page": per_page
                        }
                    },
                    "id": 1
                }
                
                headers = {
                    "PRIVATE-TOKEN": self.token,
                    "Content-Type": "application/json"
                }
                
                response = await client.post(
                    self.mcp_endpoint,
                    json=mcp_request,
                    headers=headers
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if "result" in result:
                        # Parse MCP response
                        content = result["result"].get("content", [])
                        results = []
                        for item in content:
                            if isinstance(item, dict) and "text" in item:
                                try:
                                    item_data = json.loads(item["text"])
                                    if isinstance(item_data, list):
                                        results.extend(item_data)
                                    else:
                                        results.append(item_data)
                                except json.JSONDecodeError:
                                    results.append({"content": item["text"]})
                        return results
                    elif "error" in result:
                        error = result["error"]
                        logger.warning(f"MCP error: {error.get('message', 'Unknown error')}")
                elif response.status_code == 403:
                    error_data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
                    if "insufficient_scope" in str(error_data):
                        logger.error(
                            "GitLab token lacks 'mcp' scope. "
                            "Create a new token with 'mcp', 'api', and 'read_api' scopes."
                        )
                    else:
                        logger.warning(f"MCP authentication failed: {response.status_code}")
                else:
                    logger.warning(f"MCP request failed: {response.status_code} - {response.text[:200]}")
            
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
        
        if not self.mcp_client:
            logger.warning("GitLab MCP client not available for fallback extraction")
            return []
        
        logger.info(f"Starting GitLab MCP fallback extraction for {story_key}")
        
        try:
            # 1. Use AI to identify which services might be relevant
            service_queries = await self._generate_service_search_queries(story_text, story_key)
            
            # 2. Search across GitLab group for relevant code using MCP semantic search
            # Search for: API endpoints, route definitions, OpenAPI specs related to the story
            search_results = await self._search_codebase_via_mcp(
                story_key=story_key,
                story_text=story_text,
                service_queries=service_queries
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
        Generate search queries to find relevant services and code.
        
        Args:
            story_text: Story text
            story_key: Story key
            
        Returns:
            List of search query strings
        """
        queries = []
        
        # Extract key terms from story
        # Look for service names, feature names, API-related terms
        feature_terms = []
        
        # Common patterns: "create endpoint", "new API", "add route", etc.
        if re.search(r'(create|add|new|implement).*endpoint', story_text, re.IGNORECASE):
            feature_terms.append("API endpoint")
        if re.search(r'(route|router|path)', story_text, re.IGNORECASE):
            feature_terms.append("route definition")
        if re.search(r'(openapi|swagger|api.*spec)', story_text, re.IGNORECASE):
            feature_terms.append("OpenAPI specification")
        
        # Build queries
        base_query = f"{story_key} API endpoint route"
        queries.append(base_query)
        
        if feature_terms:
            for term in feature_terms:
                queries.append(f"{story_key} {term}")
        
        # Add story-specific query
        # Extract first 50 words of story for context
        story_snippet = ' '.join(story_text.split()[:50])
        queries.append(f"{story_snippet} API endpoint")
        
        return queries
    
    async def _search_codebase_via_mcp(
        self,
        story_key: str,
        story_text: str,
        service_queries: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Search GitLab codebase using MCP semantic search.
        
        Args:
            story_key: Story key
            story_text: Story text
            service_queries: List of search queries
            
        Returns:
            List of search results with code snippets
        """
        all_results = []
        
        # Search in the configured GitLab group
        group_id = settings.gitlab_group_path  # e.g., "plainid/srv"
        
        # Try different search strategies
        search_queries = [
            f"API endpoint for {story_key}",
            f"route definition {story_key}",
            f"OpenAPI specification {story_key}",
            f"REST API {story_key}",
        ]
        
        # Add story-specific queries
        search_queries.extend(service_queries)
        
        for query in search_queries[:5]:  # Limit to 5 queries
            try:
                # Use MCP semantic code search across the group
                # This would search all projects in the group
                results = await self.mcp_client.semantic_code_search(
                    project_id=group_id,
                    semantic_query=query,
                    limit=10
                )
                
                # Also try regular GitLab search for blobs (code files)
                blob_results = await self.mcp_client.gitlab_search(
                    scope="blobs",
                    search=query,
                    group_id=group_id,
                    per_page=10
                )
                
                all_results.extend(results)
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
        
        Args:
            search_results: List of search result dictionaries
            
        Returns:
            List of APISpec objects
        """
        api_specs = []
        seen_endpoints = set()
        
        for result in search_results:
            try:
                # Get code content from result
                content = result.get('content') or result.get('text') or result.get('code', '')
                file_path = result.get('file_path') or result.get('path') or 'unknown'
                
                if not content:
                    continue
                
                # Determine file type and parse accordingly
                if any(ext in file_path.lower() for ext in ['.yaml', '.yml', '.json']):
                    # OpenAPI file
                    specs = self._parse_openapi_file(content, file_path)
                elif any(ext in file_path.lower() for ext in ['.py', '.ts', '.js']):
                    # Route definition file
                    specs = self._parse_route_file(content, file_path)
                else:
                    # Try to parse as route file anyway
                    specs = self._parse_route_file(content, file_path)
                
                # Add unique endpoints
                for spec in specs:
                    endpoint_key = f"{spec.endpoint_path}:{','.join(sorted(spec.http_methods))}"
                    if endpoint_key not in seen_endpoints:
                        api_specs.append(spec)
                        seen_endpoints.add(endpoint_key)
                        logger.debug(f"Extracted endpoint: {spec.http_methods} {spec.endpoint_path} from {file_path}")
                
            except Exception as e:
                logger.warning(f"Error extracting endpoints from search result: {e}")
                continue
        
        return api_specs
    
    def _parse_openapi_file(
        self,
        content: str,
        file_path: str
    ) -> List[APISpec]:
        """
        Parse OpenAPI YAML/JSON file and extract endpoints.
        
        Args:
            content: File content
            file_path: File path for context
            
        Returns:
            List of APISpec objects
        """
        specs = []
        
        try:
            # Parse YAML or JSON
            if content.strip().startswith('{'):
                spec = json.loads(content)
            else:
                spec = yaml.safe_load(content)
            
            if not spec or 'paths' not in spec:
                return specs
            
            # Extract all paths and methods
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
                
                # Extract parameters
                parameters = []
                for method in http_methods:
                    method_spec = methods.get(method.lower(), {})
                    params = method_spec.get('parameters', [])
                    for param in params:
                        param_name = param.get('name', '')
                        param_in = param.get('in', '')
                        if param_name:
                            parameters.append(f"{param_name} ({param_in})")
                
                # Extract request schema
                request_schema = None
                for method in http_methods:
                    method_spec = methods.get(method.lower(), {})
                    request_body = method_spec.get('requestBody', {})
                    if request_body:
                        content_types = request_body.get('content', {})
                        if content_types:
                            for content_type, schema_info in content_types.items():
                                schema = schema_info.get('schema', {})
                                if schema:
                                    request_schema = json.dumps(schema, indent=2)[:500]
                                    break
                        if request_schema:
                            break
                
                # Extract response schema
                response_schema = None
                for method in http_methods:
                    method_spec = methods.get(method.lower(), {})
                    responses = method_spec.get('responses', {})
                    if responses:
                        status_codes = []
                        for status, response_info in list(responses.items())[:3]:
                            description = response_info.get('description', '')
                            status_codes.append(f"{status}: {description}")
                        if status_codes:
                            response_schema = "; ".join(status_codes)
                            break
                
                # Extract service name from file path
                service_name = file_path.split('/')[0] if '/' in file_path else 'unknown'
                
                specs.append(APISpec(
                    endpoint_path=path,
                    http_methods=http_methods,
                    parameters=list(set(parameters)) if parameters else [],
                    request_schema=request_schema,
                    response_schema=response_schema,
                    service_name=service_name
                ))
        
        except (yaml.YAMLError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to parse OpenAPI file: {e}")
        except Exception as e:
            logger.warning(f"Error parsing OpenAPI file: {e}")
        
        return specs
    
    def _parse_route_file(
        self,
        content: str,
        file_path: str
    ) -> List[APISpec]:
        """
        Parse route definition file (FastAPI, Flask, Express, etc.) and extract endpoints.
        
        Args:
            content: File content
            file_path: File path for context
            
        Returns:
            List of APISpec objects
        """
        specs = []
        
        # FastAPI patterns: @router.get("/path"), @router.post("/path"), etc.
        fastapi_pattern = r'@router\.(get|post|put|patch|delete|head|options)\s*\(\s*["\']([^"\']+)["\']'
        
        # Flask patterns: @app.route("/path", methods=["GET"]), @app.route("/path")
        flask_pattern = r'@app\.route\s*\(\s*["\']([^"\']+)["\'][^)]*\)'
        flask_methods_pattern = r'methods\s*=\s*\[([^\]]+)\]'
        
        # Express patterns: router.get("/path"), app.post("/path"), etc.
        express_pattern = r'(?:router|app)\.(get|post|put|patch|delete|head|options)\s*\(\s*["\']([^"\']+)["\']'
        
        # Extract service name from file path
        service_name = file_path.split('/')[0] if '/' in file_path else 'unknown'
        
        # Find all FastAPI routes
        for match in re.finditer(fastapi_pattern, content, re.IGNORECASE):
            method = match.group(1).upper()
            path = match.group(2)
            if not path.startswith('/'):
                path = '/' + path
            
            # Extract path parameters
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
        
        # Find all Flask routes
        for match in re.finditer(flask_pattern, content, re.IGNORECASE):
            path = match.group(1)
            if not path.startswith('/'):
                path = '/' + path
            
            # Extract methods
            methods = ['GET']  # Default
            methods_match = re.search(flask_methods_pattern, match.group(0), re.IGNORECASE)
            if methods_match:
                methods_str = methods_match.group(1)
                methods = [m.strip().strip('"\'') for m in methods_str.split(',')]
                methods = [m.upper() for m in methods if m]
            
            # Extract path parameters
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
        
        # Find all Express routes
        for match in re.finditer(express_pattern, content, re.IGNORECASE):
            method = match.group(1).upper()
            path = match.group(2)
            if not path.startswith('/'):
                path = '/' + path
            
            # Extract path parameters
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
