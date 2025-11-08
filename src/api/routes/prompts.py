"""
API routes for prompt configuration management.
Allows viewing and editing prompt sections through the UI.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.ai import prompts_qa_focused
from src.ai.generation.prompt_builder import PromptBuilder
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


def _load_overrides() -> Dict[str, str]:
    """Load prompt overrides from disk."""
    try:
        if PROMPT_OVERRIDES_FILE.exists():
            with open(PROMPT_OVERRIDES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load prompt overrides: {e}")
    return {}


def _save_overrides(overrides: Dict[str, str]):
    """Save prompt overrides to disk."""
    try:
        PROMPT_OVERRIDES_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(PROMPT_OVERRIDES_FILE, 'w', encoding='utf-8') as f:
            json.dump(overrides, f, indent=2, ensure_ascii=False)
        logger.info("Prompt overrides saved successfully")
    except Exception as e:
        logger.error(f"Failed to save prompt overrides: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save overrides: {str(e)}")


def _get_default_content(section_id: str) -> str:
    """Get default content for a prompt section."""
    section_map = {
        'system_instruction': prompts_qa_focused.SYSTEM_INSTRUCTION,
        'reasoning_framework': prompts_qa_focused.REASONING_FRAMEWORK,
        'generation_guidelines': prompts_qa_focused.GENERATION_GUIDELINES,
        'few_shot_examples': prompts_qa_focused.FEW_SHOT_EXAMPLES,
        'company_overview': getattr(prompts_qa_focused, 'COMPANY_OVERVIEW', ''),
        'rag_grounding': prompts_qa_focused.RAG_GROUNDING_INSTRUCTIONS,
        'quality_checklist': prompts_qa_focused.QUALITY_CHECKLIST,
    }
    return section_map.get(section_id, '')


@router.get("/sections", response_model=PromptSectionsResponse)
async def get_prompt_sections():
    """
    Get all prompt sections with their current content.
    Returns default content merged with any overrides.
    """
    try:
        overrides = _load_overrides()
        
        sections = [
            PromptSection(
                id='system_instruction',
                name='System Instruction',
                description='Core role definition and critical quality rules for the AI',
                content=overrides.get('system_instruction', _get_default_content('system_instruction')),
                editable=True
            ),
            PromptSection(
                id='reasoning_framework',
                name='Reasoning Framework',
                description='Chain of thought instructions guiding the AI\'s analysis process',
                content=overrides.get('reasoning_framework', _get_default_content('reasoning_framework')),
                editable=True
            ),
            PromptSection(
                id='generation_guidelines',
                name='Generation Guidelines',
                description='Consolidated rules for test composition, naming, and writing style',
                content=overrides.get('generation_guidelines', _get_default_content('generation_guidelines')),
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
                id='company_overview',
                name='Company Overview',
                description='Company-specific context and terminology (customizable per organization)',
                content=overrides.get('company_overview', _get_default_content('company_overview')),
                editable=True
            ),
            PromptSection(
                id='rag_grounding',
                name='RAG Grounding Instructions',
                description='Instructions for using retrieved context and avoiding hallucinations',
                content=overrides.get('rag_grounding', _get_default_content('rag_grounding')),
                editable=True
            ),
            PromptSection(
                id='quality_checklist',
                name='Quality Checklist',
                description='Final validation checklist before returning test plan',
                content=overrides.get('quality_checklist', _get_default_content('quality_checklist')),
                editable=True
            ),
        ]
        
        return PromptSectionsResponse(sections=sections)
    except Exception as e:
        logger.error(f"Failed to get prompt sections: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/company-overview")
async def get_company_overview():
    """Get the company overview section specifically."""
    try:
        overrides = _load_overrides()
        content = overrides.get('company_overview', _get_default_content('company_overview'))
        return {"content": content}
    except Exception as e:
        logger.error(f"Failed to get company overview: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/company-overview")
async def update_company_overview(request: CompanyOverviewRequest):
    """Update the company overview section."""
    try:
        overrides = _load_overrides()
        overrides['company_overview'] = request.content
        _save_overrides(overrides)
        
        return {"status": "success", "message": "Company overview updated successfully"}
    except Exception as e:
        logger.error(f"Failed to update company overview: {e}")
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
        overrides = _load_overrides()
        
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
            'system_instruction', 'reasoning_framework', 'generation_guidelines',
            'few_shot_examples', 'company_overview',
            'rag_grounding', 'quality_checklist'
        ]
        
        if section_id not in valid_sections:
            raise HTTPException(status_code=404, detail=f"Section '{section_id}' not found")
        
        overrides = _load_overrides()
        overrides[section_id] = request.content
        _save_overrides(overrides)
        
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
            PROMPT_OVERRIDES_FILE.unlink()
            logger.info("Prompt overrides cleared, reset to defaults")
        
        return {"status": "success", "message": "All prompts reset to defaults"}
    except Exception as e:
        logger.error(f"Failed to reset prompts: {e}")
        raise HTTPException(status_code=500, detail=str(e))

