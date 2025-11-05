"""
GitLab Swagger/OpenAPI fetcher for indexing API documentation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional
from loguru import logger

from src.integrations.gitlab_client import GitLabClient
from src.config.settings import settings


@dataclass
class SwaggerDocument:
    """Swagger/OpenAPI document from GitLab."""
    
    service_name: str
    file_path: str
    content: str
    project_url: str
    branch: str
    project_id: int


class GitLabSwaggerFetcher:
    """
    Fetches Swagger/OpenAPI YAML files from GitLab services.
    Discovers all projects in a group and fetches their swagger docs.
    """
    
    def __init__(
        self,
        gitlab_client: Optional[GitLabClient] = None,
        group_path: Optional[str] = None,
        branch: str = 'main'
    ):
        """
        Initialize GitLab Swagger fetcher.
        
        Args:
            gitlab_client: GitLab client (creates new if not provided)
            group_path: GitLab group path (defaults to settings)
            branch: Branch to fetch from (default: 'main')
        """
        self.client = gitlab_client or GitLabClient()
        self.group_path = group_path or settings.gitlab_group_path
        self.branch = branch
        
        logger.info(f"Initialized GitLab Swagger fetcher for group: {self.group_path}")
    
    def is_available(self) -> bool:
        """Check if GitLab integration is available and enabled."""
        if not settings.gitlab_swagger_enabled:
            logger.info("GitLab Swagger indexing is disabled in settings")
            return False
        
        if not settings.gitlab_token:
            logger.warning("GitLab token not configured")
            return False
        
        return True
    
    def fetch_all(self) -> List[SwaggerDocument]:
        """
        Fetch all Swagger/OpenAPI documents from services in the group.
        
        Returns:
            List of SwaggerDocument objects
        """
        if not self.is_available():
            return []
        
        logger.info(f"🚀 Starting Swagger fetch from GitLab group: {self.group_path}")
        
        # Get all projects in the group
        projects = self.client.list_group_projects(self.group_path)
        
        if not projects:
            logger.warning(f"No projects found in group: {self.group_path}")
            return []
        
        logger.info(f"Found {len(projects)} projects in group")
        
        # Fetch swagger docs from each project
        swagger_docs = []
        for project in projects:
            docs = self._fetch_project_swagger(project)
            swagger_docs.extend(docs)
        
        logger.info(f"✅ Fetched {len(swagger_docs)} Swagger documents from {len(projects)} projects")
        return swagger_docs
    
    def _fetch_project_swagger(self, project: dict) -> List[SwaggerDocument]:
        """
        Fetch Swagger/OpenAPI files from a single project.
        
        Args:
            project: Project dictionary from GitLab API
            
        Returns:
            List of SwaggerDocument objects (may be empty)
        """
        project_id = project['id']
        project_name = project['name']
        project_url = project['web_url']
        branch = project.get('default_branch', self.branch)
        
        logger.debug(f"Checking project: {project_name} (ID: {project_id})")
        
        swagger_docs = []
        
        # Check if openapi directory exists
        openapi_dir = self.client.list_directory(project_id, 'openapi', ref=branch)
        
        if not openapi_dir:
            logger.debug(f"  No openapi/ directory in {project_name}")
            return []
        
        logger.info(f"  Found openapi/ directory in {project_name}")
        
        # Look for external.yaml and internal.yaml
        yaml_files = ['external.yaml', 'internal.yaml', 'external.yml', 'internal.yml']
        
        for yaml_file in yaml_files:
            file_path = f"openapi/{yaml_file}"
            content = self.client.get_file_content(project_id, file_path, ref=branch)
            
            if content:
                logger.info(f"  ✅ Fetched {file_path} from {project_name}")
                swagger_docs.append(SwaggerDocument(
                    service_name=project_name,
                    file_path=file_path,
                    content=content,
                    project_url=project_url,
                    branch=branch,
                    project_id=project_id
                ))
            else:
                logger.debug(f"  File not found: {file_path} in {project_name}")
        
        if not swagger_docs:
            logger.debug(f"  No Swagger files found in {project_name}/openapi/")
        
        return swagger_docs
    
    def fetch_for_service(self, service_name: str) -> List[SwaggerDocument]:
        """
        Fetch Swagger docs for a specific service.
        
        Args:
            service_name: Name of the service/project
            
        Returns:
            List of SwaggerDocument objects
        """
        if not self.is_available():
            return []
        
        logger.info(f"Fetching Swagger docs for service: {service_name}")
        
        # Get all projects and filter by name
        projects = self.client.list_group_projects(self.group_path)
        matching_projects = [p for p in projects if p['name'] == service_name or p['path'] == service_name]
        
        if not matching_projects:
            logger.warning(f"Service not found: {service_name}")
            return []
        
        swagger_docs = []
        for project in matching_projects:
            docs = self._fetch_project_swagger(project)
            swagger_docs.extend(docs)
        
        return swagger_docs

