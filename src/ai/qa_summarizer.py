"""
QA-focused summarizer for PRD/Confluence content.

Heuristic, deterministic summarization that extracts high-value signals for QA:
- Opening overview paragraph
- Bullets with requirement verbs (must/should/shall/require/validate/error)
- API hints (endpoint/method/request/response/payload)
- Acceptance-criteria-like lines
"""

import re
from typing import Optional


def _first_paragraph(text: str, max_chars: int = 600) -> str:
    text = text.strip()
    if not text:
        return ""
    # First non-empty paragraph
    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
    if not paragraphs:
        paragraphs = [text]
    para = paragraphs[0]
    return para[:max_chars] + ("..." if len(para) > max_chars else "")


def _collect_priority_lines(text: str, limit: int = 12) -> list:
    lines = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        # Requirement-like lines
        if re.search(r"\b(must|should|shall|required|validate|error|fail|deny)\b", line, re.I):
            lines.append(line)
            continue
        # API-hint lines
        if re.search(r"\b(GET|POST|PUT|PATCH|DELETE)\b|/api/|endpoint|request|response|payload|json", line, re.I):
            lines.append(line)
            continue
        # Acceptance criteria style
        if re.match(r"^(-|\*|•|\d+\.)\s+", line):
            lines.append(re.sub(r"^(-|\*|•|\d+\.)\s+", "", line))
    # Deduplicate while preserving order
    seen = set()
    unique = []
    for l in lines:
        if l not in seen:
            unique.append(l)
            seen.add(l)
        if len(unique) >= limit:
            break
    return unique


def summarize_for_qa(story_summary: Optional[str], content: str, max_chars: int = 8000) -> str:
    """
    Extract QA-relevant content from PRD.

    Prioritizes requirement/functional content.
    NO truncation - AI needs full context to understand.
    """
    # Get first few paragraphs (not just first one)
    paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()][:5]
    overview = '\n\n'.join(paragraphs)
    if len(overview) > 2000:
        overview = overview[:2000]
    
    bullets = _collect_priority_lines(content, limit=40)

    parts = []
    if overview:
        parts.append(f"**Overview**:\n{overview}")
    if bullets:
        parts.append("\n**Key Requirements & Features**:")
        parts.extend([f"• {b}" for b in bullets])

    summary = "\n".join(parts)
    # Only trim if absolutely necessary (>8000 chars)
    if len(summary) > max_chars:
        trimmed = summary[:max_chars]
        last_period = trimmed.rfind('.')
        if last_period > max_chars * 0.85:
            return trimmed[:last_period+1]
        return trimmed
    return summary


