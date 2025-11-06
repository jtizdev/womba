"""
Confluence document processor.

Parses raw Confluence page content into structured sections suitable for enrichment
and prompt injection: headings, functional requirements, acceptance criteria, use cases, etc.
"""

import re
from typing import Dict, List, Tuple
from loguru import logger


def _split_sections(text: str) -> Dict[str, str]:
    """
    Split content by common PRD headings using heuristics.
    Returns a dict of {section_name_lower: section_text}.
    """
    # Normalize newlines
    content = text.replace('\r\n', '\n')
    # Candidate section headings (add common variants)
    headings = [
        'overview', 'background', 'context',
        'goals', 'objectives', 'non-goals',
        'functional requirements', 'requirements', 'fr',
        'acceptance criteria', 'ac',
        'use cases', 'user stories', 'scenarios',
        'non-functional requirements', 'nfr', 'performance', 'security',
        'out of scope', 'assumptions', 'open questions', 'notes'
    ]

    # Build regex to split on lines that look like H2/H3 headings
    # Example: "## Functional Requirements" or "Functional Requirements:" at line start
    pattern = re.compile(r"^(#{1,6}\s*)?(?P<name>" + "|".join([re.escape(h) for h in headings]) + r")(\s*[:\-])?\s*$", re.IGNORECASE | re.MULTILINE)

    sections: Dict[str, str] = {}
    last_pos = 0
    last_name = 'overview'

    for m in pattern.finditer(content):
        current_pos = m.start()
        # Save previous section
        prev_text = content[last_pos:current_pos].strip()
        if prev_text:
            sections.setdefault(last_name, prev_text)
        # Prepare for next
        last_name = m.group('name').lower()
        last_pos = m.end()

    # Tail
    tail = content[last_pos:].strip()
    if tail:
        sections.setdefault(last_name, tail)

    return sections


def _extract_bullets(section_text: str) -> List[str]:
    """
    Extract bullet points or numbered lists from a section.
    """
    bullets = []
    for line in section_text.splitlines():
        line = line.strip()
        if re.match(r"^[-*•]\s+", line) or re.match(r"^\d+\.\s+", line):
            item = re.sub(r"^([-*•]\s+|\d+\.\s+)", "", line).strip()
            if item:
                bullets.append(item)
    # If no bullets found, fallback to sentences
    if not bullets:
        sentences = re.split(r"(?<=[.!?])\s+", section_text)
        bullets = [s.strip() for s in sentences if len(s.strip()) > 0]
    return bullets[:50]


def process_confluence_content(content: str) -> Dict[str, List[str]]:
    """
    Process raw Confluence content into structured fields.

    Returns dict with keys:
    - headings: list[str]
    - functional_requirements, acceptance_criteria, use_cases, non_functional, notes: list[str]
    """
    if not content:
        return {
            'headings': [],
            'functional_requirements': [],
            'acceptance_criteria': [],
            'use_cases': [],
            'non_functional': [],
            'notes': []
        }

    sections = _split_sections(content)
    # Collect headings keys we found
    headings_found = list({name.title() for name in sections.keys()})[:20]

    # Map of potential aliases to canonical buckets
    buckets = {
        'functional_requirements': ['functional requirements', 'requirements', 'fr'],
        'acceptance_criteria': ['acceptance criteria', 'ac'],
        'use_cases': ['use cases', 'user stories', 'scenarios'],
        'non_functional': ['non-functional requirements', 'nfr', 'performance', 'security'],
        'notes': ['out of scope', 'assumptions', 'open questions', 'notes', 'overview', 'background', 'context', 'goals', 'objectives', 'non-goals']
    }

    result = {
        'headings': headings_found,
        'functional_requirements': [],
        'acceptance_criteria': [],
        'use_cases': [],
        'non_functional': [],
        'notes': []
    }

    # Populate buckets
    for canonical, aliases in buckets.items():
        combined_text = []
        for alias in aliases:
            text = sections.get(alias)
            if text:
                combined_text.append(text)
        if combined_text:
            items = _extract_bullets("\n".join(combined_text))
            result[canonical] = items

    return result


