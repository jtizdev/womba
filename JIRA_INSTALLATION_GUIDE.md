# Womba Jira Cloud App - Installation Guide

## Overview

Womba is now a **Jira Cloud Connect app** that can be installed directly into your Jira instance! This allows you to generate AI-powered test plans directly from Jira issues without leaving your browser.

## Features

✅ **Issue Panel Integration** - Generate tests directly from any Jira issue  
✅ **Test Count Badge** - See test coverage at a glance on every issue  
✅ **Admin Configuration** - Centralized API key management  
✅ **Test Manager** - Bulk operations and history tracking  
✅ **Automatic Zephyr Integration** - Tests upload directly to Zephyr Scale  
✅ **RAG-Powered Context** - Leverages existing tests and documentation

## Prerequisites

1. **Jira Cloud instance** with admin access
2. **Render deployment** of Womba running at `https://womba.onrender.com` (or your custom URL)
3. **API Keys** ready:
   - OpenAI API key (for AI generation)
   - Zephyr Scale API token (for test upload)
   - Atlassian API token (for Jira/Confluence access)

## Installation Steps

### Step 1: Enable Development Mode (For Testing)

If you're installing from a custom URL (not the Atlassian Marketplace):

1. Go to your Jira instance: `https://your-domain.atlassian.net`
2. Click **⚙️ Settings** (gear icon in top-right)
3. Select **Apps** → **Manage apps**
4. Click **Settings** at the bottom of the left sidebar
5. Enable **"Development mode"**
6. Click **Apply**

> **Note:** Development mode allows installing apps from any URL. Disable this in production if using Marketplace version.

### Step 2: Install Womba from URL

1. Still in **Manage apps**, click **Upload app** in the top-right
2. In the popup, paste the app descriptor URL:
   ```
   https://womba.onrender.com/atlassian-connect.json
   ```
3. Click **Upload**
4. Wait 5-10 seconds for Jira to verify and install the app
5. You should see **"Womba - AI Test Generator"** appear in your apps list

> **Troubleshooting:**  
> - If installation fails, check that Render is running and accessible
> - Verify the descriptor URL is correct: `https://womba.onrender.com/atlassian-connect.json`
> - Check browser console for any errors

### Step 3: Configure API Keys

After installation, you need to configure your API keys:

1. Go to **⚙️ Settings** → **Apps** → **Manage apps**
2. Find **"Womba - AI Test Generator"** in the list
3. Click **Configure** (or go to **⚙️ Settings** → **Apps** → **Womba Configuration**)
4. Enter your API keys:
   - **OpenAI API Key**: `sk-...` (from platform.openai.com)
   - **Zephyr API Token**: From Zephyr Scale settings
   - **Atlassian API Token**: From id.atlassian.com/manage-profile/security/api-tokens
5. Click **Save Configuration**

### Step 4: Verify Installation

Test that everything is working:

1. **Open any Jira issue** (Story, Task, Bug, etc.)
2. Look at the **right sidebar** - you should see the **"Womba Test Generator"** panel
3. The panel should show:
   - Issue key
   - "Generate Tests" button
   - Current test count (if any)

If you see the panel, **congratulations! Womba is successfully installed! 🎉**

## Using Womba

### Generate Tests from an Issue

1. **Open any Jira issue** you want to create tests for
2. In the **Womba panel** on the right sidebar:
   - Click **"Generate Tests"**
   - Wait 10-30 seconds while AI analyzes the story
   - Review the generated test cases
   - Tests are automatically uploaded to Zephyr (if configured)

### Access Test Manager

For bulk operations and history:

1. Click **"Womba Test Manager"** in Jira's top navigation bar
2. From here you can:
   - Generate tests for multiple stories
   - View test generation history
   - Manage RAG data sources
   - Search existing tests

### Admin Configuration

Jira admins can access advanced settings:

1. Go to **⚙️ Settings** → **Apps** → **Womba Configuration**
2. Configure:
   - API keys and tokens
   - Data sources (Jira, Confluence, Figma)
   - RAG settings
   - Auto-generation rules

## Environment Variables

For your Render deployment, configure these environment variables:

```bash
# Required
WOMBA_BASE_URL=https://womba.onrender.com
OPENAI_API_KEY=sk-...
ATLASSIAN_BASE_URL=https://your-domain.atlassian.net
ATLASSIAN_EMAIL=your-email@company.com
ATLASSIAN_API_TOKEN=your-atlassian-token

# Optional
ZEPHYR_API_TOKEN=your-zephyr-token
ANTHROPIC_API_KEY=sk-ant-...  # Alternative to OpenAI
FIGMA_API_TOKEN=...  # If using Figma designs
```

## Security Notes

🔒 **JWT Authentication**: All communication between Jira and Womba is secured with JWT tokens  
🔒 **Shared Secrets**: Each Jira instance gets a unique shared secret for token signing  
🔒 **HTTPS Required**: Jira Cloud only communicates over HTTPS (Render provides this)  
🔒 **Scoped Permissions**: Womba only requests necessary permissions (READ, WRITE for issues)

## Uninstallation

To remove Womba from your Jira instance:

1. Go to **⚙️ Settings** → **Apps** → **Manage apps**
2. Find **"Womba - AI Test Generator"**
3. Click the **⋮** menu → **Uninstall**
4. Confirm uninstallation

> **Note:** Uninstalling will remove Womba's access but won't delete any tests already created in Zephyr.

## Troubleshooting

### "App descriptor could not be loaded"

- Check that Render is running: visit `https://womba.onrender.com/health`
- Verify the descriptor URL is accessible: `https://womba.onrender.com/atlassian-connect.json`
- Ensure your Render app has no recent crashes

### "Unable to authenticate"

- Check that API keys are configured correctly in Womba Configuration
- Verify Atlassian API token has necessary permissions
- Re-save configuration to refresh tokens

### Panel doesn't appear on issues

- Refresh the browser page (Ctrl+R / Cmd+R)
- Check that the app is **Enabled** in Manage apps
- Clear browser cache and cookies
- Try opening a different issue

### Tests not uploading to Zephyr

- Verify Zephyr API token is correct
- Check that project exists in Zephyr
- Ensure you have Zephyr Scale installed in Jira
- Check Render logs for error messages

## Support

For issues or questions:

1. Check Render logs for error messages
2. Visit the Womba repository
3. Contact your Jira administrator
4. File an issue on GitHub

## Production Deployment (Atlassian Marketplace)

For production deployments:

1. Package the app with proper icons and assets
2. Test thoroughly in development mode
3. Submit to Atlassian Marketplace for review
4. Users can install directly from Marketplace
5. No need for development mode

---

**Version**: 0.1.0  
**Last Updated**: January 2025  
**Supported Platforms**: Jira Cloud  
**Requirements**: Python 3.12+, FastAPI, JWT authentication

