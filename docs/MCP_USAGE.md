# MCP Usage in Womba

## Overview

GitLab MCP (Model Context Protocol) is integrated into Womba as a **fallback mechanism** for endpoint discovery. When normal endpoint extraction finds no results, MCP searches the GitLab codebase to find API endpoints.

## How It Works

### Flow

1. **Normal Extraction** (Primary):
   - Swagger/OpenAPI extraction from RAG
   - Explicit endpoint mentions in story
   - Semantic search in RAG

2. **AI Filtering**:
   - Filters out example endpoints
   - Keeps only actual requirements

3. **MCP Fallback** (Only if step 1-2 find nothing):
   - Triggers when `api_specs` is empty
   - Uses GitLab MCP to search codebase
   - Extracts endpoints from code files

### MCP Fallback Process

When triggered, the `GitLabFallbackExtractor`:

1. **Identifies Relevant Services**:
   - Uses AI to analyze story text
   - Determines which GitLab services to search

2. **Searches Codebase via MCP**:
   - Semantic code search for endpoint-related code
   - Searches for OpenAPI files, route definitions
   - Looks in branches matching story key (e.g., `PROJ-XXXXX`)

3. **Extracts Endpoints**:
   - Parses OpenAPI YAML/JSON files
   - Extracts route patterns from code (FastAPI, Flask, Express)
   - Returns `APISpec` objects

## Configuration

### Environment Variables

```bash
# Enable MCP fallback
GITLAB_FALLBACK_ENABLED=true

# Limit number of services to search
GITLAB_FALLBACK_MAX_SERVICES=5

# MCP server configuration
MCP_GITLAB_SERVER_COMMAND=npx
MCP_GITLAB_SERVER_ARGS=["-y", "mcp-remote", "https://gitlab.com/api/v4/mcp"]

# GitLab group to search
GITLAB_GROUP_PATH=your-company/services
```

### OAuth Authentication

MCP uses OAuth for authentication:
- First use: Opens browser for OAuth flow
- Token cached in `/home/womba/.mcp-auth` (persists across restarts)
- In Kubernetes: Port 12849 exposed for OAuth callback

## When MCP Fallback Triggers

MCP fallback **only** triggers when:
- ✅ Normal endpoint extraction finds **zero** endpoints
- ✅ `GITLAB_FALLBACK_ENABLED=true`
- ✅ MCP client is available and configured

**It does NOT trigger if:**
- ❌ Normal extraction found any endpoints (even if filtered out)
- ❌ MCP is disabled
- ❌ MCP client not configured

## Example Scenario

**Story**: PROJ-13541 (no endpoints in story, no Swagger matches)

1. Normal extraction: 0 endpoints
2. AI filtering: N/A (nothing to filter)
3. **MCP fallback triggers**:
   - Searches configured GitLab group
   - Finds branches: `feature/PROJ-13541`, `PROJ-13541`
   - Searches for OpenAPI files and route definitions
   - Extracts endpoints from found code
4. Returns extracted endpoints

## Testing MCP

### Test with a story that has no endpoints:

```bash
# Enrich a story that should trigger MCP fallback
kubectl -n womba exec <pod> -- womba enrich PROJ-XXXXX --no-cache

# Check logs for MCP activity
kubectl -n womba logs -f <pod> | grep -i "mcp\|fallback\|gitlab"
```

### Expected Log Messages:

```
No endpoints found via normal extraction, trying GitLab fallback...
Starting GitLab MCP fallback extraction for PROJ-XXXXX
GitLab MCP client configured with command: npx
Semantic code search via MCP: ...
GitLab MCP fallback extracted X API specifications
```

## Troubleshooting

### MCP Not Triggering

1. **Check if fallback is enabled**:
   ```bash
   kubectl -n womba exec <pod> -- env | grep GITLAB_FALLBACK
   ```

2. **Check if normal extraction found endpoints**:
   - If normal extraction found endpoints, MCP won't trigger
   - MCP only triggers when `api_specs` is empty

3. **Check MCP configuration**:
   ```bash
   kubectl -n womba exec <pod> -- env | grep MCP_GITLAB
   ```

### OAuth Issues

- **First use**: Check logs for OAuth URL, open in browser
- **Token cached**: Should work automatically after first auth
- **Port 12849**: Must be exposed for OAuth callback

### MCP Client Not Available

- Check if `mcp-remote` is installed in container
- Verify Node.js/npm is available
- Check logs for MCP initialization errors

## Code Location

- **MCP Client**: `src/ai/gitlab_fallback_extractor.py` → `GitLabMCPClient`
- **Fallback Extractor**: `src/ai/gitlab_fallback_extractor.py` → `GitLabFallbackExtractor`
- **Integration**: `src/ai/story_enricher.py` → Line 87-101

## Notes

- MCP is a **fallback only** - normal extraction is preferred
- MCP requires OAuth authentication (handled by `mcp-remote`)
- MCP searches are limited by `GITLAB_FALLBACK_MAX_SERVICES`
- Extracted endpoints are limited by `enrichment_max_apis`

