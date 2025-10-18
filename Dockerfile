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

# Create entrypoint script
RUN echo '#!/bin/bash\n\
if [ "$1" = "generate" ]; then\n\
    python3 generate_test_plan.py "$2"\n\
elif [ "$1" = "upload" ]; then\n\
    python3 upload_to_zephyr.py "$2"\n\
elif [ "$1" = "evaluate" ]; then\n\
    python3 evaluate_quality.py "$2"\n\
else\n\
    exec "$@"\n\
fi' > /app/entrypoint.sh && chmod +x /app/entrypoint.sh

# Set entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]

# Default command
CMD ["bash"]

# Labels
LABEL maintainer="PlainID <support@plainid.com>"
LABEL description="Womba - AI-Powered Test Generation for Jira"
LABEL version="1.0.0"

