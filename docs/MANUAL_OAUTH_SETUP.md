# Manual OAuth Token Setup for GitLab MCP

## Quick Method: Personal Access Token (Recommended)

This is the **easiest** way - no OAuth flow needed:

### Steps:

1. **Go to GitLab → Settings → Access Tokens**
   - URL: `https://gitlab.com/-/user_settings/personal_access_tokens`
   - Or: Profile → Preferences → Access Tokens

2. **Create New Token:**
   - Name: `Womba MCP Access`
   - Scopes: Check these boxes:
     - ✅ `mcp` (required for MCP endpoint)
     - ✅ `api` (required for API access)
     - ✅ `read_api` (required for reading API data)
   - Expiration: Set as needed (or leave blank for no expiration)

3. **Copy the Token:**
   - Copy the token immediately (you won't see it again!)

4. **Set in Environment:**
   ```bash
   # In .env file
   GITLAB_TOKEN=glpat-your-token-here
   ```

5. **Restart Container:**
   ```bash
   docker compose restart
   ```

6. **Verify:**
   ```bash
   docker exec womba-server python -c "
   from src.ai.gitlab_fallback_extractor import GitLabMCPClient
   import asyncio
   
   async def test():
       client = GitLabMCPClient()
       if client.mcp_available:
           results = await client.semantic_code_search('plainid/srv', 'test', limit=1)
           print(f'✅ MCP working! Got {len(results)} results')
       else:
           print('❌ MCP not available')
   
   asyncio.run(test())
   "
   ```

## Alternative: Full OAuth Flow (If PAT doesn't work)

If Personal Access Token doesn't work, you can do full OAuth:

### 1. Create OAuth Application

1. Go to GitLab → Settings → Applications
   - URL: `https://gitlab.com/-/user_settings/applications`

2. Create new application:
   - Name: `Womba MCP`
   - Redirect URI: `http://localhost:8000/oauth/callback` (or any URL)
   - Scopes: `mcp`, `api`, `read_api`
   - Click "Save application"

3. **Copy Application ID and Secret**

### 2. Get Authorization URL

```bash
# Build authorization URL
CLIENT_ID="your_application_id"
REDIRECT_URI="http://localhost:8000/oauth/callback"
SCOPE="mcp+api+read_api"
STATE="random_state_string"

AUTH_URL="https://gitlab.com/oauth/authorize?client_id=${CLIENT_ID}&redirect_uri=${REDIRECT_URI}&response_type=code&scope=${SCOPE}&state=${STATE}"

echo "Visit this URL:"
echo $AUTH_URL
```

### 3. Authorize and Get Code

1. Visit the URL in browser
2. Authorize the application
3. You'll be redirected to: `http://localhost:8000/oauth/callback?code=AUTHORIZATION_CODE&state=...`
4. Copy the `code` parameter

### 4. Exchange Code for Token

```bash
# Exchange authorization code for access token
curl -X POST "https://gitlab.com/oauth/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "client_id=${CLIENT_ID}" \
  -d "client_secret=${CLIENT_SECRET}" \
  -d "code=${AUTHORIZATION_CODE}" \
  -d "grant_type=authorization_code" \
  -d "redirect_uri=${REDIRECT_URI}"
```

Response will include:
```json
{
  "access_token": "your_oauth_access_token",
  "token_type": "Bearer",
  "expires_in": 7200,
  "refresh_token": "..."
}
```

### 5. Use OAuth Token

```bash
# In .env file
GITLAB_TOKEN=your_oauth_access_token
```

## For Kubernetes

### Option 1: Update Secret

```bash
# Create/update secret with token
kubectl -n womba create secret generic gitlab-token \
  --from-literal=GITLAB_TOKEN=your_token_here \
  --dry-run=client -o yaml | kubectl apply -f -
```

### Option 2: Update ConfigMap/Deployment

Add to your deployment YAML:
```yaml
env:
  - name: GITLAB_TOKEN
    valueFrom:
      secretKeyRef:
        name: gitlab-token
        key: GITLAB_TOKEN
```

## Verification

Test that MCP works:

```bash
# Local Docker
docker exec womba-server python -c "
import asyncio
from src.ai.gitlab_fallback_extractor import GitLabMCPClient

async def test():
    client = GitLabMCPClient()
    print(f'MCP Available: {client.mcp_available}')
    if client.mcp_available:
        results = await client.semantic_code_search('plainid/srv', 'API endpoint', limit=1)
        print(f'✅ Success! Got {len(results)} results')
    else:
        print('❌ MCP not available')

asyncio.run(test())
"
```

## Troubleshooting

**Error: "insufficient_scope"**
- Token doesn't have `mcp` scope
- Create new token with `mcp` scope

**Error: "401 Unauthorized"**
- Token is invalid or expired
- Generate new token

**Error: "403 Forbidden"**
- Token doesn't have required scopes
- Check token has: `mcp`, `api`, `read_api`

