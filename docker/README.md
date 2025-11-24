# Womba Docker Deployment Guide

Complete guide for deploying Womba using Docker on your local infrastructure or Docker Hub.

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Building Images](#building-images)
- [Docker Hub Deployment](#docker-hub-deployment)
- [Configuration](#configuration)
- [Usage](#usage)
- [Health Monitoring](#health-monitoring)
- [Volume Management](#volume-management)
- [Troubleshooting](#troubleshooting)

## Architecture Overview

Womba uses a **unified single-container architecture**:

- **womba**: One container running both FastAPI API server (port 8000) and CLI
- **API access**: `http://localhost:8000` for REST endpoints
- **CLI access**: `docker exec -it womba-server womba <command>`

Container includes:
- **ChromaDB volume**: Persistent RAG database
- **Network**: Bridge network for external communication
- **Configuration**: Environment variables from `.env` file

## Prerequisites

- Docker Engine 20.10+ or Docker Desktop
- Docker Compose 1.29+ (or Docker Compose V2)
- At least 2GB free disk space
- Network access to:
  - Your Atlassian instance
  - AI provider APIs (Anthropic/OpenAI)
  - Docker Hub (for pushing images)

## Quick Start

### 1. Clone and Configure

```bash
# Clone the repository
git clone <repository-url>
cd womba

# Copy environment template
cp env.example .env

# Edit .env with your credentials
nano .env  # or vim, code, etc.
```

**Required configuration** (in `.env`):
- `ATLASSIAN_BASE_URL`, `ATLASSIAN_EMAIL`, `ATLASSIAN_API_TOKEN`
- At least one AI key: `ANTHROPIC_API_KEY` or `OPENAI_API_KEY`
- `ZEPHYR_API_TOKEN` (for uploading test cases)

**Automatic Configuration**: The container automatically creates `~/.womba/config.yml` from environment variables on first startup. No manual configuration needed!

### 2. Start Services

```bash
# Build and start both containers
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f
```

### 3. Verify Deployment

```bash
# Check API health
curl http://localhost:8000/health

# Expected response:
# {"status":"healthy","environment":"production"}

# Access CLI
docker exec -it womba-server womba --help
```

## Building Images

### Build Image

```bash
# Build unified image with API + CLI
docker build -t womba:latest .
```

### Build with Specific Version Tags

```bash
# Tag with version
docker build -t womba:2.0.0 -t womba:latest .
```

### Build via Docker Compose

```bash
# Build service defined in docker-compose.yml
docker-compose build

# Build without cache
docker-compose build --no-cache
```

## Docker Hub Deployment

### 1. Authenticate to Docker Hub

```bash
docker login
# Enter your Docker Hub credentials
```

### 2. Tag Image for Your Organization

```bash
# Tag with your organization
docker tag womba:latest yourorg/womba:latest

# Tag with version
docker tag womba:latest yourorg/womba:2.0.0
```

### 3. Push to Docker Hub

```bash
# Push latest tag
docker push yourorg/womba:latest

# Push specific version
docker push yourorg/womba:2.0.0
```

### 4. Pull and Run on Any Server

```bash
# On your deployment server
docker pull yourorg/womba:latest

# Run with docker-compose
docker-compose up -d

# Or run standalone
docker run -d \
  --name womba-server \
  -p 8000:8000 \
  -v womba-data:/app/data \
  --env-file .env \
  yourorg/womba:latest
```

## Configuration

### Automatic Configuration from Environment Variables

Womba automatically creates its configuration on container startup from environment variables in your `.env` file. **No manual configuration needed!**

The container's entrypoint script reads the following environment variables and creates `~/.womba/config.yml`:

**Required Variables:**

```bash
# Atlassian (Required)
ATLASSIAN_BASE_URL=https://yourcompany.atlassian.net
ATLASSIAN_EMAIL=your.email@company.com
ATLASSIAN_API_TOKEN=ATATT3xFfGF0...

# Zephyr Scale (Required for test upload)
ZEPHYR_API_TOKEN=eyJ0eXAiOiJKV1QiLCJh...

# AI Provider (at least one required)
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
```

**Optional Variables:**

```bash
# Default project key
DEFAULT_PROJECT_KEY=PLAT

# AI Model Configuration
# Use gpt-4o-2024-08-06 for JSON schema support + 16K output tokens
# Alternative: gpt-4-turbo (max 4096 tokens), gpt-4o-mini (max 16K tokens)
AI_MODEL=gpt-4o-2024-08-06
MAX_TOKENS=10000
TEMPERATURE=0.8

# Feature flags
ENABLE_RAG=true
RAG_AUTO_INDEX=true
AUTO_UPLOAD=false
AUTO_CREATE_PR=false

# AI tool for code generation
AI_TOOL=aider
```

### How It Works

1. Container starts and runs `/usr/local/bin/docker-entrypoint.sh`
2. Entrypoint checks if `~/.womba/config.yml` exists
3. If not, it creates the config from environment variables
4. Then starts the API server (or runs your command)

This means:
- ✅ No manual `womba configure` needed
- ✅ Works in CI/CD pipelines
- ✅ Config persists if you mount `/home/womba/.womba` as a volume
- ✅ Environment variables take precedence on fresh starts

### Volume Configuration

The `womba-chroma-data` named volume persists ChromaDB data:

```yaml
volumes:
  womba-chroma-data:
    driver: local
```

To use a specific host path:

```yaml
volumes:
  womba-chroma-data:
    driver: local
    driver_opts:
      type: none
      o: bind
      device: /path/to/your/data
```

### Network Configuration

By default, containers use a bridge network. To connect to external services:

```yaml
networks:
  womba-network:
    driver: bridge
  external-network:
    external: true
```

## Usage

### API Server

#### Generate Test Plan via API

```bash
# Basic test plan generation
curl -X POST "http://localhost:8000/api/v1/test-plans/generate" \
  -H "Content-Type: application/json" \
  -d '{"issue_key": "PROJ-123"}'

# With Zephyr upload
curl -X POST "http://localhost:8000/api/v1/test-plans/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "issue_key": "PROJ-123",
    "upload_to_zephyr": true,
    "project_key": "PROJ"
  }'
```

#### RAG Operations

```bash
# Check RAG statistics
curl http://localhost:8000/api/v1/rag/stats

# Index a story
curl -X POST "http://localhost:8000/api/v1/rag/index" \
  -H "Content-Type: application/json" \
  -d '{"story_key": "PROJ-123"}'

# Search RAG
curl -X POST "http://localhost:8000/api/v1/rag/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "authentication flow",
    "collection": "test_plans",
    "top_k": 10
  }'
```

#### API Documentation

Visit `http://localhost:8000/docs` for interactive Swagger UI documentation.

### CLI Access

#### Access CLI

```bash
# Interactive shell
docker exec -it womba-server bash

# Run CLI commands directly
docker exec -it womba-server womba --help
```

#### CLI Commands

```bash
# Generate test plan
docker exec -it womba-server womba generate PROJ-123

# Generate and upload to Zephyr
docker exec -it womba-server womba generate PROJ-123 --upload

# Full workflow (generate + upload + PR)
docker exec -it womba-server womba all PROJ-123

# Configure Womba
docker exec -it womba-server womba configure

# RAG commands
docker exec -it womba-server womba rag refresh
docker exec -it womba-server womba rag stats
```

### Managing Services

```bash
# Start service
docker-compose up -d

# Stop service
docker-compose down

# Restart service
docker-compose restart

# View logs
docker-compose logs -f

# View real-time container stats
docker stats womba-server
```

## Health Monitoring

### API Health Check

The container includes automated health checks:

```bash
# Check health status
docker inspect womba-server --format='{{.State.Health.Status}}'

# View health check logs
docker inspect womba-server --format='{{json .State.Health}}' | jq
```

Health check configuration:
- **Interval**: Every 30 seconds
- **Timeout**: 10 seconds
- **Retries**: 3 failed checks before unhealthy
- **Start period**: 40 seconds for initialization

### Manual Health Verification

```bash
# API health endpoint
curl http://localhost:8000/health

# API root endpoint
curl http://localhost:8000/

# Check ChromaDB is accessible
docker exec -it womba-server ls -la /app/data/chroma
```

## Volume Management

### Backup ChromaDB Data

```bash
# Stop services first
docker-compose down

# Backup the volume
docker run --rm -v womba-chroma-data:/source -v $(pwd):/backup \
  alpine tar czf /backup/chroma-backup-$(date +%Y%m%d).tar.gz -C /source .

# Restart services
docker-compose up -d
```

### Restore ChromaDB Data

```bash
# Stop services
docker-compose down

# Restore from backup
docker run --rm -v womba-chroma-data:/target -v $(pwd):/backup \
  alpine tar xzf /backup/chroma-backup-20240101.tar.gz -C /target

# Restart services
docker-compose up -d
```

### Clear ChromaDB Data

```bash
# Via API
curl -X DELETE "http://localhost:8000/api/v1/rag/clear"

# Or manually
docker-compose down
docker volume rm womba-chroma-data
docker-compose up -d
```

### View Volume Location

```bash
# Find volume mount point
docker volume inspect womba-chroma-data

# View volume contents
docker run --rm -v womba-chroma-data:/data alpine ls -la /data
```

## Troubleshooting

### API Not Responding

```bash
# Check if container is running
docker ps | grep womba-server

# Check logs for errors
docker-compose logs womba

# Restart container
docker-compose restart

# Check health status
docker inspect womba-server --format='{{.State.Health.Status}}'
```

### ChromaDB Connection Issues

```bash
# Verify volume is mounted
docker exec -it womba-server ls -la /app/data/chroma

# Check permissions
docker exec -it womba-server stat /app/data/chroma

# Reset ChromaDB
docker-compose down
docker volume rm womba-chroma-data
docker-compose up -d
```

### Configuration Issues

```bash
# Verify .env file is loaded
docker exec -it womba-server env | grep ATLASSIAN

# Check configuration
docker exec -it womba-server womba configure

# Re-mount .env file
docker-compose down
docker-compose up -d
```

### Build Failures

```bash
# Clear build cache
docker-compose build --no-cache

# Check Dockerfile syntax
docker build -f Dockerfile.api --check .

# View build logs
docker-compose build 2>&1 | tee build.log
```

### Container Won't Start

```bash
# View container logs
docker logs womba-server

# Check resource constraints
docker stats womba-server

# Inspect container state
docker inspect womba-server
```

### Network Issues

```bash
# Check network connectivity
docker network inspect womba-network

# Test DNS resolution
docker exec -it womba-server nslookup yourcompany.atlassian.net

# Test external connectivity
docker exec -it womba-server curl -v https://api.anthropic.com
```

### Log Files Too Large

Log files are automatically rotated (max 10MB per file, 3 files):

```bash
# Check current log sizes
docker inspect womba-server --format='{{.HostConfig.LogConfig}}'

# Clear logs manually
docker-compose down
sudo truncate -s 0 $(docker inspect --format='{{.LogPath}}' womba)
docker-compose up -d
```

### Permission Denied Errors

Container runs as non-root user `womba` (UID 1000):

```bash
# Fix volume permissions
docker-compose down
docker run --rm -v womba-chroma-data:/data alpine chown -R 1000:1000 /data
docker-compose up -d
```

### API Key Issues

```bash
# Verify API keys are loaded
docker exec -it womba-server env | grep API_KEY

# Test Anthropic key
docker exec -it womba-server python3 -c "import os; print(os.getenv('ANTHROPIC_API_KEY')[:20])"

# Test OpenAI key
docker exec -it womba-server python3 -c "import os; print(os.getenv('OPENAI_API_KEY')[:20])"
```

## Advanced Configuration

### Custom Docker Compose Override

Create `docker-compose.override.yml` for local customizations:

```yaml
version: '3.8'

services:
  womba:
    ports:
      - "8080:8000"  # Use different host port
    environment:
      - LOG_LEVEL=DEBUG
```

### Production Deployment Checklist

#### Security
- [ ] Change `SECRET_KEY` in `.env` to a strong random value (32+ characters)
- [ ] Never commit `.env` file to version control
- [ ] Use Docker secrets or environment injection for sensitive values in production
- [ ] Container runs as non-root user (womba:1000) ✅
- [ ] `.env` file mounted read-only ✅
- [ ] No secrets baked into Docker image ✅

#### Operations
- [ ] Set appropriate `LOG_LEVEL` (INFO or WARNING for production)
- [ ] Configure proper backup schedule for ChromaDB volume
- [ ] Set up log aggregation (ELK, Splunk, Datadog, etc.)
- [ ] Configure SSL/TLS termination (reverse proxy like nginx/traefik)
- [ ] Set up monitoring and alerting (health endpoint: `/health`)
- [ ] Review and adjust resource limits
- [ ] Test disaster recovery procedures
- [ ] Enable log rotation (configured by default: 10MB x 3 files) ✅
- [ ] Test graceful shutdown (SIGTERM handling) ✅

#### Configuration
- [ ] Verify all required environment variables are set
- [ ] Test with minimal permissions (non-root user)
- [ ] Validate API keys before deploying
- [ ] Set appropriate `DEFAULT_PROJECT_KEY` for your organization

### Resource Limits

Add resource constraints in `docker-compose.yml`:

```yaml
services:
  womba:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
        reservations:
          cpus: '1'
          memory: 2G
```

## Support

For issues or questions:
- GitHub Issues: See repository issues
- Documentation: See docs/ directory

