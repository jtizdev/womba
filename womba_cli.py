#!/usr/bin/env python3
"""
Womba CLI - Simple interface for AI-powered test generation
"""

import sys
import argparse
from pathlib import Path


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
        """
    )
    
    parser.add_argument(
        'command',
        choices=['generate', 'upload', 'evaluate', 'configure', 'automate', 'all'],
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
    
    # Handle configure command (no story key needed)
    if args.command == 'configure':
        from src.config.interactive_setup import ensure_config
        ensure_config(force_setup=True)
        return
    
    # Ensure config exists for other commands
    from src.config.interactive_setup import ensure_config
    config = ensure_config()
    
    # All other commands need a story key
    if not args.story_key:
        parser.error(f"Story key is required for '{args.command}' command")
    
    # Route to appropriate handler
    if args.command == 'generate':
        import asyncio
        from src.workflows.full_workflow import FullWorkflowOrchestrator
        
        orchestrator = FullWorkflowOrchestrator(config)
        orchestrator.story_key = args.story_key
        result = asyncio.run(orchestrator._generate_test_plan())
        print(f"✅ Generated test plan for {args.story_key}")
        
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
        print(f"✅ Uploaded to Zephyr: {result}")
    
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

