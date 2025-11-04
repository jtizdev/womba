#!/usr/bin/env python3
"""
DEBUG: Check what Confluence API is actually returning.
"""

import asyncio
import httpx
import base64
from src.config.settings import settings

async def debug_confluence_api():
    """Test raw Confluence API responses."""
    auth = httpx.BasicAuth(settings.atlassian_email, settings.atlassian_api_token)
    base_url = settings.atlassian_base_url
    
    print("\n" + "="*70)
    print("🔍 DEBUGGING CONFLUENCE API RESPONSES")
    print("="*70)
    
    cql = "type=page ORDER BY lastModified DESC"
    
    # Test different limits and starts
    test_cases = [
        {"start": 0, "limit": 50},
        {"start": 0, "limit": 100},
        {"start": 50, "limit": 100},
        {"start": 100, "limit": 100},
    ]
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        for tc in test_cases:
            print(f"\n📡 Testing: start={tc['start']}, limit={tc['limit']}")
            
            url = f"{base_url}/wiki/rest/api/content/search"
            params = {
                "cql": cql,
                "limit": tc['limit'],
                "start": tc['start'],
                "expand": "body.storage,space,version"
            }
            
            try:
                response = await client.get(url, auth=auth, params=params)
                response.raise_for_status()
                data = response.json()
                
                results = data.get("results", [])
                size = data.get("size", len(results))
                total_size = data.get("totalSize")
                limit_resp = data.get("limit")
                start_resp = data.get("start")
                
                print(f"  ✅ Got {len(results)} results")
                print(f"     Response fields:")
                print(f"       - size: {size}")
                print(f"       - totalSize: {total_size}")
                print(f"       - limit: {limit_resp}")
                print(f"       - start: {start_resp}")
                print(f"       - _links.next: {data.get('_links', {}).get('next')}")
                print(f"       - nextPageToken: {data.get('nextPageToken')}")
                
                if len(results) > 0:
                    print(f"     First page: {results[0].get('title', 'N/A')[:50]}")
                    print(f"     Last page: {results[-1].get('title', 'N/A')[:50]}")
                
            except Exception as exc:
                print(f"  ❌ Error: {exc}")
    
    print("\n" + "="*70)

if __name__ == "__main__":
    asyncio.run(debug_confluence_api())

