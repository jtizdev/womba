"""
API routes for prompt configuration management.
Allows viewing and editing prompt sections through the UI.
All file I/O operations are async using asyncio.to_thread.
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.ai import prompts_compact, prompts_analysis
from src.config.settings import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/prompts")

# Path for storing prompt overrides
PROMPT_OVERRIDES_FILE = Path("data/prompt_overrides.json")


class PromptSection(BaseModel):
    """Model for a prompt section."""
    id: str
    name: str
    description: str
    content: str
    editable: bool = True


class PromptSectionsResponse(BaseModel):
    """Response model for all prompt sections."""
    sections: List[PromptSection]


class UpdateSectionRequest(BaseModel):
    """Request model for updating a prompt section."""
    content: str


class CompanyOverviewRequest(BaseModel):
    """Request model for updating company overview."""
    content: str


def _load_overrides_sync() -> Dict[str, str]:
    """Load prompt overrides from disk (sync)."""
    try:
        if PROMPT_OVERRIDES_FILE.exists():
            with open(PROMPT_OVERRIDES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load prompt overrides: {e}")
    return {}


def _save_overrides_sync(overrides: Dict[str, str]):
    """Save prompt overrides to disk (sync)."""
    try:
        PROMPT_OVERRIDES_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(PROMPT_OVERRIDES_FILE, 'w', encoding='utf-8') as f:
            json.dump(overrides, f, indent=2, ensure_ascii=False)
        logger.info("Prompt overrides saved successfully")
    except Exception as e:
        logger.error(f"Failed to save prompt overrides: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save overrides: {str(e)}")


async def _load_overrides() -> Dict[str, str]:
    """Load prompt overrides from disk (async)."""
    return await asyncio.to_thread(_load_overrides_sync)


async def _save_overrides(overrides: Dict[str, str]):
    """Save prompt overrides to disk (async)."""
    await asyncio.to_thread(_save_overrides_sync, overrides)


def _get_default_content(section_id: str) -> str:
    """Get default content for a prompt section."""
    # Map to new two-stage prompt system
    section_map = {
        'system_instruction': prompts_compact.COMPACT_SYSTEM_INSTRUCTION,
        'stage1_analysis': prompts_analysis.ANALYSIS_SYSTEM_INSTRUCTION,
        'stage2_generation': prompts_compact.COMPACT_SYSTEM_INSTRUCTION,
        'few_shot_examples': prompts_compact.COMPACT_EXAMPLE,
        'output_format': prompts_compact.COMPACT_OUTPUT_FORMAT,
        'json_schema': prompts_compact.COMPACT_JSON_SCHEMA,
    }
    return section_map.get(section_id, '')


@router.get("/sections", response_model=PromptSectionsResponse)
async def get_prompt_sections():
    """
    Get all prompt sections with their current content.
    Returns default content merged with any overrides.
    """
    try:
        overrides = await _load_overrides()
        
        # Two-stage prompt sections
        sections = [
            PromptSection(
                id='stage1_analysis',
                name='Stage 1: Analysis Prompt',
                description='Analyzes the story, detects patterns, and creates a coverage plan',
                content=overrides.get('stage1_analysis', _get_default_content('stage1_analysis')),
                editable=True
            ),
            PromptSection(
                id='stage2_generation',
                name='Stage 2: Generation Prompt',
                description='Generates test cases based on the coverage plan',
                content=overrides.get('stage2_generation', _get_default_content('stage2_generation')),
                editable=True
            ),
            PromptSection(
                id='few_shot_examples',
                name='Few-Shot Examples',
                description='Example test cases demonstrating the desired output format',
                content=overrides.get('few_shot_examples', _get_default_content('few_shot_examples')),
                editable=True
            ),
            PromptSection(
                id='output_format',
                name='Output Format',
                description='JSON output format and self-review checklist',
                content=overrides.get('output_format', _get_default_content('output_format')),
                editable=True
            ),
        ]
        
        return PromptSectionsResponse(sections=sections)
    except Exception as e:
        logger.error(f"Failed to get prompt sections: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stage1")
async def get_stage1_prompt():
    """Get the Stage 1 (Analysis) prompt."""
    try:
        overrides = await _load_overrides()
        content = overrides.get('stage1_analysis', _get_default_content('stage1_analysis'))
        return {"content": content}
    except Exception as e:
        logger.error(f"Failed to get stage1 prompt: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stage2")
async def get_stage2_prompt():
    """Get the Stage 2 (Generation) prompt."""
    try:
        overrides = await _load_overrides()
        content = overrides.get('stage2_generation', _get_default_content('stage2_generation'))
        return {"content": content}
    except Exception as e:
        logger.error(f"Failed to get stage2 prompt: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/full")
async def get_full_prompt():
    """
    Get the complete assembled prompt (read-only preview).
    This shows how all sections combine together.
    """
    try:
        # Build a sample prompt to show the structure
        # Note: This is a simplified version for preview purposes
        overrides = await _load_overrides()
        
        sections_order = [
            'system_instruction',
            'reasoning_framework',
            'generation_guidelines',
            'test_structure',
            'few_shot_examples',
            'company_overview',
            'rag_grounding',
            'quality_checklist',
        ]
        
        full_prompt_parts = []
        for section_id in sections_order:
            content = overrides.get(section_id, _get_default_content(section_id))
            if content:
                full_prompt_parts.append(f"# {section_id.replace('_', ' ').title()}\n\n{content}")
        
        full_prompt = "\n\n" + "="*80 + "\n\n".join(full_prompt_parts)
        
        return {"content": full_prompt}
    except Exception as e:
        logger.error(f"Failed to get full prompt: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/sections/{section_id}")
async def update_section(section_id: str, request: UpdateSectionRequest):
    """Update a specific prompt section."""
    try:
        valid_sections = [
            'stage1_analysis', 'stage2_generation', 
            'few_shot_examples', 'output_format'
        ]
        
        if section_id not in valid_sections:
            raise HTTPException(status_code=404, detail=f"Section '{section_id}' not found")
        
        overrides = await _load_overrides()
        overrides[section_id] = request.content
        await _save_overrides(overrides)
        
        return {"status": "success", "message": f"Section '{section_id}' updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update section {section_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reset")
async def reset_prompts():
    """Reset all prompts to defaults by clearing overrides."""
    try:
        if PROMPT_OVERRIDES_FILE.exists():
            await asyncio.to_thread(PROMPT_OVERRIDES_FILE.unlink)
            logger.info("Prompt overrides cleared, reset to defaults")
        
        return {"status": "success", "message": "All prompts reset to defaults"}
    except Exception as e:
        logger.error(f"Failed to reset prompts: {e}")
        raise HTTPException(status_code=500, detail=str(e))
