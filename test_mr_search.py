#!/usr/bin/env python3
"""
Test MR search directly.
"""

import asyncio
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.ai.gitlab_fallback_extractor import GitLabMCPClient


async def test_mr_search():
    print("=" * 80)
    print("TESTING MR SEARCH FOR PLAT-13541")
    print("=" * 80)
    print()
    
    client = GitLabMCPClient()
    
    print(f"MCP available: {client.mcp_available}")
    print()
    
    print("Searching for merge requests with PLAT-13541...")
    results = await client.gitlab_search(
        scope="merge_requests",
        search="PLAT-13541",
        per_page=20
    )
    
    print(f"Found {len(results)} results")
    print()
    
    for i, result in enumerate(results[:3], 1):
        print(f"Result {i}:")
        print(f"  Type: {type(result)}")
        if isinstance(result, dict):
            print(f"  Keys: {list(result.keys())}")
            print(f"  Project ID: {result.get('project_id')}")
            print(f"  Source project ID: {result.get('source_project_id')}")
            print(f"  Title: {result.get('title', 'N/A')}")
            print(f"  Source branch: {result.get('source_branch', 'N/A')}")
        else:
            print(f"  Value: {result}")
        print()


if __name__ == "__main__":
    asyncio.run(test_mr_search())

