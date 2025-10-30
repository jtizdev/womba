#!/usr/bin/env python3
"""
Womba CLI - Simple interface for AI-powered test generation
"""

import sys
import argparse
from pathlib import Path
from loguru import logger


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Womba - AI-powered test generation from Jira stories to Zephyr Scale",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  womba generate PLAT-12991              # Generate test plan
  womba upload PLAT-12991                # Upload to Zephyr
  womba generate PLAT-12991 --upload     # Generate and upload
  womba evaluate PLAT-12991              # Check quality score
  womba configure                        # Interactive setup
  
  # Full end-to-end workflow:
  womba all PLAT-12991                   # Generate + Upload + Create tests + PR
  
  # Automation (generate executable test code):
  womba automate PLAT-12991 --repo /path/to/test/repo
  womba automate PLAT-12991 --repo /path/to/test/repo --framework playwright
  womba automate PLAT-12991 --repo /path/to/test/repo --ai-tool cursor
  
  # RAG (Retrieval-Augmented Generation) management:
  womba index PLAT-12991                 # Index a story's context
  womba index-all                        # Index all available data (batch)
  womba rag-stats                        # Show RAG statistics
  womba rag-clear                        # Clear RAG database
        """
    )
    
    parser.add_argument(
        'command',
        choices=['generate', 'upload', 'evaluate', 'configure', 'automate', 'all', 
                 'index', 'index-all', 'rag-stats', 'rag-clear', 'rag-view'],
        help='Command to execute'
    )
    
    parser.add_argument(
        'story_key',
        nargs='?',
        help='Jira story key (e.g., PLAT-12991)'
    )
    
    parser.add_argument(
        '--upload',
        action='store_true',
        help='Automatically upload after generation'
    )
    
    parser.add_argument(
        '--yes', '-y',
        action='store_true',
        help='Auto-confirm prompts (for automation)'
    )
    
    parser.add_argument(
        '--no-cache',
        action='store_true',
        help='Bypass cache, fetch fresh data'
    )
    
    parser.add_argument(
        '--repo',
        help='Path to customer automation repository (for automate command)'
    )
    
    parser.add_argument(
        '--framework',
        choices=['auto', 'playwright', 'cypress', 'rest-assured', 'junit', 'pytest'],
        default='auto',
        help='Test framework (auto-detected if not specified)'
    )
    
    parser.add_argument(
        '--ai-tool',
        choices=['aider', 'cursor'],
        default='aider',
        help='AI tool to use for code generation (default: aider)'
    )
    
    parser.add_argument(
        '--create-pr',
        action='store_true',
        default=True,
        help='Automatically create PR after generating code'
    )
    
    args = parser.parse_args()
    
    # Handle commands that don't need story key
    if args.command == 'configure':
        from src.config.interactive_setup import ensure_config
        ensure_config(force_setup=True)
        return
    
    if args.command == 'rag-stats':
        from src.cli.rag_commands import show_rag_stats
        show_rag_stats()
        return
    
    if args.command == 'rag-clear':
        from src.cli.rag_commands import clear_rag_database
        clear_rag_database(confirm=args.yes)
        return
    
    if args.command == 'rag-view':
        from src.cli.rag_commands import view_rag_documents
        
        # Parse collection from story_key or prompt
        if args.story_key:
            collection = args.story_key
        else:
            print("Usage: womba rag-view COLLECTION [--limit N] [--project-key KEY] [--full]")
            print("\nCollections: test_plans, confluence_docs, jira_stories, existing_tests")
            return
        
        view_rag_documents(
            collection=collection,
            limit=getattr(args, 'limit', 10),
            project_key=getattr(args, 'project_key', None),
            show_full=getattr(args, 'full', False)
        )
        return
    
    if args.command == 'index-all':
        import asyncio
        from src.config.config_manager import ConfigManager
        from src.cli.rag_commands import index_all_data
        
        try:
            # Load config (don't prompt if missing)
            manager = ConfigManager()
            if not manager.exists():
                print("\n❌ No configuration found!")
                print("💡 Run 'womba configure' first to set up your credentials")
                return
            
            config = manager.load()
            if not config:
                print("\n❌ Error loading configuration!")
                print("💡 Run 'womba configure' to reconfigure")
                return
            
            # Use configured project key (required)
            project_key = config.project_key
            if not project_key:
                print("\n❌ Project key not configured!")
                print("💡 Run 'womba configure' to set your project key")
                return
            
            print(f"\n🔄 Starting batch indexing for project: {project_key}")
            print("(Using configured project key)")
            
            print("\nThis will index all available data from your project.")
            print("This may take several minutes.\n")
            
            # Run async indexing
            results = asyncio.run(index_all_data(project_key))
            
            print("\n✅ Batch indexing complete!")
            print(f"📊 Indexed: {results['tests']} tests, {results['stories']} stories, {results['docs']} docs")
            print("💡 Run 'womba rag-stats' to see detailed statistics")
            
        except ValueError as e:
            print(f"\n❌ Configuration Error: {e}")
            print("💡 Run 'womba configure' to set up your API keys")
            return
        except Exception as e:
            print(f"\n❌ Indexing failed: {e}")
            logger.exception("Full error details:")
            return
    
    # Ensure config exists for other commands
    from src.config.interactive_setup import ensure_config
    config = ensure_config()
    
    # All other commands need a story key (except those already handled)
    if not args.story_key and args.command not in ['rag-stats', 'rag-clear', 'index-all', 'configure']:
        parser.error(f"Story key is required for '{args.command}' command")
    
    # Route to appropriate handler
    if args.command == 'index':
        import asyncio
        from src.cli.rag_commands import index_story_context
        
        try:
            asyncio.run(index_story_context(args.story_key))
        except ValueError as e:
            print(f"\n❌ Configuration Error: {e}")
            print("💡 Run 'womba configure' to set up your API keys")
            return
        except Exception as e:
            print(f"\n❌ Indexing failed: {e}")
            logger.exception("Full error details:")
            return
    
    elif args.command == 'generate':
        import asyncio
        from src.workflows.full_workflow import FullWorkflowOrchestrator
        
        orchestrator = FullWorkflowOrchestrator(config)
        orchestrator.story_key = args.story_key
        result = asyncio.run(orchestrator._generate_test_plan())
        print(f"✅ Generated test plan for {args.story_key}")
        
        if config.enable_rag:
            print("📊 RAG was used for context-grounded generation")
        
        if args.upload:
            print("\n🚀 Auto-uploading to Zephyr...")
            upload_result = asyncio.run(orchestrator._upload_to_zephyr())
            print(f"✅ Uploaded to Zephyr: {upload_result}")
    
    elif args.command == 'upload':
        import asyncio
        from src.workflows.full_workflow import FullWorkflowOrchestrator
        
        orchestrator = FullWorkflowOrchestrator(config)
        orchestrator.story_key = args.story_key
        # First generate test plan, then upload
        asyncio.run(orchestrator._generate_test_plan())
        result = asyncio.run(orchestrator._upload_to_zephyr())
        print(f"✅ Uploaded to Zephyr: {len(result)}")
    
    elif args.command == 'evaluate':
        import asyncio
        from src.ai.quality_scorer import QualityScorer
        
        scorer = QualityScorer()
        result = asyncio.run(scorer.evaluate_test_plan(args.story_key))
        print(f"✅ Quality evaluation: {result}")
    
    elif args.command == 'automate':
        # Validate requirements
        if not args.repo:
            parser.error("--repo is required for 'automate' command")
        
        import asyncio
        from src.workflows.full_workflow import FullWorkflowOrchestrator
        
        orchestrator = FullWorkflowOrchestrator(config)
        result = asyncio.run(orchestrator.run(
            args.story_key,
            args.repo
        ))
        print(f"✅ Automation complete: {result}")
    
    elif args.command == 'all':
        # Full end-to-end workflow
        print(f"\n🚀 Running full Womba workflow for {args.story_key}")
        print("=" * 80)
        
        import asyncio
        from src.workflows.full_workflow import run_full_workflow
        
        result = asyncio.run(run_full_workflow(
            story_key=args.story_key,
            config=config,
            repo_path=args.repo
        ))
        
        # Display summary
        print("\n" + "=" * 80)
        print("✅ Workflow Complete!")
        print("=" * 80)
        print(f"\n📋 Story: {result['story_key']} - {result['story_title']}")
        print(f"🧪 Test Cases: {result['test_cases_generated']}")
        if result['zephyr_test_ids']:
            print(f"📤 Zephyr IDs: {', '.join(result['zephyr_test_ids'][:5])}")
        print(f"📁 Files Generated: {len(result['generated_files'])}")
        print(f"🌿 Branch: {result['branch_name']}")
        if result['pr_url']:
            print(f"🔗 PR/MR: {result['pr_url']}")
        print("\n" + "=" * 80 + "\n")


if __name__ == '__main__':
    main()

