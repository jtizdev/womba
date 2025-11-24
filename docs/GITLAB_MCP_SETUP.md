# GitLab MCP Setup Guide

This guide explains how to properly set up and use GitLab MCP (Model Context Protocol) in Womba for fallback endpoint discovery.

## Overview

Womba uses GitLab MCP as a fallback mechanism for finding API endpoints when normal Swagger/RAG extraction finds no results. The MCP allows semantic code search across your GitLab repositories.

**Two Integration Approaches:**
1. **REST API (Primary)**: For OpenAPI/Swagger file fetching and RAG indexing
2. **MCP (Fallback)**: For semantic code search and endpoint discovery

## Architecture

```
Story Enrichment Flow:
├─ Primary: Swagger/RAG extraction → Extract from Swagger docs
├─ Filter: AI-based filtering to remove example endpoints
└─ Fallback: GitLab MCP semantic search → Search codebase for endpoints
```

## Setup Instructions

### 1. Create GitLab Personal Access Token (PAT)

This is the **manual OAuth credentials approach** your DevOps recommended.

**Steps:**
1. Go to: https://gitlab.com/-/user_settings/personal_access_tokens
2. Click "Add new token"
3. **Name**: `womba-mcp` (or similar)
4. **Expiration date**: Choose based on your security policy (e.g., 1 year)
5. **Scopes**: Select ALL of these (important!):
   - ✅ `api` - Full API access
   - ✅ `read_api` - Read API access
   - ✅ `mcp` - MCP protocol access (if available, otherwise just api + read_api)
   - ✅ `read_repository` - Read repository contents
6. Click "Create personal access token"
7. **Copy the token immediately** (you won't see it again!)

### 2. Configure Environment Variables

Add to your `.env` file:

```bash
# GitLab Configuration
GITLAB_BASE_URL=https://gitlab.com
GITLAB_GROUP_PATH=your-company/services
GITLAB_TOKEN=glpat-xxxxxxxxxxxxxxxx  # Your PAT from step 1

# GitLab MCP Configuration (for fallback endpoint extraction)
GITLAB_FALLBACK_ENABLED=true
MCP_GITLAB_TOKEN=glpat-xxxxxxxxxxxxxxxx  # Same PAT as GITLAB_TOKEN
```

### 3. Docker Configuration

The Dockerfile already includes Node.js and `mcp-remote`:

```dockerfile
# Install mcp-remote for GitLab MCP connection
RUN npm install -g mcp-remote || true
```

### 4. How MCP Works in Womba

The `GitLabMCPClient` in `src/ai/gitlab_fallback_extractor.py`:

1. **Uses direct HTTP calls** to GitLab's MCP endpoint
2. **No OAuth flow needed** - uses your PAT token directly
3. **Sends JSON-RPC requests** to `/api/v4/mcp` endpoint
4. **Searches for code** using semantic queries (AI-powered)

Example flow:
```python
# When no endpoints found:
gitlab_extractor = GitLabFallbackExtractor()
api_specs = await gitlab_extractor.extract_from_codebase(
    story_key="PROJ-13541",
    story_text="Policy list with pagination...",
    project_key="PLAT"
)
# Returns: [APISpec(path="/policies", methods=["GET"], ...)]
```

## Testing MCP Integration

### Local Testing

1. Set your token in `.env`:
```bash
GITLAB_TOKEN=glpat-xxxxx
MCP_GITLAB_TOKEN=glpat-xxxxx
GITLAB_FALLBACK_ENABLED=true
```

2. Run test script:
```bash
cd /Users/royregev/womba
python -m pytest tests/test_gitlab_mcp.py -v
# Or manually:
python test_mcp_fallback.py
```

### Docker Testing

1. Rebuild Docker image:
```bash
cd /Users/royregev/womba
docker-compose build --no-cache womba-server
```

2. Run container with token:
```bash
docker-compose up -d womba-server
docker-compose logs -f womba-server
```

3. Check if MCP is working:
```bash
docker-compose exec womba-server python -c "
from src.ai.gitlab_fallback_extractor import GitLabMCPClient
import asyncio

async def test():
    client = GitLabMCPClient()
    print(f'MCP Available: {client.mcp_available}')
    if client.mcp_available:
        results = await client.semantic_code_search(
            project_id='plainid/srv',
            semantic_query='API endpoint for policy list',
            limit=5
        )
        print(f'Found {len(results)} results')

asyncio.run(test())
"
```

### Kubernetes Testing

1. Update secret with token:
```bash
kubectl -n womba create secret generic womba-gitlab-creds \
  --from-literal=GITLAB_TOKEN=glpat-xxxxx \
  --from-literal=MCP_GITLAB_TOKEN=glpat-xxxxx \
  --dry-run=client -o yaml | kubectl apply -f -
```

2. Update deployment to use secret
3. Restart pods:
```bash
kubectl -n womba rollout restart deployment/womba-server
```

4. Check logs:
```bash
kubectl -n womba logs -f deployment/womba-server
```

## Troubleshooting

### "MCP not available for semantic code search"

**Cause**: Token not set or MCP disabled
**Fix**: 
- Check `.env` has `GITLAB_TOKEN` and `MCP_GITLAB_TOKEN`
- Check `GITLAB_FALLBACK_ENABLED=true`
- Rebuild Docker: `docker-compose build --no-cache`

### "MCP authentication failed: 403"

**Cause**: Token lacks required scopes
**Fix**:
- Delete old token: https://gitlab.com/-/user_settings/personal_access_tokens
- Create new token with `api`, `read_api`, `mcp` scopes

### "insufficient_scope in error"

**Cause**: Token doesn't have `mcp` scope
**Fix**:
- If `mcp` scope unavailable: use `api` + `read_api`
- Update `.env` and restart

### MCP returns no results

**Cause**: 
- Query not matching code patterns
- Endpoints in wrong format
- Service not in configured group path

**Debug**:
```bash
# Check what MCP sees
docker-compose exec womba-server python -c "
from src.ai.gitlab_fallback_extractor import GitLabFallbackExtractor
import asyncio

async def debug_search():
    extractor = GitLabFallbackExtractor()
    results = await extractor._search_codebase_via_mcp(
        story_key='PROJ-13541',
        story_text='Policy list endpoint with pagination',
        service_queries=['policy', 'list', 'endpoint']
    )
    for r in results[:3]:
        print(r)

asyncio.run(debug_search())
"
```

## Configuration Reference

| Environment Variable | Default | Description |
|---|---|---|
| `GITLAB_TOKEN` | None | GitLab PAT for REST API (OpenAPI fetching) |
| `GITLAB_BASE_URL` | https://gitlab.com | GitLab instance URL |
| `GITLAB_GROUP_PATH` | your-company/services | Group path for service repositories |
| `GITLAB_FALLBACK_ENABLED` | true | Enable MCP fallback extraction |
| `MCP_GITLAB_TOKEN` | None | GitLab PAT for MCP (same as GITLAB_TOKEN) |
| `MCP_GITLAB_SERVER_COMMAND` | npx | MCP server command |
| `MCP_GITLAB_SERVER_ARGS` | JSON array | MCP server command arguments |

## How It's Different from Cursor's MCP Setup

**Cursor's MCP Setup** (via Cursor settings):
- Runs `mcp-remote` locally
- Opens browser for OAuth flow
- Manages tokens automatically
- Uses stdio/HTTP communication

**Womba's MCP Setup** (in Docker):
- Uses **direct HTTP calls** to GitLab API
- No OAuth flow needed - uses **PAT token directly**
- Manual credential management
- No need for `mcp-remote` process running
- Works in containerized environments

## FAQ

**Q: Do I need to run `mcp-remote` separately?**
A: No. Womba makes direct HTTP calls to GitLab's MCP endpoint using your PAT token.

**Q: Is OAuth required?**
A: Only if using `mcp-remote`. Since we use PATs directly, OAuth is **optional**.

**Q: Can I use Cursor's MCP connection in Womba?**
A: Not directly. Womba uses its own `GitLabMCPClient` with HTTP + PAT authentication. Cursor's MCP setup is separate.

**Q: What if I don't have the `mcp` scope?**
A: Use `api` + `read_api` scopes - they provide similar functionality for codebase access.

**Q: Will this work in Kubernetes?**
A: Yes! Just make sure the `MCP_GITLAB_TOKEN` environment variable is set in the pod.

## Next Steps

1. Create a GitLab PAT with `api`, `read_api`, `mcp` scopes
2. Add to `.env`: `GITLAB_TOKEN=glpat-xxxxx` and `MCP_GITLAB_TOKEN=glpat-xxxxx`
3. Rebuild Docker: `docker-compose build --no-cache womba-server`
4. Test with a story that has no normal endpoints extracted
5. Check logs to confirm MCP fallback is working

---

**Need help?** Check:
- `src/ai/gitlab_fallback_extractor.py` - MCP client implementation
- `src/ai/story_enricher.py` - Where MCP is called (lines 88-98)
- Docker logs: `docker-compose logs -f womba-server`

