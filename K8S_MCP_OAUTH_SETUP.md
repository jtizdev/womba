# MCP OAuth Setup for Kubernetes

## Current Implementation

MCP OAuth cache is stored in: `~/.mcp-auth/` (which resolves to `/home/womba/.mcp-auth/` in the container)

**NEW**: The OAuth cache path is now configurable via `MCP_OAUTH_CACHE_DIR` environment variable for Kubernetes deployments.

## Kubernetes Requirements

For MCP to work in Kubernetes, you need:

### 1. Persistent Volume for OAuth Cache

The OAuth credentials must be persisted across pod restarts. Create a PersistentVolumeClaim:

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: womba-mcp-auth-pvc
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 100Mi  # OAuth cache is small, 100Mi is plenty
```

### 2. Mount PVC in Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: womba-server
spec:
  template:
    spec:
      containers:
      - name: womba-server
        env:
        # Configure OAuth cache path to match PVC mount
        - name: MCP_OAUTH_CACHE_DIR
          value: "/home/womba/.mcp-auth"
        volumeMounts:
        - name: mcp-auth-cache
          mountPath: /home/womba/.mcp-auth
        volumes:
        - name: mcp-auth-cache
          persistentVolumeClaim:
            claimName: womba-mcp-auth-pvc
```

### 3. Initial OAuth Setup (One-Time)

**Option A: Pre-populate from Local Machine (Recommended)**

```bash
# 1. Authenticate locally (if not already done)
python test_mcp_setup.py
# → Browser opens, authorize

# 2. Export OAuth credentials
./export_mcp_oauth.sh
# → Creates mcp-oauth-credentials/ directory

# 3. Copy credentials to K8s pod
kubectl create secret generic mcp-oauth-credentials \
  --from-file=mcp-oauth-credentials/

# 4. In your Deployment, add initContainer to copy credentials:
initContainers:
- name: copy-mcp-auth
  image: plainid/womba:latest
  command: ['sh', '-c', 'cp -r /mcp-oauth/* /home/womba/.mcp-auth/']
  volumeMounts:
  - name: mcp-auth-cache
    mountPath: /home/womba/.mcp-auth
  - name: mcp-oauth-secret
    mountPath: /mcp-oauth
volumes:
- name: mcp-oauth-secret
  secret:
    secretName: mcp-oauth-credentials
```

**Option B: Manual OAuth in K8s (Alternative)**

1. Port-forward to expose OAuth callback:
   ```bash
   kubectl port-forward deployment/womba-server 12849:12849
   ```

2. Trigger MCP call (check logs for OAuth URL):
   ```bash
   kubectl exec -it deployment/womba-server -- womba generate PLAT-13541
   kubectl logs deployment/womba-server | grep -i "oauth\|authorize"
   ```

3. Open OAuth URL in browser, authorize
4. Token will be saved to PVC

### 4. Verify Setup

```bash
# Check if OAuth cache exists in pod
kubectl exec deployment/womba-server -- ls -la /home/womba/.mcp-auth/

# Test MCP
kubectl exec deployment/womba-server -- python -c "
from src.ai.gitlab_fallback_extractor import GitLabMCPClient
import asyncio

async def test():
    client = GitLabMCPClient()
    print(f'MCP Available: {client.mcp_available}')
    print(f'OAuth Cache: {client.oauth_cache_dir}')
    if client.mcp_available:
        results = await client.semantic_code_search(
            project_id='38091458',
            semantic_query='API endpoint',
            limit=3
        )
        print(f'Results: {len(results)}')

asyncio.run(test())
"
```

## Important Notes

1. **OAuth Cache Path**: Currently hardcoded to `Path.home() / ".mcp-auth"` which resolves to `/home/womba/.mcp-auth/` in the container
2. **First-Time Auth**: Browser won't open in K8s, so you must pre-populate credentials OR use port-forward
3. **Token Persistence**: Tokens persist as long as the PVC exists
4. **Token Expiration**: OAuth tokens can expire; if MCP stops working, re-authenticate

## Troubleshooting

**Issue**: "MCP not available" in K8s
- Check: `kubectl exec deployment/womba-server -- which npx`
- Check: `kubectl exec deployment/womba-server -- ls -la /home/womba/.mcp-auth/`
- Solution: Ensure PVC is mounted and credentials exist

**Issue**: OAuth callback fails
- Check: Port 12849 is accessible (may need Service/Ingress)
- Solution: Use pre-populated credentials instead

**Issue**: Token expired
- Solution: Re-authenticate locally, export, and update secret/PVC

