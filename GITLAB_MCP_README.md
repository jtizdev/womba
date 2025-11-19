# GitLab MCP Implementation in Womba

## Quick Start

### 1. Create GitLab Personal Access Token (PAT)

**Why**: Womba needs a token to authenticate with GitLab's MCP endpoint for semantic code search.

**Steps**:
1. Visit: https://gitlab.com/-/user_settings/personal_access_tokens
2. Click "Add new token"
3. Fill in:
   - **Name**: `womba-mcp`
   - **Expiration date**: 1 year (or your preference)
4. **Select these scopes**:
   - ✅ `api` - Full API access
   - ✅ `read_api` - Read API access
   - ✅ `mcp` - MCP protocol access (if available)
   - ✅ `read_repository` - Read repository contents
5. Click "Create personal access token"
6. **Copy the token immediately** (you won't see it again!)

### 2. Update `.env` File

Add/update these variables:

```bash
GITLAB_TOKEN=glpat-xxxxxxxxxxxxxxxx        # Your PAT (for REST API)
MCP_GITLAB_TOKEN=glpat-xxxxxxxxxxxxxxxx    # Same PAT (for MCP)
GITLAB_FALLBACK_ENABLED=true                # Enable fallback
```

### 3. Rebuild Docker

```bash
cd /Users/royregev/womba
docker-compose build --no-cache womba-server
docker-compose up -d
```

### 4. Test It

```bash
# Option A: Run test script
python test_mcp_setup.py

# Option B: Check Docker logs
docker-compose logs -f womba-server | grep -i mcp

# Option C: Generate test plan for story with no normal endpoints
# (Go to womba-ui and generate a test plan - MCP should kick in as fallback)
```

---

## How It Works

### Architecture

```
Story Enrichment Flow:
├─ Step 1: Swagger/RAG Extraction
│         └─ Search OpenAPI docs and similar existing tests
├─ Step 2: AI-based Filtering
│         └─ Remove example endpoints that aren't relevant
└─ Step 3: GitLab MCP Fallback (IF no endpoints found)
          └─ Semantic code search across repositories
          └─ Extract endpoints from found code
```

### Why This Design?

1. **Swagger first**: Explicit API documentation is most reliable
2. **RAG second**: Learn from existing tests and patterns
3. **MCP fallback**: If endpoints aren't documented, search the code
4. **Semantic search**: Uses AI to understand code, not just regex

---

## What's Different from Cursor's MCP?

| Aspect | Cursor's MCP | Womba's MCP |
|--------|--------------|------------|
| **Protocol** | stdio/HTTP | Direct HTTP calls |
| **Auth** | OAuth (browser flow) | PAT token (no OAuth needed) |
| **Setup** | Click "Enable MCP" in settings | Add env vars, rebuild Docker |
| **Works in Docker** | ❌ No (needs browser) | ✅ Yes (uses PAT directly) |
| **Works in K8s** | ❌ No (needs browser) | ✅ Yes (set env var in pod) |
| **mcp-remote needed** | ✅ Yes | ❌ No (direct HTTP) |

**Key advantage**: Womba's approach works everywhere - local, Docker, Kubernetes - without needing a browser for OAuth.

---

## Configuration Reference

### Environment Variables

```bash
# Required for MCP to work
GITLAB_TOKEN=glpat-...                  # Token for REST API (OpenAPI fetching)
MCP_GITLAB_TOKEN=glpat-...              # Token for MCP (same as above)

# Optional (defaults shown)
GITLAB_BASE_URL=https://gitlab.com
GITLAB_GROUP_PATH=plainid/srv
GITLAB_FALLBACK_ENABLED=true
GITLAB_FALLBACK_MAX_SERVICES=5

# Not needed (for reference only)
MCP_GITLAB_SERVER_COMMAND=npx           # Womba doesn't use this
MCP_GITLAB_SERVER_ARGS=[...]            # Womba doesn't use this
```

### Code Implementation

**Entry point**: `src/ai/story_enricher.py` lines 88-98
- Calls `GitLabFallbackExtractor.extract_from_codebase()`
- Only triggered if zero endpoints found after filtering

**MCP Client**: `src/ai/gitlab_fallback_extractor.py`
- `GitLabMCPClient`: Handles HTTP communication with GitLab API
- `GitLabFallbackExtractor`: Orchestrates codebase search

---

## Troubleshooting

### Issue: "MCP not available for semantic code search"

**Cause**: Token not configured
**Fix**:
```bash
# Check .env has both tokens
grep GITLAB_TOKEN .env
grep MCP_GITLAB_TOKEN .env

# Rebuild Docker
docker-compose build --no-cache womba-server
```

### Issue: "MCP authentication failed: 403"

**Cause**: Token lacks required scopes
**Fix**:
```bash
# 1. Delete old token: https://gitlab.com/-/user_settings/personal_access_tokens
# 2. Create new token with scopes: api, read_api, mcp, read_repository
# 3. Update .env with new token
# 4. Rebuild: docker-compose build --no-cache womba-server
```

### Issue: "insufficient_scope in error"

**Cause**: Token doesn't have `mcp` scope
**Fix**:
- If `mcp` scope not available in GitLab: use `api` + `read_api` (they work similarly)
- Ensure token has at least these three scopes:
  - ✅ `api`
  - ✅ `read_api`
  - ✅ `mcp` (optional, but recommended)

### Issue: MCP returns no results

**Cause**: Query not matching code, or endpoints in wrong format
**Debug**:
```bash
# Check what MCP is searching
docker-compose exec womba-server python test_mcp_setup.py

# Check Docker logs for search queries
docker-compose logs womba-server | grep "semantic query"
```

### Issue: "Token doesn't start with glpat-"

**Cause**: Using wrong token format
**Fix**:
- Ensure you're using a Personal Access Token (glpat-*)
- Not OAuth token or CI/CD token

---

## Testing MCP Setup

### Local Testing (Before Docker)

```bash
# Set up .env with token
export GITLAB_TOKEN=glpat-xxxxx
export MCP_GITLAB_TOKEN=glpat-xxxxx

# Run test script
python test_mcp_setup.py
```

### Docker Testing

```bash
# Build and start
docker-compose build --no-cache womba-server
docker-compose up -d womba-server

# Run tests inside container
docker-compose exec womba-server python test_mcp_setup.py

# Check logs
docker-compose logs -f womba-server
```

### Kubernetes Testing

```bash
# Create secret with token
kubectl -n womba create secret generic womba-gitlab-creds \
  --from-literal=GITLAB_TOKEN=glpat-xxxxx \
  --from-literal=MCP_GITLAB_TOKEN=glpat-xxxxx \
  --dry-run=client -o yaml | kubectl apply -f -

# Update deployment to use secret (in K8s yaml)
# env:
# - name: GITLAB_TOKEN
#   valueFrom:
#     secretKeyRef:
#       name: womba-gitlab-creds
#       key: GITLAB_TOKEN

# Restart pods
kubectl -n womba rollout restart deployment/womba-server

# Check logs
kubectl -n womba logs -f deployment/womba-server
```

---

## How to Use Womba with MCP

### Example: Generate Test Plan with Fallback

1. **Create a story** in Jira (e.g., "Add pagination to policies endpoint")

2. **Generate test plan** in womba-ui:
   ```
   Story: PLAT-13541
   Generate → Wait for analysis
   ```

3. **Womba's process**:
   - Step 1: Tries to find OpenAPI for policies endpoint → Success
   - Step 2: Filters to remove examples
   - Step 3: Generates tests from swagger
   
   **OR** (if Step 1 finds nothing):
   - Step 1: No swagger docs found
   - Step 2: Skipped (no endpoints)
   - Step 3: Uses GitLab MCP to search codebase
   - Step 4: Finds policy endpoint in code
   - Step 5: Generates tests from found endpoints

4. **Check logs** to see what MCP found:
   ```bash
   docker-compose logs womba-server | grep -i "gitlab.*fallback"
   ```

---

## Automatic vs. Manual Token Setup

### Automatic (Cursor's MCP)
- User clicks "Enable MCP" in Cursor settings
- Browser opens for OAuth authentication
- Token managed automatically by Cursor
- **Problem**: Doesn't work in Docker/Kubernetes

### Manual (Womba's MCP)
- DevOps creates PAT in GitLab
- Token stored in `.env` or Kubernetes secret
- Womba uses token directly
- **Advantage**: Works everywhere

Your DevOps recommended the **manual approach**, which is why this implementation uses PAT tokens instead of OAuth.

---

## Common Questions

**Q: Do I need to run mcp-remote separately?**
A: No. Womba makes direct HTTP calls to GitLab's API. mcp-remote is optional.

**Q: Why use MCP if we have Swagger?**
A: As a fallback! Some endpoints might not be documented in Swagger but exist in code.

**Q: Will this increase costs?**
A: No. Uses existing GitLab API quota. No additional services to pay for.

**Q: Is the token exposed?**
A: No. It's stored in `.env` (not committed to git) or Kubernetes secret (encrypted in cluster).

**Q: How often does MCP get called?**
A: Only when normal endpoint extraction finds zero results. Very efficient.

**Q: Can I disable MCP?**
A: Yes: `GITLAB_FALLBACK_ENABLED=false` in `.env`

---

## Next Steps

1. ✅ Create GitLab PAT with required scopes
2. ✅ Add `GITLAB_TOKEN` and `MCP_GITLAB_TOKEN` to `.env`
3. ✅ Rebuild Docker: `docker-compose build --no-cache womba-server`
4. ✅ Start womba: `docker-compose up -d`
5. ✅ Test: `python test_mcp_setup.py`
6. ✅ Generate test plans and observe MCP fallback in logs

---

## Support & Debugging

**Still having issues?**

Check these files for implementation details:
- `src/ai/gitlab_fallback_extractor.py` - MCP client code
- `src/ai/story_enricher.py` - Where MCP is called
- `src/config/settings.py` - Configuration handling
- `test_mcp_setup.py` - Comprehensive test script

**Logs to check**:
```bash
# Docker
docker-compose logs womba-server | grep -i "mcp\|fallback\|gitlab"

# Kubernetes
kubectl -n womba logs deployment/womba-server | grep -i "mcp\|fallback\|gitlab"
```

**Error messages to look for**:
- "MCP not available" → Token not set
- "insufficient_scope" → Token needs better scopes
- "MCP authentication failed: 403" → Token invalid or expired
- "No endpoints found via MCP" → Code doesn't match search query

---

## References

- GitLab Personal Access Tokens: https://docs.gitlab.com/ee/user/profile/personal_access_tokens.html
- GitLab MCP: https://docs.gitlab.com/ee/api/graphql/
- Womba MCP Docs: `docs/GITLAB_MCP_SETUP.md`

