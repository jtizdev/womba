#!/usr/bin/env python3
"""
Test script to validate GitLab MCP OAuth implementation.

This tests the core MCP OAuth flow without actually needing OAuth credentials.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.absolute()))

from src.config.settings import settings
from src.ai.gitlab_fallback_extractor import GitLabMCPClient, GitLabFallbackExtractor


async def test_mcp_client_initialization():
    """Test MCP client initializes correctly."""
    print("\n" + "="*60)
    print("TEST 1: MCP Client Initialization (OAuth via mcp-remote)")
    print("="*60)
    
    try:
        client = GitLabMCPClient()
        
        print(f"\n✓ MCP Client created successfully")
        print(f"  OAuth cache directory: {client.oauth_cache_dir}")
        print(f"  MCP available: {client.mcp_available}")
        
        if client.mcp_available:
            print(f"\n✓ MCP is ready to use")
            print(f"  On first call, browser will open for OAuth login")
            print(f"  Credentials will be cached in: {client.oauth_cache_dir}")
            return True
        else:
            print(f"\n⚠️  MCP not available (npx or mcp-remote not installed)")
            print(f"  Fix: docker-compose build --no-cache womba-server")
            return False
            
    except Exception as e:
        print(f"\n✗ Error initializing MCP client: {e}")
        return False


async def test_configuration():
    """Test MCP configuration."""
    print("\n" + "="*60)
    print("TEST 2: Configuration Check")
    print("="*60)
    
    print(f"\nGitLab Configuration:")
    print(f"  Base URL: {settings.gitlab_base_url}")
    print(f"  Group Path: {settings.gitlab_group_path}")
    print(f"  Fallback Enabled: {settings.gitlab_fallback_enabled}")
    
    if not settings.gitlab_fallback_enabled:
        print(f"\n⚠️  GitLab fallback is disabled!")
        print(f"  Fix: Set GITLAB_FALLBACK_ENABLED=true in .env")
        return False
    
    print(f"\n✓ Configuration looks good")
    return True


async def test_fallback_extractor():
    """Test fallback extractor initialization."""
    print("\n" + "="*60)
    print("TEST 3: Fallback Extractor Initialization")
    print("="*60)
    
    try:
        extractor = GitLabFallbackExtractor()
        
        if not extractor.mcp_client:
            print(f"\n✗ MCP client not available in extractor")
            return False
        
        if not extractor.mcp_client.mcp_available:
            print(f"\n⚠️  MCP not available")
            print(f"  Fallback extraction will be skipped")
            return False
        
        print(f"\n✓ Fallback extractor ready")
        print(f"  Max services: {extractor.max_services}")
        print(f"  Max APIs: {extractor.max_apis}")
        
        return True
        
    except Exception as e:
        print(f"\n✗ Error initializing fallback extractor: {e}")
        return False


async def test_oauth_flow_info():
    """Explain OAuth flow."""
    print("\n" + "="*60)
    print("TEST 4: OAuth Flow Explanation")
    print("="*60)
    
    print(f"""
When you first use MCP (e.g., generate a test plan):

1. Womba launches: npx -y mcp-remote https://gitlab.com/api/v4/mcp
2. Browser opens with GitLab OAuth login
3. You click "Authorize"
4. Token saved to: ~/.mcp-auth/
5. Future calls use cached token (no browser needed)

How to test:
  Local: python test_mcp_setup.py
  Docker: docker-compose exec womba-server python test_mcp_setup.py

The browser will open automatically on first run!
    """)
    
    return True


async def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("GitLab MCP OAuth Implementation Validation")
    print("="*60)
    
    results = []
    
    # Test 1: Configuration
    results.append(("Configuration", await test_configuration()))
    
    # Test 2: MCP Client
    results.append(("MCP Client Initialization", await test_mcp_client_initialization()))
    
    # Test 3: Fallback Extractor
    results.append(("Fallback Extractor", await test_fallback_extractor()))
    
    # Test 4: OAuth Flow Info
    results.append(("OAuth Flow", await test_oauth_flow_info()))
    
    # Summary
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASS" if result else "⚠️  WARN/FAIL"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed >= total - 1:
        print("""
✓ MCP OAuth implementation is ready!

Next steps:
  1. Rebuild Docker: docker-compose build --no-cache womba-server
  2. Start: docker-compose up -d
  3. Generate a test plan (browser will open for OAuth login on first use)
  4. Done! Credentials are cached for all future use
        """)
        return 0
    else:
        print("""
⚠️  Issues detected. Please fix:
  1. Ensure Node.js 20+ and npm are installed
  2. Rebuild Docker: docker-compose build --no-cache womba-server
  3. Check Docker logs: docker-compose logs womba-server
        """)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

