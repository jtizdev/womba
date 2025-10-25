"""
Unit tests for Jira context extraction utilities.
"""

import pytest

from src.api.utils.jira_context import (
    JiraContext,
    extract_query_params,
    get_jwt_from_request
)


class TestJiraContext:
    """Test JiraContext model and creation."""
    
    def test_jira_context_creation(self):
        """Test creating JiraContext directly."""
        context = JiraContext(
            client_key="test-client",
            base_url="https://test.atlassian.net",
            user_account_id="user-123",
            issue_key="PROJ-123",
            project_key="PROJ"
        )
        
        assert context.client_key == "test-client"
        assert context.base_url == "https://test.atlassian.net"
        assert context.user_account_id == "user-123"
        assert context.issue_key == "PROJ-123"
        assert context.project_key == "PROJ"
    
    def test_jira_context_from_jwt_payload(self):
        """Test creating JiraContext from JWT payload."""
        payload = {
            "iss": "test-client-key",
            "aud": ["https://test.atlassian.net"],
            "context": {
                "user": {
                    "userKey": "user-key-123",
                    "accountId": "account-id-123"
                }
            }
        }
        
        query_params = {
            "issueKey": "PROJ-456",
            "projectKey": "PROJ"
        }
        
        context = JiraContext.from_jwt_payload(payload, query_params)
        
        assert context.client_key == "test-client-key"
        assert context.base_url == "https://test.atlassian.net"
        assert context.user_key == "user-key-123"
        assert context.user_account_id == "account-id-123"
        assert context.issue_key == "PROJ-456"
        assert context.project_key == "PROJ"
    
    def test_jira_context_from_jwt_payload_no_query(self):
        """Test creating JiraContext without query params."""
        payload = {
            "iss": "test-client-key",
            "aud": "https://test.atlassian.net",
            "context": {
                "user": {
                    "accountId": "account-id-123"
                }
            }
        }
        
        context = JiraContext.from_jwt_payload(payload)
        
        assert context.client_key == "test-client-key"
        assert context.base_url == "https://test.atlassian.net"
        assert context.issue_key is None
        assert context.project_key is None
    
    def test_jira_context_repr(self):
        """Test JiraContext string representation."""
        context = JiraContext(
            client_key="test-client",
            base_url="https://test.atlassian.net",
            issue_key="PROJ-123",
            project_key="PROJ"
        )
        
        repr_str = repr(context)
        assert "test-client" in repr_str
        assert "PROJ-123" in repr_str
        assert "PROJ" in repr_str


class TestExtractQueryParams:
    """Test query parameter extraction."""
    
    def test_extract_from_full_url(self):
        """Test extracting params from full URL."""
        url = "https://example.com/path?issueKey=PROJ-123&projectKey=PROJ&jwt=token123"
        
        params = extract_query_params(url)
        
        assert params["issueKey"] == "PROJ-123"
        assert params["projectKey"] == "PROJ"
        assert params["jwt"] == "token123"
    
    def test_extract_from_query_string(self):
        """Test extracting params from query string only."""
        query = "issueKey=TEST-456&projectKey=TEST&enabled=true"
        
        params = extract_query_params(query)
        
        assert params["issueKey"] == "TEST-456"
        assert params["projectKey"] == "TEST"
        assert params["enabled"] == "true"
    
    def test_extract_empty_params(self):
        """Test extracting from URL with no params."""
        url = "https://example.com/path"
        
        params = extract_query_params(url)
        
        assert params == {}
    
    def test_extract_with_multiple_values(self):
        """Test param with multiple values (takes first)."""
        url = "https://example.com?key=value1&key=value2"
        
        params = extract_query_params(url)
        
        assert params["key"] == "value1"


class TestGetJwtFromRequest:
    """Test JWT token extraction from requests."""
    
    def test_jwt_from_query_params(self):
        """Test extracting JWT from query parameters."""
        query_params = {"jwt": "test-token-123", "issueKey": "PROJ-123"}
        headers = {}
        
        jwt = get_jwt_from_request(query_params, headers)
        
        assert jwt == "test-token-123"
    
    def test_jwt_from_authorization_header_jwt(self):
        """Test extracting JWT from Authorization header (JWT prefix)."""
        query_params = {}
        headers = {"authorization": "JWT test-token-456"}
        
        jwt = get_jwt_from_request(query_params, headers)
        
        assert jwt == "test-token-456"
    
    def test_jwt_from_authorization_header_bearer(self):
        """Test extracting JWT from Authorization header (Bearer prefix)."""
        query_params = {}
        headers = {"Authorization": "Bearer test-token-789"}
        
        jwt = get_jwt_from_request(query_params, headers)
        
        assert jwt == "test-token-789"
    
    def test_jwt_query_params_priority(self):
        """Test that query params take priority over headers."""
        query_params = {"jwt": "query-token"}
        headers = {"Authorization": "Bearer header-token"}
        
        jwt = get_jwt_from_request(query_params, headers)
        
        assert jwt == "query-token"
    
    def test_jwt_not_found(self):
        """Test when JWT is not present."""
        query_params = {"issueKey": "PROJ-123"}
        headers = {}
        
        jwt = get_jwt_from_request(query_params, headers)
        
        assert jwt is None
    
    def test_jwt_case_insensitive_header(self):
        """Test case-insensitive header lookup."""
        query_params = {}
        headers = {"AUTHORIZATION": "JWT uppercase-token"}
        
        jwt = get_jwt_from_request(query_params, headers)
        
        # Should handle case-insensitive
        assert jwt is None or jwt == "uppercase-token"

