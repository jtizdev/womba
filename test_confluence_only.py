#!/usr/bin/env python3
"""
Quick Confluence pagination test - validates we fetch ALL pages efficiently.
"""

import asyncio
import sys
import time
from loguru import logger

# Configure minimal logging for the test
logger.remove()
logger.add(sys.stderr, level="INFO", format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}")

from src.aggregator.confluence_client import ConfluenceClient


async def test_confluence_pagination():
    """Test that Confluence fetches ALL pages efficiently."""
    print("\n" + "="*70)
    print("🧪 TESTING CONFLUENCE PAGINATION")
    print("="*70)
    
    client = ConfluenceClient()
    cql = "type=page ORDER BY lastModified DESC"
    
    print(f"CQL: {cql}")
    print("Using search_all_pages() method...")
    
    start_time = time.time()
    
    try:
        all_pages = await client.search_all_pages(cql, limit=100)
        
        total_duration = time.time() - start_time
        
        print("\n" + "="*70)
        print(f"✅ RESULT: Fetched {len(all_pages)} pages in {total_duration:.2f}s")
        print(f"   Speed: {len(all_pages)/total_duration:.1f} pages/sec")
        
        # Check spaces
        spaces = set()
        for page in all_pages:
            space_data = page.get('space', {})
            if isinstance(space_data, dict):
                space_key = space_data.get('key', '')
            else:
                space_key = str(space_data)
            if space_key:
                spaces.add(space_key)
        
        print(f"   Spaces found: {', '.join(sorted(spaces))}")
        print("="*70)
        
        if len(all_pages) <= 50:
            print("⚠️  WARNING: Got 50 or fewer - might be a bug!")
            return False
        
        return True
        
    except Exception as exc:
        print(f"\n❌ FAILED: {exc}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    result = asyncio.run(test_confluence_pagination())
    sys.exit(0 if result else 1)

