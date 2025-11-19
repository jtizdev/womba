#!/bin/bash
# Export MCP OAuth credentials for Docker

set -e

echo "=========================================="
echo "Export MCP OAuth Credentials for Docker"
echo "=========================================="
echo ""

OAUTH_CACHE="$HOME/.mcp-auth"
EXPORT_DIR="./mcp-oauth-credentials"

if [ ! -d "$OAUTH_CACHE" ]; then
    echo "❌ OAuth cache not found at: $OAUTH_CACHE"
    echo ""
    echo "To create OAuth credentials:"
    echo "  1. Run: python test_mcp_oauth_signin.py"
    echo "  2. Authorize in browser when it opens"
    echo "  3. Run this script again"
    exit 1
fi

echo "Found OAuth cache at: $OAUTH_CACHE"
echo ""

# Create export directory
mkdir -p "$EXPORT_DIR"
rm -rf "$EXPORT_DIR"/*

# Copy OAuth cache
echo "Copying OAuth credentials..."
cp -r "$OAUTH_CACHE"/* "$EXPORT_DIR/"

echo "✅ OAuth credentials exported to: $EXPORT_DIR"
echo ""
echo "Files exported:"
ls -la "$EXPORT_DIR"
echo ""
echo "Next steps:"
echo "  1. Review the exported credentials"
echo "  2. Build Docker with: docker compose build"
echo "  3. Credentials will be copied into Docker image"
echo ""

