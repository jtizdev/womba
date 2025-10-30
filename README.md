# Womba - AI-Powered Test Generation for Jira

**Automatically generate comprehensive test cases from Jira stories and upload to Zephyr Scale.**

## Features

- 🤖 **AI-Powered**: Uses GPT-4o to generate feature-specific test cases
- 🧠 **RAG-Enhanced**: Learns from your company's context (past tests, docs, patterns)
- 📊 **High Quality**: 88%+ pass rate with built-in quality scoring
- 🔗 **Jira Integration**: Fetches stories, subtasks, comments, and linked issues
- 📚 **Confluence Integration**: Pulls related documentation automatically
- 📘 **PlainID Docs Awareness**: Indexes [docs.plainid.io](https://docs.plainid.io/) endpoints for request/response payload details
- 🎯 **Smart Filtering**: Filters to top 50 most relevant existing tests
- 📁 **Intelligent Organization**: Suggests optimal folder structure
- ✅ **Zephyr Upload**: Uploads tests with steps, links to stories
- 🔄 **Continuous Learning**: Auto-indexes new test plans for future improvement

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

### First Time Setup

```bash
# 1. Interactive setup
womba configure

# 2. Index existing tests (one-time, improves quality)
womba index-all
# This fetches ALL existing tests from Zephyr and indexes them for RAG
# Takes 1-5 minutes depending on number of tests
```

### Daily Usage - Full Workflow

```bash
# Option 1: Complete workflow (recommended)
womba all PLAT-12991
# Does: Generate → Upload → Create automated tests → Create PR

# Option 2: Just generate and upload
womba generate PLAT-12991 --upload

# Option 3: Step by step
womba generate PLAT-12991   # Generate test plan (with RAG)
womba evaluate PLAT-12991   # Check quality (optional)
womba upload PLAT-12991     # Upload to Zephyr
womba index PLAT-12991      # Index for future use (optional, auto-enabled)
```

### How RAG Improves Your Tests

RAG (Retrieval-Augmented Generation) makes tests **company-specific**:
- Uses **your** terminology from Confluence docs
- Follows **your** test patterns from existing tests
- Matches **your** test structure and style
- Learns from **your** past test plans

**Enable by default**: RAG is automatically enabled. To disable: Set `ENABLE_RAG=false` in config.

### Keeping RAG Fresh

**Auto-indexed:**
- ✅ Test plans you generate (automatic, no action needed)

**Manual refresh needed:**
- ⚠️ New tests teammates upload to Zephyr
- ⚠️ New/updated Confluence docs
- ⚠️ Other people's test plans

**Recommended refresh schedule:**
```bash
# Weekly (captures team's work)
womba index-all

# Or before important features
womba index PLAT-12991  # Fresh Confluence docs for this story
womba generate PLAT-12991
```

## Configuration

Create a `.env` file with your credentials:

```bash
# Atlassian (Jira & Confluence)
ATLASSIAN_BASE_URL=https://your-company.atlassian.net
ATLASSIAN_EMAIL=your-email@company.com
ATLASSIAN_API_TOKEN=your-atlassian-token

# Zephyr Scale
ZEPHYR_API_TOKEN=your-zephyr-token

# OpenAI (required for RAG embeddings)
OPENAI_API_KEY=your-openai-api-key

# RAG Configuration (optional)
ENABLE_RAG=true              # Enable RAG (recommended)
RAG_AUTO_INDEX=true          # Auto-index new test plans
RAG_COLLECTION_PATH=./data/chroma  # Vector database path

# PlainID Documentation (optional)
PLAINID_DOC_INDEX_ENABLED=true
PLAINID_DOC_URLS="https://docs.plainid.io/authorization-apis/runtime"
PLAINID_DOC_PROJECT_KEY=GLOBAL  # Metadata tag for external docs

# Optional: API Documentation
API_DOCS_URL=https://docs.your-company.com/api
API_DOCS_TYPE=openapi  # or 'postman', 'readme', 'auto'
```

Or use interactive setup:
```bash
womba configure
# Walks you through all settings including RAG
```

## Quality Results

- **Pass Rate**: 88-100% (target: 70%)
- **Average Quality**: 74-88/100  
- **Test Count**: 8 comprehensive tests per story
- **Speed**: ~60-90 seconds per story (RAG adds ~0.5s)
- **With RAG**: Tests match your company's style and terminology perfectly

## RAG Commands

```bash
# View RAG database statistics
womba rag-stats

# Index all existing tests (one-time setup)
womba index-all

# Index a specific story
womba index PLAT-12991

# Clear RAG database
womba rag-clear
```

See [docs/RAG.md](docs/RAG.md) for detailed RAG documentation.

## Project Structure

```
womba/
├── src/
│   ├── aggregator/      # Jira, Confluence, API docs clients
│   ├── ai/              # AI test generation + RAG
│   │   ├── rag_store.py           # Vector database
│   │   ├── embedding_service.py   # OpenAI embeddings
│   │   ├── context_indexer.py     # Index documents
│   │   ├── rag_retriever.py       # Semantic search
│   │   └── test_plan_generator.py # AI generation with RAG
│   ├── integrations/    # Zephyr integration
│   ├── models/          # Data models
│   ├── config/          # Settings
│   ├── core/            # Base classes
│   ├── utils/           # Utilities
│   ├── api/             # FastAPI web interface
│   ├── automation/      # Test code generation
│   └── workflows/       # Full workflows
├── tests/               # Test suite
│   ├── unit/            # Unit tests (with mocks)
│   ├── integration/     # Integration tests
│   └── manual/          # Manual validation scripts
├── docs/
│   ├── RAG.md           # RAG documentation
│   ├── AUTOMATION.md    # Automation docs
│   └── API.md           # API documentation
├── data/
│   └── chroma/          # RAG vector database
└── womba_cli.py         # CLI entry point
```

## Requirements

- Python 3.9+
- Jira Cloud with API access
- Zephyr Scale
- OpenAI API key (for AI generation + RAG embeddings)
- ~500MB disk space for RAG vector database (scales with data)

## License

MIT

## Documentation

- **[RAG Guide](docs/RAG.md)** - Comprehensive RAG documentation
- **[Automation Guide](docs/AUTOMATION.md)** - Automated test code generation
- **[API Documentation](docs/API.md)** - REST API reference
- **[GitHub MCP Integration](docs/github-mcp-integration.md)** - Bridge MCP tools with repository context
- **[Setup Guide](docs/SETUP.md)** - Detailed setup instructions

## Troubleshooting

### RAG Not Working?
```bash
# Check if RAG is enabled and has data
womba rag-stats

# Re-index if needed
womba index-all
```

See [docs/RAG.md#troubleshooting](docs/RAG.md#troubleshooting) for detailed troubleshooting.

## Support

For issues and questions, please open an issue on GitHub.
