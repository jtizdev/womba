# Womba Quick Start Guide

## 🚀 5-Minute Setup

### 1. Install

```bash
# Option A: From GitHub (current)
git clone https://github.com/plainid/womba.git
cd womba
pip install -e .

# Option B: From PyPI (when published)
pip install womba

# Option C: Docker
docker pull plainid/womba:latest
```

### 2. Configure

```bash
# Copy example config
cp .env.example .env

# Edit with your credentials
nano .env  # or vim, code, etc.
```

Required settings:
```bash
JIRA_BASE_URL=https://your-company.atlassian.net
JIRA_EMAIL=your-email@company.com
JIRA_API_TOKEN=your-jira-token
ZEPHYR_API_TOKEN=your-zephyr-token
OPENAI_API_KEY=sk-proj-your-key
```

### 3. Use Womba

```bash
# One command to do it all! 🚀
womba generate PLAT-12991 --upload

# Or step by step:
womba generate PLAT-12991    # Generate tests
womba evaluate PLAT-12991    # Check quality (optional)
womba upload PLAT-12991      # Upload to Zephyr
```

## 📋 Common Commands

```bash
# Generate and upload in one command 🚀
womba generate PLAT-12991 --upload

# Generate only
womba generate PLAT-12991

# Check quality before upload
womba evaluate PLAT-12991

# Upload after review
womba upload PLAT-12991

# Interactive setup (first time)
womba configure

# Docker (advanced)
docker run --env-file .env plainid/womba generate PLAT-12991 --upload
```

## 🔧 Development

```bash
# Install dependencies
make install

# Run tests
make test

# Format code
make format

# Build package
make build

# Clean up
make clean
```

## 📊 Expected Results

**Quality**: 70-100% pass rate (target: 70%)  
**Speed**: 60-90 seconds per story  
**Tests**: 8 comprehensive test cases per story  

## 🆘 Troubleshooting

### Error: "Invalid API token"
- Check `.env` file credentials
- Regenerate tokens in Jira/Zephyr settings

### Error: "Story not found"
- Verify story key format (e.g., PLAT-12991)
- Check Jira permissions

### Slow performance
- First run fetches all tests (15s)
- Subsequent runs use cache (1s)
- Cache expires after 30 minutes

## 📚 Documentation

- **README.md**: Full overview
- **DEPLOYMENT.md**: Deployment options
- **FORGE_PLUGIN_PLAN.md**: Future Forge plugin
- **DEPLOYMENT_SUMMARY.md**: Quick reference

## 💬 Support

- **Issues**: GitHub Issues
- **Email**: support@plainid.com
- **Docs**: See README.md

## 🎯 Next Steps

1. ✅ Test on your own stories
2. ✅ Customize prompts (optional)
3. ✅ Integrate into CI/CD (optional)
4. ✅ Try Forge plugin (when available)

