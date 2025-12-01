"""
Query-Focused Context Extractor for RAG.

Extracts only QA-relevant content from documents based on story context.
Uses a multi-stage pipeline:
1. Chunk document into semantic sections
2. Score each chunk for relevance to story
3. Score each chunk for testability
4. Filter and rank chunks
5. Optionally AI-summarize long chunks

This replaces generic summarization with targeted extraction that:
- Focuses on the specific story's requirements
- Prioritizes testable content over background/history
- Respects token budgets while maximizing value
"""

import re
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from loguru import logger


@dataclass
class ScoredChunk:
    """A document chunk with relevance and testability scores."""
    text: str
    relevance_score: float  # 0.0 to 1.0 - how relevant to story
    testability_score: float  # 0.0 to 1.0 - how testable
    combined_score: float  # weighted combination
    section_type: str  # 'requirement', 'use_case', 'api', 'background', 'other'
    char_count: int


# Patterns that indicate testable content
TESTABLE_PATTERNS = [
    # Requirements language
    (r'\b(must|should|shall|will|can|cannot|may not)\b', 0.3),
    # Conditional behavior
    (r'\b(when|if|given|then|unless|provided that)\b', 0.2),
    # Observable behaviors
    (r'\b(returns?|displays?|shows?|creates?|updates?|deletes?|validates?)\b', 0.25),
    # Error cases
    (r'\b(error|fail|invalid|unauthorized|forbidden|denied|reject)\b', 0.3),
    # API methods
    (r'\b(GET|POST|PUT|DELETE|PATCH)\b', 0.35),
    # API paths
    (r'/[a-zA-Z0-9_/-]+', 0.2),
    # Acceptance criteria markers
    (r'\b(accept|criteria|AC|given|when|then)\b', 0.25),
    # Verification language
    (r'\b(verify|check|ensure|confirm|assert)\b', 0.15),
]

# Patterns that indicate non-testable content
NON_TESTABLE_PATTERNS = [
    # Historical/background
    (r'\b(history|background|context|historically|previously)\b', -0.3),
    # Decision discussions
    (r'\b(decided|discussed|agreed|meeting|call|sync|review)\b', -0.25),
    # Alternatives
    (r'\b(option|alternative|considered|proposed|suggestion)\b', -0.2),
    # Meta content
    (r'\b(note:|disclaimer|fyi|btw|aside)\b', -0.15),
    # Future/tentative
    (r'\b(might|could|possibly|potentially|tbd|todo)\b', -0.1),
]

# Section type patterns for classification
SECTION_PATTERNS = {
    'requirement': r'\b(requirement|must|shall|should|mandatory)\b',
    'use_case': r'\b(use case|scenario|user story|as a user|workflow)\b',
    'api': r'\b(api|endpoint|request|response|GET|POST|PUT|DELETE|PATCH)\b',
    'acceptance': r'\b(acceptance|criteria|AC|given|when|then)\b',
    'background': r'\b(background|overview|context|introduction|history)\b',
}


class QueryFocusedExtractor:
    """
    Extracts QA-relevant content from documents based on story context.
    
    Pipeline:
    1. Chunk document into semantic sections
    2. Score each chunk for relevance to story keywords
    3. Score each chunk for testability
    4. Filter and rank chunks by combined score
    5. Optionally AI-summarize long high-value chunks
    
    Usage:
        extractor = QueryFocusedExtractor()
        focused_content = await extractor.extract_relevant_content(
            document=confluence_doc,
            story_keywords=['audit', 'tenant', 'login'],
            acceptance_criteria=['audit records created for login'],
            max_output_chars=2000
        )
    """
    
    def __init__(
        self,
        min_relevance_score: float = 0.3,
        use_ai_summarization: bool = True,
        ai_model: str = "gpt-4o-mini"
    ):
        """
        Initialize the extractor.
        
        Args:
            min_relevance_score: Minimum combined score to include chunk (0.0-1.0)
            use_ai_summarization: Whether to use AI for long chunk summarization
            ai_model: Model to use for AI summarization
        """
        self.min_relevance_score = min_relevance_score
        self.use_ai_summarization = use_ai_summarization
        self.ai_model = ai_model
        
        logger.info(f"[EXTRACTOR] Initialized QueryFocusedExtractor: "
                   f"min_score={min_relevance_score}, ai_summarize={use_ai_summarization}")
    
    async def extract_relevant_content(
        self,
        document: str,
        story_keywords: List[str],
        acceptance_criteria: List[str],
        story_summary: Optional[str] = None,
        max_output_chars: int = 2000
    ) -> str:
        """
        Extract only QA-relevant content from document.
        
        Args:
            document: Full document text
            story_keywords: Keywords from the story (components, labels, key terms)
            acceptance_criteria: List of acceptance criteria from story
            story_summary: Optional story summary for context
            max_output_chars: Maximum characters in output
            
        Returns:
            Focused content string with only QA-relevant sections
        """
        if not document or len(document.strip()) < 50:
            logger.debug("[EXTRACTOR] Document too short, returning as-is")
            return document.strip()
        
        original_len = len(document)
        logger.info(f"[EXTRACTOR] Processing document: {original_len} chars, "
                   f"{len(story_keywords)} keywords, {len(acceptance_criteria)} ACs")
        
        # Step 1: Chunk document
        chunks = self._chunk_document(document)
        logger.debug(f"[EXTRACTOR] Split into {len(chunks)} chunks")
        
        # Step 2 & 3: Score each chunk
        scored_chunks = []
        for chunk in chunks:
            relevance = self._score_relevance(chunk, story_keywords, acceptance_criteria)
            testability = self._score_testability(chunk)
            section_type = self._classify_section(chunk)
            
            # Combined score: 60% relevance, 40% testability
            combined = (relevance * 0.6) + (testability * 0.4)
            
            scored_chunks.append(ScoredChunk(
                text=chunk,
                relevance_score=relevance,
                testability_score=testability,
                combined_score=combined,
                section_type=section_type,
                char_count=len(chunk)
            ))
        
        # Step 4: Filter and rank
        filtered = [c for c in scored_chunks if c.combined_score >= self.min_relevance_score]
        filtered.sort(key=lambda x: x.combined_score, reverse=True)
        
        logger.info(f"[EXTRACTOR] Filtered: {len(scored_chunks)} -> {len(filtered)} chunks "
                   f"(threshold={self.min_relevance_score})")
        
        if not filtered:
            # Fallback: return top 3 chunks by score even if below threshold
            logger.warning("[EXTRACTOR] No chunks passed threshold, using top 3")
            filtered = sorted(scored_chunks, key=lambda x: x.combined_score, reverse=True)[:3]
        
        # Step 5: Build output within budget
        output_parts = []
        current_chars = 0
        
        for chunk in filtered:
            chunk_text = chunk.text
            
            # If chunk is too long and AI summarization enabled, summarize it
            if len(chunk_text) > 1000 and self.use_ai_summarization:
                chunk_text = await self._ai_summarize_chunk(
                    chunk_text, 
                    story_summary or "",
                    acceptance_criteria
                )
            
            # Check if we can fit this chunk
            if current_chars + len(chunk_text) > max_output_chars:
                # Try to fit partial
                remaining = max_output_chars - current_chars
                if remaining > 200:
                    # Truncate at sentence boundary
                    truncated = self._truncate_at_sentence(chunk_text, remaining)
                    if truncated:
                        output_parts.append(truncated)
                        current_chars += len(truncated)
                break
            
            output_parts.append(chunk_text)
            current_chars += len(chunk_text)
        
        result = "\n\n".join(output_parts)
        
        # Log extraction stats
        reduction = (1 - len(result) / original_len) * 100 if original_len > 0 else 0
        logger.info(f"[EXTRACTOR] Extraction complete: {original_len} -> {len(result)} chars "
                   f"({reduction:.1f}% reduction)")
        
        # Log section type breakdown
        section_counts = {}
        for chunk in filtered[:len(output_parts)]:
            section_counts[chunk.section_type] = section_counts.get(chunk.section_type, 0) + 1
        logger.debug(f"[EXTRACTOR] Section breakdown: {section_counts}")
        
        return result
    
    def _chunk_document(self, document: str) -> List[str]:
        """
        Split document into semantic chunks.
        
        Splits by:
        1. Markdown headers (##, ###)
        2. Double newlines (paragraphs)
        3. Horizontal rules (---, ***)
        """
        # Normalize newlines
        text = document.replace('\r\n', '\n')
        
        # Split by headers first
        header_pattern = r'\n(?=#{1,6}\s+)'
        sections = re.split(header_pattern, text)
        
        chunks = []
        for section in sections:
            # Further split long sections by paragraphs
            if len(section) > 800:
                paragraphs = re.split(r'\n\n+', section)
                for para in paragraphs:
                    para = para.strip()
                    if len(para) > 50:  # Skip very short paragraphs
                        chunks.append(para)
            else:
                section = section.strip()
                if len(section) > 50:
                    chunks.append(section)
        
        # Merge very short chunks with next chunk
        merged = []
        buffer = ""
        for chunk in chunks:
            if len(buffer) + len(chunk) < 200:
                buffer += "\n" + chunk if buffer else chunk
            else:
                if buffer:
                    merged.append(buffer)
                buffer = chunk
        if buffer:
            merged.append(buffer)
        
        return merged if merged else [document.strip()]
    
    def _score_relevance(
        self,
        chunk: str,
        story_keywords: List[str],
        acceptance_criteria: List[str]
    ) -> float:
        """
        Score chunk relevance to story (0.0 to 1.0).
        
        Based on:
        - Keyword overlap with story keywords
        - Semantic overlap with acceptance criteria
        """
        if not chunk:
            return 0.0
        
        chunk_lower = chunk.lower()
        score = 0.0
        
        # Keyword matching (40% of relevance)
        if story_keywords:
            keyword_matches = sum(1 for kw in story_keywords if kw.lower() in chunk_lower)
            keyword_score = min(keyword_matches / max(len(story_keywords), 1), 1.0)
            score += keyword_score * 0.4
        
        # AC term matching (60% of relevance)
        if acceptance_criteria:
            ac_matches = 0
            for ac in acceptance_criteria:
                # Extract key terms from AC (words > 4 chars)
                ac_terms = [w.lower() for w in ac.split() if len(w) > 4]
                matches = sum(1 for term in ac_terms if term in chunk_lower)
                if matches >= 2:  # At least 2 terms match
                    ac_matches += 1
            
            ac_score = min(ac_matches / max(len(acceptance_criteria), 1), 1.0)
            score += ac_score * 0.6
        
        return min(score, 1.0)
    
    def _score_testability(self, chunk: str) -> float:
        """
        Score chunk testability (0.0 to 1.0).
        
        Higher scores for content that describes verifiable behavior.
        Lower scores for background, history, discussions.
        """
        if not chunk:
            return 0.0
        
        chunk_lower = chunk.lower()
        score = 0.5  # Start neutral
        
        # Apply testable patterns (boost score)
        for pattern, weight in TESTABLE_PATTERNS:
            matches = len(re.findall(pattern, chunk_lower, re.IGNORECASE))
            score += min(matches * weight * 0.1, weight)  # Cap contribution per pattern
        
        # Apply non-testable patterns (reduce score)
        for pattern, weight in NON_TESTABLE_PATTERNS:
            matches = len(re.findall(pattern, chunk_lower, re.IGNORECASE))
            score += min(matches * weight * 0.1, weight)  # weight is negative
        
        # Clamp to 0.0-1.0
        return max(0.0, min(1.0, score))
    
    def _classify_section(self, chunk: str) -> str:
        """Classify chunk into section type."""
        chunk_lower = chunk.lower()
        
        best_type = 'other'
        best_score = 0
        
        for section_type, pattern in SECTION_PATTERNS.items():
            matches = len(re.findall(pattern, chunk_lower, re.IGNORECASE))
            if matches > best_score:
                best_score = matches
                best_type = section_type
        
        return best_type
    
    async def _ai_summarize_chunk(
        self,
        chunk: str,
        story_summary: str,
        acceptance_criteria: List[str]
    ) -> str:
        """
        Use AI to extract QA-relevant points from a long chunk.
        
        Only called for chunks > 1000 chars when AI summarization is enabled.
        """
        try:
            from src.config.settings import settings
            import openai
            
            client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
            
            ac_text = "\n".join(f"- {ac}" for ac in acceptance_criteria[:5])
            
            prompt = f"""Extract ONLY the QA-testable requirements from this document section.

Story Context: {story_summary[:500] if story_summary else 'Not provided'}

Acceptance Criteria:
{ac_text}

Document Section:
{chunk[:2000]}

Output ONLY:
1. Functional requirements that can be tested
2. Expected behaviors with specific conditions
3. Error cases and edge cases
4. API endpoints/methods mentioned

Skip: Background, history, decisions, meeting notes, alternatives considered.

Format as bullet points. Be concise (max 500 chars)."""

            response = await client.chat.completions.create(
                model=self.ai_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=300,
                temperature=0.1
            )
            
            result = response.choices[0].message.content.strip()
            logger.debug(f"[EXTRACTOR] AI summarized {len(chunk)} -> {len(result)} chars")
            return result
            
        except Exception as e:
            logger.warning(f"[EXTRACTOR] AI summarization failed: {e}, using truncation")
            return self._truncate_at_sentence(chunk, 500)
    
    def _truncate_at_sentence(self, text: str, max_chars: int) -> str:
        """Truncate text at sentence boundary."""
        if len(text) <= max_chars:
            return text
        
        truncated = text[:max_chars]
        
        # Try to end at sentence boundary
        last_period = truncated.rfind('.')
        last_newline = truncated.rfind('\n')
        cut_point = max(last_period, last_newline)
        
        if cut_point > max_chars * 0.7:
            return truncated[:cut_point + 1].strip()
        
        return truncated.strip() + "..."


def extract_story_keywords(story_summary: str, story_description: str, 
                           components: List[str], labels: List[str]) -> List[str]:
    """
    Extract keywords from story for relevance matching.
    
    Args:
        story_summary: Story title/summary
        story_description: Full story description
        components: Jira components
        labels: Jira labels
        
    Returns:
        List of keywords for matching
    """
    keywords = set()
    
    # Add components and labels directly
    keywords.update(c.lower() for c in components if c)
    keywords.update(l.lower() for l in labels if l)
    
    # Extract key terms from summary (words > 4 chars, not common words)
    common_words = {'that', 'this', 'with', 'from', 'have', 'been', 'will', 'should',
                   'would', 'could', 'about', 'which', 'their', 'there', 'when', 'what'}
    
    for text in [story_summary, story_description]:
        if text:
            words = re.findall(r'\b[a-zA-Z]{4,}\b', text.lower())
            keywords.update(w for w in words if w not in common_words)
    
    # Limit to most relevant keywords
    return list(keywords)[:30]


# Convenience function for synchronous usage
def extract_relevant_content_sync(
    document: str,
    story_keywords: List[str],
    acceptance_criteria: List[str],
    story_summary: Optional[str] = None,
    max_output_chars: int = 2000,
    min_relevance_score: float = 0.3,
    use_ai_summarization: bool = False  # Disabled by default for sync
) -> str:
    """
    Synchronous wrapper for extract_relevant_content.
    
    Note: AI summarization is disabled by default in sync mode.
    """
    extractor = QueryFocusedExtractor(
        min_relevance_score=min_relevance_score,
        use_ai_summarization=use_ai_summarization
    )
    
    return asyncio.run(extractor.extract_relevant_content(
        document=document,
        story_keywords=story_keywords,
        acceptance_criteria=acceptance_criteria,
        story_summary=story_summary,
        max_output_chars=max_output_chars
    ))


# ============================================================================
# UNIFIED EXTRACTION FOR ALL SOURCE TYPES
# ============================================================================

# Source-specific extraction configurations
SOURCE_CONFIGS = {
    'confluence': {
        'max_chars': 2000,
        'min_relevance': 0.3,
        'prioritize_sections': ['requirement', 'acceptance', 'use_case', 'api'],
        'use_ai_summarization': True,
    },
    'swagger': {
        'max_chars': 1500,
        'min_relevance': 0.4,  # Higher threshold - we want exact matches
        'prioritize_sections': ['api'],
        'use_ai_summarization': False,  # Keep exact API specs
    },
    'external': {
        'max_chars': 1500,
        'min_relevance': 0.35,
        'prioritize_sections': ['api', 'requirement'],
        'use_ai_summarization': True,
    },
    'test_plan': {
        'max_chars': 1000,
        'min_relevance': 0.5,  # High threshold - only very similar tests
        'prioritize_sections': ['requirement', 'use_case'],
        'use_ai_summarization': False,  # Keep test structure intact
    },
    'existing_test': {
        'max_chars': 800,
        'min_relevance': 0.6,  # Very high - for duplicate detection
        'prioritize_sections': ['requirement'],
        'use_ai_summarization': False,
    },
    'jira_story': {
        'max_chars': 1000,
        'min_relevance': 0.4,
        'prioritize_sections': ['requirement', 'acceptance'],
        'use_ai_summarization': True,
    },
}


async def extract_relevant_from_any_source(
    content: str,
    source_type: str,
    story_keywords: List[str],
    acceptance_criteria: List[str],
    story_summary: Optional[str] = None,
    max_chars: Optional[int] = None
) -> str:
    """
    Apply appropriate extraction based on source type.
    
    This is the UNIFIED entry point for extracting relevant content from ANY source.
    Each source type has its own configuration for:
    - Maximum output characters
    - Minimum relevance threshold
    - Section prioritization
    - AI summarization toggle
    
    Args:
        content: Raw content to extract from
        source_type: One of 'confluence', 'swagger', 'external', 'test_plan', 'existing_test', 'jira_story'
        story_keywords: Keywords from the story for relevance matching
        acceptance_criteria: ACs from the story for relevance matching
        story_summary: Optional story summary for AI summarization context
        max_chars: Override max chars (uses source default if None)
        
    Returns:
        Extracted content string, filtered and summarized appropriately
    """
    if not content or len(content.strip()) < 50:
        return content.strip() if content else ""
    
    # Get source-specific config
    config = SOURCE_CONFIGS.get(source_type, SOURCE_CONFIGS['confluence'])
    
    effective_max_chars = max_chars or config['max_chars']
    
    # If content is already short enough and source doesn't need AI summarization, return as-is
    if len(content) <= effective_max_chars and not config['use_ai_summarization']:
        return content.strip()
    
    logger.debug(f"[EXTRACTOR] Processing {source_type} content: {len(content)} chars -> max {effective_max_chars}")
    
    # Create extractor with source-specific settings
    extractor = QueryFocusedExtractor(
        min_relevance_score=config['min_relevance'],
        use_ai_summarization=config['use_ai_summarization'],
        ai_model="gpt-4o-mini"
    )
    
    # Extract relevant content
    result = await extractor.extract_relevant_content(
        document=content,
        story_keywords=story_keywords,
        acceptance_criteria=acceptance_criteria,
        story_summary=story_summary,
        max_output_chars=effective_max_chars
    )
    
    logger.info(f"[EXTRACTOR] {source_type}: {len(content)} -> {len(result)} chars "
               f"({(1 - len(result)/len(content))*100:.1f}% reduction)")
    
    return result


def extract_swagger_endpoints(
    swagger_content: str,
    story_keywords: List[str]
) -> str:
    """
    Special extraction for Swagger/OpenAPI content.
    
    Keeps only endpoints that match story keywords.
    Preserves request/response examples for matching endpoints.
    
    Args:
        swagger_content: Raw Swagger document content
        story_keywords: Keywords from the story
        
    Returns:
        Filtered Swagger content with only relevant endpoints
    """
    if not swagger_content:
        return ""
    
    lines = swagger_content.split('\n')
    result_lines = []
    current_endpoint = []
    in_relevant_endpoint = False
    endpoint_header = ""
    
    # Keywords to match (lowercase)
    keywords_lower = [kw.lower() for kw in story_keywords if len(kw) > 2]
    
    for line in lines:
        line_lower = line.lower()
        
        # Check if this is an endpoint line (GET, POST, etc.)
        if any(method in line_lower for method in ['get ', 'post ', 'put ', 'patch ', 'delete ']):
            # Check if previous endpoint was relevant
            if in_relevant_endpoint and current_endpoint:
                result_lines.extend(current_endpoint)
                result_lines.append("")  # Separator
            
            # Start new endpoint
            current_endpoint = [line]
            endpoint_header = line
            
            # Check if this endpoint is relevant
            in_relevant_endpoint = any(kw in line_lower for kw in keywords_lower)
            
        elif current_endpoint:
            # Continue building current endpoint
            current_endpoint.append(line)
            
            # Also check content for relevance
            if not in_relevant_endpoint and any(kw in line_lower for kw in keywords_lower):
                in_relevant_endpoint = True
    
    # Don't forget last endpoint
    if in_relevant_endpoint and current_endpoint:
        result_lines.extend(current_endpoint)
    
    result = '\n'.join(result_lines)
    
    if result:
        logger.info(f"[EXTRACTOR] Swagger: kept {len(result_lines)} lines of relevant endpoints")
    else:
        # If no matches, return truncated original
        logger.warning("[EXTRACTOR] Swagger: no keyword matches, returning truncated content")
        return swagger_content[:1500] + "\n... [truncated]" if len(swagger_content) > 1500 else swagger_content
    
    return result

