#!/bin/bash

# GitLab MCP Setup Script for Womba
# This script helps configure GitLab MCP with manual PAT credentials

set -e

echo ""
echo "========================================"
echo "GitLab MCP Setup for Womba"
echo "========================================"
echo ""

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "Error: .env file not found"
    echo "Please create .env file first (copy from env.example)"
    exit 1
fi

# Step 1: Get GitLab Token
echo "Step 1: GitLab Personal Access Token (PAT)"
echo "=========================================="
echo ""
echo "You need to create a GitLab PAT with the following scopes:"
echo "  ✓ api           - Full API access"
echo "  ✓ read_api      - Read API access"
echo "  ✓ mcp           - MCP protocol access (if available)"
echo "  ✓ read_repository - Read repository contents"
echo ""
echo "Instructions:"
echo "1. Go to: https://gitlab.com/-/user_settings/personal_access_tokens"
echo "2. Click 'Add new token'"
echo "3. Name: 'womba-mcp'"
echo "4. Select all required scopes above"
echo "5. Copy the token (you won't see it again!)"
echo ""
read -p "Enter your GitLab PAT: " -s GITLAB_TOKEN
echo ""

if [ -z "$GITLAB_TOKEN" ]; then
    echo "Error: No token provided"
    exit 1
fi

# Validate token format
if ! [[ $GITLAB_TOKEN =~ ^glpat- ]]; then
    echo "Warning: Token doesn't start with 'glpat-'"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Step 2: Verify token works
echo ""
echo "Step 2: Verifying Token"
echo "======================="
echo ""
echo "Testing token with GitLab API..."

# Test token (simple API call to verify authentication)
response=$(curl -s -H "PRIVATE-TOKEN: $GITLAB_TOKEN" \
    https://gitlab.com/api/v4/user)

if echo "$response" | grep -q "\"id\""; then
    username=$(echo "$response" | grep -o '"username":"[^"]*"' | cut -d'"' -f4)
    echo "✓ Token verified! Authenticated as: $username"
else
    echo "✗ Token verification failed"
    echo "Response: $response"
    exit 1
fi

# Step 3: Update .env file
echo ""
echo "Step 3: Updating .env"
echo "====================="
echo ""

# Function to update or add env variable
update_env() {
    local key=$1
    local value=$2
    local file=".env"
    
    if grep -q "^$key=" "$file"; then
        # Update existing
        sed -i '' "s|^$key=.*|$key=$value|" "$file"
        echo "  Updated: $key"
    else
        # Add new
        echo "$key=$value" >> "$file"
        echo "  Added: $key"
    fi
}

update_env "GITLAB_TOKEN" "$GITLAB_TOKEN"
update_env "MCP_GITLAB_TOKEN" "$GITLAB_TOKEN"
update_env "GITLAB_FALLBACK_ENABLED" "true"

# Step 4: Verify configuration
echo ""
echo "Step 4: Configuration Summary"
echo "=============================="
echo ""

# Show relevant config
grep -E "GITLAB_|MCP_" .env | grep -v "^#" || true

# Step 5: Test configuration
echo ""
echo "Step 5: Testing MCP Setup"
echo "========================="
echo ""

if command -v python3 &> /dev/null; then
    echo "Running MCP configuration test..."
    python3 test_mcp_setup.py || true
else
    echo "Python 3 not found - skipping test"
fi

# Step 6: Next steps
echo ""
echo "Step 6: Next Steps"
echo "=================="
echo ""
echo "1. Rebuild Docker image:"
echo "   docker-compose build --no-cache womba-server"
echo ""
echo "2. Start womba:"
echo "   docker-compose up -d"
echo ""
echo "3. Check logs:"
echo "   docker-compose logs -f womba-server"
echo ""
echo "4. Test with a story (in womba-ui):"
echo "   - Generate a test plan for a story with no API endpoints"
echo "   - MCP should fall back to codebase search"
echo "   - Check logs: 'Starting GitLab MCP fallback extraction'"
echo ""
echo "✓ Setup complete!"

