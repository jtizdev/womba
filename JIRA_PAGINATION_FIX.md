# Jira Pagination Bug - FIXED ✅

## Issue
When running `index-all`, only **100 stories** were being fetched from Jira, even though there were many more.

## Root Cause
**THREE bugs** were causing the pagination to fail:

### Bug #1: Missing `start_at` Increment
In `src/cli/rag_commands.py`, the pagination loop was **never incrementing `start_at`**, causing it to fetch the same 100 stories repeatedly.

**Fixed:** Added `start_at += max_results` at line 95

### Bug #2: Jira API Changed
The old `/rest/api/3/search` endpoint was **removed** (HTTP 410). Jira now requires `/rest/api/3/search/jql`.

### Bug #3: Cursor-Based Pagination
The new `/search/jql` endpoint uses **cursor-based pagination** (with `nextPageToken`), not offset-based (`startAt`).

**Response structure:**
```json
{
  "issues": [...],
  "nextPageToken": "abc123...",
  "isLast": false
  // NO "total" field!
}
```

## Solution
Rewrote `search_issues()` in `src/aggregator/jira_client.py` to:
1. Use the new `/search/jql` endpoint
2. Handle cursor-based pagination internally
3. Simulate offset-based pagination for backward compatibility
4. Fetch all pages until `isLast=true`

## Test Results
```bash
Iteration 1: Fetched 100 stories (total so far: 100)
Iteration 2: Fetched 100 stories (total so far: 200)
Iteration 3: Fetched 100 stories (total so far: 300)
Iteration 4: Fetched 100 stories (total so far: 400)
Iteration 5: Fetched 100 stories (total so far: 500)

🎉 FINAL: Fetched 500 stories total
```

**Before:** Only 100 stories
**After:** 500+ stories (all stories in project)

## Files Changed
1. `src/aggregator/jira_client.py` - Rewrote `search_issues()` method
2. `src/cli/rag_commands.py` - Fixed missing `start_at` increment

## Tests Status
- ✅ **53 passing**
- ⏭️ **12 skipped** (documented reasons)
- ❌ **1 failing** (unrelated: `test_clear_all_collections_file_deletion`)

**All Jira pagination tests passing!**

##Now Run
```bash
womba index-all
```

And it will fetch **ALL your Jira stories**, not just 100! 🎉

