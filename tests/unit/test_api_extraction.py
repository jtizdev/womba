"""
Unit tests for API endpoint extraction.

Tests that API endpoints are correctly extracted from story descriptions and subtasks.
"""

import pytest
from src.ai.swagger_extractor import SwaggerExtractor


def test_extract_api_from_subtask_with_get_method():
    """Test extracting API endpoint from subtask with GET method."""
    description = """
    need to create endpoint to fetch policies by application, need to work the same as existing fechPoliciesByX 
    for ruleset, action, dynamic group & condition we use
    GET policy-mgmt/dynamic-group/b8825285-6c6d-40c3-ae47-d1bb196f5339/policies
    GET policy-mgmt/policy/action/e5a38e3f-d7a0-4477-af1b-fba0ba040ab5/search?offset=0&limit=10
    """
    
    extractor = SwaggerExtractor()
    endpoints = extractor._extract_endpoints_explicit(description)
    
    # Should find both endpoints
    assert len(endpoints) >= 2, f"Should find 2 endpoints, found {len(endpoints)}"
    assert any('/policy-mgmt/dynamic-group' in ep for ep in endpoints), \
        "Should find dynamic-group endpoint"
    assert any('/policy-mgmt/policy/action' in ep for ep in endpoints), \
        "Should find policy action endpoint"


def test_extract_api_from_post_endpoint():
    """Test extracting POST endpoint with request body."""
    description = """
    Implement API endpoint for policy creation:
    POST /policy-mgmt/1.0/policies
    Request body: { "name": "string", "type": "masking", "scope": "prod" }
    Returns: 201 Created with policy ID
    """
    
    extractor = SwaggerExtractor()
    endpoints = extractor._extract_endpoints_explicit(description)
    
    assert len(endpoints) >= 1, f"Should find POST endpoint, found {len(endpoints)}"
    assert any('/policy-mgmt' in ep and 'policies' in ep for ep in endpoints), \
        f"Should find policies endpoint, got {endpoints}"


def test_extract_traditional_api_paths():
    """Test extracting traditional /api/ prefixed paths."""
    description = """
    The service exposes these endpoints:
    POST /api/v1/authorization/validate
    GET /api/v2/policies/list
    """
    
    extractor = SwaggerExtractor()
    endpoints = extractor._extract_endpoints_explicit(description)
    
    assert len(endpoints) >= 2, f"Should find 2 /api/ endpoints, found {len(endpoints)}"
    assert any('/api/v1/authorization' in ep for ep in endpoints)
    assert any('/api/v2/policies' in ep for ep in endpoints)


def test_normalize_paths_without_leading_slash():
    """Test that paths without leading slash are normalized."""
    description = "GET policy-mgmt/policies/search"
    
    extractor = SwaggerExtractor()
    endpoints = extractor._extract_endpoints_explicit(description)
    
    # Should normalize to /policy-mgmt/policies/search
    assert len(endpoints) >= 1
    endpoint = list(endpoints)[0]
    assert endpoint.startswith('/'), f"Path should be normalized with leading /, got {endpoint}"
    assert 'policy-mgmt' in endpoint


def test_filter_short_paths():
    """Test that single-segment paths are filtered out."""
    description = "GET /health and POST /status and GET /api/v1/policies/validate"
    
    extractor = SwaggerExtractor()
    endpoints = extractor._extract_endpoints_explicit(description)
    
    # Should only include /api/v1/policies/validate (multi-segment)
    # /health and /status are too short (< 2 segments)
    for ep in endpoints:
        assert ep.count('/') >= 2, f"Should filter single-segment paths, got {ep}"


@pytest.mark.asyncio
async def test_merge_builds_correct_http_methods():
    """Test that merge correctly extracts HTTP methods from text."""
    text = """
    GET /policy-mgmt/policies/search
    POST /policy-mgmt/policies
    PATCH /policy-mgmt/policies/123
    """
    
    extractor = SwaggerExtractor()
    explicit_paths = extractor._extract_endpoints_explicit(text)
    
    # Build specs (no semantic matches)
    specs = extractor._merge_and_build_specs(explicit_paths, [], text)
    
    assert len(specs) >= 3, f"Should build 3 specs, got {len(specs)}"
    
    # Check methods are captured
    search_spec = next((s for s in specs if 'search' in s.endpoint_path), None)
    assert search_spec is not None, "Should find search endpoint"
    assert 'GET' in search_spec.http_methods, f"Should have GET method, got {search_spec.http_methods}"
    
    create_spec = next((s for s in specs if s.endpoint_path.endswith('/policies')), None)
    if create_spec:
        assert 'POST' in create_spec.http_methods, f"Should have POST method, got {create_spec.http_methods}"

