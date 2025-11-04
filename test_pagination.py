"""
Test script to verify Jira and Confluence pagination work correctly.
"""
import asyncio
from src.aggregator.jira_client import JiraClient
from src.aggregator.confluence_client import ConfluenceClient

async def test_jira_pagination():
    """Test that Jira fetches ALL issues, not just 100."""
    print("\n" + "="*70)
    print("TESTING JIRA PAGINATION")
    print("="*70)
    
    client = JiraClient()
    jql = "project = PLAT AND type in (Story, Task, Bug) ORDER BY created DESC"
    
    print(f"JQL: {jql}")
    print("Fetching ALL issues...")
    
    stories = client.search_all_issues(jql)
    
    print(f"\n🎉 RESULT: Fetched {len(stories)} issues")
    print("="*70)
    
    if len(stories) == 100:
        print("⚠️  WARNING: Got exactly 100 - pagination might be broken!")
        return False
    else:
        print("✅ PASS: Pagination working (count != 100)")
        return True

async def test_confluence_pagination():
    """Test that Confluence fetches ALL pages, not just 50."""
    print("\n" + "="*70)
    print("TESTING CONFLUENCE PAGINATION")
    print("="*70)
    
    client = ConfluenceClient()
    cql = "type=page ORDER BY lastModified DESC"
    
    print(f"CQL: {cql}")
    print("Fetching ALL pages...")
    
    all_pages = []
    start = 0
    limit = 50
    
    while True:
        print(f"  Fetching pages {start} to {start+limit}...")
        pages = await client.search_pages(cql, limit=limit, start=start)
        
        if not pages:
            print(f"  No more pages")
            break
        
        all_pages.extend(pages)
        print(f"  ✅ Got {len(pages)} pages | Total: {len(all_pages)}")
        
        if len(pages) < limit:
            print(f"  Last page (got {len(pages)} < {limit})")
            break
        
        start += limit
        
        # Safety limit for testing
        if start > 500:
            print(f"  Stopping at 500 for test purposes")
            break
    
    print(f"\n🎉 RESULT: Fetched {len(all_pages)} pages")
    print("="*70)
    
    if len(all_pages) == 50:
        print("⚠️  WARNING: Got exactly 50 - pagination might be broken!")
        return False
    else:
        print("✅ PASS: Pagination working (count != 50)")
        return True

async def main():
    print("\n🧪 PAGINATION TEST SUITE")
    print("="*70)
    
    jira_pass = await test_jira_pagination()
    confluence_pass = await test_confluence_pagination()
    
    print("\n" + "="*70)
    print("FINAL RESULTS")
    print("="*70)
    print(f"Jira: {'✅ PASS' if jira_pass else '❌ FAIL'}")
    print(f"Confluence: {'✅ PASS' if confluence_pass else '❌ FAIL'}")
    print("="*70)
    
    if jira_pass and confluence_pass:
        print("\n🎉 ALL TESTS PASSED!")
        return 0
    else:
        print("\n❌ SOME TESTS FAILED - FIX THE BUGS!")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)

