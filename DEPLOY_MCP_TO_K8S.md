# Deploy MCP to Kubernetes

## Current Status
❌ MCP code exists in repo but NOT in K8s pod

## Steps to Deploy

### Option 1: Rebuild and Deploy

1. **Build new Docker image:**
   ```bash
   docker build --no-cache -t womba:latest .
   ```

2. **Tag for your registry:**
   ```bash
   docker tag womba:latest your-registry/womba:latest
   ```

3. **Push to registry:**
   ```bash
   docker push your-registry/womba:latest
   ```

4. **Update K8s deployment:**
   ```bash
   kubectl -n womba set image deployment/womba-server womba-server=your-registry/womba:latest
   kubectl -n womba rollout status deployment/womba-server
   ```

5. **Verify MCP code is in pod:**
   ```bash
   kubectl -n womba exec <pod> -- ls -la /app/src/ai/gitlab_fallback_extractor.py
   ```

### Option 2: Update K8s ConfigMap/Secrets

1. **Set MCP environment variables:**
   ```bash
   kubectl -n womba create configmap mcp-config \
     --from-literal=MCP_GITLAB_SERVER_COMMAND=npx \
     --from-literal=MCP_GITLAB_SERVER_ARGS='["-y", "mcp-remote", "https://gitlab.com/api/v4/mcp"]' \
     --from-literal=GITLAB_FALLBACK_ENABLED=true \
     --dry-run=client -o yaml | kubectl apply -f -
   ```

2. **Update deployment to use configmap:**
   ```yaml
   envFrom:
     - configMapRef:
         name: mcp-config
   ```

## After Deployment: Authenticate MCP

1. **Start port-forward for OAuth callback:**
   ```bash
   kubectl -n womba port-forward <pod-name> 12849:12849
   ```
   Keep this running in a separate terminal!

2. **Trigger MCP to get OAuth URL:**
   ```bash
   kubectl -n womba exec <pod> -- python -c "
   import asyncio
   from src.ai.gitlab_fallback_extractor import GitLabMCPClient
   
   async def test():
       client = GitLabMCPClient()
       if client.mcp_available:
           try:
               await client.semantic_code_search('plainid/srv', 'test', limit=1)
           except Exception as e:
               print(f'Will show OAuth URL: {e}')
   
   asyncio.run(test())
   "
   ```

3. **Check logs for OAuth URL:**
   ```bash
   kubectl -n womba logs <pod> | grep -i "authorize\|oauth" | tail -10
   ```

4. **Open URL in browser and authorize**

5. **Verify authentication:**
   ```bash
   kubectl -n womba exec <pod> -- ls -la /home/womba/.mcp-auth/
   ```

## Quick Script

Use `./authenticate_mcp.sh` after deployment is complete.

