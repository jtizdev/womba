#!/usr/bin/env python3
"""
Detailed MCP search test to see what data we're getting.
"""

import asyncio
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.ai.gitlab_fallback_extractor import GitLabFallbackExtractor


async def test_detailed():
    print("=" * 80)
    print("DETAILED MCP SEARCH TEST FOR PLAT-13541")
    print("=" * 80)
    print()
    
    extractor = GitLabFallbackExtractor()
    
    # Test branch discovery
    print("STEP 1: Finding branches for PLAT-13541...")
    print()
    branches = await extractor._find_branches_for_story("PLAT-13541")
    print(f"Found {len(branches)} branches/projects")
    for i, branch in enumerate(branches, 1):
        print(f"  {i}. Project ID: {branch.get('project_id')}")
        print(f"     Path: {branch.get('path', 'N/A')}")
        print(f"     Ref: {branch.get('ref', 'N/A')}")
    print()
    
    # Test query generation
    print("STEP 2: Generating search queries...")
    print()
    story_text = """Show Policy list by Application. Create BE endpoint for fetching policies by application id."""
    queries = await extractor._generate_service_search_queries(story_text, "PLAT-13541")
    print(f"Generated {len(queries)} queries:")
    for i, q in enumerate(queries, 1):
        print(f"  {i}. {q}")
    print()
    
    # Test search
    print("STEP 3: Searching codebase...")
    print()
    search_results = await extractor._search_codebase_via_mcp(
        story_key="PLAT-13541",
        story_text=story_text,
        service_queries=queries,
        branches=branches
    )
    print(f"Found {len(search_results)} search results")
    print()
    
    # Show first few results in detail
    for i, result in enumerate(search_results[:5], 1):
        print(f"Result {i}:")
        print(f"  Type: {type(result)}")
        if isinstance(result, dict):
            print(f"  Keys: {list(result.keys())}")
            print(f"  Path: {result.get('path') or result.get('file_path', 'N/A')}")
            content = result.get('content') or result.get('text') or result.get('data', '')
            if content:
                print(f"  Content preview: {str(content)[:200]}...")
        print()
    
    # Test endpoint extraction
    print("STEP 4: Extracting endpoints...")
    print()
    api_specs = extractor._extract_endpoints_from_search_results(search_results)
    print(f"Extracted {len(api_specs)} API specifications")
    for i, spec in enumerate(api_specs, 1):
        print(f"  {i}. {' '.join(spec.http_methods)} {spec.endpoint_path}")
    print()
    
    # Test DTO extraction
    print("STEP 5: Extracting DTOs...")
    print()
    dtos = extractor._extract_dto_definitions(search_results)
    print(f"Found {len(dtos)} DTO definitions")
    for dto_name, dto_fields in list(dtos.items())[:3]:
        print(f"  {dto_name}:")
        for field_name, field_info in list(dto_fields.items())[:5]:
            print(f"    - {field_name}: {field_info.get('type', 'unknown')}")
    print()
    
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Branches found: {len(branches)}")
    print(f"Search results: {len(search_results)}")
    print(f"Endpoints extracted: {len(api_specs)}")
    print(f"DTOs extracted: {len(dtos)}")
    print()
    
    if api_specs:
        print("✅ MCP FALLBACK IS WORKING!")
    else:
        print("⚠️  MCP is working but not finding endpoints")
        print("Need to improve search queries or extraction logic")


if __name__ == "__main__":
    asyncio.run(test_detailed())

