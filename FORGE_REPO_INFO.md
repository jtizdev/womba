# Forge Plugin - Separate Repository

## Why Separate Repos?

**womba** (this repo): CLI tool for technical users
- Install via `pip install womba`
- Full control, runs locally
- Can be used as Python library

**womba-forge** (separate repo): Atlassian Marketplace app
- Install via one-click from Marketplace
- For non-technical users (Product, QA)
- Hosted by Atlassian

## Forge Repository

**URL**: `https://github.com/jtizdev/womba-forge` (to be created)

### How They Work Together

```
┌─────────────────────────────────────────┐
│     womba-forge (Marketplace App)       │
│  ┌────────────────────────────────────┐ │
│  │  Jira Issue Panel (React)          │ │
│  │  [Generate Tests] button           │ │
│  └────────────────────────────────────┘ │
│              ↓                          │
│  ┌────────────────────────────────────┐ │
│  │  Forge Serverless Function         │ │
│  │  (calls womba CLI as library)      │ │
│  └────────────────────────────────────┘ │
└─────────────────────────────────────────┘
              ↓ (imports)
┌─────────────────────────────────────────┐
│         womba (Python package)          │
│  - src/aggregator/                      │
│  - src/ai/                              │
│  - src/integrations/                    │
└─────────────────────────────────────────┘
```

### Forge App Uses CLI as Library

In `womba-forge` repo:

```python
# forge-app/src/backend.py
from womba.aggregator import StoryCollector
from womba.ai import TestPlanGenerator
from womba.integrations import ZephyrIntegration

async def generate_tests_handler(issue_key: str):
    # Use womba as library
    collector = StoryCollector()
    context = await collector.collect_story_context(issue_key)
    
    generator = TestPlanGenerator()
    test_plan = await generator.generate_test_plan(context)
    
    return test_plan
```

## Next Steps

### To Create Forge Plugin Repo

1. Create new GitHub repo: `https://github.com/jtizdev/womba-forge`
2. Initialize Forge app:
   ```bash
   git clone https://github.com/jtizdev/womba-forge.git
   cd womba-forge
   forge create --template jira-issue-panel
   ```
3. Add `womba` as dependency:
   ```json
   {
     "dependencies": {
       "womba": "^1.0.0"
     }
   }
   ```
4. Build React UI and serverless functions
5. Deploy to Atlassian Marketplace

## Timeline

- **CLI (womba)**: ✅ Ready now
- **Forge Plugin**: 📋 Planned (3-4 months)

See `FORGE_PLUGIN_PLAN.md` for full implementation details.

## For Customers

**Use CLI now**: Install and use `womba` immediately  
**Wait for Forge**: One-click Marketplace app coming soon

Both will use the same core logic, just different interfaces!

