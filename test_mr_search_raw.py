#!/usr/bin/env python3
"""
Test MR search - show raw data.
"""

import asyncio
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.ai.gitlab_fallback_extractor import GitLabMCPClient


async def test_mr_search():
    client = GitLabMCPClient()
    
    print("Searching for merge requests with PLAT-13541...")
    results = await client.gitlab_search(
        scope="merge_requests",
        search="PLAT-13541",
        per_page=20
    )
    
    print(f"Found {len(results)} results")
    print()
    
    for i, result in enumerate(results, 1):
        print(f"Result {i}:")
        print(f"  Raw: {json.dumps(result, indent=2, default=str)}")
        print()


if __name__ == "__main__":
    asyncio.run(test_mr_search())

