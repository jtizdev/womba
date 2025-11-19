# GitLab MCP Configuration for Womba

This guide explains how to configure GitLab MCP (Model Context Protocol) for womba's fallback endpoint extraction feature.

## Overview

Womba uses GitLab MCP for codebase search when no API endpoints are found via normal Swagger/RAG extraction. The GitLab REST API client is only used for OpenAPI file fetching in RAG indexing.

## Configuration Options

### Option 1: Configure via Environment Variables (Recommended for Docker/Production)

Add these to your `.env` file:

```bash
# Enable GitLab fallback
GITLAB_FALLBACK_ENABLED=true

# MCP Server Configuration (using mcp-remote as recommended by DevOps)
# Command to run the MCP server (default: 'npx')
MCP_GITLAB_SERVER_COMMAND=npx

# MCP Server arguments as JSON array
# Using mcp-remote to connect to GitLab's MCP API endpoint
MCP_GITLAB_SERVER_ARGS=["-y", "mcp-remote", "https://gitlab.com/api/v4/mcp"]

# Optional: GitLab token for MCP authentication
# If not set, MCP server may use Cursor's configured token
MCP_GITLAB_TOKEN=your_gitlab_token_here
```

### Option 2: Use Cursor's MCP Configuration (Recommended for Development)

If you're running womba in the same environment as Cursor and have MCP configured in Cursor:

1. **Configure MCP in Cursor:**
   - Open Cursor Settings
   - Navigate to MCP/Extensions settings
   - Add GitLab MCP server configuration

2. **Cursor MCP Configuration Example:**
   ```json
   {
     "mcpServers": {
       "GitLab": {
         "command": "npx",
         "args": [
           "@modelcontextprotocol/server-gitlab"
         ],
         "env": {
           "GITLAB_TOKEN": "your_token_here",
           "GITLAB_BASE_URL": "https://gitlab.com"
         }
       }
     }
   }
   ```

3. **For womba to use Cursor's MCP:**
   - If womba runs in the same process/context as Cursor, it can access the MCP connection
   - Otherwise, configure womba separately using Option 1

### Option 3: Manual MCP Server Setup (Using mcp-remote - Recommended)

1. **mcp-remote is used via npx (no installation needed):**
   - The `-y` flag tells npx to automatically install if not present
   - No global installation required

2. **Configure in womba's `.env` (default configuration):**
   ```bash
   MCP_GITLAB_SERVER_COMMAND=npx
   MCP_GITLAB_SERVER_ARGS=["-y", "mcp-remote", "https://gitlab.com/api/v4/mcp"]
   ```

   This is the default configuration, so you can omit these if using defaults.

## Verification

To verify MCP is working:

1. **Check logs:**
   When womba starts, you should see:
   ```
   GitLab MCP client configured with command: npx
   ```

2. **Test fallback extraction:**
   - Create a story with no explicit API endpoints
   - Run story enrichment
   - Check logs for: `Starting GitLab MCP fallback extraction for PLAT-XXXXX`
   - If MCP is working, you'll see search results

3. **Common Issues:**
   - **"MCP server not configured"**: Set `MCP_GITLAB_SERVER_COMMAND` in `.env`
   - **"MCP client library not available"**: Run `pip install mcp`
   - **"Failed to initialize MCP client"**: Check MCP server command and args are correct
   - **No search results**: Verify GitLab token has access to repositories

## Troubleshooting

### MCP Server Not Starting

- Verify the command exists: `which npx` or check the executable path
- Check MCP server package is installed: `npm list -g @modelcontextprotocol/server-gitlab`
- Review womba logs for MCP initialization errors

### Authentication Issues

- Ensure `MCP_GITLAB_TOKEN` is set and valid
- Or configure token in Cursor's MCP settings
- Token needs access to the GitLab group specified in `GITLAB_GROUP_PATH`

### No Results from MCP Search

- Verify the story key matches branch naming conventions (e.g., `PLAT-13541`)
- Check that repositories in `GITLAB_GROUP_PATH` are accessible
- Review MCP search query logs to see what's being searched

## Architecture Notes

- **GitLab REST API**: Used only for OpenAPI file fetching in RAG indexing (`src/external/gitlab_swagger_fetcher.py`)
- **GitLab MCP**: Used only for fallback endpoint extraction (`src/ai/gitlab_fallback_extractor.py`)
- **Separation**: These are intentionally separate - REST API for file access, MCP for intelligent codebase search

