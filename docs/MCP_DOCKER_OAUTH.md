# MCP OAuth Authentication in Docker

## Overview

`mcp-remote` uses OAuth flow for GitLab authentication. In Docker, we need to:
1. Expose the OAuth callback port
2. Mount the auth cache directory so tokens persist
3. Handle the initial OAuth flow

## Setup

### 1. Initial OAuth Authentication

When you first use MCP in Docker, `mcp-remote` will try to open a browser. Since Docker can't open a browser, you need to:

**Option A: Manual OAuth (Recommended)**
1. Run a test MCP call that will trigger OAuth
2. Check the logs for the OAuth URL
3. Open that URL in your browser on your host machine
4. Complete authentication
5. The token will be cached in the mounted volume

**Option B: Use Host Network (Alternative)**
If you're running Docker on your local machine, you can use host network mode so `mcp-remote` can open your browser:

```yaml
# In docker-compose.yml
network_mode: "host"
```

But this is less secure and not recommended for production.

### 2. Verify Configuration

The Docker setup includes:
- **Port 12849**: Exposed for OAuth callback
- **Volume `womba-mcp-auth`**: Mounted at `/home/womba/.mcp-auth` to persist tokens

### 3. Test OAuth Flow

```bash
# Trigger MCP call (this will start OAuth flow)
docker exec womba-server womba enrich PROJ-13541 --no-cache

# Check logs for OAuth URL
docker logs womba-server | grep -i "authorize\|oauth"

# The URL will look like:
# https://gitlab.com/oauth/authorize?response_type=code&client_id=...
```

### 4. Complete Authentication

1. Copy the OAuth URL from logs
2. Open it in your browser
3. Authorize the application
4. The token will be automatically stored in the mounted volume
5. Future MCP calls will use the cached token

## Troubleshooting

**Issue**: OAuth callback fails
- **Solution**: Ensure port 12849 is accessible from your host machine

**Issue**: Token not persisting
- **Solution**: Check that `womba-mcp-auth` volume is properly mounted

**Issue**: Browser can't open in Docker
- **Solution**: Use manual OAuth flow (Option A above)

## Notes

- Tokens are stored in `/home/womba/.mcp-auth/` inside the container
- This directory is mounted as a Docker volume, so tokens persist across container restarts
- The OAuth callback port (12849) is exposed so GitLab can redirect back to the container

