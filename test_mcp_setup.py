#!/usr/bin/env python3
"""
Test script to validate GitLab MCP setup in Womba.

Run this to verify MCP is properly configured and working.
Usage:
  python test_mcp_setup.py
"""

import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.absolute()))

from loguru import logger
from src.config.settings import settings
from src.ai.gitlab_fallback_extractor import GitLabMCPClient, GitLabFallbackExtractor


async def test_mcp_configuration():
    """Test basic MCP configuration."""
    print("\n" + "="*60)
    print("1. Configuration Check")
    print("="*60)
    
    print(f"GitLab Base URL: {settings.gitlab_base_url}")
    print(f"GitLab Group Path: {settings.gitlab_group_path}")
    print(f"GitLab Token Set: {'✓' if settings.gitlab_token else '✗'}")
    print(f"GitLab MCP Token Set: {'✓' if settings.mcp_gitlab_token else '✗'}")
    print(f"GitLab Fallback Enabled: {settings.gitlab_fallback_enabled}")
    
    if not settings.gitlab_token:
        print("\n⚠️  WARNING: GITLAB_TOKEN not set in environment!")
        print("   Add to .env: GITLAB_TOKEN=glpat-xxxxx")
        return False
    
    if not settings.mcp_gitlab_token:
        print("\n⚠️  WARNING: MCP_GITLAB_TOKEN not set in environment!")
        print("   Add to .env: MCP_GITLAB_TOKEN=glpat-xxxxx")
        return False
    
    print("\n✓ Configuration looks good!")
    return True


async def test_mcp_client():
    """Test GitLab MCP client initialization."""
    print("\n" + "="*60)
    print("2. MCP Client Initialization")
    print("="*60)
    
    try:
        client = GitLabMCPClient()
        print(f"MCP Client Available: {'✓' if client.mcp_available else '✗'}")
        
        if client.mcp_available:
            print(f"MCP Base URL: {client.base_url}")
            print(f"MCP Endpoint: {client.mcp_endpoint}")
            print("\n✓ MCP client initialized successfully!")
            return True
        else:
            print("\n✗ MCP client not available!")
            print("  Possible causes:")
            print("  - GITLAB_TOKEN or MCP_GITLAB_TOKEN not set")
            print("  - httpx library not installed")
            print("  - Network connectivity issues")
            return False
    
    except Exception as e:
        print(f"\n✗ Error initializing MCP client: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_semantic_code_search():
    """Test GitLab MCP semantic code search."""
    print("\n" + "="*60)
    print("3. Semantic Code Search Test")
    print("="*60)
    
    try:
        client = GitLabMCPClient()
        
        if not client.mcp_available:
            print("✗ MCP client not available - skipping semantic search test")
            return False
        
        print("Searching for 'policy list API endpoint'...")
        
        results = await client.semantic_code_search(
            project_id=settings.gitlab_group_path,
            semantic_query="policy list API endpoint",
            limit=5
        )
        
        print(f"Found {len(results)} results")
        
        if results:
            print("\nSample results:")
            for i, result in enumerate(results[:3], 1):
                print(f"\n  Result {i}:")
                if 'file_path' in result:
                    print(f"    File: {result['file_path']}")
                if 'path' in result:
                    print(f"    Path: {result['path']}")
                if 'content' in result:
                    content = str(result['content'])[:100]
                    print(f"    Content: {content}...")
            
            print("\n✓ Semantic search is working!")
            return True
        else:
            print("\n⚠️  No results found")
            print("  This could mean:")
            print("  - No matching code in repositories")
            print("  - MCP token lacks required scopes")
            print("  - Search query too specific")
            return False
    
    except Exception as e:
        print(f"\n✗ Error in semantic search: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_gitlab_search():
    """Test GitLab MCP search function."""
    print("\n" + "="*60)
    print("4. GitLab Search Test")
    print("="*60)
    
    try:
        client = GitLabMCPClient()
        
        if not client.mcp_available:
            print("✗ MCP client not available - skipping GitLab search test")
            return False
        
        print("Searching GitLab blobs for 'PLAT-13541'...")
        
        results = await client.gitlab_search(
            scope="blobs",
            search="PLAT-13541",
            group_id=settings.gitlab_group_path,
            per_page=5
        )
        
        print(f"Found {len(results)} results")
        
        if results:
            print("\nSample results:")
            for i, result in enumerate(results[:2], 1):
                print(f"\n  Result {i}:")
                print(f"    {result}")
            
            print("\n✓ GitLab search is working!")
            return True
        else:
            print("\n⚠️  No results found for 'PLAT-13541'")
            print("  This could mean:")
            print("  - No references to PLAT-13541 in code")
            print("  - MCP token lacks required scopes")
            return False
    
    except Exception as e:
        print(f"\n✗ Error in GitLab search: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_fallback_extractor():
    """Test full fallback extractor."""
    print("\n" + "="*60)
    print("5. Full Fallback Extractor Test")
    print("="*60)
    
    try:
        extractor = GitLabFallbackExtractor()
        
        if not extractor.mcp_client or not extractor.mcp_client.mcp_available:
            print("✗ MCP client not available - skipping fallback extractor test")
            return False
        
        print("Testing extraction for PLAT-13541...")
        
        story_text = """
        PLAT-13541: Policy List with Pagination
        Implement a new endpoint to retrieve policies with pagination support.
        The endpoint should accept page and limit parameters.
        """
        
        api_specs = await extractor.extract_from_codebase(
            story_key="PLAT-13541",
            story_text=story_text,
            project_key="PLAT"
        )
        
        print(f"Extracted {len(api_specs)} API specifications")
        
        if api_specs:
            print("\nExtracted endpoints:")
            for spec in api_specs[:3]:
                print(f"\n  - {spec.endpoint_path}")
                print(f"    Methods: {', '.join(spec.http_methods)}")
                if spec.parameters:
                    print(f"    Parameters: {', '.join(spec.parameters)}")
                if spec.service_name:
                    print(f"    Service: {spec.service_name}")
            
            print("\n✓ Fallback extractor is working!")
            return True
        else:
            print("\n⚠️  No API specifications extracted")
            print("  This could mean:")
            print("  - No matching code found")
            print("  - No routes/endpoints in code")
            return False
    
    except Exception as e:
        print(f"\n✗ Error in fallback extractor: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("GitLab MCP Setup Validation")
    print("="*60)
    
    results = []
    
    # Test 1: Configuration
    results.append(("Configuration", await test_mcp_configuration()))
    
    # Test 2: MCP Client
    results.append(("MCP Client", await test_mcp_client()))
    
    # Test 3: Semantic Search
    results.append(("Semantic Search", await test_semantic_code_search()))
    
    # Test 4: GitLab Search
    results.append(("GitLab Search", await test_gitlab_search()))
    
    # Test 5: Fallback Extractor
    results.append(("Fallback Extractor", await test_fallback_extractor()))
    
    # Summary
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✓ All tests passed! GitLab MCP is properly configured.")
        return 0
    elif passed >= total - 1:
        print("\n⚠️  Most tests passed. Check warnings above.")
        return 0
    else:
        print("\n✗ MCP setup needs attention. See errors above.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

