#!/usr/bin/env python3
"""
Test full endpoint extraction with aggregation.
"""

import asyncio
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.ai.gitlab_fallback_extractor import GitLabFallbackExtractor


async def test():
    print("=" * 80)
    print("TESTING FULL ENDPOINT EXTRACTION")
    print("=" * 80)
    print()
    
    extractor = GitLabFallbackExtractor()
    
    # Search for PolicyController
    print("Searching for PolicyController...")
    results = await extractor.mcp_client.gitlab_search(
        scope="blobs",
        search="PolicyController @GetMapping",
        group_id="plainid/srv",
        per_page=15
    )
    
    print(f"Found {len(results)} search results")
    print()
    
    # Extract endpoints using the aggregation method
    print("Extracting endpoints with aggregation...")
    api_specs = extractor._extract_endpoints_from_search_results(results)
    
    print(f"✅ Extracted {len(api_specs)} API specifications")
    print()
    
    for i, spec in enumerate(api_specs, 1):
        print(f"{i}. {' '.join(spec.http_methods)} {spec.endpoint_path}")
        print(f"   Service: {spec.service_name}")
        if spec.parameters:
            print(f"   Parameters: {spec.parameters}")
        if spec.request_example:
            print(f"   Request Example: {spec.request_example[:100]}...")
        if spec.response_example:
            print(f"   Response Example: {spec.response_example[:100]}...")
        print()


if __name__ == "__main__":
    asyncio.run(test())

