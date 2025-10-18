"""
Text processing utilities shared across the codebase.
"""

from typing import List, Any, Set, Optional
import re


def extract_keywords(
    text: str, 
    min_length: int = 4,
    stop_words: Optional[Set[str]] = None
) -> List[str]:
    """
    Extract meaningful keywords from text.
    
    Used by: folder matching, duplicate detection, search
    
    Args:
        text: Text to extract keywords from
        min_length: Minimum keyword length
        stop_words: Set of words to ignore
        
    Returns:
        List of unique keywords
    """
    if stop_words is None:
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'with', 'by', 'from', 'up', 'about', 'into', 'through', 'during',
            'before', 'after', 'above', 'below', 'between', 'under', 'again',
            'further', 'then', 'once', 'here', 'there', 'when', 'where', 'why',
            'how', 'all', 'both', 'each', 'few', 'more', 'most', 'other', 'some',
            'such', 'no', 'nor', 'not', 'only', 'own', 'same', 'so', 'than',
            'too', 'very', 'can', 'will', 'just', 'should', 'now', 'is', 'are',
            'was', 'were', 'been', 'being', 'have', 'has', 'had', 'do', 'does',
            'did', 'get', 'add', 'create', 'update', 'delete', 'test', 'verify'
        }
    
    # Split and clean
    words = text.lower().split()
    
    # Filter: length > min_length, not a stop word, alphanumeric
    keywords = [
        w for w in words 
        if len(w) >= min_length and w not in stop_words and w.isalnum()
    ]
    
    # Remove duplicates while preserving order
    seen = set()
    unique_keywords = []
    for kw in keywords:
        if kw not in seen:
            seen.add(kw)
            unique_keywords.append(kw)
    
    return unique_keywords


def parse_adf_to_text(adf_content: Any) -> str:
    """
    Parse Atlassian Document Format (ADF) to plain text.
    
    Args:
        adf_content: ADF content (dict or str)
        
    Returns:
        Plain text extracted from ADF
    """
    if isinstance(adf_content, str):
        return adf_content
    
    if not isinstance(adf_content, dict):
        return str(adf_content) if adf_content else ""
    
    text_parts = []
    
    def extract_recursive(node):
        if isinstance(node, dict):
            # Extract text node
            if node.get('type') == 'text':
                text = node.get('text', '')
                if text:
                    text_parts.append(text)
                
                # If this text node has link marks, also add the URL
                if 'marks' in node:
                    for mark in node.get('marks', []):
                        if mark.get('type') == 'link':
                            href = mark.get('attrs', {}).get('href', '')
                            if href:
                                text_parts.append(f' [{href}] ')
            
            # Extract inlineCard nodes (Confluence/Jira links)
            if node.get('type') == 'inlineCard':
                url = node.get('attrs', {}).get('url', '')
                if url:
                    text_parts.append(f' {url} ')
            
            # Add newlines for paragraphs
            if node.get('type') == 'paragraph':
                text_parts.append('\n')
            
            # Recurse into content
            if 'content' in node:
                for child in node['content']:
                    extract_recursive(child)
                    
        elif isinstance(node, list):
            for item in node:
                extract_recursive(item)
    
    extract_recursive(adf_content)
    return ' '.join(text_parts).strip()


def extract_urls_from_text(text: str, pattern: Optional[str] = None) -> List[str]:
    """
    Extract URLs from text.
    
    Args:
        text: Text containing URLs
        pattern: Optional regex pattern for specific URL types
        
    Returns:
        List of unique URLs
    """
    if pattern:
        matches = re.findall(pattern, text)
    else:
        # Generic URL pattern
        matches = re.findall(r'https?://[^\s<>"]+|www\.[^\s<>"]+', text)
    
    return list(set(matches))


def calculate_text_similarity(text1: str, text2: str) -> float:
    """
    Calculate similarity score between two texts using keyword overlap.
    
    Args:
        text1: First text
        text2: Second text
        
    Returns:
        Similarity score between 0 and 1
    """
    keywords1 = set(extract_keywords(text1))
    keywords2 = set(extract_keywords(text2))
    
    if not keywords1 or not keywords2:
        return 0.0
    
    intersection = keywords1 & keywords2
    union = keywords1 | keywords2
    
    return len(intersection) / len(union) if union else 0.0

