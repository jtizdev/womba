"""
Interactive configuration wizard for Womba
"""

import sys
from pathlib import Path
from loguru import logger

from src.config.user_config import WombaConfig
from src.config.config_manager import ConfigManager


def prompt_for_config() -> WombaConfig:
    """Interactive prompt for configuration"""
    print("\n" + "=" * 80)
    print("🚀 Womba First-Time Setup")
    print("=" * 80)
    print("\nLet's configure Womba to work with your Atlassian (Jira/Confluence), Zephyr, and repositories.")
    print("You can skip optional fields by pressing Enter.\n")
    
    config = WombaConfig()
    
    # Atlassian settings
    print("📋 Atlassian Configuration (Jira & Confluence)")
    print("-" * 40)
    config.atlassian_url = input("Atlassian URL (e.g., https://yourcompany.atlassian.net): ").strip()
    config.atlassian_email = input("Atlassian email: ").strip()
    config.atlassian_api_token = input("Atlassian API token: ").strip()
    
    # Zephyr settings
    print("\n🧪 Zephyr Scale Configuration")
    print("-" * 40)
    config.zephyr_api_token = input("Zephyr API token: ").strip()
    config.project_key = input("Default project key (e.g., PLAT) [optional]: ").strip()
    
    # AI settings
    print("\n🤖 AI Configuration")
    print("-" * 40)
    config.openai_api_key = input("OpenAI API key: ").strip()
    model_choice = input("AI model (gpt-4o/gpt-4-turbo) [gpt-4o]: ").strip()
    if model_choice:
        config.ai_model = model_choice
    
    # Repository settings (optional)
    print("\n📁 Repository Configuration (Optional)")
    print("-" * 40)
    print("If you always work with the same automation repository, you can set it here.")
    repo_input = input("Default repository path [skip]: ").strip()
    if repo_input:
        config.repo_path = repo_input
        
        # Try to detect git provider
        manager = ConfigManager()
        config.git_provider = manager.detect_git_provider(repo_input)
        config.git_remote_url = manager.get_git_remote_url(repo_input)
        
        if config.git_provider != "auto":
            print(f"  ✓ Detected git provider: {config.git_provider}")
    
    branch_input = input("Default branch (master/main) [master]: ").strip()
    if branch_input:
        config.default_branch = branch_input
    
    # Preferences
    print("\n⚙️  Preferences")
    print("-" * 40)
    auto_upload = input("Auto-upload to Zephyr? (y/n) [n]: ").strip().lower()
    config.auto_upload = auto_upload == 'y'
    
    auto_pr = input("Auto-create PR/MR? (y/n) [y]: ").strip().lower()
    config.auto_create_pr = auto_pr != 'n'
    
    ai_tool = input("AI code generation tool (aider/cursor) [aider]: ").strip()
    if ai_tool:
        config.ai_tool = ai_tool
    
    # RAG Settings
    print("\n🧠 RAG (Retrieval-Augmented Generation) Configuration")
    print("-" * 40)
    print("RAG ensures test generation uses your company's context and past patterns.")
    print("This improves consistency and prevents generic tests.")
    rag_choice = input("Enable RAG? (y/n) [y]: ").strip().lower()
    config.enable_rag = rag_choice != 'n'
    
    if config.enable_rag:
        rag_auto = input("Auto-index test plans after generation? (y/n) [y]: ").strip().lower()
        config.rag_auto_index = rag_auto != 'n'
    
    # Womba API (optional)
    print("\n🌐 Womba Cloud (Optional)")
    print("-" * 40)
    print("Enable cloud sync to access your config from any machine.")
    api_key = input("Womba API key [skip]: ").strip()
    if api_key:
        config.womba_api_key = api_key
    
    print("\n" + "=" * 80)
    print("✅ Configuration complete!")
    print("=" * 80)
    
    return config


def ensure_config(force_setup: bool = False) -> WombaConfig:
    """Ensure config exists, prompt if needed"""
    manager = ConfigManager()
    
    if force_setup or not manager.exists():
        if not force_setup:
            print("\n⚠️  No configuration found.")
        config = prompt_for_config()
        
        # Validate required fields
        missing = config.get_missing_fields()
        if missing:
            print(f"\n⚠️  Warning: Missing required fields: {', '.join(missing)}")
            print("Some commands may not work until these are configured.")
        
        # Save config
        manager.save(config, sync_cloud=bool(config.womba_api_key))
        print(f"\n💾 Config saved to {manager.config_file}")
        
        if config.womba_api_key:
            print("☁️  Config synced to Womba cloud")
        
        return config
    else:
        config = manager.load()
        if config is None:
            print("❌ Error loading config. Running setup again...")
            return ensure_config(force_setup=True)
        return config


def show_config() -> None:
    """Display current configuration"""
    manager = ConfigManager()
    config = manager.load()
    
    if not config:
        print("❌ No configuration found. Run 'womba configure' to set up.")
        return
    
    print("\n" + "=" * 80)
    print("📋 Current Womba Configuration")
    print("=" * 80)
    
    print("\n🔐 Credentials")
    print(f"  Atlassian URL:    {config.atlassian_url or '(not set)'}")
    print(f"  Atlassian Email:  {config.atlassian_email or '(not set)'}")
    print(f"  Atlassian Token:  {'*' * 20 if config.atlassian_api_token else '(not set)'}")
    print(f"  Zephyr Token:     {'*' * 20 if config.zephyr_api_token else '(not set)'}")
    print(f"  OpenAI API Key:   {'*' * 20 if config.openai_api_key else '(not set)'}")
    
    print("\n📁 Repository")
    print(f"  Default Path:     {config.repo_path or '(not set)'}")
    print(f"  Git Provider:     {config.git_provider}")
    print(f"  Default Branch:   {config.default_branch}")
    
    print("\n⚙️  Preferences")
    print(f"  AI Model:         {config.ai_model}")
    print(f"  AI Tool:          {config.ai_tool}")
    print(f"  Auto Upload:      {config.auto_upload}")
    print(f"  Auto Create PR:   {config.auto_create_pr}")
    print(f"  RAG Enabled:      {config.enable_rag}")
    print(f"  RAG Auto-Index:   {config.rag_auto_index}")
    
    print("\n☁️  Cloud Sync")
    print(f"  Womba API Key:    {'*' * 20 if config.womba_api_key else '(not configured)'}")
    print(f"  Status:           {'✓ Enabled' if config.womba_api_key else '✗ Disabled'}")
    
    print("\n" + "=" * 80)
    print(f"📍 Config file: {manager.config_file}")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    # Run interactive setup
    if len(sys.argv) > 1 and sys.argv[1] == "show":
        show_config()
    else:
        ensure_config(force_setup=True)

