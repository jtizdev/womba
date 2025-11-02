#!/usr/bin/env python3
"""
Standalone script to index PlainID documentation only.
Useful for testing and quick re-indexing of external docs.
"""

import asyncio
from src.ai.context_indexer import ContextIndexer
from src.config.settings import settings

async def main():
    print("=" * 80)
    print("PlainID Documentation Indexer")
    print("=" * 80)
    print(f"\nConfiguration:")
    print(f"  Base URL: {settings.plainid_doc_base_url}")
    print(f"  Max pages: {settings.plainid_doc_max_pages}")
    print(f"  Max depth: {settings.plainid_doc_max_depth}")
    print(f"  Request delay: {settings.plainid_doc_request_delay}s")
    print(f"  Enabled: {settings.plainid_doc_index_enabled}")
    print()
    
    indexer = ContextIndexer()
    
    print("🔄 Starting PlainID documentation indexing...")
    print("This will:")
    print("  1. Discover URLs from docs.plainid.io/v1-api")
    print("  2. Fetch content via GET requests")
    print("  3. Index into external_docs collection")
    print()
    
    count = await indexer.index_external_docs()
    
    print()
    print("=" * 80)
    if count > 0:
        print(f"✅ Successfully indexed {count} PlainID documentation pages!")
    else:
        print("⚠️  No documents indexed. Check logs for errors.")
    print("=" * 80)
    print()
    print("Next steps:")
    print("  - Run 'python womba_cli.py rag-stats' to verify")
    print("  - Run 'python womba_cli.py rag-view external_docs --limit 5' to preview")
    print("  - Test with 'python womba_cli.py generate PLAT-16263'")

if __name__ == "__main__":
    asyncio.run(main())

