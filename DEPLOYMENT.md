# Womba Deployment Guide

This document explains how to deploy Womba in three different ways:
1. **CLI Tool** (Customer installation)
2. **Atlassian Forge Plugin** (Marketplace app - separate repo)
3. **SaaS API** (Future - hosted service)

---

## 1. CLI Tool Deployment (Current)

### For Customers to Install

#### Option A: Install from PyPI (Recommended)

```bash
# Install via pip
pip install womba

# Configure credentials
womba-configure

# Generate tests
womba-generate PLAT-12991

# Upload to Zephyr
womba-upload PLAT-12991
```

#### Option B: Install from GitHub

```bash
# Clone repository
git clone https://github.com/plainid/womba.git
cd womba

# Install in development mode
pip install -e .

# Or install normally
pip install .

# Configure
python3 setup_env.py

# Use
python3 generate_test_plan.py PLAT-12991
python3 upload_to_zephyr.py PLAT-12991
```

#### Option C: Docker Container

```bash
# Pull image
docker pull plainid/womba:latest

# Run with env file
docker run --env-file .env plainid/womba generate PLAT-12991

# Or run interactively
docker run -it --env-file .env plainid/womba bash
```

### Customer Onboarding

**Time**: < 10 minutes

**Steps**:
1. Install Python 3.9+ (if not already installed)
2. `pip install womba`
3. `womba-configure` (interactive setup)
4. `womba-generate <story-key>` (test)
5. Done!

**Requirements**:
- Python 3.9+
- Jira Cloud API access
- Zephyr Scale license
- OpenAI API key

---

## 2. Atlassian Forge Plugin (Separate Repo)

**Repository**: `https://github.com/plainid/womba-forge`

### Architecture

```
Jira Issue Panel (Browser)
         ↓
Forge Serverless Function (Atlassian Cloud)
         ↓
Womba SaaS API (Your Backend)
         ↓
OpenAI API
```

### Customer Experience

1. **Install from Marketplace**
   - Search "Womba" in Atlassian Marketplace
   - Click "Install"
   - Configure API key in settings

2. **Use in Jira**
   - Open any Jira story
   - See "Womba AI" panel on right side
   - Click "Generate Tests" button
   - Review generated tests
   - Click "Upload to Zephyr"
   - Done!

### Forge Project Structure

```
womba-forge/
├── manifest.yml          # Forge app configuration
├── src/
│   ├── index.js         # Serverless functions
│   └── frontend/
│       ├── index.jsx    # React UI
│       └── components/
│           ├── TestGenerator.jsx
│           ├── TestList.jsx
│           └── QualityScore.jsx
├── static/
│   └── icon.png
├── package.json
└── README.md
```

### Deployment Steps (Forge)

```bash
# In womba-forge repo
forge login
forge create
forge deploy
forge install --upgrade

# For production
forge deploy --environment production
```

### Forge Benefits

✅ **No Infrastructure**: Customer doesn't install anything
✅ **Auto Updates**: Push updates, all customers get them
✅ **Built into Jira**: Native UI, seamless experience
✅ **Secure**: Atlassian handles auth, no API keys exposed
✅ **Scalable**: Atlassian handles hosting

### Forge Limitations

⚠️ **Slower**: Cold starts (~2-3s)
⚠️ **Limited**: Function timeouts (30s max)
⚠️ **Review Process**: 2-4 weeks approval
⚠️ **Costs**: Pay per execution

---

## 3. Repository Structure (Two Repos)

### Repo 1: womba (CLI Tool)

```
womba/                           # Main CLI tool
├── src/
│   ├── aggregator/             # Jira, Confluence clients
│   ├── ai/                     # AI generation
│   ├── integrations/           # Zephyr
│   ├── models/                 # Data models
│   ├── config/                 # Settings
│   ├── core/                   # Base classes
│   └── utils/                  # Utilities
├── tests/                      # Test suite
├── generate_test_plan.py       # CLI script
├── upload_to_zephyr.py         # Upload script
├── evaluate_quality.py         # Quality check
├── setup.py                    # Package setup
├── requirements-minimal.txt    # Dependencies
├── README.md                   # Main docs
├── DEPLOYMENT.md               # This file
└── .env.example                # Config template
```

**Deploy**: PyPI, GitHub Releases, Docker Hub

### Repo 2: womba-forge (Atlassian Plugin)

```
womba-forge/                     # Separate repo
├── manifest.yml                # Forge config
├── src/
│   ├── index.js                # Backend functions
│   └── frontend/
│       ├── index.jsx           # React entry
│       └── components/         # UI components
├── static/
│   └── icon.png
├── package.json
├── forge-settings.json
└── README.md
```

**Deploy**: Atlassian Forge CLI → Marketplace

---

## 4. Deployment Matrix

| Feature | CLI Tool | Forge Plugin | SaaS API |
|---------|----------|--------------|----------|
| **Installation** | pip install | Marketplace | N/A (API) |
| **Customer Setup** | 10 min | 2 min | Instant |
| **Infrastructure** | Customer | Atlassian | Your cloud |
| **Updates** | Manual | Auto | Auto |
| **Speed** | Fast | Medium | Fast |
| **Offline** | Yes | No | No |
| **Cost** | Free | Per-install | Subscription |
| **Control** | Full | Limited | Full |

---

## 5. Recommended Strategy

### Phase 1: CLI Tool (Current) ✅
- **Target**: Technical customers (DevOps, QA leads)
- **Distribution**: GitHub, PyPI
- **Support**: Documentation + GitHub Issues

### Phase 2: Forge Plugin (Next 3 months)
- **Target**: Non-technical customers (Product, QA)
- **Distribution**: Atlassian Marketplace
- **Support**: In-app help + Email support

### Phase 3: SaaS API (Future)
- **Target**: Enterprise customers
- **Distribution**: Private cloud
- **Support**: Dedicated support + SLA

---

## 6. Migration Path

### For Customers

**CLI → Forge**:
- No migration needed
- Both can coexist
- Forge uses same backend logic

**Forge → SaaS**:
- Transparent upgrade
- Same UI
- Better performance

### For Development

**CLI**:
```python
# Direct imports
from src.ai.test_plan_generator import TestPlanGenerator
generator = TestPlanGenerator()
```

**Forge**:
```javascript
// Call CLI as subprocess or API
const { exec } = require('child_process');
exec('womba-generate PLAT-12991');

// Or call your SaaS API
fetch('https://api.womba.ai/generate', {
  method: 'POST',
  body: JSON.stringify({ issueKey: 'PLAT-12991' })
});
```

---

## 7. Next Steps

### To Deploy CLI

```bash
# 1. Build package
python setup.py sdist bdist_wheel

# 2. Upload to PyPI
twine upload dist/*

# 3. Test installation
pip install womba
womba-generate --help
```

### To Create Forge Plugin

```bash
# 1. Create new repo
git clone https://github.com/plainid/womba-forge.git
cd womba-forge

# 2. Initialize Forge
forge create --template jira-issue-panel

# 3. Develop
forge tunnel  # Local development

# 4. Deploy
forge deploy --environment staging
forge install --site your-site.atlassian.net

# 5. Publish
forge deploy --environment production
# Submit to marketplace
```

### To Prepare for SaaS

```bash
# 1. Create FastAPI wrapper
# 2. Add authentication (API keys)
# 3. Deploy to cloud (AWS Lambda, GCP Cloud Run)
# 4. Add monitoring (Sentry, DataDog)
# 5. Add billing (Stripe)
```

---

## 8. Customer Support

### CLI Tool

**Documentation**: README.md, examples/
**Issues**: GitHub Issues
**Chat**: Discord/Slack community

### Forge Plugin

**Documentation**: In-app help
**Issues**: Atlassian Support Portal
**Chat**: Live chat (future)

### SaaS API

**Documentation**: API docs (OpenAPI)
**Issues**: Support tickets
**Chat**: Dedicated support engineer

---

**Status**: CLI Ready ✅ | Forge Planned 📋 | SaaS Future 🔮

