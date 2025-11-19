"""
GitLab fallback endpoint extractor using MCP for discovering endpoints from codebase.
Used when no endpoints are found via normal Swagger/RAG extraction.

Uses mcp-remote with OAuth for secure authentication to GitLab MCP.
"""

import re
import json
import yaml
import subprocess
import os
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
    
    Authenticates through browser OAuth login, credentials cached locally.
    Works in Docker and Kubernetes without browser access (uses cached OAuth).
    """
    
    def __init__(self):
        """Initialize GitLab MCP client with mcp-remote."""
        self.mcp_available = False
        self.mcp_process = None
        self.oauth_cache_dir = None
        
        try:
            # Set up OAuth cache directory
            self.oauth_cache_dir = Path.home() / ".mcp-auth"
            self.oauth_cache_dir.mkdir(parents=True, exist_ok=True)
            
            logger.info(f"GitLab MCP client initialized (OAuth cache: {self.oauth_cache_dir})")
            logger.info("Using mcp-remote with OAuth authentication")
            
            # Check if mcp-remote is available
            try:
                result = subprocess.run(
                    ["which", "mcp-remote"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    logger.debug(f"mcp-remote found at: {result.stdout.strip()}")
                    self.mcp_available = True
                else:
                    logger.warning("mcp-remote not found in PATH - will try npx")
                    # Try npx as fallback
                    result = subprocess.run(
                        ["which", "npx"],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if result.returncode == 0:
                        logger.debug("npx found - can use 'npx mcp-remote'")
                        self.mcp_available = True
                    else:
                        logger.warning("Neither mcp-remote nor npx found")
                        self.mcp_available = False
            except Exception as e:
                logger.warning(f"Failed to check for mcp-remote: {e}")
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
            logger.debug(f"Semantic code search via GitLab MCP: {semantic_query} in {project_id}")
            
            # Use mcp-remote to call GitLab MCP
            # This will use cached OAuth credentials if available
            cmd = [
                "npx", "-y", "mcp-remote",
                "https://gitlab.com/api/v4/mcp",
                "--",
                "semantic_code_search",
                json.dumps({
                    "project_id": project_id,
                    "semantic_query": semantic_query,
                    "directory_path": directory_path,
                    "limit": limit
                })
            ]
            
            logger.debug(f"Running: {' '.join(cmd[:4])} ...")
            
            result = await asyncio.to_thread(
                subprocess.run,
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(self.oauth_cache_dir)
            )
            
            if result.returncode == 0:
                try:
                    output = json.loads(result.stdout)
                    if isinstance(output, list):
                        return output
                    elif isinstance(output, dict) and "result" in output:
                        return output.get("result", [])
                    return []
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse MCP response: {result.stdout[:200]}")
                    return []
            else:
                if "authentication" in result.stderr.lower() or "oauth" in result.stderr.lower():
                    logger.warning("MCP authentication failed - OAuth credentials may have expired")
                    logger.info("Please re-authenticate by visiting: https://gitlab.com/-/user_settings/personal_access_tokens")
                else:
                    logger.warning(f"MCP request failed: {result.stderr[:200]}")
                return []
        
        except subprocess.TimeoutExpired:
            logger.warning("MCP semantic search timed out")
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
            logger.debug(f"GitLab search via MCP: {search} (scope: {scope})")
            
            cmd = [
                "npx", "-y", "mcp-remote",
                "https://gitlab.com/api/v4/mcp",
                "--",
                "gitlab_search",
                json.dumps({
                    "scope": scope,
                    "search": search,
                    "project_id": project_id,
                    "group_id": group_id,
                    "per_page": per_page
                })
            ]
            
            result = await asyncio.to_thread(
                subprocess.run,
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(self.oauth_cache_dir)
            )
            
            if result.returncode == 0:
                try:
                    output = json.loads(result.stdout)
                    if isinstance(output, list):
                        return output
                    elif isinstance(output, dict) and "result" in output:
                        return output.get("result", [])
                    return []
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse MCP response: {result.stdout[:200]}")
                    return []
            else:
                if "authentication" in result.stderr.lower() or "oauth" in result.stderr.lower():
                    logger.warning("MCP authentication failed - OAuth credentials may have expired")
                else:
                    logger.warning(f"MCP request failed: {result.stderr[:200]}")
                return []
        
        except subprocess.TimeoutExpired:
            logger.warning("MCP GitLab search timed out")
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
        
        if not self.mcp_client or not self.mcp_client.mcp_available:
            logger.warning("GitLab MCP client not available for fallback extraction")
            return []
        
        logger.info(f"Starting GitLab MCP fallback extraction for {story_key}")
        
        try:
            # 1. Use AI to identify which services might be relevant
            service_queries = await self._generate_service_search_queries(story_text, story_key)
            
            # 2. Search across GitLab group for relevant code using MCP semantic search
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
        feature_terms = []
        
        # Common patterns
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
        
        group_id = settings.gitlab_group_path
        
        # Try different search strategies
        search_queries = [
            f"API endpoint for {story_key}",
            f"route definition {story_key}",
            f"OpenAPI specification {story_key}",
            f"REST API {story_key}",
        ]
        
        search_queries.extend(service_queries)
        
        for query in search_queries[:5]:  # Limit to 5 queries
            try:
                # Use MCP semantic code search
                results = await self.mcp_client.semantic_code_search(
                    project_id=group_id,
                    semantic_query=query,
                    limit=10
                )
                
                # Also try regular GitLab search
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
                    specs = self._parse_openapi_file(content, file_path)
                elif any(ext in file_path.lower() for ext in ['.py', '.ts', '.js']):
                    specs = self._parse_route_file(content, file_path)
                else:
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
                
                # Extract parameters and schemas
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
    
    def _parse_route_file(
        self,
        content: str,
        file_path: str
    ) -> List[APISpec]:
        """Parse route definition file (FastAPI, Flask, Express, etc.)."""
        specs = []
        
        # FastAPI patterns
        fastapi_pattern = r'@router\.(get|post|put|patch|delete|head|options)\s*\(\s*["\']([^"\']+)["\']'
        
        # Flask patterns
        flask_pattern = r'@app\.route\s*\(\s*["\']([^"\']+)["\'][^)]*\)'
        flask_methods_pattern = r'methods\s*=\s*\[([^\]]+)\]'
        
        # Express patterns
        express_pattern = r'(?:router|app)\.(get|post|put|patch|delete|head|options)\s*\(\s*["\']([^"\']+)["\']'
        
        service_name = file_path.split('/')[0] if '/' in file_path else 'unknown'
        
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
