#!/usr/bin/env python3
"""
Interactive setup script for Womba configuration.
This will guide you through setting up your .env file.
"""

import os
from pathlib import Path


def main():
    """Interactive configuration setup"""
    print("╔════════════════════════════════════════════════════════════════╗")
    print("║                                                                ║")
    print("║             🔧 Womba Configuration Setup                       ║")
    print("║                                                                ║")
    print("╚════════════════════════════════════════════════════════════════╝")
    print()
    print("This wizard will help you configure Womba with your credentials.")
    print()
    
    # Check if .env already exists
    env_path = Path('.env')
    if env_path.exists():
        response = input("⚠️  .env file already exists. Overwrite? (y/N): ")
        if response.lower() != 'y':
            print("❌ Setup cancelled.")
            return
    
    # Collect configuration
    print("\n📋 Jira Configuration")
    print("─" * 60)
    jira_url = input("Jira Base URL (e.g., https://your-company.atlassian.net): ").strip()
    jira_email = input("Jira Email: ").strip()
    jira_token = input("Jira API Token: ").strip()
    
    print("\n📋 Confluence Configuration (Optional - press Enter to use same as Jira)")
    print("─" * 60)
    confluence_url = input(f"Confluence URL [{jira_url}/wiki]: ").strip() or f"{jira_url}/wiki"
    confluence_email = input(f"Confluence Email [{jira_email}]: ").strip() or jira_email
    confluence_token = input(f"Confluence API Token [{jira_token}]: ").strip() or jira_token
    
    print("\n📋 Zephyr Scale Configuration")
    print("─" * 60)
    zephyr_token = input("Zephyr API Token: ").strip()
    
    print("\n📋 OpenAI Configuration")
    print("─" * 60)
    openai_key = input("OpenAI API Key (sk-...): ").strip()
    
    print("\n📋 Optional Configuration (press Enter to skip)")
    print("─" * 60)
    api_docs_url = input("API Documentation URL (optional): ").strip()
    figma_token = input("Figma API Token (optional): ").strip()
    
    # Create .env content
    env_content = f"""# Jira Configuration
JIRA_BASE_URL={jira_url}
JIRA_EMAIL={jira_email}
JIRA_API_TOKEN={jira_token}

# Confluence Configuration
CONFLUENCE_BASE_URL={confluence_url}
CONFLUENCE_EMAIL={confluence_email}
CONFLUENCE_API_TOKEN={confluence_token}

# Zephyr Scale Configuration
ZEPHYR_API_KEY={zephyr_token}
ZEPHYR_BASE_URL=https://api.zephyrscale.smartbear.com/v2

# OpenAI Configuration
OPENAI_API_KEY={openai_key}

# Optional: Customer API Documentation
{f'API_DOCS_URL={api_docs_url}' if api_docs_url else '# API_DOCS_URL='}
{f'API_DOCS_TYPE=auto' if api_docs_url else '# API_DOCS_TYPE=auto'}

# Optional: Figma
{f'FIGMA_API_TOKEN={figma_token}' if figma_token else '# FIGMA_API_TOKEN='}

# Application Settings
SECRET_KEY=womba-secret-key-{os.urandom(8).hex()}
ENVIRONMENT=production
LOG_LEVEL=INFO
DATABASE_URL=sqlite:///./womba.db

# AI Model Configuration
DEFAULT_AI_MODEL=gpt-4o
TEMPERATURE=0.8
MAX_TOKENS=10000
"""
    
    # Write .env file
    with open('.env', 'w') as f:
        f.write(env_content)
    
    print("\n✅ Configuration saved to .env")
    print("\n📋 Next steps:")
    print("   1. Test: womba generate PLAT-12991")
    print("   2. Or: python3 generate_test_plan.py PLAT-12991")
    print()
    print("💡 Tip: Your .env file is gitignored and will not be committed.")
    print()


if __name__ == '__main__':
    main()
