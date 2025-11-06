"""
Swagger endpoint extractor for enrichment pipeline.
Extracts relevant API endpoints from Swagger/OpenAPI docs using semantic + explicit matching.
"""

import re
import json
import yaml
from typing import List, Optional, Set
from loguru import logger

from src.ai.rag_store import RAGVectorStore
from src.models.enriched_story import APISpec
from src.config.settings import settings


class SwaggerExtractor:
    """
    Extracts relevant API endpoints from Swagger/OpenAPI documentation.
    
    Uses two strategies:
    1. Semantic search: Query swagger_docs RAG for story-related endpoints
    2. Explicit extraction: Regex scan for endpoint mentions in story text
    """
    
    def __init__(self):
        """Initialize Swagger extractor with RAG store."""
        self.rag_store = RAGVectorStore()
        self.max_apis = settings.enrichment_max_apis
    
    async def extract_endpoints(
        self,
        story_text: str,
        project_key: str,
        subtask_texts: Optional[List[str]] = None
    ) -> List[APISpec]:
        """
        Extract relevant API endpoints using semantic + explicit matching.
        
        Args:
            story_text: Combined story summary + description + AC
            project_key: Project key for filtering
            subtask_texts: Optional list of subtask descriptions
            
        Returns:
            List of APISpec objects with endpoint details
        """
        logger.info(f"Extracting API endpoints for story (max: {self.max_apis})")
        
        # Combine all text for analysis
        combined_text = story_text
        if subtask_texts:
            combined_text += "\n" + "\n".join(subtask_texts)
        
        # Strategy 1: Extract explicitly mentioned endpoints
        explicit_endpoints = self._extract_endpoints_explicit(combined_text)
        logger.debug(f"Found {len(explicit_endpoints)} explicit endpoint mentions")
        
        # Strategy 2: Semantic search for related endpoints
        semantic_matches = await self._extract_endpoints_semantic(
            story_text, 
            project_key,
            top_k=self.max_apis * 2  # Get more, then filter
        )
        logger.debug(f"Found {len(semantic_matches)} semantic endpoint matches")
        
        # Merge and deduplicate (pass combined_text for method extraction)
        api_specs = self._merge_and_build_specs(explicit_endpoints, semantic_matches, combined_text)
        
        # Limit to max_apis
        api_specs = api_specs[:self.max_apis]
        
        # Debug: Log extracted APIs
        logger.debug("=" * 80)
        logger.debug(f"SWAGGER API EXTRACTION RESULTS ({len(api_specs)} endpoints)")
        logger.debug("=" * 80)
        logger.debug(f"Explicit endpoint mentions found: {explicit_endpoints}")
        logger.debug(f"Semantic matches from RAG: {len(semantic_matches)}")
        logger.debug("\nExtracted API Specifications:")
        for i, api in enumerate(api_specs, 1):
            logger.debug(f"{i}. {' '.join(api.http_methods)} {api.endpoint_path}")
            logger.debug(f"   Service: {api.service_name}")
            if api.parameters:
                logger.debug(f"   Parameters: {', '.join(api.parameters)}")
            if api.request_schema:
                logger.debug(f"   Request: {api.request_schema[:100]}...")
            if api.response_schema:
                logger.debug(f"   Response: {api.response_schema[:100]}...")
        logger.debug("=" * 80)
        
        logger.info(f"Extracted {len(api_specs)} API specifications")
        return api_specs
    
    def _extract_endpoints_explicit(self, text: str) -> Set[str]:
        """
        Extract explicitly mentioned API endpoint paths from text.
        
        Args:
            text: Text to scan
            
        Returns:
            Set of endpoint paths found
        """
        endpoints = set()
        
        # Pattern 1: Method + path (GET /path, POST /path, etc.)
        # This catches PlainID endpoints like "GET policy-mgmt/policies" or "GET /policy-mgmt/policies"
        method_pattern = r'(GET|POST|PUT|PATCH|DELETE)\s+(/?[a-zA-Z][a-zA-Z0-9_/\-{}.?&=%\[\]]+)'
        method_matches = re.findall(method_pattern, text, re.IGNORECASE)
        for method, path in method_matches:
            # Normalize path (ensure it starts with /)
            if not path.startswith('/'):
                path = '/' + path
            # Clean up query params and fragments for deduplication
            clean_path = path.split('?')[0].split('#')[0]
            if clean_path.count('/') >= 2:  # At least /segment/segment
                endpoints.add(clean_path)
        
        # Pattern 2: /api/... style paths (for traditional API paths)
        api_pattern = r'/api/[a-zA-Z0-9/_\-{}.]+[a-zA-Z0-9}]'
        matches = re.findall(api_pattern, text)
        endpoints.update(matches)
        
        return endpoints
    
    async def _extract_endpoints_semantic(
        self,
        query_text: str,
        project_key: str,
        top_k: int = 10
    ) -> List[dict]:
        """
        Semantically search swagger docs for relevant endpoints.
        
        Args:
            query_text: Story text for semantic matching
            project_key: Project key for filtering
            top_k: Number of results to retrieve
            
        Returns:
            List of swagger doc matches with metadata
        """
        try:
            # Query swagger docs collection
            results = await self.rag_store.retrieve_similar(
                collection_name=self.rag_store.SWAGGER_DOCS_COLLECTION,
                query_text=query_text,
                top_k=top_k,
                metadata_filter={"project_key": project_key}
            )
            
            return results
            
        except Exception as e:
            logger.warning(f"Swagger semantic search failed: {e}")
            return []
    
    def _merge_and_build_specs(
        self,
        explicit_paths: Set[str],
        semantic_matches: List[dict],
        text: str
    ) -> List[APISpec]:
        """
        Merge explicit and semantic matches, build APISpec objects.
        
        Args:
            explicit_paths: Explicitly mentioned endpoint paths
            semantic_matches: Swagger docs from semantic search
            text: Original text to extract methods from
            
        Returns:
            List of APISpec objects
        """
        specs = []
        seen_paths = set()
        
        # Build map of paths to methods from original text
        path_to_methods = {}
        method_pattern = r'(GET|POST|PUT|PATCH|DELETE)\s+(/?[a-zA-Z][a-zA-Z0-9_/\-{}.?&=%\[\]]+)'
        for method, path in re.findall(method_pattern, text, re.IGNORECASE):
            if not path.startswith('/'):
                path = '/' + path
            clean_path = path.split('?')[0].split('#')[0]
            if clean_path not in path_to_methods:
                path_to_methods[clean_path] = []
            path_to_methods[clean_path].append(method.upper())
        
        # Process semantic matches first (have full swagger data)
        for match in semantic_matches:
            try:
                doc_text = match.get('document', '')
                metadata = match.get('metadata', {})
                
                # Parse swagger content from document
                api_spec = self._parse_swagger_doc(doc_text, metadata)
                
                if api_spec and api_spec.endpoint_path not in seen_paths:
                    # Prioritize if explicitly mentioned
                    if any(explicit in api_spec.endpoint_path for explicit in explicit_paths):
                        specs.insert(0, api_spec)  # Put at front
                    else:
                        specs.append(api_spec)
                    
                    seen_paths.add(api_spec.endpoint_path)
                    
            except Exception as e:
                logger.debug(f"Failed to parse swagger match: {e}")
                continue
        
        # Add explicit paths that weren't found in semantic matches
        for path in explicit_paths:
            if path not in seen_paths:
                # Get methods from text or default to common ones
                methods = path_to_methods.get(path, ["GET"])
                specs.append(APISpec(
                    endpoint_path=path,
                    http_methods=methods,
                    service_name="Mentioned in story"
                ))
                seen_paths.add(path)
        
        return specs
    
    def _parse_swagger_doc(self, doc_text: str, metadata: dict) -> Optional[APISpec]:
        """
        Parse swagger document text and extract APISpec.
        
        Args:
            doc_text: Swagger document text from RAG
            metadata: Document metadata
            
        Returns:
            APISpec if successfully parsed, None otherwise
        """
        try:
            # Extract endpoint path from document
            path_match = re.search(r'(GET|POST|PUT|PATCH|DELETE)\s+(/[^\s\n]+)', doc_text)
            if not path_match:
                return None
            
            method = path_match.group(1)
            endpoint_path = path_match.group(2)
            
            # Extract all methods for this endpoint
            methods = re.findall(r'(GET|POST|PUT|PATCH|DELETE)\s+' + re.escape(endpoint_path), doc_text)
            methods = list(set(methods)) if methods else [method]
            
            # Extract parameters
            param_section = re.search(r'Parameters?:\s*\n(.*?)(?:\n\n|\n[A-Z]|$)', doc_text, re.DOTALL)
            parameters = []
            if param_section:
                param_lines = param_section.group(1).split('\n')
                for line in param_lines:
                    param_match = re.search(r'-\s+(\w+)\s*\(([^)]+)\)', line)
                    if param_match:
                        parameters.append(f"{param_match.group(1)} ({param_match.group(2)})")
            
            # Extract request body info
            request_schema = None
            request_section = re.search(r'Request Body:\s*\n(.*?)(?:\n\n|Responses?:|\n[A-Z]|$)', doc_text, re.DOTALL)
            if request_section:
                request_schema = request_section.group(1).strip()[:200]  # Limit length
            
            # Extract response info
            response_schema = None
            response_section = re.search(r'Responses?:\s*\n(.*?)(?:\n\n|\n[A-Z]|$)', doc_text, re.DOTALL)
            if response_section:
                response_text = response_section.group(1).strip()
                # Extract first few response codes
                response_codes = re.findall(r'(\d{3}):\s*([^\n]+)', response_text)
                if response_codes:
                    response_schema = "; ".join([f"{code}: {desc}" for code, desc in response_codes[:3]])
            
            # Extract auth info
            auth_section = re.search(r'Authentication:\s*\n(.*?)(?:\n\n|\n[A-Z]|$)', doc_text, re.DOTALL)
            authentication = None
            if auth_section:
                authentication = auth_section.group(1).strip()[:100]
            
            return APISpec(
                endpoint_path=endpoint_path,
                http_methods=methods,
                request_schema=request_schema,
                response_schema=response_schema,
                parameters=parameters,
                authentication=authentication,
                service_name=metadata.get('service_name', 'Unknown')
            )
            
        except Exception as e:
            logger.debug(f"Failed to parse swagger doc: {e}")
            return None

