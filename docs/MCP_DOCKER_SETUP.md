# GitLab MCP in Docker - Complete Setup Guide

This guide explains how to set up GitLab MCP with Womba running in Docker.

## Problem Statement

You have Womba running in Docker/Kubernetes and want to enable GitLab MCP for fallback endpoint discovery. Unlike Cursor, Docker containers can't open browsers for OAuth flows, so we use **manual PAT token authentication**.

## Solution Overview

```
Womba in Docker/K8s
    ↓
Generates Test Plan
    ↓
Tries: Swagger/OpenAPI docs
    ↓
If empty: GitLab MCP Fallback
    ↓
HTTP Request to GitLab API
    ↓
Sends PAT Token in PRIVATE-TOKEN header
    ↓
GitLab returns code search results
    ↓
Extract endpoints from code
```

## Step-by-Step Setup

### Step 1: Create GitLab Personal Access Token

**Location**: https://gitlab.com/-/user_settings/personal_access_tokens

**Process**:
1. Click "Add new token"
2. **Name**: `womba-docker-mcp`
3. **Expiration**: 1 year recommended
4. **Scopes** (MUST CHECK ALL):
   - ✅ `api` - Full API access
   - ✅ `read_api` - Read API access
   - ✅ `mcp` - MCP protocol access
   - ✅ `read_repository` - Read repo contents
5. Click "Create personal access token"
6. **COPY THE TOKEN** (shown only once!)

Token format: `glpat-xxxxxxxxxxxxxxxx`

### Step 2: Update Docker Environment

#### Option A: Using `.env` File (Docker Compose)

Edit `.env` in project root:

```bash
# GitLab Configuration
GITLAB_TOKEN=glpat-xxxxxxxxxxxxxxxx        # Paste your token
MCP_GITLAB_TOKEN=glpat-xxxxxxxxxxxxxxxx    # Same token
GITLAB_FALLBACK_ENABLED=true                # Enable MCP fallback
GITLAB_BASE_URL=https://gitlab.com
GITLAB_GROUP_PATH=your-company/services
```

Save the file. Docker will automatically load these when you run `docker-compose up`.

#### Option B: Using Kubernetes Secret

If running in Kubernetes:

```bash
# Create secret with token
kubectl -n womba create secret generic womba-gitlab-creds \
  --from-literal=GITLAB_TOKEN=glpat-xxxxxxxxxxxxxxxx \
  --from-literal=MCP_GITLAB_TOKEN=glpat-xxxxxxxxxxxxxxxx \
  --dry-run=client -o yaml | kubectl apply -f -

# Secret now available as environment variables in pods
```

Update your `womba-server` deployment YAML to use the secret:

```yaml
spec:
  containers:
  - name: womba-server
    env:
    - name: GITLAB_TOKEN
      valueFrom:
        secretKeyRef:
          name: womba-gitlab-creds
          key: GITLAB_TOKEN
    - name: MCP_GITLAB_TOKEN
      valueFrom:
        secretKeyRef:
          name: womba-gitlab-creds
          key: MCP_GITLAB_TOKEN
```

### Step 3: Rebuild Docker Image

The Dockerfile already includes everything needed:
- Node.js and npm (for mcp-remote, optional)
- Python dependencies (including `mcp` and `httpx`)
- MCP auth directory setup

**Rebuild to ensure latest code**:

```bash
cd /Users/royregev/womba
docker-compose build --no-cache womba-server
```

This rebuilds the image and pulls in any new environment variables from `.env`.

### Step 4: Start Womba

```bash
# Start womba-server with MCP support
docker-compose up -d womba-server

# Verify it's running
docker-compose ps

# Check logs for MCP initialization
docker-compose logs womba-server
```

### Step 5: Verify MCP Is Working

#### Check Configuration

```bash
# Print current configuration
docker-compose exec womba-server python -c "
from src.config.settings import settings
print(f'GitLab Token Set: {bool(settings.gitlab_token)}')
print(f'MCP Token Set: {bool(settings.mcp_gitlab_token)}')
print(f'Fallback Enabled: {settings.gitlab_fallback_enabled}')
print(f'Base URL: {settings.gitlab_base_url}')
"
```

#### Run MCP Test

```bash
# Run comprehensive MCP test suite
docker-compose exec womba-server python test_mcp_setup.py
```

Expected output:
```
✓ PASS: Configuration
✓ PASS: MCP Client
✓ PASS: Semantic Search
✓ PASS: GitLab Search
✓ PASS: Fallback Extractor

Total: 5/5 tests passed
✓ All tests passed! GitLab MCP is properly configured.
```

#### Check Logs

```bash
# Monitor logs for MCP activity
docker-compose logs -f womba-server | grep -i "mcp\|fallback"
```

Look for messages like:
```
INFO: Starting GitLab MCP fallback extraction for PROJ-13541
INFO: GitLab MCP client initialized (endpoint: https://gitlab.com/api/v4/mcp)
INFO: Using direct HTTP calls with token authentication (no OAuth needed)
INFO: Semantic code search via GitLab MCP: ...
```

## Testing MCP in Action

### Test 1: Generate Test Plan with Fallback

1. **Go to womba-ui**: http://localhost:3000

2. **Generate test plan** for a story with no Swagger docs:
   ```
   Example: PROJ-13541 (if Swagger doesn't have this endpoint)
   ```

3. **Check logs** to see MCP kick in:
   ```bash
   docker-compose logs womba-server | tail -50
   ```

4. **Verify test plan** includes endpoints found by MCP

### Test 2: Direct API Test

```bash
# Call test generation API directly
curl -X POST http://localhost:8000/api/v1/test-plans \
  -H "Content-Type: application/json" \
  -d '{
    "issue_key": "PROJ-13541",
    "project_key": "PLAT"
  }'
```

Check logs for MCP activity.

### Test 3: Docker Container Test

```bash
# Go inside the container
docker-compose exec womba-server /bin/bash

# Run MCP test script
python test_mcp_setup.py

# Check configuration
cat /app/.env | grep MCP_

# Exit
exit
```

## Troubleshooting Docker MCP Issues

### Issue 1: Token Not Found

**Error**: `MCP not available for semantic code search`

**Debug**:
```bash
# Check if .env exists
ls -la /Users/royregev/womba/.env

# Check if token is in container
docker-compose exec womba-server python -c "
import os
print(f'GITLAB_TOKEN: {os.getenv(\"GITLAB_TOKEN\")}')
print(f'MCP_GITLAB_TOKEN: {os.getenv(\"MCP_GITLAB_TOKEN\")}')
"
```

**Fix**:
```bash
# Update .env
echo "GITLAB_TOKEN=glpat-xxxxx" >> .env
echo "MCP_GITLAB_TOKEN=glpat-xxxxx" >> .env

# Rebuild and restart
docker-compose build --no-cache womba-server
docker-compose up -d womba-server
```

### Issue 2: 403 Forbidden (Token Invalid)

**Error**: `MCP authentication failed: 403`

**Debug**:
```bash
# Test token directly
docker-compose exec womba-server curl -i \
  -H "PRIVATE-TOKEN: glpat-xxxxx" \
  https://gitlab.com/api/v4/user
```

**Fix**:
1. Token expired → Create new token at: https://gitlab.com/-/user_settings/personal_access_tokens
2. Token lacks scopes → Add: `api`, `read_api`, `mcp`, `read_repository`
3. Wrong token → Verify token starts with `glpat-`

### Issue 3: insufficient_scope Error

**Error**: `GitLab token lacks 'mcp' scope`

**Fix**:
```bash
# If 'mcp' scope not available, ensure you have at minimum:
# ✅ api
# ✅ read_api
# ✅ read_repository (for accessing code)

# Create new token with these scopes and update .env
```

### Issue 4: MCP Returns No Results

**Possible Causes**:
1. Endpoints not in configured group (`GITLAB_GROUP_PATH`)
2. Code not matching search query
3. Endpoints in unexpected format

**Debug**:
```bash
# Check what group we're searching
docker-compose exec womba-server python -c "
from src.config.settings import settings
print(f'Searching in: {settings.gitlab_group_path}')
"

# Run semantic search manually
docker-compose exec womba-server python -c "
import asyncio
from src.ai.gitlab_fallback_extractor import GitLabMCPClient

async def test():
    client = GitLabMCPClient()
    results = await client.semantic_code_search(
        project_id='your-company/services',
        semantic_query='policy list endpoint',
        limit=10
    )
    print(f'Found {len(results)} results')
    for r in results[:2]:
        print(r)

asyncio.run(test())
"
```

## Production Deployment Checklist

- [ ] Created GitLab PAT with required scopes (`api`, `read_api`, `mcp`)
- [ ] Added `GITLAB_TOKEN` and `MCP_GITLAB_TOKEN` to `.env` or K8s secret
- [ ] Set `GITLAB_FALLBACK_ENABLED=true` in environment
- [ ] Rebuilt Docker image: `docker-compose build --no-cache womba-server`
- [ ] Restarted womba-server: `docker-compose up -d`
- [ ] Ran MCP test: `docker-compose exec womba-server python test_mcp_setup.py`
- [ ] Generated test plan and verified MCP fallback works
- [ ] Checked logs for no errors: `docker-compose logs womba-server`
- [ ] Token stored securely (not in git, or in K8s secret)

## Monitoring MCP Usage

### Log File Analysis

```bash
# See all MCP-related activity
docker-compose logs womba-server | grep -i "mcp\|fallback\|gitlab"

# Follow logs in real-time
docker-compose logs -f womba-server | grep -i "mcp"

# Count MCP calls
docker-compose logs womba-server | grep -i "starting gitlab mcp fallback" | wc -l
```

### Performance Metrics

MCP fallback typically adds 2-5 seconds to test plan generation:
- Network request to GitLab: 1-2s
- Semantic search processing: 1-3s
- Endpoint extraction: 0.5-1s

This is acceptable since it's only called when normal extraction finds no results.

## Security Considerations

1. **Token Storage**:
   - Local: Stored in `.env` (add to `.gitignore`)
   - Docker: Can be passed via environment variables
   - K8s: Use Kubernetes Secrets (encrypted in etcd)

2. **Token Rotation**:
   - Recommended: Rotate PAT every 90 days
   - Create new token, update `.env` or secret
   - Restart pods/containers

3. **Token Scope**:
   - Limit to necessary scopes only
   - Don't use tokens with `admin` scope
   - Review token usage periodically

4. **Network Security**:
   - All requests to GitLab use HTTPS
   - Token in HTTP header `PRIVATE-TOKEN`
   - Kubernetes secret encryption recommended

## Reference

- Full setup guide: `GITLAB_MCP_README.md`
- Configuration details: `docs/GITLAB_MCP_SETUP.md`
- Test script: `test_mcp_setup.py`
- MCP client code: `src/ai/gitlab_fallback_extractor.py`
- Story enricher: `src/ai/story_enricher.py` (lines 88-98)

