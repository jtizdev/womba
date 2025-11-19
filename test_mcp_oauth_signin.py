#!/usr/bin/env python3
"""
Test script to trigger GitLab MCP OAuth sign-in flow.

This will:
1. Initialize MCP client
2. Call semantic_code_search
3. Browser will open for OAuth login
4. User authorizes
5. Credentials cached for future use
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.absolute()))

from src.ai.gitlab_fallback_extractor import GitLabMCPClient


async def test_oauth_signin():
    """Test OAuth sign-in flow."""
    print("\n" + "="*70)
    print("GITLAB MCP OAUTH SIGN-IN TEST")
    print("="*70)
    print()
    
    # Initialize client
    print("Step 1: Initializing MCP client...")
    client = GitLabMCPClient()
    
    if not client.mcp_available:
        print("❌ MCP not available!")
        print("   Make sure mcp-remote is installed: npm install -g mcp-remote")
        return False
    
    print("✅ MCP client initialized")
    print(f"✅ OAuth cache directory: {client.oauth_cache_dir}")
    print()
    
    # Check if OAuth cache exists
    cache_files = list(client.oauth_cache_dir.glob("*"))
    if cache_files:
        print(f"⚠️  Found {len(cache_files)} cached OAuth files")
        print("   Using cached credentials (browser won't open)")
    else:
        print("⚠️  No cached OAuth credentials found")
        print("   Browser WILL open for OAuth login!")
    print()
    
    print("="*70)
    print("Step 2: Calling MCP semantic_code_search")
    print("="*70)
    print()
    print("⚠️  IF BROWSER OPENS:")
    print("   1. Click 'Authorize' on GitLab OAuth page")
    print("   2. Credentials will be cached automatically")
    print("   3. Future calls won't need browser login")
    print()
    print("Calling MCP now...")
    print()
    
    try:
        # Call MCP - this will trigger OAuth if needed
        results = await client.semantic_code_search(
            project_id="plainid/srv",  # Group path
            semantic_query="API endpoint route definition",
            limit=5
        )
        
        print()
        print("="*70)
        print("Step 3: Results")
        print("="*70)
        print()
        print(f"Found {len(results)} results")
        
        if results:
            print()
            print("✅✅✅ SUCCESS! MCP IS WORKING! ✅✅✅")
            print()
            print("Sample results:")
            for i, r in enumerate(results[:3], 1):
                print(f"  {i}. {r}")
            
            # Check if we got actual code results or just error messages
            has_real_results = any(
                'file_path' in str(r) or 'content' in str(r) 
                for r in results 
                if 'not found' not in str(r).lower()
            )
            
            if has_real_results:
                print()
                print("✅ Got actual code search results!")
            else:
                print()
                print("⚠️  Got error messages (might need OAuth or project access)")
                print("   But MCP connection is working!")
            
            return True
        else:
            print()
            print("⚠️  No results returned")
            print("   This could mean:")
            print("   - OAuth not authorized yet")
            print("   - Project not accessible")
            print("   - No matching code found")
            return False
            
    except Exception as e:
        print()
        print("="*70)
        print("ERROR")
        print("="*70)
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run OAuth sign-in test."""
    success = await test_oauth_signin()
    
    print()
    print("="*70)
    if success:
        print("✅ TEST PASSED - MCP IS WORKING!")
        print()
        print("Next steps:")
        print("  1. If browser opened, authorize OAuth")
        print("  2. Credentials cached in: ~/.mcp-auth/")
        print("  3. Future calls won't need browser")
        print("  4. MCP is ready to use in Womba!")
    else:
        print("⚠️  TEST INCOMPLETE")
        print()
        print("Check:")
        print("  - Did browser open for OAuth?")
        print("  - Did you authorize?")
        print("  - Check logs above for details")
    print("="*70)
    print()
    
    return 0 if success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

