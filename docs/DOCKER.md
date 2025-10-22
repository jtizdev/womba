# 🐳 Running Womba with Docker

This guide explains how to use Womba with Docker, including RAG (vector database) support.

## Quick Start

### 1. Build the Docker Image

```bash
docker build -f Dockerfile.cli -t womba:latest .
```

### 2. Using Docker Compose (Recommended)

Docker Compose makes it easier to manage volumes and persistent data:

```bash
# Start the container
docker-compose up -d

# Run Womba commands
docker-compose exec womba womba configure
docker-compose exec womba womba index-all
docker-compose exec womba womba generate PLAT-12991

# Check RAG stats
docker-compose exec womba womba rag-stats

# Stop the container
docker-compose down
```

### 3. Using Docker Directly

```bash
# Run container with volume mount for RAG persistence
docker run -it --rm \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/.env:/app/.env:ro \
  womba:latest \
  womba rag-stats

# Interactive shell
docker run -it --rm \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/.env:/app/.env:ro \
  womba:latest \
  bash
```

## Data Persistence

### RAG Database Location

- **Inside Container**: `/app/data/chroma/`
- **Host Machine**: `./data/chroma/` (mounted as volume)

The RAG database is **automatically persisted** using Docker volumes, so your indexed data survives container restarts!

### What Gets Persisted:

```
data/
├── chroma/
│   ├── chroma.sqlite3           # Document metadata & collections
│   └── <collection-id>/         # Vector embeddings
│       ├── data_level0.bin
│       └── ...
```

## Configuration

### Option 1: Mount `.env` File (Recommended)

Create a `.env` file on your host machine:

```bash
# .env
OPENAI_API_KEY=sk-...
JIRA_URL=https://yourcompany.atlassian.net
JIRA_EMAIL=you@company.com
JIRA_API_TOKEN=...
ZEPHYR_API_TOKEN=...
CONFLUENCE_URL=https://yourcompany.atlassian.net/wiki
CONFLUENCE_EMAIL=you@company.com
CONFLUENCE_API_TOKEN=...
```

Then mount it:

```bash
docker run -v $(pwd)/.env:/app/.env:ro womba:latest womba configure
```

### Option 2: Use Interactive Setup

```bash
docker-compose exec womba womba configure
# Follow the prompts to set up your API keys
```

## Common Workflows

### First-Time Setup

```bash
# 1. Start container
docker-compose up -d

# 2. Configure Womba
docker-compose exec womba womba configure

# 3. Index all existing data
docker-compose exec womba womba index-all

# This will take 5-15 minutes for large projects
# The RAG database is automatically saved to ./data/chroma
```

### Daily Usage

```bash
# Generate test plan with RAG
docker-compose exec womba womba generate PLAT-12991

# Upload to Zephyr
docker-compose exec womba womba upload PLAT-12991

# Full workflow
docker-compose exec womba womba all PLAT-12991
```

### RAG Management

```bash
# View RAG statistics
docker-compose exec womba womba rag-stats

# Index a specific story
docker-compose exec womba womba index PLAT-12991

# Re-index everything (useful after team adds new tests)
docker-compose exec womba womba index-all

# Clear RAG database (fresh start)
docker-compose exec womba womba rag-clear --yes
```

## Volume Management

### Backup RAG Database

```bash
# Create backup
tar -czf womba-rag-backup-$(date +%Y%m%d).tar.gz data/

# Restore from backup
tar -xzf womba-rag-backup-20231021.tar.gz
```

### Reset RAG Database

```bash
# Option 1: Use CLI
docker-compose exec womba womba rag-clear --yes

# Option 2: Delete files directly
rm -rf data/chroma/*
docker-compose exec womba womba index-all
```

### Check Database Size

```bash
du -sh data/chroma/
# Example output: 17M data/chroma/
```

## Troubleshooting

### Container Can't Write to Volume

If you get permission errors:

```bash
# Fix permissions
sudo chown -R $(id -u):$(id -g) data/

# Or create directory first
mkdir -p data/chroma
docker-compose up -d
```

### RAG Database Not Persisting

Make sure the volume is properly mounted:

```bash
# Check volume mounts
docker-compose exec womba ls -la /app/data/chroma

# Should show chroma.sqlite3 and collection directories
```

### Out of Disk Space

ChromaDB can grow large with many indexed documents:

- **1000 tests**: ~17 MB
- **10,000 tests**: ~170 MB
- **100,000 tests**: ~1.7 GB

Monitor disk usage:

```bash
docker system df
df -h ./data
```

## Production Deployment

### Environment Variables

For production, use environment variables instead of `.env` file:

```yaml
# docker-compose.prod.yml
services:
  womba:
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - JIRA_URL=${JIRA_URL}
      - JIRA_EMAIL=${JIRA_EMAIL}
      # ... other secrets from CI/CD
```

### Shared RAG Database (Team Setup)

For teams, you can share a single RAG database:

```bash
# Mount a network/shared volume
volumes:
  - /shared/womba-rag:/app/data

# Multiple team members use the same indexed data
```

### Regular Re-indexing (Cron Job)

Keep RAG fresh with scheduled re-indexing:

```bash
# crontab entry
0 2 * * * docker-compose exec womba womba index-all
```

## Architecture

```
┌─────────────────────────────────┐
│   Docker Container (womba)      │
│                                 │
│  ┌──────────────────────────┐  │
│  │   Womba CLI              │  │
│  │   (Python App)           │  │
│  └──────────────────────────┘  │
│              ↓                  │
│  ┌──────────────────────────┐  │
│  │   ChromaDB               │  │
│  │   /app/data/chroma/      │←─┼─── Volume Mount
│  └──────────────────────────┘  │
└─────────────────────────────────┘
                ↓
    ┌─────────────────────────┐
    │   Host Machine          │
    │   ./data/chroma/        │
    │   (Persistent Storage)  │
    └─────────────────────────┘
```

## Next Steps

- See [RAG.md](./RAG.md) for RAG concepts and workflow
- See [SETUP.md](./SETUP.md) for configuration details
- See [API.md](./API.md) for API server deployment

