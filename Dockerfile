# Womba - AI-Powered Test Generation
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for caching)
COPY requirements-render.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements-render.txt

# Copy application code
COPY src/ ./src/
COPY generate_test_plan.py .
COPY upload_to_zephyr.py .
COPY evaluate_quality.py .
COPY setup_env.py .

# No entrypoint - let Render use its startCommand from render.yaml
# Default CMD will be overridden by Render's startCommand
CMD ["bash"]

# Labels
LABEL maintainer="PlainID <support@plainid.com>"
LABEL description="Womba - AI-Powered Test Generation for Jira"
LABEL version="1.0.0"

