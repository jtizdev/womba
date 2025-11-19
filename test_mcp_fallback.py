#!/usr/bin/env python3
"""
Test script to verify GitLab MCP fallback is working for PLAT-13541.
This script triggers story enrichment and monitors for MCP fallback.
"""

import asyncio
import sys
from loguru import logger
from src.aggregator.story_collector import StoryCollector
from src.ai.story_enricher import StoryEnricher
from src.ai.enrichment_cache import EnrichmentCache

# Configure logging to see MCP messages
logger.remove()
logger.add(sys.stderr, level="DEBUG", format="{time} | {level} | {name}:{function}:{line} | {message}")

async def test_mcp_fallback():
    """Test MCP fallback for PLAT-13541"""
    story_key = "PLAT-13541"
    
    print(f"\n{'='*80}")
    print(f"Testing GitLab MCP Fallback for {story_key}")
    print(f"{'='*80}\n")
    
    try:
        # Clear cache to force fresh enrichment
        cache = EnrichmentCache()
        cache.clear_cache(story_key)
        print("✅ Cleared cache for fresh enrichment\n")
        
        # Collect story context
        print(f"📥 Collecting story context for {story_key}...")
        collector = StoryCollector()
        context = await collector.collect_story_context(story_key)
        main_story = context.main_story
        
        print(f"✅ Collected context:")
        print(f"   • Story: {main_story.summary}")
        print(f"   • Subtasks: {len(context.get('subtasks', []))}")
        print(f"   • Linked stories: {len(context.get('linked_stories', []))}\n")
        
        # Enrich story (this should trigger MCP fallback if no endpoints found)
        print(f"🔬 Enriching story (this should trigger MCP fallback if no endpoints)...")
        print("   Monitoring for MCP fallback messages...\n")
        
        enricher = StoryEnricher()
        enriched = await enricher.enrich_story(
            main_story=main_story,
            story_context=context
        )
        
        # Check results
        print(f"\n{'='*80}")
        print(f"ENRICHMENT RESULTS")
        print(f"{'='*80}\n")
        
        print(f"📊 API Specifications Found: {len(enriched.api_specifications)}")
        if enriched.api_specifications:
            print("\n✅ Endpoints extracted:")
            for i, api in enumerate(enriched.api_specifications, 1):
                print(f"   {i}. {', '.join(api.http_methods)} {api.endpoint_path}")
                print(f"      Service: {api.service_name}")
                if api.parameters:
                    print(f"      Parameters: {', '.join(api.parameters)}")
        else:
            print("\n⚠️  NO ENDPOINTS FOUND")
            print("   This means MCP fallback should have been triggered!")
            print("   Check logs above for MCP fallback messages.\n")
        
        print(f"\n📝 Functional Points: {len(enriched.functional_points)}")
        print(f"🎯 Acceptance Criteria: {len(enriched.acceptance_criteria)}")
        print(f"🔗 Related Stories: {len(enriched.related_stories)}")
        print(f"⚠️  Risk Areas: {len(enriched.risk_areas)}")
        
        # Check if MCP was used
        print(f"\n{'='*80}")
        print("MCP FALLBACK VERIFICATION")
        print(f"{'='*80}\n")
        
        if len(enriched.api_specifications) > 0:
            print("✅ Endpoints were found!")
            print("   If these came from MCP fallback, check the service_name field.")
            print("   MCP-extracted endpoints should have service names from GitLab projects.")
        else:
            print("⚠️  No endpoints found - MCP fallback should have been triggered")
            print("   Check the logs above for:")
            print("   - 'Starting GitLab MCP fallback extraction'")
            print("   - 'GitLab MCP client configured'")
            print("   - 'Semantic code search via MCP'")
            print("   - 'GitLab MCP fallback extracted X API specifications'")
        
        return enriched
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        logger.exception("Full traceback:")
        raise

if __name__ == "__main__":
    asyncio.run(test_mcp_fallback())

