# Womba Forge App - Setup Checklist

> **Note**: This is a **Phase 3** feature, planned for implementation after the CLI tool is production-stable (2-3 weeks after Phase 2 completion).

## Prerequisites

Before starting Forge app development:

- [ ] CLI tool has been stable in production for 2-3 weeks
- [ ] No critical bugs in womba-api
- [ ] Performance optimizations complete (Phase 2)
- [ ] Atlassian Developer account created
- [ ] Womba API deployed and stable (Render.com or AWS)
- [ ] OpenAI API key configured
- [ ] Forge CLI installed: `npm install -g @forge/cli`
- [ ] Node.js 18+ installed
- [ ] Git and GitHub access configured

## Repository Setup

1. [ ] Create new repository: `womba-forge` (separate from `womba`)
2. [ ] Initialize Forge project: `forge create`
   - App name: `womba-ai-test-generator`
   - Category: Jira
   - Template: `jira-issue-panel`
3. [ ] Set up Git remote: `git remote add origin https://github.com/your-org/womba-forge.git`
4. [ ] Initialize npm: `npm init -y`

## Configuration

### Environment Variables

Add these to Forge environment variables:

```bash
# Womba API Configuration
WOMBA_API_URL=https://womba.onrender.com
WOMBA_API_KEY=your-womba-api-key

# OpenAI (optional, if calling directly)
OPENAI_API_KEY=your-openai-key

# Jira Configuration (handled by Forge automatically)
# JIRA_BASE_URL - provided by Forge context
# JIRA_API_TOKEN - Forge handles authentication
```

Set environment variables:
```bash
forge variables set WOMBA_API_URL https://womba.onrender.com
forge variables set WOMBA_API_KEY your-key-here
```

### Manifest Configuration

Update `manifest.yml` with required permissions:

```yaml
permissions:
  scopes:
    - read:jira-work          # Read Jira issues
    - write:jira-work         # Create/update test cases
    - read:jira-user          # User info
    - storage:app             # Cache test plans
  
  external:
    fetch:
      backend:
        - 'https://womba.onrender.com'  # Your Womba API
        - 'https://api.zephyrscale.smartbear.com'  # Zephyr (if needed)
  
  content:
    styles:
      - 'unsafe-inline'  # For React styling
```

## Development Steps

### Phase 1: Basic Setup (Week 1)

1. [ ] Configure `manifest.yml` (see FORGE.md)
2. [ ] Create basic React UI in `src/frontend/index.jsx`
3. [ ] Implement serverless function in `src/index.js`
4. [ ] Test locally: `forge tunnel`
5. [ ] Install on dev Jira site: `forge install --site your-dev-site.atlassian.net`

### Phase 2: Core Features (Week 2-3)

1. [ ] Implement "Generate Tests" button
2. [ ] Connect to Womba API
3. [ ] Display generated test cases
4. [ ] Add quality score display
5. [ ] Implement "Upload to Zephyr" functionality
6. [ ] Add loading states and error handling

### Phase 3: Polish & Testing (Week 4-5)

1. [ ] Add caching (Forge storage API)
2. [ ] Optimize API calls
3. [ ] Add analytics/telemetry
4. [ ] Write unit tests
5. [ ] Test on multiple Jira instances
6. [ ] Performance optimization

### Phase 4: Marketplace Submission (Week 6-7)

1. [ ] Create marketing assets:
   - [ ] App icon (512x512)
   - [ ] Banner image (1280x960)
   - [ ] Screenshots (1280x800, at least 3)
   - [ ] Demo video (optional but recommended)
2. [ ] Write app description
3. [ ] Set pricing tier (free trial + paid plans)
4. [ ] Submit to Atlassian Marketplace
5. [ ] Wait for review (2-4 weeks)

## Testing Checklist

Before deploying to staging/production:

- [ ] Generate tests for simple story (< 5 subtasks)
- [ ] Generate tests for complex story (> 10 subtasks)
- [ ] Test with story that has Confluence links
- [ ] Test with story that has NO Confluence links
- [ ] Test upload to Zephyr (verify test cases appear)
- [ ] Test error handling (invalid story key)
- [ ] Test with slow network (timeout handling)
- [ ] Test on mobile (Jira mobile app)
- [ ] Verify caching works (second load faster)
- [ ] Check memory usage (no leaks)

## Deployment Commands

```bash
# Deploy to staging
forge deploy --environment staging

# Install on staging site
forge install --site your-staging.atlassian.net --environment staging

# Deploy to production (after testing)
forge deploy --environment production

# Promote to all installs
forge install upgrade
```

## Security Checklist

- [ ] API keys never exposed in frontend code
- [ ] All API calls authenticated
- [ ] Input validation on all user inputs
- [ ] Rate limiting configured
- [ ] Error messages don't leak sensitive info
- [ ] CORS configured correctly
- [ ] Audit logging enabled

## Monitoring & Support

After launch:

- [ ] Set up monitoring (Forge logs, Sentry)
- [ ] Create support email/Slack channel
- [ ] Set up feedback collection
- [ ] Monitor Marketplace reviews
- [ ] Track usage metrics
- [ ] Plan regular updates (monthly)

## Resources

- [Forge Documentation](https://developer.atlassian.com/platform/forge/)
- [Forge CLI Reference](https://developer.atlassian.com/platform/forge/cli-reference/)
- [Jira Issue Panel Tutorial](https://developer.atlassian.com/platform/forge/jira-issue-panel/)
- [Womba API Documentation](./womba-api/README.md)
- [Womba Forge Architecture](./FORGE.md)

---

**Status**: Phase 3 - Planned for Q1 2025  
**Last Updated**: 2024-10-19

