"""
Validation script to verify index-all completed successfully.
"""
import asyncio
from src.ai.rag_store import RAGVectorStore

async def main():
    print("=" * 70)
    print("VALIDATING INDEX-ALL RESULTS")
    print("=" * 70)
    
    store = RAGVectorStore()
    stats = store.get_all_stats()
    
    print("\n📊 RAG DATABASE STATISTICS:")
    print("-" * 70)
    
    total_docs = 0
    for collection_name, count in stats.items():
        print(f"  {collection_name:30s}: {count:,} documents")
        total_docs += count
    
    print("-" * 70)
    print(f"  {'TOTAL':30s}: {total_docs:,} documents")
    print("=" * 70)
    
    # Validation checks
    print("\n✓ VALIDATION CHECKS:")
    checks_passed = 0
    checks_total = 0
    
    # Check 1: Jira stories indexed
    checks_total += 1
    if stats.get('jira_stories', 0) > 10000:
        print(f"  ✓ Jira stories: {stats.get('jira_stories', 0):,} (expected > 10,000)")
        checks_passed += 1
    else:
        print(f"  ✗ Jira stories: {stats.get('jira_stories', 0):,} (expected > 10,000)")
    
    # Check 2: Existing tests indexed
    checks_total += 1
    if stats.get('existing_tests', 0) > 0:
        print(f"  ✓ Existing tests: {stats.get('existing_tests', 0):,}")
        checks_passed += 1
    else:
        print(f"  ✗ Existing tests: {stats.get('existing_tests', 0):,}")
    
    # Check 3: Confluence docs indexed
    checks_total += 1
    if stats.get('confluence_docs', 0) > 0:
        print(f"  ✓ Confluence docs: {stats.get('confluence_docs', 0):,}")
        checks_passed += 1
    else:
        print(f"  ✗ Confluence docs: {stats.get('confluence_docs', 0):,}")
    
    # Check 4: External docs indexed
    checks_total += 1
    if stats.get('external_docs', 0) > 0:
        print(f"  ✓ External docs: {stats.get('external_docs', 0):,}")
        checks_passed += 1
    else:
        print(f"  ✗ External docs: {stats.get('external_docs', 0):,}")
    
    print("\n" + "=" * 70)
    if checks_passed == checks_total:
        print(f"✅ ALL CHECKS PASSED ({checks_passed}/{checks_total})")
    else:
        print(f"⚠️  SOME CHECKS FAILED ({checks_passed}/{checks_total})")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(main())

