#!/bin/bash
# Helper script to set up MCP token

echo "🔐 GitLab MCP Token Setup"
echo "========================"
echo ""

echo "Step 1: Create GitLab Personal Access Token"
echo "--------------------------------------------"
echo ""
echo "Visit: https://gitlab.com/-/user_settings/personal_access_tokens"
echo ""
echo "Required scopes:"
echo "  ✅ mcp"
echo "  ✅ api"
echo "  ✅ read_api"
echo ""
read -p "Press Enter when you have the token..."

echo ""
echo "Step 2: Enter your token"
echo "------------------------"
read -p "Paste your GitLab token: " GITLAB_TOKEN

if [ -z "$GITLAB_TOKEN" ]; then
    echo "❌ Token is empty"
    exit 1
fi

echo ""
echo "Step 3: Update .env file"
echo "------------------------"

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found. Creating from env.example..."
    cp env.example .env
fi

# Update or add GITLAB_TOKEN
if grep -q "^GITLAB_TOKEN=" .env; then
    # Update existing
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        sed -i '' "s|^GITLAB_TOKEN=.*|GITLAB_TOKEN=$GITLAB_TOKEN|" .env
    else
        # Linux
        sed -i "s|^GITLAB_TOKEN=.*|GITLAB_TOKEN=$GITLAB_TOKEN|" .env
    fi
    echo "✅ Updated GITLAB_TOKEN in .env"
else
    # Add new
    echo "" >> .env
    echo "# GitLab MCP Token" >> .env
    echo "GITLAB_TOKEN=$GITLAB_TOKEN" >> .env
    echo "✅ Added GITLAB_TOKEN to .env"
fi

echo ""
echo "Step 4: Restart container"
echo "-------------------------"
read -p "Restart Docker container now? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    docker compose restart
    echo "✅ Container restarted"
fi

echo ""
echo "Step 5: Test MCP"
echo "----------------"
read -p "Test MCP connection now? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    docker exec womba-server python -c "
import asyncio
from src.ai.gitlab_fallback_extractor import GitLabMCPClient

async def test():
    client = GitLabMCPClient()
    print(f'MCP Available: {client.mcp_available}')
    if client.mcp_available:
        print('Testing connection...')
        try:
            results = await client.semantic_code_search('plainid/srv', 'test', limit=1)
            print(f'✅ MCP working! Got {len(results)} results')
        except Exception as e:
            error = str(e)
            if 'insufficient_scope' in error.lower():
                print('❌ Token lacks mcp scope - create new token with mcp scope')
            else:
                print(f'⚠️  Error: {error}')
    else:
        print('❌ MCP not available')

asyncio.run(test())
" 2>&1
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "If MCP is working, you're all set!"
echo "If not, check the error message above."

