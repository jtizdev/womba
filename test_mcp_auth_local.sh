#!/bin/bash
# Test MCP authentication locally in Docker

echo "🔐 MCP Authentication Test (Local Docker)"
echo "========================================"
echo ""

# Check if container is running
if ! docker ps | grep -q womba-server; then
    echo "❌ womba-server container not running"
    echo "   Start it with: docker compose up -d"
    exit 1
fi

echo "✅ Container is running"
echo ""

# Check if MCP code exists
if ! docker exec womba-server ls /app/src/ai/gitlab_fallback_extractor.py > /dev/null 2>&1; then
    echo "❌ MCP code not found in container"
    echo "   Rebuild with: docker build --no-cache -t womba:latest ."
    exit 1
fi

echo "✅ MCP code found"
echo ""

# Port 12849 should be exposed in docker-compose.yml
echo "📡 OAuth callback port 12849 should be exposed"
echo "   (Check docker-compose.yml ports section)"
echo ""

# Test MCP client
echo "🧪 Testing MCP client..."
docker exec womba-server python -c "
import asyncio
from src.ai.gitlab_fallback_extractor import GitLabMCPClient

async def test():
    client = GitLabMCPClient()
    print(f'MCP Available: {client.mcp_available}')
    
    if not client.mcp_available:
        print('❌ MCP not available')
        return
    
    if not client.server_params:
        print('❌ MCP server params not configured')
        return
    
    print('✅ MCP configured correctly')
    print(f'   Command: {client.server_params.command}')
    print(f'   Args: {client.server_params.args}')
    print()
    print('🔍 Attempting MCP call (this will trigger OAuth if not authenticated)...')
    
    try:
        results = await client.semantic_code_search(
            project_id='plainid/srv',
            semantic_query='API endpoint for policies',
            limit=1
        )
        print(f'✅ MCP call succeeded! Got {len(results)} results')
    except Exception as e:
        error_msg = str(e)
        if 'oauth' in error_msg.lower() or 'authorize' in error_msg.lower():
            print('⚠️  OAuth authentication needed')
            print('   Check logs for OAuth URL:')
            print('   docker logs womba-server | grep -i oauth')
        else:
            print(f'❌ Error: {e}')

asyncio.run(test())
" 2>&1

echo ""
echo "📋 Next Steps:"
echo "   1. Check logs for OAuth URL:"
echo "      docker logs womba-server | grep -i 'authorize\|oauth' | tail -10"
echo ""
echo "   2. Open the OAuth URL in your browser"
echo ""
echo "   3. Authorize the application"
echo ""
echo "   4. Verify authentication:"
echo "      docker exec womba-server ls -la /home/womba/.mcp-auth/"

