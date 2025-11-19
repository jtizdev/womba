# Manual MCP OAuth Setup for Docker

This guide shows you how to manually add OAuth credentials to Docker so MCP works without browser authentication.

## Step-by-Step Instructions

### Step 1: Export OAuth Credentials from Local Machine

If you already have OAuth credentials cached locally:

```bash
./export_mcp_oauth.sh
```

This will:
- Copy OAuth cache from `~/.mcp-auth/` to `./mcp-oauth-credentials/`
- Prepare credentials for Docker build

### Step 2: If You Don't Have OAuth Credentials Yet

If you need to create OAuth credentials first:

```bash
# This will open browser for OAuth login
python test_mcp_oauth_signin.py

# After authorizing in browser, export credentials
./export_mcp_oauth.sh
```

### Step 3: Build Docker with Credentials

```bash
# Ensure mcp-oauth-credentials directory exists
mkdir -p mcp-oauth-credentials

# Build Docker image (credentials will be copied into image)
docker compose build
```

### Step 4: Verify in Docker

```bash
# Start container
docker compose up -d

# Check if OAuth credentials are in container
docker compose exec womba ls -la ~/.mcp-auth/

# Test MCP
docker compose exec womba python -c "
from src.ai.gitlab_fallback_extractor import GitLabMCPClient
import asyncio

async def test():
    client = GitLabMCPClient()
    print(f'MCP Available: {client.mcp_available}')
    if client.mcp_available:
        results = await client.semantic_code_search(
            project_id='plainid/srv',
            semantic_query='API endpoint',
            limit=3
        )
        print(f'Results: {len(results)}')

asyncio.run(test())
"
```

## What Gets Copied

The `mcp-oauth-credentials/` directory contains:
- OAuth access tokens
- Client info
- Code verifiers

These are copied into Docker at `/home/womba/.mcp-auth/` during build.

## Troubleshooting

### "mcp-oauth-credentials directory not found"

**Fix:** Run `./export_mcp_oauth.sh` first to export credentials.

### "No OAuth credentials found"

**Fix:** 
1. Run `python test_mcp_oauth_signin.py` to authenticate
2. Authorize in browser
3. Run `./export_mcp_oauth.sh` again

### "MCP still asking for OAuth in Docker"

**Fix:** 
1. Verify credentials copied: `docker compose exec womba ls -la ~/.mcp-auth/`
2. Check permissions: `docker compose exec womba ls -la ~/.mcp-auth/mcp-remote-0.1.30/`
3. Rebuild: `docker compose build --no-cache`

## Files Created

- `mcp-oauth-credentials/` - OAuth credentials directory (DO NOT COMMIT TO GIT)
- `export_mcp_oauth.sh` - Script to export credentials
- `setup_docker_mcp.sh` - Complete setup script

## Security Note

⚠️ **DO NOT COMMIT `mcp-oauth-credentials/` TO GIT!**

Add to `.gitignore`:
```
mcp-oauth-credentials/
```

The credentials contain OAuth tokens that should be kept private.

