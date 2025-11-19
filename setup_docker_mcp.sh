#!/bin/bash
# Setup script to export OAuth credentials and prepare Docker build

set -e

echo "=========================================="
echo "Docker MCP OAuth Setup"
echo "=========================================="
echo ""

# Step 1: Export OAuth credentials
echo "Step 1: Exporting OAuth credentials..."
if [ -f "./export_mcp_oauth.sh" ]; then
    chmod +x ./export_mcp_oauth.sh
    ./export_mcp_oauth.sh
else
    echo "❌ export_mcp_oauth.sh not found!"
    exit 1
fi

echo ""
echo "Step 2: Verifying credentials exported..."
# Ensure directory exists even if empty (for Docker COPY)
mkdir -p ./mcp-oauth-credentials

if [ -d "./mcp-oauth-credentials" ] && [ "$(ls -A ./mcp-oauth-credentials 2>/dev/null)" ]; then
    echo "✅ OAuth credentials exported successfully"
    echo ""
    echo "Files ready for Docker:"
    ls -la ./mcp-oauth-credentials/
    echo ""
    echo "Step 3: Ready to build Docker!"
    echo ""
    echo "Run: docker compose build"
    echo ""
    echo "The OAuth credentials will be copied into the Docker image"
    echo "and MCP will work without needing browser authentication."
else
    echo "⚠️  No OAuth credentials found!"
    echo ""
    echo "To create OAuth credentials:"
    echo "  1. Run: python test_mcp_oauth_signin.py"
    echo "  2. Authorize in browser when it opens"
    echo "  3. Run this script again: ./setup_docker_mcp.sh"
    exit 1
fi

