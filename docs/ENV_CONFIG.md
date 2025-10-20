# Environment Configuration Guide

This file documents all environment variables used by Womba.

## Required Configuration

### Atlassian (Jira & Confluence)
```bash
ATLASSIAN_BASE_URL=https://your-company.atlassian.net
ATLASSIAN_EMAIL=your-email@company.com
ATLASSIAN_API_TOKEN=your-atlassian-token
```

### Zephyr Scale
```bash
ZEPHYR_API_TOKEN=your-zephyr-token
ZEPHYR_BASE_URL=https://api.zephyrscale.smartbear.com/v2
```

### OpenAI
```bash
OPENAI_API_KEY=your-openai-api-key
```

## Optional Configuration


### Anthropic (Claude)
```bash
ANTHROPIC_API_KEY=your-anthropic-key
# Only needed if using Claude instead of OpenAI
```

### API Documentation
```bash
API_DOCS_URL=https://docs.your-company.com/api
API_DOCS_TYPE=openapi  # or 'postman', 'readme', 'auto'
```

### Figma
```bash
FIGMA_API_TOKEN=your-figma-token
FIGMA_FILE_ID=your-default-figma-file-id
```

### Test Automation (for `womba automate`)
```bash
AUTO_REPO_PATH=/path/to/your/test/repository
AUTO_FRAMEWORK=auto  # or 'playwright', 'cypress', 'rest-assured', 'junit', 'pytest'
AUTO_AI_TOOL=aider  # or 'cursor'
```

### Womba API (for Forge app)
```bash
WOMBA_API_KEY=your-womba-api-key
WOMBA_API_URL=https://womba.onrender.com
```

## Setup Instructions

1. **Copy template**:
   ```bash
   cp .env.template .env
   ```

2. **Edit `.env`**:
   ```bash
   nano .env  # or your preferred editor
   ```

3. **Get API tokens**:
   - **Atlassian**: https://id.atlassian.com/manage-profile/security/api-tokens
   - **Zephyr**: Settings → API Tokens in Zephyr Scale
   - **OpenAI**: https://platform.openai.com/api-keys
   - **GitHub**: `gh auth login` (automatic)

4. **Verify configuration**:
   ```bash
   womba configure  # Interactive setup
   ```

## Security Notes

- Never commit `.env` to git
- `.env` is in `.gitignore` by default
- Use separate tokens for different environments
- Rotate tokens regularly (every 90 days)
- Use read-only tokens where possible

## Environment-Specific Configuration

### Development
```bash
# .env.development
ATLASSIAN_BASE_URL=https://your-dev.atlassian.net
WOMBA_API_URL=http://localhost:8000
```

### Production
```bash
# .env.production
ATLASSIAN_BASE_URL=https://your-company.atlassian.net
WOMBA_API_URL=https://womba.onrender.com
```

## Troubleshooting

### "API key not found"
Ensure `.env` is in the project root and properly formatted.

### "Permission denied"
Check that API tokens have correct permissions:
- Atlassian: Read issues, browse projects
- Zephyr: Read and write test cases
- OpenAI: Full API access

### "Invalid token"
Regenerate tokens and update `.env`.

---

For more help, see `docs/SETUP.md`

