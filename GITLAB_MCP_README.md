# GitLab MCP Implementation in Womba - OAuth Authentication

This guide explains how to use GitLab MCP with Womba using **OAuth authentication** (no manual token management needed).

## Quick Start (OAuth Flow)

### 1. Enable MCP in `.env`

```bash
GITLAB_FALLBACK_ENABLED=true
GITLAB_BASE_URL=https://gitlab.com
GITLAB_GROUP_PATH=plainid/srv
```

### 2. First Run - Browser OAuth Login

When you first generate a test plan or run:
```bash
docker-compose exec womba-server python test_mcp_setup.py
```

**What happens:**
1. Browser automatically opens with GitLab OAuth login
2. Click "Authorize" to grant MCP access
3. OAuth token is **cached locally** in `~/.mcp-auth/`
4. Browser closes automatically

### 3. Subsequent Runs

Your OAuth credentials are cached! No need to log in again:
- ✅ Run multiple test generations
- ✅ Restart container
- ✅ Switch between local/Docker (cache persists)

---

## How OAuth MCP Works

```
First Run:
├─ Womba starts MCP client
├─ Launches: npx -y mcp-remote https://gitlab.com/api/v4/mcp
├─ Browser opens → GitLab OAuth login
├─ User clicks "Authorize"
├─ Token saved to ~/.mcp-auth/
└─ Browser closes automatically

Subsequent Runs:
├─ Womba starts MCP client
├─ Launches: npx -y mcp-remote https://gitlab.com/api/v4/mcp
├─ Reads cached token from ~/.mcp-auth/
├─ Connected immediately ✓
└─ No browser, no user interaction needed
```

---

## Architecture

```
Story Enrichment Flow:
├─ Step 1: Swagger/RAG Extraction
│         └─ Search OpenAPI docs and similar existing tests
├─ Step 2: AI-based Filtering
│         └─ Remove example endpoints that aren't relevant
└─ Step 3: GitLab MCP Fallback (IF no endpoints found)
          ├─ Use mcp-remote via npx
          ├─ OAuth authentication (cached credentials)
          ├─ Semantic code search across repositories
          └─ Extract endpoints from found code
```

---

## Installation & Setup

### Prerequisites

Docker image includes:
- ✅ Node.js 20.x
- ✅ npm (for `mpc-remote`)
- ✅ Python MCP library

### Docker Setup

```bash
# 1. Update .env
cat >> .env << 'EOF'
GITLAB_FALLBACK_ENABLED=true
GITLAB_BASE_URL=https://gitlab.com
GITLAB_GROUP_PATH=plainid/srv
EOF

# 2. Rebuild Docker image
docker-compose build --no-cache womba-server

# 3. Start Womba
docker-compose up -d womba-server

# 4. Generate test plan (will trigger OAuth on first run)
# or run: docker-compose exec womba-server python test_mcp_setup.py
```

### Kubernetes Setup

```bash
# 1. Create ConfigMap with settings
kubectl create configmap womba-mcp-config \
  --from-literal=GITLAB_FALLBACK_ENABLED=true \
  --from-literal=GITLAB_BASE_URL=https://gitlab.com \
  --from-literal=GITLAB_GROUP_PATH=plainid/srv

# 2. Create persistent volume for OAuth cache
# (Ensure ~/.mcp-auth is mounted as PVC)

# 3. Update deployment to use ConfigMap and mount cache volume

# 4. Deploy and trigger first test generation
# (This will initiate OAuth flow - you'll need to manually authenticate)
```

---

## Testing MCP Setup

### Local Test Script

```bash
python test_mcp_setup.py
```

Expected output on first run:
```
======================================
GitLab MCP Setup Validation
======================================

1. Configuration Check
✓ Configuration looks good!

2. MCP Client Initialization
→ Browser will open for GitLab OAuth login
→ Waiting for authentication...
→ [Browser opens, user clicks "Authorize"]
✓ MCP client initialized successfully!

3. Semantic Code Search Test
Searching for 'policy list API endpoint'...
Found 5 results
✓ Semantic search is working!

...

Total: 5/5 tests passed
✓ All tests passed! GitLab MCP is properly configured.
```

### Docker Container Test

```bash
# Run test inside container
docker-compose exec womba-server python test_mcp_setup.py

# Check MCP cache
docker-compose exec womba-server ls -la ~/.mcp-auth/

# Check logs for MCP activity
docker-compose logs womba-server | grep -i "mcp\|oauth"
```

---

## Troubleshooting

### Issue 1: "Browser didn't open for OAuth"

**Cause**: Running in headless environment (Docker, K8s)
**Fix**:
- Authenticate on your local machine first: `python test_mcp_setup.py`
- Copy `~/.mcp-auth/` to the pod/container
- Or: Use `mcp-remote` manually to cache credentials

### Issue 2: "OAuth credentials expired"

**Cause**: Token cached from months ago
**Fix**:
```bash
# Clear cache and re-authenticate
rm -rf ~/.mcp-auth/*
python test_mcp_setup.py  # Will prompt for OAuth again
```

### Issue 3: "MCP not available for semantic code search"

**Cause**: mcp-remote not installed or npx not found
**Fix**:
```bash
# Check if mcp-remote is installed
which mcp-remote

# Check if npx is available
which npx

# In Docker, rebuild to ensure Node.js is included
docker-compose build --no-cache womba-server
```

### Issue 4: "Permission denied" for ~/.mcp-auth/

**Cause**: Directory permission issue
**Fix**:
```bash
# Ensure directory exists and has correct permissions
mkdir -p ~/.mcp-auth
chmod 700 ~/.mcp-auth
```

---

## Using MCP in Docker/Kubernetes

### Local + Docker (with shared cache)

```bash
# 1. Authenticate locally first
python test_mcp_setup.py
# → Browser opens, you click "Authorize"
# → Token saved to ~/.mcp-auth/

# 2. Docker automatically uses cached token
docker-compose up -d womba-server
docker-compose exec womba-server python test_mcp_setup.py
# → Works immediately, no browser needed!
```

### Kubernetes (with PVC for cache)

```yaml
# In your Deployment spec:
spec:
  template:
    spec:
      containers:
      - name: womba-server
        volumeMounts:
        - name: mcp-auth-cache
          mountPath: /home/womba/.mcp-auth
      volumes:
      - name: mcp-auth-cache
        persistentVolumeClaim:
          claimName: womba-mcp-auth-pvc
```

---

## OAuth Flow Details

### What Happens Behind the Scenes

1. **mcp-remote Start**
   ```bash
   npx -y mcp-remote https://gitlab.com/api/v4/mcp
   ```

2. **OAuth Initiation**
   - mcp-remote opens browser to GitLab OAuth endpoint
   - Shows: "Authorize Womba to access your GitLab"

3. **User Authorizes**
   - User clicks "Authorize"
   - GitLab redirects back to local callback

4. **Token Caching**
   - Token saved to `~/.mcp-auth/tokens.json` (encrypted)
   - Refresh tokens stored for auto-renewal

5. **Future Connections**
   - mcp-remote reads cached token
   - Connects immediately without browser

### Security

- ✅ OAuth tokens **never** exposed in logs
- ✅ Tokens **encrypted** in cache directory
- ✅ Only `api` and `read_api` scopes requested
- ✅ No PAT tokens needed (browser login only)

---

## Configuration Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `GITLAB_FALLBACK_ENABLED` | true | Enable MCP fallback |
| `GITLAB_BASE_URL` | https://gitlab.com | GitLab instance |
| `GITLAB_GROUP_PATH` | plainid/srv | Group to search |
| `MCP_GITLAB_SERVER_COMMAND` | npx | Command to run mcp-remote |
| `MCP_GITLAB_SERVER_ARGS` | ["-y", "mcp-remote", "..."] | Args for mcp-remote |

---

## FAQ

**Q: Do I need to set a token?**
A: No! OAuth handles it automatically. Just set `GITLAB_FALLBACK_ENABLED=true`.

**Q: Will the browser open every time?**
A: No, only on first run. Credentials are cached afterward.

**Q: What if I'm in a Docker container?**
A: Authenticate on your local machine first, then Docker uses the cached token.

**Q: How long are OAuth tokens cached?**
A: GitLab OAuth tokens last 2 hours, but refresh tokens renew them automatically.

**Q: Can I use PAT tokens instead?**
A: Yes, but OAuth is simpler and more secure (no token storage needed).

**Q: What scopes does Womba request?**
A: Only `api` and `read_api` - no admin or sensitive scopes.

**Q: Is this secure?**
A: Yes! Tokens are cached encrypted, not stored in `.env` or git.

---

## Next Steps

1. ✅ Add `GITLAB_FALLBACK_ENABLED=true` to `.env`
2. ✅ Rebuild Docker: `docker-compose build --no-cache womba-server`
3. ✅ Start: `docker-compose up -d`
4. ✅ Test: `docker-compose exec womba-server python test_mcp_setup.py`
5. ✅ Authenticate via browser OAuth login
6. ✅ Generate test plans - MCP fallback will work!

---

## References

- mcp-remote: https://github.com/modelcontextprotocol/server-gitlab
- GitLab OAuth: https://docs.gitlab.com/ee/api/oauth2.html
- Full setup guide: `docs/MCP_DOCKER_SETUP.md`
- MCP implementation: `src/ai/gitlab_fallback_extractor.py`
- Story enricher: `src/ai/story_enricher.py` (lines 88-98)
