# Setup Guide for Womba

This guide will help you set up Womba for development or production use.

## Prerequisites

- Python 3.11 or higher
- PostgreSQL 14+ (for production) or SQLite (for development)
- Git
- Access to:
  - Jira Cloud instance
  - Zephyr Scale subscription
  - GitHub/GitLab account
  - Anthropic API (Claude)

## Step-by-Step Setup

### 1. Clone and Install Dependencies

```bash
# Clone the repository
git clone https://github.com/yourusername/womba.git
cd womba

# Create a virtual environment
python -m venv venv

# Activate the virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Copy the example environment file:

```bash
cp .env.example .env
```

Now edit `.env` with your actual credentials:

#### AI Provider Keys

**Anthropic (Claude) API Key:**
1. Go to https://console.anthropic.com/
2. Create an account or sign in
3. Navigate to "API Keys"
4. Create a new API key
5. Copy the key and set `ANTHROPIC_API_KEY` in `.env`

#### Atlassian (Jira) Configuration

**Atlassian Base URL:**
- This is your Atlassian Cloud URL (e.g., `https://yourcompany.atlassian.net`)
- Set `ATLASSIAN_BASE_URL` in `.env`

**Atlassian API Token:**
1. Go to https://id.atlassian.com/manage-profile/security/api-tokens
2. Click "Create API token"
3. Give it a name (e.g., "Womba Integration")
4. Copy the token immediately (you won't see it again)
5. Set `ATLASSIAN_API_TOKEN` in `.env`
6. Set `ATLASSIAN_EMAIL` to your Atlassian account email

**Required Jira Permissions:**
- Browse Projects
- View Issues
- Create Issues
- Edit Issues
- Link Issues

#### Zephyr Scale Configuration

**Zephyr Scale API Key:**

For Zephyr Scale Cloud:
1. Log into Jira
2. Go to Apps → Zephyr Scale → API Access Tokens
3. Click "Create Access Token"
4. Give it a name and select appropriate scopes:
   - Read test cases
   - Write test cases
   - Link test cases
5. Copy the token
6. Set `ZEPHYR_API_KEY` in `.env`

#### GitHub Personal Access Token

**Create GitHub PAT:**
1. Go to https://github.com/settings/tokens
2. Click "Generate new token" → "Generate new token (classic)"
3. Give it a name (e.g., "Womba Test Automation")
4. Select scopes:
   - `repo` (Full control of private repositories)
   - `write:packages` (if using GitHub Packages)
5. Click "Generate token"
6. Copy the token immediately
7. Set `GITHUB_TOKEN` in `.env`

**Required GitHub Permissions:**
- Read repository content
- Write repository content
- Create pull requests
- Create branches

#### Optional: Figma API Token

If you want to integrate with Figma designs:

1. Go to https://www.figma.com/developers/api#access-tokens
2. Generate a personal access token
3. Set `FIGMA_API_TOKEN` in `.env`
4. Set `ENABLE_FIGMA_INTEGRATION=true` in `.env`

### 3. Database Setup

**For Development (SQLite):**

No additional setup needed. SQLite will create a file automatically.

**For Production (PostgreSQL):**

```bash
# Install PostgreSQL (if not already installed)
# On macOS:
brew install postgresql

# Create database
createdb womba

# Update DATABASE_URL in .env
DATABASE_URL=postgresql://username:password@localhost:5432/womba
```

Run migrations:

```bash
alembic upgrade head
```

### 4. Verify Configuration

Test that everything is configured correctly:

```bash
# Test API keys and connections
python -m pytest tests/integration/test_configuration.py -v
```

### 5. Run the Application

**Development Mode:**

```bash
uvicorn src.api.main:app --reload --port 8000
```

**Production Mode:**

```bash
uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --workers 4
```

Visit http://localhost:8000/docs to see the API documentation.

### 6. Test the Setup

**Test Jira Integration:**

```bash
curl -X GET "http://localhost:8000/api/v1/stories/YOURPROJECT-123" \
  -H "Content-Type: application/json"
```

**Generate a Test Plan:**

```bash
curl -X POST "http://localhost:8000/api/v1/test-plans/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "issue_key": "YOURPROJECT-123",
    "upload_to_zephyr": false
  }'
```

## Configuration for Your Repository

To use the automated test code generation feature with your repository:

1. **Grant Repository Access:**
   - For GitHub: Add the GitHub PAT with repo access
   - Ensure the token has permission to create branches and PRs

2. **Repository Structure:**
   - Womba will analyze your repository to detect test framework
   - Ensure your test directory follows standard conventions:
     - Java: `src/test/java` or `test/`
     - JavaScript: `test/`, `tests/`, `__tests__/`
     - Python: `tests/`, `test/`

3. **Test First PR:**
   - Start with a small story to test the full workflow
   - Review the generated PR carefully
   - Provide feedback to improve future generations

## Troubleshooting

### Jira Connection Issues

**Error: "Unauthorized" or "401"**
- Verify `ATLASSIAN_EMAIL` matches your Atlassian account
- Regenerate API token and update `.env`
- Check that API tokens haven't expired

**Error: "Issue not found"**
- Verify issue key format (e.g., `PROJ-123`)
- Ensure you have permission to view the project
- Check that the issue exists

### Zephyr Integration Issues

**Error: "Invalid API key"**
- Verify you're using the correct Zephyr Scale token
- Check token hasn't expired
- Ensure token has write permissions

### AI Generation Issues

**Error: "Anthropic API error"**
- Check `ANTHROPIC_API_KEY` is valid
- Verify you have sufficient API credits
- Check API rate limits

### GitHub PR Creation Issues

**Error: "Permission denied"**
- Verify GitHub token has `repo` scope
- Check repository exists and is accessible
- Ensure token hasn't expired

## Security Best Practices

1. **Never commit `.env` file** - It's already in `.gitignore`
2. **Rotate API keys regularly** - Set reminders to rotate every 90 days
3. **Use environment-specific tokens** - Different tokens for dev/staging/prod
4. **Enable 2FA** - On all accounts (GitHub, Jira, Anthropic)
5. **Monitor API usage** - Set up alerts for unusual activity
6. **Use AWS Secrets Manager in production** - For secure credential management

## Next Steps

1. Read the [API Documentation](API.md)
2. Explore the [Examples](../examples/)
3. Run the test suite: `pytest tests/`
4. Try generating your first test plan!

## Support

For issues:
- GitHub Issues: https://github.com/yourusername/womba/issues
- Email: support@womba.ai
- Documentation: https://docs.womba.ai

