#!/bin/bash
set -e

# Auto-create Womba config from environment variables
if [ ! -f /home/womba/.womba/config.yml ]; then
  echo "📝 Creating Womba configuration from environment variables..."
  mkdir -p /home/womba/.womba
  
  python3 << 'EOF'
import os
import yaml
from pathlib import Path

config = {
    'atlassian_url': os.getenv('ATLASSIAN_BASE_URL', ''),
    'atlassian_email': os.getenv('ATLASSIAN_EMAIL', ''),
    'atlassian_api_token': os.getenv('ATLASSIAN_API_TOKEN', ''),
    'zephyr_api_token': os.getenv('ZEPHYR_API_TOKEN', ''),
    'openai_api_key': os.getenv('OPENAI_API_KEY', ''),
    'gitlab_token': os.getenv('GITLAB_TOKEN', ''),
    'project_key': os.getenv('DEFAULT_PROJECT_KEY', 'PLAT'),
    'ai_model': os.getenv('AI_MODEL', 'gpt-4o'),
    'auto_upload': os.getenv('AUTO_UPLOAD', 'false').lower() == 'true',
    'auto_create_pr': os.getenv('AUTO_CREATE_PR', 'false').lower() == 'true',
    'ai_tool': os.getenv('AI_TOOL', 'aider'),
    'enable_rag': os.getenv('ENABLE_RAG', 'true').lower() == 'true',
    'rag_auto_index': os.getenv('RAG_AUTO_INDEX', 'true').lower() == 'true',
}

config_path = Path('/home/womba/.womba/config.yml')
with open(config_path, 'w') as f:
    yaml.safe_dump(config, f, default_flow_style=False)

# Verify required fields
missing = []
if not config['atlassian_url']:
    missing.append('ATLASSIAN_BASE_URL')
if not config['atlassian_api_token']:
    missing.append('ATLASSIAN_API_TOKEN')
if not config['zephyr_api_token']:
    missing.append('ZEPHYR_API_TOKEN')
if not config['openai_api_key']:
    missing.append('OPENAI_API_KEY')

if missing:
    print(f"⚠️  Warning: Missing environment variables: {', '.join(missing)}")
    print("Some features may not work correctly.")
else:
    print("✅ Configuration created successfully")
EOF
else
  echo "ℹ️  Using existing Womba configuration at /home/womba/.womba/config.yml"
fi

# Handle signals properly for graceful shutdown
trap 'echo "Received SIGTERM, shutting down gracefully..."; exit 0' SIGTERM
trap 'echo "Received SIGINT, shutting down gracefully..."; exit 0' SIGINT

# Execute the command passed to the container
exec "$@"

