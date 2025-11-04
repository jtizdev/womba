#!/usr/bin/env python3
"""
Womba CLI - Simple interface for AI-powered test generation
"""

import sys
import argparse
from pathlib import Path
from loguru import logger

from src.config.settings import settings
from src.cli.rag_refresh import RAGRefreshManager


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
  womba generate PLAT-12991 --upload --folder "Regression/UI"   # Generate + upload into folder
  womba upload-plan --file test_plans/test_plan_PLAT-12991.json --folder "Regression/UI"   # Upload saved plan
  womba index-source --source jira --source confluence              # Index specific sources only
        """
    )
    
    parser.add_argument(
        'command',
        choices=['generate', 'upload', 'upload-plan', 'evaluate', 'configure', 'automate', 'all', 
                 'index', 'index-all', 'index-source', 'rag-stats', 'rag-clear', 'rag-view'],
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
    
    parser.add_argument(
        '--project-key',
        dest='project_key_override',
        help='Override project key for indexing commands'
    )

    parser.add_argument(
        '--source',
        dest='sources',
        action='append',
        help='Data source to index (use with index-source). Options: jira, confluence, zephyr, plainid. Repeatable.'
    )
    
    parser.add_argument(
        '--folder',
        dest='folder_path',
        help='Target Zephyr folder path (e.g., "Parent/Sub")'
    )

    parser.add_argument(
        '--file',
        dest='file_path',
        help='Path to test plan JSON file (use with upload-plan)'
    )

    parser.add_argument(
        '--force-refresh',
        action='store_true',
        help='Force RAG indexing even if refresh interval has not elapsed'
    )

    parser.add_argument(
        '--refresh-hours',
        type=float,
        help='Override RAG refresh interval (hours) for this command'
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

            project_key = config.project_key
            if not project_key:
                print("\n❌ Project key not configured!")
                print("💡 Run 'womba configure' to set your project key")
                return

            refresh_manager = RAGRefreshManager()
            refresh_hours = args.refresh_hours if args.refresh_hours is not None else settings.rag_refresh_hours
            if not args.force_refresh and refresh_hours is not None and not refresh_manager.should_refresh(project_key, 'index_all', refresh_hours):
                last = refresh_manager.get_last_refresh(project_key, 'index_all')
                hours_since = refresh_manager.hours_since_refresh(project_key, 'index_all') or 0.0
                remaining = max(refresh_hours - hours_since, 0.0)
                formatted_last = last.isoformat() if last else 'unknown'
                print(f"\n⏳ Last full refresh for {project_key} ran at {formatted_last} (≈{hours_since:.1f}h ago).")
                print(f"💡 Next refresh due in ~{remaining:.1f}h. Use --force-refresh to override.")
                return

            print(f"\n🔄 Starting batch indexing for project: {project_key}")
            print("(Using configured project key)")

            print("\nThis will index all available data from your project.")
            print("This may take several minutes.\n")

            results = asyncio.run(index_all_data(
                project_key,
                refresh_manager=refresh_manager,
                refresh_hours=refresh_hours,
                force=args.force_refresh
            ))

            print("\n✅ Batch indexing complete!")
            print(f"📊 Indexed: {results['tests']} tests, {results['stories']} stories, {results['docs']} docs, {results.get('external_docs', 0)} external docs")
            print("💡 Run 'womba rag-stats' to see detailed statistics")

        except ValueError as e:
            print(f"\n❌ Configuration Error: {e}")
            print("💡 Run 'womba configure' to set up your API keys")
            return
        except Exception as e:
            print(f"\n❌ Indexing failed: {e}")
            logger.exception("Full error details:")
            return
        return
    
    if args.command == 'index-source':
        import asyncio
        from src.config.config_manager import ConfigManager
        from src.cli.rag_commands import index_specific_sources

        sources = args.sources or []
        if not sources:
            parser.error("--source is required for 'index-source'. Use multiple --source flags for more than one.")

        manager = ConfigManager()
        if not manager.exists():
            print("\n❌ No configuration found!")
            print("💡 Run 'womba configure' first to set up your credentials")
            return

        config_obj = manager.load()
        project_key = args.project_key_override or (config_obj.project_key if config_obj else None)
        if not project_key:
            print("\n❌ Project key not configured!")
            print("💡 Run 'womba configure' or provide --project-key")
            return

        valid_sources = {'zephyr', 'jira', 'confluence', 'plainid', 'external'}
        canonical_map = {
            'zephyr': 'tests',
            'jira': 'stories',
            'confluence': 'docs',
            'plainid': 'external_docs',
            'external': 'external_docs'
        }
        normalized_sources = []
        for src in sources:
            key = src.lower()
            if key not in valid_sources:
                parser.error(f"Unknown source '{src}'. Valid options: {', '.join(sorted(valid_sources))}")
            normalized_sources.append(key)

        refresh_manager = RAGRefreshManager()
        refresh_hours = args.refresh_hours if args.refresh_hours is not None else settings.rag_refresh_hours
        due_sources = normalized_sources
        if not args.force_refresh and refresh_hours is not None:
            due_sources = [s for s in normalized_sources if refresh_manager.should_refresh(project_key, canonical_map[s], refresh_hours)]
            if not due_sources:
                messages = []
                for src in normalized_sources:
                    hours_since = refresh_manager.hours_since_refresh(project_key, canonical_map[src])
                    if hours_since is None:
                        continue
                    remaining = max(refresh_hours - hours_since, 0.0)
                    messages.append(f"{src}: next in ~{remaining:.1f}h")
                if messages:
                    print("\n⏳ All requested sources were refreshed recently:")
                    for msg in messages:
                        print(f"  • {msg}")
                    print("💡 Use --force-refresh to override.")
                else:
                    print("\nℹ️ No due sources detected (no previous refresh recorded).")
                return

        try:
            asyncio.run(index_specific_sources(due_sources, project_key, refresh_manager=refresh_manager))
        except ValueError as e:
            print(f"\n❌ {e}")
            return
        except Exception as e:
            print(f"\n❌ Targeted indexing failed: {e}")
            logger.exception("Full error details:")
            return
        return
    
    if args.command == 'upload-plan':
        from src.models.test_plan import TestPlan
        from src.integrations.zephyr_integration import ZephyrIntegration
        import asyncio

        if not args.file_path:
            parser.error("--file is required for 'upload-plan'")

        plan_path = Path(args.file_path)
        if not plan_path.exists():
            parser.error(f"Test plan file does not exist: {plan_path}")

        try:
            test_plan = TestPlan.model_validate_json(plan_path.read_text())
        except Exception as exc:
            print(f"\n❌ Failed to parse test plan JSON: {exc}")
            return

        project_key = args.project_key_override or (test_plan.story.key.split('-')[0] if test_plan.story and test_plan.story.key else None)
        if not project_key:
            parser.error("Could not determine project key. Provide --project-key.")

        folder_path = args.folder_path
        zephyr = ZephyrIntegration()
        print(f"\n🚀 Uploading test plan from {plan_path} to project {project_key}")
        if folder_path:
            print(f"📁 Target folder: {folder_path}")

        results = asyncio.run(zephyr.upload_test_plan(
            test_plan=test_plan,
            project_key=project_key,
            folder_path=folder_path
        ))

        success = {k: v for k, v in results.items() if not str(v).startswith('ERROR')}
        failures = {k: v for k, v in results.items() if str(v).startswith('ERROR')}

        print("\n✅ Uploaded test cases:")
        for title, key in success.items():
            print(f"  {title} -> {key}")

        if failures:
            print("\n⚠️ Failures:")
            for title, err in failures.items():
                print(f"  {title}: {err}")

        print(f"\nSummary: {len(success)} succeeded, {len(failures)} failed")
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
        import json
        from pathlib import Path
        from src.workflows.full_workflow import FullWorkflowOrchestrator
        from src.cli.rag_commands import index_all_data

        project_key = args.story_key.split('-')[0]
        refresh_manager = RAGRefreshManager()
        refresh_hours = args.refresh_hours if args.refresh_hours is not None else settings.rag_refresh_hours

        if refresh_hours is not None and (args.force_refresh or refresh_manager.should_refresh(project_key, 'index_all', refresh_hours)):
            if args.force_refresh:
                print("\n⚙️ Force refreshing RAG before generation...")
            else:
                print(f"\n⏳ RAG refresh is due (>{refresh_hours}h). Running index-all before generation...")
            asyncio.run(index_all_data(
                project_key,
                refresh_manager=refresh_manager,
                refresh_hours=refresh_hours,
                force=True
            ))

        orchestrator = FullWorkflowOrchestrator(config)
        orchestrator.story_key = args.story_key
        orchestrator.folder_path = args.folder_path
        result = asyncio.run(orchestrator._generate_test_plan())
        
        # Save test plan to JSON file
        output_dir = Path("test_plans")
        output_dir.mkdir(exist_ok=True)
        test_plan_file = output_dir / f"test_plan_{args.story_key}.json"
        
        with open(test_plan_file, 'w') as f:
            # Convert TestPlan to dict, handling non-serializable Jira objects
            def clean_dict(obj):
                """Recursively clean dict of non-serializable objects."""
                if isinstance(obj, dict):
                    return {k: clean_dict(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [clean_dict(item) for item in obj]
                elif hasattr(obj, '__dict__') and not isinstance(obj, (str, int, float, bool, type(None))):
                    # Convert custom objects to string
                    return str(obj)
                else:
                    return obj
            
            test_plan_dict = orchestrator.test_plan.model_dump()
            test_plan_dict = clean_dict(test_plan_dict)
            json.dump(test_plan_dict, f, indent=2, default=str)
        
        print(f"\n✅ Generated test plan for {args.story_key}")
        print(f"📄 Test plan saved to: {test_plan_file.absolute()}")
        print(f"📊 Generated {len(orchestrator.test_plan.test_cases)} test cases")
        
        if args.upload:
            print("\n🚀 Uploading to Zephyr...")
            upload_result = asyncio.run(orchestrator._upload_to_zephyr(force=True))
            
            # Print ONLY Zephyr URLs
            project_key = args.story_key.split('-')[0]
            print(f"\n🔗 Test Case URLs:")
            for test_title, zephyr_key in upload_result.items():
                if not zephyr_key.startswith('ERROR'):
                    # Zephyr URL format: https://plainid.atlassian.net/projects/{PROJECT}?selectedItem=...#!/v2/testCase/{TEST_KEY}/testScript
                    zephyr_url = f"https://plainid.atlassian.net/projects/{project_key}?selectedItem=com.atlassian.plugins.atlassian-connect-plugin:com.kanoah.test-manager__main-project-page#!/v2/testCase/{zephyr_key}/testScript"
                    print(zephyr_url)
                else:
                    print(f"ERROR: {test_title} - {zephyr_key}")
    
    elif args.command == 'upload':
        import asyncio
        from src.workflows.full_workflow import FullWorkflowOrchestrator
        
        orchestrator = FullWorkflowOrchestrator(config)
        orchestrator.story_key = args.story_key
        orchestrator.folder_path = args.folder_path
        # First generate test plan, then upload
        asyncio.run(orchestrator._generate_test_plan())
        result = asyncio.run(orchestrator._upload_to_zephyr(force=True))
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
        orchestrator.folder_path = args.folder_path
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
            repo_path=args.repo,
            folder_path=args.folder_path
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

