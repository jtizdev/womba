"""
CLI commands for story enrichment.
"""

import json
from pathlib import Path
from loguru import logger

from src.aggregator.story_collector import StoryCollector
from src.ai.story_enricher import StoryEnricher
from src.ai.enrichment_cache import EnrichmentCache
from src.config.config_manager import ConfigManager


async def enrich_story_command(
    story_key: str,
    use_cache: bool = True,
    export_path: str = None
) -> None:
    """
    Enrich a story and display the results.
    
    Args:
        story_key: Jira story key
        use_cache: Whether to use cached enrichment
        export_path: Optional path to export enriched story JSON
    """
    print(f"\n🔍 Enriching story: {story_key}")
    print("=" * 60)
    
    try:
        # Validate configuration
        config_manager = ConfigManager()
        if not config_manager.exists():
            print("\n❌ No configuration found!")
            print("💡 Run 'womba configure' first to set up your credentials")
            return
        
        config = config_manager.load()
        if not config:
            print("\n❌ Error loading configuration!")
            print("💡 Run 'womba configure' to reconfigure")
            return
        
        # Initialize services
        enrichment_cache = EnrichmentCache()
        story_enricher = StoryEnricher()
        story_collector = StoryCollector()
        
        # Check cache first
        if use_cache:
            print("\n📦 Checking cache...")
            cached = enrichment_cache.get_cached(story_key)
            if cached:
                print(f"✅ Found cached enrichment (age: {(cached.enrichment_timestamp).strftime('%Y-%m-%d %H:%M:%S')})")
                _display_enriched_story(cached)
                
                if export_path:
                    _export_enriched_story(cached, export_path)
                
                return
            else:
                print("ℹ️  No cached enrichment found")
        else:
            print("\n🔄 Cache disabled, forcing fresh enrichment...")
            enrichment_cache.clear_cache(story_key)
        
        # Collect story context
        print(f"\n📥 Collecting story context for {story_key}...")
        story_context = await story_collector.collect_story_context(story_key)
        main_story = story_context.main_story
        
        print(f"✅ Collected context:")
        print(f"   • Story: {main_story.summary}")
        print(f"   • Subtasks: {len(story_context.get('subtasks', []))}")
        print(f"   • Linked stories: {len(story_context.get('linked_stories', []))}")
        print(f"   • Comments: {len(story_context.get('story_comments', []))}")
        
        # Enrich story
        print(f"\n🔬 Enriching story with context analysis...")
        print("   • Following linked stories recursively")
        print("   • Extracting API specifications from Swagger")
        print("   • Identifying platform components")
        print("   • Analyzing risk areas")
        
        enriched = await story_enricher.enrich_story(
            main_story=main_story,
            story_context=story_context
        )
        
        # Cache result
        enrichment_cache.save_cached(enriched, main_story.updated)
        print("\n💾 Enrichment cached for future use")
        
        # Display results
        _display_enriched_story(enriched)
        
        # Export if requested
        if export_path:
            _export_enriched_story(enriched, export_path)
        
        print("\n✅ Story enrichment complete!")
        print(f"💡 This enriched context will be used automatically for test generation")
        
    except Exception as e:
        print(f"\n❌ Enrichment failed: {e}")
        logger.exception("Full error details:")
        raise


def _display_enriched_story(enriched) -> None:
    """Display enriched story in formatted output."""
    print("\n" + "=" * 60)
    print(f"📋 ENRICHED STORY: {enriched.story_key}")
    print("=" * 60)
    
    # Feature narrative
    print("\n📖 FEATURE NARRATIVE:")
    print("-" * 60)
    for line in enriched.feature_narrative.split('\n'):
        if line.strip():
            print(f"   {line}")
    
    # Acceptance criteria
    if enriched.acceptance_criteria:
        print("\n✅ ACCEPTANCE CRITERIA:")
        print("-" * 60)
        for i, ac in enumerate(enriched.acceptance_criteria, 1):
            print(f"   {i}. {ac}")
    
    # Functional points
    if enriched.functional_points:
        print(f"\n🎯 FUNCTIONALITY TO TEST ({len(enriched.functional_points)} points):")
        print("-" * 60)
        for i, fp in enumerate(enriched.functional_points[:20], 1):
            print(f"   {i}. {fp}")
        if len(enriched.functional_points) > 20:
            print(f"   ... and {len(enriched.functional_points) - 20} more")
    
    # Platform components
    if enriched.platform_components:
        print("\n🏗️  PLATFORM COMPONENTS:")
        print("-" * 60)
        for comp in enriched.platform_components:
            print(f"   • {comp}")
    
    # NOTE: API specifications are now built separately via APIContext during prompt construction
    # They use a fallback flow: story → swagger RAG → GitLab MCP
    # Use the 'generate' command to see API specs in the final prompt
    
    # Risk areas
    if enriched.risk_areas:
        print(f"\n⚠️  RISK AREAS & TESTING FOCUS:")
        print("-" * 60)
        for risk in enriched.risk_areas:
            print(f"   • {risk}")
    
    # Related stories
    if enriched.related_stories:
        print(f"\n🔗 RELATED STORIES ({len(enriched.related_stories)}):")
        print("-" * 60)
        for related in enriched.related_stories[:5]:
            print(f"   • {related}")
        if len(enriched.related_stories) > 5:
            print(f"   ... and {len(enriched.related_stories) - 5} more")
    
    # Metadata
    print("\n📊 ENRICHMENT METADATA:")
    print("-" * 60)
    print(f"   • Source stories analyzed: {len(enriched.source_story_ids)}")
    print(f"   • Enrichment timestamp: {enriched.enrichment_timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   • Stories: {', '.join(enriched.source_story_ids[:5])}")
    if len(enriched.source_story_ids) > 5:
        print(f"     ... and {len(enriched.source_story_ids) - 5} more")


def _export_enriched_story(enriched, export_path: str) -> None:
    """Export enriched story to JSON file."""
    try:
        path = Path(export_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(enriched.dict(), f, indent=2, default=str)
        
        print(f"\n💾 Exported enriched story to: {path}")
        
    except Exception as e:
        print(f"\n⚠️  Export failed: {e}")
        logger.error(f"Failed to export enriched story: {e}")

