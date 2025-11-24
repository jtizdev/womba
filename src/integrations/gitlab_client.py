"""
GitLab API client for fetching projects and files.
"""

from typing import List, Dict, Optional, Any
from loguru import logger

try:
    import gitlab
    from gitlab.exceptions import GitlabError, GitlabGetError
except ImportError:
    gitlab = None
    GitlabError = Exception
    GitlabGetError = Exception

from src.config.settings import settings


class GitLabClient:
    """
    Client for interacting with GitLab API.
    Supports listing group projects and fetching file contents.
    """
    
    def __init__(self, token: Optional[str] = None, base_url: Optional[str] = None):
        """
        Initialize GitLab client.
        
        Args:
            token: GitLab personal access token (defaults to settings)
            base_url: GitLab base URL (defaults to settings)
        """
        if gitlab is None:
            raise ImportError(
                "python-gitlab is required for GitLab integration. "
                "Install it with: pip install python-gitlab"
            )
        
        self.token = token or settings.gitlab_token
        self.base_url = base_url or settings.gitlab_base_url
        
        if not self.token:
            raise ValueError("GitLab token is required. Set GITLAB_TOKEN in environment or config.")
        
        # Initialize GitLab client
        self.gl = gitlab.Gitlab(self.base_url, private_token=self.token)
        
        try:
            self.gl.auth()
            logger.info(f"Successfully authenticated with GitLab at {self.base_url}")
        except GitlabError as e:
            logger.error(f"Failed to authenticate with GitLab: {e}")
            raise
    
    def list_group_projects(self, group_path: str) -> List[Dict[str, Any]]:
        """
        List all projects in a GitLab group.
        
        Args:
            group_path: Full path to the group (e.g., "your-group/your-services")
            
        Returns:
            List of project dictionaries with id, name, path, web_url
        """
        try:
            logger.info(f"Fetching projects from GitLab group: {group_path}")
            
            # Get the group
            group = self.gl.groups.get(group_path)
            
            # Get all projects in the group (including subgroups)
            projects = group.projects.list(all=True, include_subgroups=True)
            
            project_list = []
            for project in projects:
                project_list.append({
                    'id': project.id,
                    'name': project.name,
                    'path': project.path,
                    'path_with_namespace': project.path_with_namespace,
                    'web_url': project.web_url,
                    'default_branch': getattr(project, 'default_branch', 'main')
                })
            
            logger.info(f"Found {len(project_list)} projects in group {group_path}")
            return project_list
            
        except GitlabGetError as e:
            logger.error(f"Group not found: {group_path} - {e}")
            return []
        except GitlabError as e:
            logger.error(f"Failed to list projects in group {group_path}: {e}")
            return []
    
    def get_file_content(
        self, 
        project_id: int, 
        file_path: str, 
        ref: str = 'main'
    ) -> Optional[str]:
        """
        Get file content from a GitLab project.
        
        Args:
            project_id: GitLab project ID
            file_path: Path to file in repository
            ref: Branch/tag/commit ref (default: 'main')
            
        Returns:
            File content as string, or None if not found
        """
        try:
            project = self.gl.projects.get(project_id)
            
            # Get file
            file_data = project.files.get(file_path=file_path, ref=ref)
            
            # Decode content (it's base64 encoded)
            content = file_data.decode().decode('utf-8')
            
            logger.debug(f"Fetched file {file_path} from project {project_id} (ref: {ref})")
            return content
            
        except GitlabGetError:
            logger.debug(f"File not found: {file_path} in project {project_id} (ref: {ref})")
            return None
        except GitlabError as e:
            logger.error(f"Failed to fetch file {file_path} from project {project_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching file {file_path}: {e}")
            return None
    
    def list_directory(
        self,
        project_id: int,
        path: str = '',
        ref: str = 'main'
    ) -> List[Dict[str, Any]]:
        """
        List contents of a directory in a GitLab project.
        
        Args:
            project_id: GitLab project ID
            path: Directory path (empty string for root)
            ref: Branch/tag/commit ref (default: 'main')
            
        Returns:
            List of file/directory dictionaries with name, type, path
        """
        try:
            project = self.gl.projects.get(project_id)
            
            # List repository tree
            items = project.repository_tree(path=path, ref=ref, all=True)
            
            result = []
            for item in items:
                result.append({
                    'name': item['name'],
                    'type': item['type'],  # 'blob' (file) or 'tree' (directory)
                    'path': item['path'],
                    'mode': item['mode']
                })
            
            logger.debug(f"Listed {len(result)} items in {path or 'root'} of project {project_id}")
            return result
            
        except GitlabGetError:
            logger.debug(f"Directory not found: {path} in project {project_id} (ref: {ref})")
            return []
        except GitlabError as e:
            logger.error(f"Failed to list directory {path} in project {project_id}: {e}")
            return []
    
    def check_file_exists(
        self,
        project_id: int,
        file_path: str,
        ref: str = 'main'
    ) -> bool:
        """
        Check if a file exists in a GitLab project.
        
        Args:
            project_id: GitLab project ID
            file_path: Path to file in repository
            ref: Branch/tag/commit ref (default: 'main')
            
        Returns:
            True if file exists, False otherwise
        """
        try:
            project = self.gl.projects.get(project_id)
            project.files.get(file_path=file_path, ref=ref)
            return True
        except GitlabGetError:
            return False
        except GitlabError:
            return False
    
    def list_branches(
        self,
        project_id: int,
        search_pattern: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        List branches in a GitLab project, optionally filtered by search pattern.
        
        Args:
            project_id: GitLab project ID
            search_pattern: Optional pattern to filter branch names (e.g., "PROJ-12345")
            
        Returns:
            List of branch dictionaries with name, commit info
        """
        try:
            project = self.gl.projects.get(project_id)
            branches = project.branches.list(all=True)
            
            branch_list = []
            for branch in branches:
                branch_name = branch.name
                
                # Filter by pattern if provided
                if search_pattern and search_pattern.lower() not in branch_name.lower():
                    continue
                
                branch_list.append({
                    'name': branch_name,
                    'default': branch.default if hasattr(branch, 'default') else False,
                    'protected': branch.protected if hasattr(branch, 'protected') else False,
                    'commit': {
                        'id': branch.commit.get('id') if hasattr(branch, 'commit') else None,
                        'message': branch.commit.get('message') if hasattr(branch, 'commit') else None
                    } if hasattr(branch, 'commit') else None
                })
            
            logger.debug(f"Found {len(branch_list)} branches in project {project_id} (pattern: {search_pattern})")
            return branch_list
            
        except GitlabError as e:
            logger.error(f"Failed to list branches for project {project_id}: {e}")
            return []
    
    def search_code(
        self,
        project_id: int,
        search_query: str,
        ref: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for code in a GitLab project using GitLab's search API.
        
        Args:
            project_id: GitLab project ID
            search_query: Search query (e.g., "@router.get" or "openapi")
            ref: Optional branch/tag to search in (defaults to default branch)
            
        Returns:
            List of search results with file path, content snippets, etc.
        """
        try:
            project = self.gl.projects.get(project_id)
            
            # Use GitLab's search API
            # Note: GitLab search API might have limitations, so we'll use repository search
            results = []
            
            # Try to use the project's search endpoint
            # GitLab python library doesn't have direct search, so we'll use a workaround
            # by searching through repository tree for relevant files
            logger.debug(f"Searching code in project {project_id} for: {search_query}")
            
            # For now, return empty - actual search will be done by scanning files
            # This method is a placeholder for future GitLab API search integration
            return results
            
        except GitlabError as e:
            logger.error(f"Failed to search code in project {project_id}: {e}")
            return []

