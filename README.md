# Womba - AI-Powered Test Generation for Jira

**Automatically generate comprehensive test cases from Jira stories and upload to Zephyr Scale.**

## Features

- 🤖 **AI-Powered**: Uses GPT-4o to generate feature-specific test cases
- 📊 **High Quality**: 88%+ pass rate with built-in quality scoring
- 🔗 **Jira Integration**: Fetches stories, subtasks, comments, and linked issues
- 📚 **Confluence Integration**: Pulls related documentation automatically
- 🎯 **Smart Filtering**: Filters to top 50 most relevant existing tests
- 📁 **Intelligent Organization**: Suggests optimal folder structure
- ✅ **Zephyr Upload**: Uploads tests with steps, links to stories

## Installation

```bash
# Clone the repository
git clone https://github.com/your-org/womba.git
cd womba

# Install dependencies
pip install -r requirements-minimal.txt

# Configure credentials
cp .env.example .env
# Edit .env with your credentials
```

## Quick Start

```bash
# Generate test plan for a Jira story
python3 generate_test_plan.py PLAT-12991

# Upload to Zephyr
python3 upload_to_zephyr.py PLAT-12991

# Evaluate quality (optional)
python3 evaluate_quality.py PLAT-12991
```

## Configuration

Create a `.env` file with your credentials:

```bash
# Jira
JIRA_BASE_URL=https://your-company.atlassian.net
JIRA_EMAIL=your-email@company.com
JIRA_API_TOKEN=your-jira-token

# Confluence
CONFLUENCE_BASE_URL=https://your-company.atlassian.net/wiki
CONFLUENCE_EMAIL=your-email@company.com
CONFLUENCE_API_TOKEN=your-confluence-token

# Zephyr Scale
ZEPHYR_API_TOKEN=your-zephyr-token

# OpenAI
OPENAI_API_KEY=sk-proj-...

# Optional: API Documentation
API_DOCS_URL=https://docs.your-company.com/api
API_DOCS_TYPE=openapi  # or 'postman', 'readme', 'auto'
```

## Quality Results

- **Pass Rate**: 88-100% (target: 70%)
- **Average Quality**: 74-88/100
- **Test Count**: 8 comprehensive tests per story
- **Speed**: ~60-90 seconds per story

## Project Structure

```
womba/
├── src/
│   ├── aggregator/      # Jira, Confluence, API docs clients
│   ├── ai/              # AI test generation
│   ├── integrations/    # Zephyr integration
│   ├── models/          # Data models
│   ├── config/          # Settings
│   ├── core/            # Base classes
│   ├── utils/           # Utilities
│   └── mcp/             # MCP integration (optional)
├── tests/               # Test suite
├── generate_test_plan.py
├── upload_to_zephyr.py
└── evaluate_quality.py
```

## Requirements

- Python 3.9+
- Jira Cloud with API access
- Zephyr Scale
- OpenAI API key

## License

MIT

## Support

For issues and questions, please open an issue on GitHub.
