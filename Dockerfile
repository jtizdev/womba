# Womba - AI-Powered Test Generation with RAG
# Unified container with both API server and CLI functionality
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies (including Node.js and npm for MCP server)
RUN apt-get update && apt-get install -y \
    git \
    curl \
    ca-certificates \
    gnupg \
    && mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main" | tee /etc/apt/sources.list.d/nodesource.list \
    && apt-get update && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN useradd -m -u 1000 womba && \
    chown -R womba:womba /app

# Copy requirements first (for layer caching optimization)
COPY requirements-minimal.txt .

# Install Python dependencies (includes ChromaDB for RAG and MCP client)
RUN pip install --no-cache-dir -r requirements-minimal.txt

# Install mcp-remote for GitLab MCP connection (for fallback endpoint extraction)
# Note: Using npx -y so it doesn't need global install, but keeping npm available
RUN npm install -g mcp-remote || true

# Copy application code
COPY src/ ./src/
COPY womba_cli.py .
COPY setup.py .
COPY pyproject.toml .
COPY README.md .

# Copy entrypoint script
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Install Womba package (provides both 'womba' CLI and API)
RUN pip install -e .

# Create data directory for ChromaDB with proper permissions
RUN mkdir -p /app/data/chroma && \
    chown -R womba:womba /app/data

# Switch to non-root user
USER womba

# Expose API port
EXPOSE 8000

# Health check for API server
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Volume mount point for persistent RAG database
VOLUME ["/app/data"]

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    HOST=0.0.0.0 \
    PORT=8000

# Set entrypoint for auto-configuration and signal handling
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]

# Default: Run FastAPI server
# CLI accessible via: docker exec -it womba-server womba <command>
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "info"]

# Labels for Docker Hub
LABEL maintainer="PlainID <support@plainid.com>"
LABEL description="Womba - AI-Powered Test Generation with RAG (API + CLI)"
LABEL version="2.0.0"
LABEL org.opencontainers.image.source="https://github.com/plainid/womba"
LABEL org.opencontainers.image.vendor="PlainID"
LABEL org.opencontainers.image.title="Womba"
LABEL org.opencontainers.image.description="AI-powered test generation from Jira stories with RAG support"

