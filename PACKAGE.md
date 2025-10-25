# Womba Python Package

Womba is now available as an installable Python package! This means you can use it across multiple repositories and projects without needing to clone the entire codebase.

## Installation Methods

### 1. From GitHub (Recommended for now)

```bash
# Install from GitHub
pip install git+https://github.com/jtizdev/womba.git

# Or install a specific branch/tag
pip install git+https://github.com/jtizdev/womba.git@main
```

### 2. Local Development Install

```bash
# Clone and install in editable mode
git clone https://github.com/jtizdev/womba.git
cd womba
pip install -e .

# With development dependencies
pip install -e ".[dev]"

# With API server support
pip install -e ".[api]"
```

### 3. From PyPI (Future)

Once published to PyPI:
```bash
pip install womba
```

## Usage

### As a CLI Tool

After installation, use `womba` command from anywhere:

```bash
# Generate test plan for a Jira story
womba generate PLAT-12345

# Upload to Zephyr
womba upload PLAT-12345

# Full workflow (generate + upload + create branch)
womba all PLAT-12345 --repo /path/to/repo

# Check version
womba --version

# Get help
womba --help
```

### As a Python Library

Import and use Womba in your Python projects:

```python
import asyncio
from src.aggregator.story_collector import StoryCollector
from src.ai.test_plan_generator import TestPlanGenerator
from src.config.user_config import load_config

async def generate_tests():
    # Load configuration
    config = load_config()
    
    # Collect story context
    collector = StoryCollector()
    story_data = await collector.collect_story_context("PLAT-12345")
    
    # Generate test plan
    generator = TestPlanGenerator(
        api_key=config.openai_api_key,
        model=config.ai_model
    )
    test_plan = await generator.generate_test_plan(story_data)
    
    print(f"Generated {len(test_plan.test_cases)} test cases")
    return test_plan

# Run
asyncio.run(generate_tests())
```

## Use in Different Repositories

### Repository A - Frontend Tests

```bash
cd /path/to/frontend-repo

# Install Womba
pip install git+https://github.com/jtizdev/womba.git

# Generate tests from terminal
womba generate PLAT-100

# Or use in Python script
python scripts/generate_frontend_tests.py
```

### Repository B - Backend Tests

```bash
cd /path/to/backend-repo

# Install Womba
pip install git+https://github.com/jtizdev/womba.git

# Generate tests
womba generate PLAT-200
```

### CI/CD Integration

Add to your `.github/workflows/test-generation.yml`:

```yaml
name: Generate Tests

on:
  workflow_dispatch:
    inputs:
      jira_key:
        description: 'Jira Story Key'
        required: true

jobs:
  generate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install Womba
        run: pip install git+https://github.com/jtizdev/womba.git
      
      - name: Generate Tests
        env:
          ATLASSIAN_BASE_URL: ${{ secrets.ATLASSIAN_BASE_URL }}
          ATLASSIAN_EMAIL: ${{ secrets.ATLASSIAN_EMAIL }}
          ATLASSIAN_API_TOKEN: ${{ secrets.ATLASSIAN_API_TOKEN }}
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
        run: womba generate ${{ inputs.jira_key }}
```

## Configuration

Womba works with configuration from:

1. **Environment Variables** (recommended for CI/CD)
2. **`.env` file** (recommended for local development)
3. **`~/.womba/config.yml`** (user-specific settings)

### Quick Setup

Create `.env` in your repository:

```bash
# .env
ATLASSIAN_BASE_URL=https://yourcompany.atlassian.net
ATLASSIAN_EMAIL=your.email@company.com
ATLASSIAN_API_TOKEN=your-atlassian-token
OPENAI_API_KEY=sk-your-openai-key
ZEPHYR_API_TOKEN=your-zephyr-token  # Optional
```

Then run Womba:
```bash
womba generate PLAT-12345
```

## Advanced Usage

### Custom Test Generation Script

```python
# scripts/batch_generate.py
import asyncio
from src.aggregator.story_collector import StoryCollector
from src.ai.test_plan_generator import TestPlanGenerator
from src.config.user_config import load_config

async def generate_for_sprint(story_keys):
    """Generate tests for multiple stories"""
    config = load_config()
    collector = StoryCollector()
    generator = TestPlanGenerator(
        api_key=config.openai_api_key,
        model=config.ai_model
    )
    
    for story_key in story_keys:
        print(f"Processing {story_key}...")
        story_data = await collector.collect_story_context(story_key)
        test_plan = await generator.generate_test_plan(story_data)
        print(f"  → Generated {len(test_plan.test_cases)} tests")

# Run
stories = ["PLAT-100", "PLAT-101", "PLAT-102"]
asyncio.run(generate_for_sprint(stories))
```

### Integration with Test Frameworks

```python
# tests/conftest.py
import pytest
from src.aggregator.story_collector import StoryCollector

@pytest.fixture
async def story_context():
    """Fixture to get story context"""
    collector = StoryCollector()
    return await collector.collect_story_context("PLAT-12345")

# tests/test_generated.py
import pytest

async def test_user_authentication(story_context):
    """Test generated from Womba"""
    # Use context from story
    assert story_context.main_story
    # Your test logic here
```

## Building and Distributing

### Build Package

```bash
# Install build tools
pip install build twine

# Build
python -m build

# Output:
# dist/womba-1.3.0.tar.gz
# dist/womba-1.3.0-py3-none-any.whl
```

### Publish to PyPI (Internal)

```bash
# Test on TestPyPI first
twine upload --repository testpypi dist/*

# Then publish to PyPI
twine upload dist/*
```

### Private Package Server

Host on your company's private PyPI server:
```bash
# Install from private server
pip install womba --index-url https://pypi.company.com/simple/
```

## Uninstall

```bash
pip uninstall womba
```

## Benefits of Package Installation

✅ **Use in multiple repos** - Install once, use everywhere  
✅ **Version control** - Pin specific versions  
✅ **Easy updates** - `pip install --upgrade womba`  
✅ **CI/CD friendly** - Simple one-line install  
✅ **No git cloning** - Just `pip install`  
✅ **Clean dependencies** - Automatic dep management  
✅ **Team distribution** - Share via PyPI or GitHub  

## Package Contents

When you install Womba, you get:

- **CLI Tool**: `womba` command
- **Python API**: All `src/` modules
- **Configuration**: Auto-setup for `.env` and `config.yml`
- **Dependencies**: Auto-installed

## Support

- **Issues**: https://github.com/jtizdev/womba/issues
- **Documentation**: https://github.com/jtizdev/womba#readme
- **Installation Guide**: [INSTALL.md](./INSTALL.md)

