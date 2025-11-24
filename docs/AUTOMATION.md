# Womba Test Automation - Code Generation Guide

Generate executable test code automatically from AI test plans and create pull requests in your automation repository.

## Overview

Womba can analyze your test automation repository, understand its patterns, and generate executable test code that matches your style. It supports multiple frameworks and uses AI tools (aider or cursor) to ensure the generated code fits seamlessly into your codebase.

## Supported Frameworks

- **Playwright** (JavaScript/TypeScript)
- **Cypress** (JavaScript/TypeScript)
- **Selenium** (Python, Java, JavaScript)
- **REST Assured** (Java)
- **JUnit** (Java)
- **Pytest** (Python)
- **Auto-detection** (recommended)

## Prerequisites

### 1. Install AI Code Generation Tool

Choose one:

**Option A: Aider (Recommended)**
```bash
pip install aider-chat
```

**Option B: Cursor CLI**
```bash
# Install Cursor IDE, then cursor-cli is available
```

### 2. Configure GitHub CLI (for PR creation)

```bash
# Install GitHub CLI
brew install gh  # macOS
# or: https://cli.github.com/

# Authenticate
gh auth login
```

### 3. Prepare Your Automation Repository

Ensure your test repository:
- Is a git repository
- Has clear test patterns (file naming, structure)
- Has existing test files as examples
- Has write permissions for creating branches

## Usage

### Basic Workflow

1. **Generate test plan** (as usual):
```bash
womba generate PROJ-12991
```

2. **Review the generated test plan**:
```json
test_plan_PROJ-12991.json
```

3. **Generate executable test code**:
```bash
womba automate PROJ-12991 --repo /path/to/your/test/repo
```

This will:
- Analyze your repo structure and patterns
- Generate executable test files matching your style
- Create a new git branch
- Commit the generated code
- Push the branch
- Open a pull request

### Advanced Options

**Specify framework explicitly:**
```bash
womba automate PROJ-12991 \
  --repo /path/to/test/repo \
  --framework playwright
```

**Use cursor instead of aider:**
```bash
womba automate PROJ-12991 \
  --repo /path/to/test/repo \
  --ai-tool cursor
```

**Generate code without creating PR:**
```bash
womba automate PROJ-12991 \
  --repo /path/to/test/repo \
  --create-pr false
```

## How It Works

### Step 1: Repository Analysis

The tool analyzes your repository to understand:
- Test framework used (Playwright, Cypress, etc.)
- File naming patterns (`*.test.js`, `*_test.py`, etc.)
- Directory structure (`tests/`, `e2e/`, etc.)
- Import patterns and dependencies
- Code style and structure

### Step 2: Prompt Generation

Creates a detailed prompt for the AI tool that includes:
- Test cases from the test plan
- Repository patterns and conventions
- Framework-specific requirements
- Expected file structure

### Step 3: Code Generation

The AI tool (aider or cursor):
- Reads your existing test files
- Understands your patterns
- Generates new test files matching your style
- Ensures code quality and best practices

### Step 4: PR Creation

- Creates a new branch: `feature/ai-tests-{story-key}`
- Commits all generated files
- Pushes to remote
- Creates a pull request with:
  - Detailed description
  - Test coverage summary
  - Links to Jira story
  - Review checklist

## Example

```bash
# Full workflow
womba generate PROJ-15471
womba automate PROJ-15471 --repo /Users/you/projects/my-tests

# Output:
🤖 Womba Test Automation - PROJ-15471
================================================================================

📄 Loading test plan from test_plan_PROJ-15471.json...
✅ Loaded 6 test cases

🔧 Initializing test code generator...
   Repository: /Users/you/projects/my-tests
   Framework: auto
   AI Tool: aider

🚀 Generating test code...
   This may take 2-5 minutes...

✅ SUCCESS! Pull Request created:
   https://github.com/your-org/my-tests/pull/42

📋 Next steps:
   1. Review the generated test code
   2. Run the tests locally
   3. Approve and merge the PR
```

## Generated Code Example

For a story about "Asset Type Source Change", Womba might generate:

**Input (Test Plan)**:
```json
{
  "title": "Change Asset Type Source from Request to External",
  "steps": [
    {
      "action": "POST /pops with custom ID",
      "expected_result": "POP created successfully"
    }
  ]
}
```

**Output (Playwright Test)**:
```typescript
// tests/asset-type/change-source.test.ts
import { test, expect } from '@playwright/test';
import { createPOP, updateAssetType } from '../helpers/api';

test.describe('Asset Type Source Change', () => {
  test('should change asset type source from Request to External', async ({ request }) => {
    // Step 1: Create POP with custom ID
    const pop = await createPOP(request, {
      id: 'test-pop-001',
      type: 'Snowflake'
    });
    expect(pop.id).toBe('test-pop-001');
    
    // Step 2: Update asset type source
    const updated = await updateAssetType(request, {
      assetTypeId: 'customer-data',
      source: 'external',
      popId: 'test-pop-001'
    });
    expect(updated.source).toBe('external');
    
    // Verify change persisted
    const asset = await request.get(`/api/v1/asset-types/customer-data`);
    expect(asset.source).toBe('external');
  });
});
```

Notice how the AI:
- Matched your file naming pattern
- Used your project's helper functions
- Followed your assertion style
- Structured the test like your existing tests

## Configuration

Add to `.env` (optional):

```bash
# Test Automation
AUTO_REPO_PATH=/path/to/default/test/repo
AUTO_FRAMEWORK=playwright
AUTO_AI_TOOL=aider

# GitHub (for PR creation)
GITHUB_TOKEN=ghp_xxx  # Optional, gh CLI handles this
```

## Pricing & Resources

### AI Tool Costs

**Aider**:
- Uses your OpenAI API key
- Cost: ~$0.10-$0.50 per test suite generation
- Supports multiple models (GPT-4, Claude)

**Cursor**:
- Uses Cursor Pro subscription ($20/month)
- Unlimited generations included

### Time

- Repository analysis: 5-10 seconds
- Code generation: 2-5 minutes (depending on test count)
- PR creation: 5-10 seconds

**Total**: ~3-5 minutes per story

## Troubleshooting

### "Aider not found"

```bash
pip install aider-chat
```

### "cursor command not found"

Install Cursor IDE from https://cursor.sh

### "Failed to create PR"

Ensure GitHub CLI is authenticated:
```bash
gh auth status
gh auth login  # if not authenticated
```

### "Permission denied"

Check repository write permissions:
```bash
cd /path/to/test/repo
git remote -v  # verify you have push access
```

### "Generated code doesn't match our style"

The AI learns from existing tests. Ensure:
- You have clear, consistent patterns
- Existing tests follow best practices
- Test files are well-documented

## Best Practices

1. **Review Generated Code**: Always review before merging
2. **Run Tests Locally**: Verify tests pass before approving PR
3. **Iterate**: If code quality is low, improve your existing tests
4. **Use Auto-detection**: Let Womba detect your framework
5. **Keep Patterns Consistent**: Maintain clear test patterns in your repo

## Advanced: Custom Templates

Coming soon: Ability to provide custom code templates for your organization.

## Security

- AI tools run locally in your repository
- No code is sent to Womba servers
- Only test plans (JSON) are processed
- Git credentials handled by `gh` CLI
- API keys never exposed in generated code

## Support

For issues or questions:
- GitHub Issues: https://github.com/your-org/womba/issues
- Email: support@womba.ai
- Docs: https://docs.womba.ai

---

**Status**: Beta - Currently supports Playwright, Cypress, REST Assured, JUnit, Pytest  
**Last Updated**: 2024-10-19

