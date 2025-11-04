"""
Dynamic API documentation client - fetches customer-specific API docs.

NOTE: This class is currently not in use. PlainIDDocCrawler (src/external/plainid_crawler.py)
is the preferred implementation for fetching API documentation. This class is kept for
potential future use with non-PlainID customers.
"""

from typing import Dict, List, Optional
import httpx
from loguru import logger

from src.config.settings import settings


class APIDocsClient:
    """
    Fetches API documentation for ANY customer, not just PlainID.
    
    Supports multiple doc formats:
    - OpenAPI/Swagger (JSON/YAML)
    - Postman Collections
    - Readme.io / GitBook
    - Custom documentation sites
    """
    
    def __init__(self):
        self.doc_cache: Dict[str, str] = {}
    
    async def get_api_docs_for_project(self, project_key: str) -> Optional[str]:
        """
        Dynamically fetch API docs based on project configuration.
        
        Strategy:
        1. Check project settings for API doc URL
        2. Try common OpenAPI paths
        3. Check Confluence for "API Documentation" pages
        4. Fall back to Jira description links
        
        Args:
            project_key: Jira project key (e.g., "PLAT")
            
        Returns:
            API documentation as text, or None if not found
        """
        # Check cache first
        if project_key in self.doc_cache:
            logger.info(f"Using cached API docs for {project_key}")
            return self.doc_cache[project_key]
        
        logger.info(f"Fetching API documentation for project: {project_key}")
        
        # Strategy 1: Check if customer provided API doc URL in settings
        api_doc_url = self._get_api_doc_url_from_settings(project_key)
        if api_doc_url:
            docs = await self._fetch_from_url(api_doc_url)
            if docs:
                self.doc_cache[project_key] = docs
                return docs
        
        # Strategy 2: Try to find OpenAPI/Swagger spec
        docs = await self._try_openapi_discovery(project_key)
        if docs:
            self.doc_cache[project_key] = docs
            return docs
        
        # Strategy 3: Search Confluence for API docs
        docs = await self._search_confluence_for_api_docs(project_key)
        if docs:
            self.doc_cache[project_key] = docs
            return docs
        
        logger.warning(f"No API documentation found for project {project_key}")
        return None
    
    def _get_api_doc_url_from_settings(self, project_key: str) -> Optional[str]:
        """
        Check if customer configured API doc URL in settings/env.
        
        Example .env:
        API_DOCS_URL=https://docs.mycompany.com/api
        API_DOCS_TYPE=openapi  # or 'postman', 'readme'
        """
        # For PlainID specifically (temporary)
        if project_key == "PLAT":
            return "https://docs.plainid.io/apidocs/policy-management-apis"
        
        # Check environment variable for other customers
        api_docs_url = getattr(settings, 'api_docs_url', None)
        return api_docs_url
    
    async def _fetch_from_url(self, url: str) -> Optional[str]:
        """
        Fetch API documentation from a URL.
        
        Supports:
        - HTML documentation pages
        - OpenAPI JSON/YAML
        - Markdown files
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                
                content_type = response.headers.get('content-type', '')
                
                if 'json' in content_type:
                    # OpenAPI JSON
                    data = response.json()
                    return self._format_openapi_spec(data)
                elif 'yaml' in content_type or 'yml' in url:
                    # OpenAPI YAML
                    import yaml
                    data = yaml.safe_load(response.text)
                    return self._format_openapi_spec(data)
                elif 'html' in content_type:
                    # HTML page - extract text
                    return self._extract_text_from_html(response.text)
                else:
                    # Markdown or plain text
                    return response.text[:10000]  # Limit to 10k chars
                    
        except Exception as e:
            logger.error(f"Failed to fetch API docs from {url}: {e}")
            return None
    
    async def _try_openapi_discovery(self, project_key: str) -> Optional[str]:
        """
        Try common OpenAPI/Swagger paths.
        
        Common paths:
        - /api/docs
        - /swagger.json
        - /openapi.json
        - /api-docs
        """
        if not settings.atlassian_base_url:
            return None
        
        # Extract base domain from Atlassian URL
        base_domain = settings.atlassian_base_url.split('.atlassian.net')[0]
        if '://' in base_domain:
            base_domain = base_domain.split('://')[1]
        
        # Try common API doc URLs
        potential_urls = [
            f"https://api.{base_domain}.com/docs",
            f"https://api.{base_domain}.com/swagger.json",
            f"https://api.{base_domain}.com/openapi.json",
            f"https://{base_domain}.com/api/docs",
        ]
        
        for url in potential_urls:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(url)
                    if response.status_code == 200:
                        logger.info(f"Found API docs at: {url}")
                        return await self._fetch_from_url(url)
            except:
                continue
        
        return None
    
    async def _search_confluence_for_api_docs(self, project_key: str) -> Optional[str]:
        """
        Search Confluence for API documentation pages.
        
        Searches for pages with titles like:
        - "API Documentation"
        - "REST API"
        - "Management API"
        """
        try:
            from src.aggregator.confluence_client import ConfluenceClient
            
            confluence = ConfluenceClient()
            
            # Search for API documentation pages
            search_terms = [
                f"title ~ 'API Documentation' AND space = {project_key}",
                f"title ~ 'REST API' AND space = {project_key}",
                f"title ~ 'Management API'",
            ]
            
            for term in search_terms:
                pages = await confluence.search_pages(term)
                if pages:
                    # Get the first page
                    page_id = pages[0].get('id')
                    page = await confluence.get_page(page_id)
                    if page:
                        logger.info(f"Found API docs in Confluence: {page.get('title')}")
                        return page.get('body', {}).get('storage', {}).get('value', '')[:10000]
            
        except Exception as e:
            logger.warning(f"Failed to search Confluence for API docs: {e}")
        
        return None
    
    def _format_openapi_spec(self, spec: Dict) -> str:
        """
        Format OpenAPI spec into readable text for AI.
        
        Extracts:
        - Available endpoints
        - HTTP methods
        - Parameters
        - Response schemas
        """
        formatted = []
        
        # Add API info
        if 'info' in spec:
            formatted.append(f"API: {spec['info'].get('title', 'Unknown')}")
            formatted.append(f"Version: {spec['info'].get('version', 'Unknown')}")
            formatted.append("")
        
        # Add endpoints
        if 'paths' in spec:
            formatted.append("Available Endpoints:")
            formatted.append("")
            
            for path, methods in spec['paths'].items():
                for method, details in methods.items():
                    if method in ['get', 'post', 'put', 'delete', 'patch']:
                        summary = details.get('summary', 'No description')
                        formatted.append(f"  {method.upper()} {path}")
                        formatted.append(f"    {summary}")
                        
                        # Add parameters if present
                        if 'parameters' in details:
                            params = [p.get('name') for p in details['parameters']]
                            formatted.append(f"    Parameters: {', '.join(params)}")
                        
                        formatted.append("")
        
        return '\n'.join(formatted)
    
    def _extract_text_from_html(self, html: str) -> str:
        """
        Extract plain text from HTML documentation page.
        
        Uses BeautifulSoup if available, falls back to regex.
        """
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()
            
            # Get text
            text = soup.get_text()
            
            # Clean up whitespace
            lines = (line.strip() for line in text.splitlines())
            text = '\n'.join(line for line in lines if line)
            
            return text[:10000]  # Limit to 10k chars
            
        except ImportError:
            # BeautifulSoup not installed, use simple regex
            import re
            text = re.sub(r'<[^>]+>', '', html)
            text = re.sub(r'\s+', ' ', text)
            return text[:10000]

