# Installing Womba as a Package

## Quick Installation

### From PyPI (Once Published)

```bash
# Install Womba
pip install womba

# Or install with API support
pip install womba[api]

# Or install with development tools
pip install womba[dev]
```

### From GitHub (Current)

```bash
# Install directly from GitHub
pip install git+https://github.com/jtizdev/womba.git

# Or clone and install in editable mode for development
git clone https://github.com/jtizdev/womba.git
cd womba
pip install -e .
```

### From Source

```bash
# Clone the repository
git clone https://github.com/jtizdev/womba.git
cd womba

# Install
pip install .

# Or install in editable mode for development
pip install -e ".[dev]"
```

## Verification

After installation, verify Womba is accessible:

```bash
# Check version
womba --version

# Show help
womba --help

# Try generating test plans
womba generate PLAT-12345
```

## Usage in Other Projects

Once installed, you can use Womba in any Python project:

### As a CLI Tool

```bash
# From any directory
cd /path/to/your/project
womba generate JIRA-123
womba upload JIRA-123
```

### As a Python Library

```python
# In your Python scripts
from src.aggregator.story_collector import StoryCollector
from src.ai.test_plan_generator import TestPlanGenerator
from src.config.user_config import load_config

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
```

### In Your Test Scripts

```python
# tests/generate_tests.py
import asyncio
from womba_cli import generate_command

async def generate_tests_for_sprint():
    """Generate tests for all stories in current sprint"""
    story_keys = ["PLAT-100", "PLAT-101", "PLAT-102"]
    
    for story_key in story_keys:
        print(f"Generating tests for {story_key}...")
        await generate_command(story_key)
        
if __name__ == "__main__":
    asyncio.run(generate_tests_for_sprint())
```

## Configuration

Womba uses configuration from multiple sources:

1. **Environment Variables** (`.env` file)
2. **User Config** (`~/.womba/config.yml`)
3. **Command Line Arguments**

### Quick Setup

```bash
# Configure Atlassian
export ATLASSIAN_BASE_URL="https://your-company.atlassian.net"
export ATLASSIAN_EMAIL="your.email@company.com"
export ATLASSIAN_API_TOKEN="your-api-token"

# Configure OpenAI
export OPENAI_API_KEY="sk-your-openai-key"

# Configure Zephyr (optional)
export ZEPHYR_API_TOKEN="your-zephyr-token"

# Run Womba
womba generate PLAT-12345
```

Or create `.env` file in your project:

```bash
# .env
ATLASSIAN_BASE_URL=https://your-company.atlassian.net
ATLASSIAN_EMAIL=your.email@company.com
ATLASSIAN_API_TOKEN=your-api-token
OPENAI_API_KEY=sk-your-openai-key
ZEPHYR_API_TOKEN=your-zephyr-token
```

## Advanced Usage

### Install with Specific Features

```bash
# Minimal installation (core features only)
pip install womba

# With API server support
pip install womba[api]

# With development tools
pip install womba[dev]

# Everything
pip install womba[api,dev]
```

### Use in CI/CD

```yaml
# .github/workflows/generate-tests.yml
name: Generate Tests

on:
  issues:
    types: [labeled]

jobs:
  generate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Install Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install Womba
        run: pip install womba
      
      - name: Generate Tests
        env:
          ATLASSIAN_BASE_URL: ${{ secrets.ATLASSIAN_BASE_URL }}
          ATLASSIAN_EMAIL: ${{ secrets.ATLASSIAN_EMAIL }}
          ATLASSIAN_API_TOKEN: ${{ secrets.ATLASSIAN_API_TOKEN }}
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
        run: |
          womba generate ${{ github.event.issue.key }}
```

### Use in Docker

```dockerfile
# Dockerfile
FROM python:3.11-slim

# Install Womba
RUN pip install womba

# Set environment variables
ENV ATLASSIAN_BASE_URL=""
ENV ATLASSIAN_EMAIL=""
ENV ATLASSIAN_API_TOKEN=""
ENV OPENAI_API_KEY=""

# Run Womba
ENTRYPOINT ["womba"]
CMD ["--help"]
```

## Troubleshooting

### ImportError: No module named 'src'

Make sure you've installed Womba properly:
```bash
pip install -e .  # For development
# or
pip install womba  # From PyPI
```

### Command not found: womba

The `womba` command might not be in your PATH. Try:
```bash
python -m womba_cli --help
# or
python womba_cli.py --help
```

### Missing dependencies

Install all dependencies:
```bash
pip install -r requirements-minimal.txt
```

## Uninstall

```bash
pip uninstall womba
```

## Support

- **Issues**: https://github.com/jtizdev/womba/issues
- **Documentation**: https://github.com/jtizdev/womba#readme

