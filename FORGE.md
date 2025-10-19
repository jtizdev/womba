# Womba Forge Plugin Plan

**Status**: 🔴 **Phase 3 - Not Yet Implemented** (Post-CLI Stabilization)

**Repository**: `https://github.com/plainid/womba-forge` (to be created)

This document outlines the plan for creating an Atlassian Forge plugin version of Womba.

---

## Current Status (October 2024)

**✅ Completed:**
- Womba Python Core (test generation, Jira/Confluence integration)
- Multi-language CLIs (Python, Go, Java, Node.js)
- Config management with local+cloud sync
- Full end-to-end workflow (`womba all` command)
- Zephyr Scale integration
- Automated test code generation
- PR/MR creation (GitLab + GitHub)

**🚧 In Progress:**
- Web UI for config & dashboard
- CLI testing suite
- API enhancements for config sync

**📋 Planned (Phase 3):**
- Atlassian Forge app implementation
- Will be implemented after CLI stabilization and production testing
- Estimated timeline: Q1 2025

---

## Overview

**Goal**: Allow customers to generate AI test cases directly from Jira without installing anything.

**User Experience**:
1. Install "Womba AI" from Atlassian Marketplace
2. Open any Jira story
3. Click "Generate Tests" button in right panel
4. Review generated tests
5. Click "Upload to Zephyr"
6. Done!

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Customer's Browser                       │
│  ┌────────────────────────────────────────────────────────┐ │
│  │         Jira Issue View (Atlassian Cloud)             │ │
│  │  ┌──────────────────────────────────────────────────┐ │ │
│  │  │         Womba AI Panel (React)                   │ │ │
│  │  │  ┌────────────────────────────────────────────┐  │ │ │
│  │  │  │  [Generate AI Tests] button                │  │ │ │
│  │  │  │  Test cases list                           │  │ │ │
│  │  │  │  Quality score: 88/100                     │  │ │ │
│  │  │  │  [Upload to Zephyr] button                 │  │ │ │
│  │  │  └────────────────────────────────────────────┘  │ │ │
│  │  └──────────────────────────────────────────────────┘ │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                           ↓ (invoke)
┌─────────────────────────────────────────────────────────────┐
│           Forge Serverless Function (Atlassian)             │
│  - Hosted by Atlassian                                      │
│  - No infrastructure needed                                  │
│  - Auto-scales                                              │
└─────────────────────────────────────────────────────────────┘
                           ↓ (calls)
┌─────────────────────────────────────────────────────────────┐
│              Womba SaaS API (Your Backend)                  │
│  - Reuses CLI logic                                         │
│  - FastAPI wrapper                                          │
│  - Hosted on AWS/GCP                                        │
└─────────────────────────────────────────────────────────────┘
                           ↓ (calls)
┌─────────────────────────────────────────────────────────────┐
│                     OpenAI API                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Project Structure (womba-forge repo)

```
womba-forge/
├── manifest.yml                    # Forge app configuration
├── package.json                    # Dependencies
├── forge-settings.json             # Forge settings
├── README.md                       # Setup instructions
│
├── src/
│   ├── index.js                    # Backend serverless functions
│   │   ├── generateTests()         # Call Womba API
│   │   ├── uploadToZephyr()        # Upload via Forge API
│   │   └── getQualityScore()       # Quality check
│   │
│   └── frontend/
│       ├── index.jsx               # React entry point
│       ├── App.jsx                 # Main app component
│       │
│       └── components/
│           ├── TestGenerator.jsx   # Generate button + form
│           ├── TestList.jsx        # Display test cases
│           ├── QualityScore.jsx    # Show quality metrics
│           ├── UploadButton.jsx    # Upload to Zephyr
│           └── LoadingSpinner.jsx  # Loading state
│
├── static/
│   ├── icon.png                    # Marketplace icon
│   ├── banner.png                  # Marketplace banner
│   └── screenshot-*.png            # Screenshots
│
└── tests/
    ├── backend/                    # Test serverless functions
    └── frontend/                   # Test React components
```

---

## Implementation Steps

### Step 1: Initialize Forge Project

```bash
# Create new repository
git clone https://github.com/plainid/womba-forge.git
cd womba-forge

# Install Forge CLI
npm install -g @forge/cli

# Login to Forge
forge login

# Create new app
forge create
? App name: womba-ai-test-generator
? Category: Jira
? Template: jira-issue-panel

# This creates initial structure
```

### Step 2: Configure manifest.yml

```yaml
# manifest.yml
app:
  id: ari:cloud:ecosystem::app/womba-test-generator

modules:
  # Right-side panel in Jira issue
  jira:issuePanel:
    - key: womba-panel
      function: panel
      title: Womba AI Test Generator
      icon: https://womba.ai/icon.png
      
  # Quick action button
  jira:issueGlance:
    - key: womba-glance
      function: glance
      title: Generate Tests
      icon: https://womba.ai/icon.png

  # Serverless functions
  function:
    - key: panel
      handler: panel.run
      
    - key: generate-tests
      handler: generateTests.run
      
    - key: upload-to-zephyr
      handler: uploadToZephyr.run

permissions:
  scopes:
    - read:jira-work
    - write:jira-work
    - read:jira-user
  
  external:
    fetch:
      backend:
        - 'https://api.womba.ai'          # Your SaaS API
        - 'https://api.openai.com'         # Direct AI calls (optional)
  
  content:
    styles:
      - 'unsafe-inline'

resources:
  - key: womba-api-key
    name: Womba API Key
    type: string

app:
  runtime:
    name: nodejs18.x
```

### Step 3: Implement Backend Functions

```javascript
// src/index.js
import Resolver from '@forge/resolver';
import api, { route, fetch } from '@forge/api';

const resolver = new Resolver();

// Generate test cases
resolver.define('generateTests', async (req) => {
  const { issueKey } = req.payload;
  const { context } = req;
  
  try {
    // Get Jira issue details
    const issueResponse = await api.asUser().requestJira(
      route`/rest/api/3/issue/${issueKey}`,
      {
        headers: {
          'Accept': 'application/json'
        }
      }
    );
    
    const issue = await issueResponse.json();
    
    // Call Womba SaaS API
    const wombaResponse = await fetch('https://api.womba.ai/generate', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': process.env.WOMBA_API_KEY
      },
      body: JSON.stringify({
        issueKey,
        issueSummary: issue.fields.summary,
        issueDescription: issue.fields.description
      })
    });
    
    const testPlan = await wombaResponse.json();
    
    return {
      success: true,
      testPlan,
      qualityScore: testPlan.qualityScore || 0
    };
    
  } catch (error) {
    console.error('Error generating tests:', error);
    return {
      success: false,
      error: error.message
    };
  }
});

// Upload to Zephyr
resolver.define('uploadToZephyr', async (req) => {
  const { issueKey, testCases } = req.payload;
  
  try {
    // Upload each test case to Zephyr via Forge API
    const results = [];
    
    for (const testCase of testCases) {
      const response = await api.asUser().requestJira(
        route`/rest/atm/1.0/testcase`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            projectKey: issueKey.split('-')[0],
            name: testCase.title,
            objective: testCase.description,
            precondition: testCase.preconditions,
            steps: testCase.steps.map(step => ({
              description: step.action,
              expectedResult: step.expected_result,
              testData: step.test_data
            }))
          })
        }
      );
      
      const result = await response.json();
      results.push(result);
    }
    
    return {
      success: true,
      uploadedCount: results.length,
      testCaseKeys: results.map(r => r.key)
    };
    
  } catch (error) {
    console.error('Error uploading to Zephyr:', error);
    return {
      success: false,
      error: error.message
    };
  }
});

export const handler = resolver.getDefinitions();
```

### Step 4: Implement Frontend (React)

```jsx
// src/frontend/index.jsx
import React, { useState, useEffect } from 'react';
import ForgeReconciler, { Text, Button, Badge, Spinner } from '@forge/react';
import { invoke, view } from '@forge/bridge';

const App = () => {
  const [context, setContext] = useState(null);
  const [loading, setLoading] = useState(false);
  const [testPlan, setTestPlan] = useState(null);
  const [error, setError] = useState(null);
  
  useEffect(() => {
    view.getContext().then(setContext);
  }, []);
  
  const generateTests = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const result = await invoke('generateTests', {
        issueKey: context.extension.issue.key
      });
      
      if (result.success) {
        setTestPlan(result.testPlan);
      } else {
        setError(result.error);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };
  
  const uploadToZephyr = async () => {
    setLoading(true);
    
    try {
      const result = await invoke('uploadToZephyr', {
        issueKey: context.extension.issue.key,
        testCases: testPlan.testCases
      });
      
      if (result.success) {
        alert(`Successfully uploaded ${result.uploadedCount} test cases!`);
      } else {
        setError(result.error);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };
  
  if (!context) {
    return <Spinner />;
  }
  
  return (
    <>
      <Text>Womba AI Test Generator</Text>
      
      {error && <Badge appearance="removed">{error}</Badge>}
      
      <Button 
        onClick={generateTests} 
        isDisabled={loading}
      >
        {loading ? 'Generating...' : 'Generate AI Tests'}
      </Button>
      
      {testPlan && (
        <>
          <Badge appearance="added">
            Quality: {testPlan.qualityScore}/100
          </Badge>
          
          <Text>Generated {testPlan.testCases.length} test cases</Text>
          
          {testPlan.testCases.map((tc, i) => (
            <div key={i}>
              <Text>{i+1}. {tc.title}</Text>
              <Text content={tc.description} />
            </div>
          ))}
          
          <Button 
            appearance="primary"
            onClick={uploadToZephyr}
            isDisabled={loading}
          >
            Upload to Zephyr
          </Button>
        </>
      )}
    </>
  );
};

ForgeReconciler.render(<App />);
```

### Step 5: Deployment

```bash
# Development (local testing)
forge tunnel

# Deploy to staging
forge deploy --environment staging
forge install --site your-site.atlassian.net --environment staging

# Deploy to production
forge deploy --environment production

# Publish to Marketplace
# 1. Go to developer.atlassian.com
# 2. Submit app for review
# 3. Wait 2-4 weeks for approval
# 4. App appears in Marketplace
```

---

## Key Differences: CLI vs Forge

| Feature | CLI (womba) | Forge (womba-forge) |
|---------|------------|---------------------|
| **Code Reuse** | Direct Python imports | Call SaaS API |
| **Infrastructure** | Customer's | Atlassian's |
| **Installation** | pip install | Marketplace click |
| **Updates** | Manual | Automatic |
| **Speed** | Fast (local) | Medium (cold start) |
| **Timeout** | None | 30s max |
| **Auth** | .env file | Forge handles it |
| **Cost** | Free | Per-install fee |

---

## Womba SaaS API (Bridge Between)

To support the Forge plugin, you need a SaaS API wrapper:

```python
# womba-api/main.py (FastAPI)
from fastapi import FastAPI, Header
from src.aggregator.story_collector import StoryCollector
from src.ai.test_plan_generator import TestPlanGenerator

app = FastAPI()

@app.post("/generate")
async def generate_tests(
    issueKey: str,
    api_key: str = Header(..., alias="X-API-Key")
):
    # Validate API key
    if not validate_api_key(api_key):
        return {"error": "Invalid API key"}, 401
    
    # Use CLI logic
    collector = StoryCollector()
    context = await collector.collect_story_context(issueKey)
    
    generator = TestPlanGenerator()
    test_plan = await generator.generate_test_plan(context)
    
    return {
        "success": True,
        "testPlan": test_plan.dict(),
        "qualityScore": calculate_quality(test_plan)
    }
```

---

## Timeline

**Week 1-2**: Setup Forge project, basic UI  
**Week 3-4**: Implement backend functions  
**Week 5-6**: Build SaaS API wrapper  
**Week 7-8**: Testing, polish  
**Week 9-10**: Marketplace submission  
**Week 11-14**: Marketplace review (Atlassian)  
**Week 15**: Public launch! 🚀

---

## Next Steps

1. ✅ Finish CLI tool (womba repo) - **COMPLETE**
2. ✅ Build SaaS API wrapper (womba-api on Render.com) - **COMPLETE**
3. ⏳ Create womba-forge repo - **PHASE 3**
4. ⏳ Implement Forge plugin - **PHASE 3**
5. ⏳ Submit to Marketplace - **PHASE 3**

---

**Status**: Planning Complete | **Implementation: Phase 3 (After CLI Stabilization)**

**Important**: The Forge app implementation is scheduled for **Phase 3**, after the CLI tool has been deployed and proven stable in production for 2-3 weeks. This ensures:
- CLI logic is battle-tested before wrapping it in Forge
- API endpoints are stable and performant
- Authentication and security patterns are validated
- No breaking changes impact Forge customers

**Estimated Timeline**:
- Phase 1: CLI Development - ✅ Complete
- Phase 2: Production Enhancements (performance, automation) - 🔄 In Progress
- Phase 3: Forge Plugin - 📅 Planned (2-3 weeks after Phase 2)

For setup instructions when ready, see `FORGE_SETUP_CHECKLIST.md`.

