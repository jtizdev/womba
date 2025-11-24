# Womba 🧪

AI-powered test generation from Jira stories

## What it Does

Womba automatically generates comprehensive test cases by:
1. Collecting context from Jira (story, subtasks, linked issues, comments)
2. Retrieving related Confluence documentation
3. Using RAG (Retrieval-Augmented Generation) with ChromaDB for context-aware test generation

## Quick Start

### Option 1: Docker (Recommended for Production)

**Prerequisites**: Docker and Docker Compose installed

```bash
# Clone repository
git clone <repository-url>
cd womba

# Configure environment
cp env.example .env
# Edit .env with your credentials

# Start services
docker-compose up -d

# Verify deployment
curl http://localhost:8000/health

# Use CLI
docker exec -it womba-server womba generate PROJ-123

# Use API
curl -X POST "http://localhost:8000/api/v1/test-plans/generate" \
  -H "Content-Type: application/json" \
  -d '{"issue_key": "PROJ-123"}'
```

**See [docker/README.md](docker/README.md) for complete Docker deployment guide.**

### Option 2: Local Installation

```bash
pip install -r requirements-minimal.txt
```

### Configuration

Run interactive setup:

```bash
python3 womba_cli.py configure
```

You'll need:
- Atlassian URL, email, and API token
- (Optional) Automation repository path

### Usage

**Generate test plan only:**
```bash
python3 womba_cli.py generate PLAT-12345
```

**Generate and upload to Zephyr:**
```bash
python3 womba_cli.py generate PLAT-12345 --upload
```

**Full workflow (generate + upload + create branch + PR):**
```bash
python3 womba_cli.py all PLAT-12345
```

## Features

- **Smart Complexity Scoring**: Automatically determines test count based on story complexity
  - Simple stories (score < 5): 4-6 tests
  - Medium stories (5-12): 6-10 tests  
  - Complex stories (12+): 10-15 tests

- **Deep Context Analysis**: Uses all available context sources:
  - Subtasks (implementation details)
  - Linked issues (integration points)
  - Confluence docs (business requirements)
  - Comments (edge cases)

- **RAG-Powered Generation**: ChromaDB-based retrieval for context-aware test generation
  - Indexes existing test plans
  - Learns from your testing patterns
  - Provides consistent, high-quality tests

- **Flexible Access**:
  - **API Server**: REST API for integration (FastAPI on port 8000)
  - **CLI**: Command-line interface via `docker exec`
  - Both in one unified container with shared ChromaDB persistence

- **Clean Output**: Test titles are clear and specific (no generic prefixes)

## Docker Deployment

Womba can be deployed using Docker:

```bash
# Build and run with docker-compose (recommended)
docker-compose up -d

# Use API
curl http://localhost:8000/health

# Use CLI
docker exec -it womba-server womba generate PROJ-123
```

**What's included in the container:**
- ✅ FastAPI server (port 8000) + CLI access
- ✅ ChromaDB for RAG functionality
- ✅ All core features (indexing, searching, test plan generation)
- ✅ Health checks and automatic restarts
- ✅ Persistent storage for vector database
- ✅ Production-ready configuration

**Core functionality available:**
- Generate test plans via API or CLI
- Index Jira stories and test plans into RAG
- Search semantic context from ChromaDB
- Upload test cases to Zephyr Scale
- Full workflow automation (generate + upload + PR)

## Configuration Files

- `~/.womba/config.yml` - Your credentials and preferences
- `.env` (optional) - Environment-specific overrides

## Documentation

- [Setup Guide](docs/SETUP.md) - Detailed setup instructions
- [API Reference](docs/API.md) - API server documentation
- [Automation](docs/AUTOMATION.md) - Code generation setup

## Requirements

- Python 3.9+
- Atlassian account with Jira and Confluence access

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT

