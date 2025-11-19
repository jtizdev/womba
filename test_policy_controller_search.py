#!/usr/bin/env python3
"""
Test searching for PolicyController and extracting endpoints.
"""

import asyncio
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.ai.gitlab_fallback_extractor import GitLabFallbackExtractor


async def test():
    print("=" * 80)
    print("TESTING POLICY CONTROLLER SEARCH")
    print("=" * 80)
    print()
    
    extractor = GitLabFallbackExtractor()
    
    # Search for PolicyController directly
    print("Searching for PolicyController...")
    results = await extractor.mcp_client.gitlab_search(
        scope="blobs",
        search="PolicyController @GetMapping",
        group_id="plainid/srv",
        per_page=10
    )
    
    print(f"Found {len(results)} results")
    print()
    
    # Show first result
    if results:
        first = results[0]
        print(f"First result:")
        print(f"  Path: {first.get('path', 'N/A')}")
        print(f"  Project ID: {first.get('project_id', 'N/A')}")
        content = first.get('data', '')
        print(f"  Content: {content[:300]}...")
        print()
        
        # Try to extract endpoints from this content
        print("Extracting endpoints from PolicyController...")
        specs = extractor._parse_route_file(content, first.get('path', ''))
        print(f"Extracted {len(specs)} endpoints")
        for spec in specs:
            print(f"  - {' '.join(spec.http_methods)} {spec.endpoint_path}")


if __name__ == "__main__":
    asyncio.run(test())

