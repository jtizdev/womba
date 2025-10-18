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
        """
    )
    
    parser.add_argument(
        'command',
        choices=['generate', 'upload', 'evaluate', 'configure'],
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
        '--no-cache',
        action='store_true',
        help='Bypass cache, fetch fresh data'
    )
    
    args = parser.parse_args()
    
    # Handle configure command (no story key needed)
    if args.command == 'configure':
        from setup_env import main as setup_main
        setup_main()
        return
    
    # All other commands need a story key
    if not args.story_key:
        parser.error(f"Story key is required for '{args.command}' command")
    
    # Route to appropriate handler
    if args.command == 'generate':
        from generate_test_plan import main as generate_main
        generate_main(args.story_key)
        
        if args.upload:
            print("\n🚀 Auto-uploading to Zephyr...")
            from upload_to_zephyr import main as upload_main
            upload_main(args.story_key)
    
    elif args.command == 'upload':
        from upload_to_zephyr import main as upload_main
        upload_main(args.story_key)
    
    elif args.command == 'evaluate':
        from evaluate_quality import main as evaluate_main
        evaluate_main(args.story_key)


if __name__ == '__main__':
    main()

