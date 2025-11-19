#!/bin/bash
# Script to authenticate MCP with GitLab in Kubernetes

NAMESPACE="womba"
POD_NAME=$(kubectl -n $NAMESPACE get pods -o jsonpath='{.items[0].metadata.name}')

if [ -z "$POD_NAME" ]; then
    echo "❌ No pods found in namespace $NAMESPACE"
    exit 1
fi

echo "🔐 MCP Authentication Setup"
echo "=========================="
echo ""
echo "Pod: $POD_NAME"
echo ""

# Check if port-forward is needed
echo "Step 1: Setting up port forwarding for OAuth callback..."
echo ""
echo "⚠️  IMPORTANT: Run this in a SEPARATE terminal and keep it running:"
echo ""
echo "   kubectl -n $NAMESPACE port-forward $POD_NAME 12849:12849"
echo ""
read -p "Press Enter when port-forward is running in another terminal..."

# Trigger MCP to get OAuth URL
echo ""
echo "Step 2: Triggering MCP to get OAuth URL..."
echo "This will attempt to use MCP and show you the OAuth URL"
echo ""

# Try to trigger MCP by enriching a story that needs it
echo "Checking logs for OAuth URL..."
echo ""

# Start following logs in background and trigger MCP
kubectl -n $NAMESPACE logs -f $POD_NAME 2>&1 | grep -i "oauth\|authorize" &
LOG_PID=$!

# Give it a moment
sleep 2

# Try to trigger MCP (this will fail but should show OAuth URL)
kubectl -n $NAMESPACE exec $POD_NAME -- python -c "
import asyncio
from src.ai.gitlab_fallback_extractor import GitLabMCPClient

async def test():
    client = GitLabMCPClient()
    if client.mcp_available:
        print('Testing MCP connection...')
        try:
            results = await client.semantic_code_search(
                project_id='plainid/srv',
                semantic_query='test',
                limit=1
            )
        except Exception as e:
            print(f'Error (expected): {e}')
    else:
        print('MCP not available')

asyncio.run(test())
" 2>&1 || echo "MCP test triggered"

# Wait a bit for logs
sleep 5

# Kill log follower
kill $LOG_PID 2>/dev/null

echo ""
echo "Step 3: Check the logs above for OAuth URL"
echo ""
echo "The URL will look like:"
echo "https://gitlab.com/oauth/authorize?response_type=code&client_id=..."
echo ""
echo "Step 4: Open that URL in your browser and authorize"
echo ""
echo "Step 5: After authorization, MCP token will be cached"
echo ""
echo "To check if authenticated, run:"
echo "kubectl -n $NAMESPACE exec $POD_NAME -- ls -la /home/womba/.mcp-auth/"

