#!/usr/bin/env python3
"""
End-to-end test of GitLab MCP fallback for PLAT-13541.
"""

import asyncio
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.ai.gitlab_fallback_extractor import GitLabFallbackExtractor
from src.config.settings import settings


async def test_mcp_fallback():
    print("=" * 80)
    print("TESTING GITLAB MCP FALLBACK FOR PLAT-13541")
    print("=" * 80)
    print()
    
    # Check settings
    print(f"✓ GITLAB_FALLBACK_ENABLED: {settings.gitlab_fallback_enabled}")
    print(f"✓ GitLab group: {settings.gitlab_group_path}")
    print()
    
    # Create extractor
    print("Creating GitLabFallbackExtractor...")
    extractor = GitLabFallbackExtractor()
    
    if not extractor.mcp_client:
        print("❌ MCP client is None")
        return False
    
    if not extractor.mcp_client.mcp_available:
        print("❌ MCP not available")
        return False
    
    print(f"✓ MCP client initialized")
    print(f"✓ MCP remote path: {extractor.mcp_client.mcp_remote_path}")
    print()
    
    # Test extraction
    story_key = "PLAT-13541"
    story_text = """
    Show Policy list by Application
    
    This story introduces a new UI capability that enables users to view a list of policies 
    associated with a specific application.
    
    Create BE endpoint for fetching policies by application id: need to create endpoint to fetch 
    policies by application, need to work the same as existing fechPoliciesByX
    
    for ruleset, action, dynamic group & condition we use
    GET policy-mgmt/dynamic-group/b8825285-6c6d-40c3-ae47-d1bb196f5339/policies
    GET policy-mgmt/policy/action/e5a38e3f-d7a0-4477-af1b-fba0ba040ab5/search?offset=0&limit=10
    """
    
    print(f"Extracting endpoints for {story_key}...")
    print()
    
    api_specs = await extractor.extract_from_codebase(
        story_key=story_key,
        story_text=story_text,
        project_key="PLAT"
    )
    
    print()
    print("=" * 80)
    print("RESULTS")
    print("=" * 80)
    print()
    
    if not api_specs:
        print("⚠️  No API specifications found")
        print("This could mean:")
        print("  - No branches found for PLAT-13541")
        print("  - No code found in those branches")
        print("  - No endpoints/DTOs extracted from code")
        return False
    
    print(f"✅ Found {len(api_specs)} API specification(s)")
    print()
    
    for i, spec in enumerate(api_specs, 1):
        print(f"API {i}:")
        print(f"  Path: {' '.join(spec.http_methods)} {spec.endpoint_path}")
        if spec.service_name:
            print(f"  Service: {spec.service_name}")
        if spec.request_example:
            print(f"  Request Example: {spec.request_example[:100]}...")
        if spec.response_example:
            print(f"  Response Example: {spec.response_example[:100]}...")
        if spec.dto_definitions:
            print(f"  DTOs: {list(spec.dto_definitions.keys())}")
        print()
    
    return True


if __name__ == "__main__":
    success = asyncio.run(test_mcp_fallback())
    sys.exit(0 if success else 1)

