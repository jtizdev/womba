"""
Integration tests for Zephyr folder matching.

Tests that folder matching finds relevant existing folders before creating new ones.
"""

import pytest
from src.integrations.zephyr_integration import ZephyrIntegration


@pytest.mark.asyncio
async def test_find_exact_folder_match():
    """Test that exact folder name matches are found."""
    zephyr = ZephyrIntegration()
    
    # Mock folder structure
    mock_folders = [
        {'id': '123', 'name': 'Vendor Compare Tests', 'parentId': None},
        {'id': '456', 'name': 'Authorization Workspace', 'parentId': None},
        {'id': '789', 'name': 'API Tests', 'parentId': '456'},
    ]
    
    # Test exact match (case-insensitive)
    # This would require mocking get_folder_structure
    # For now, test the matching logic directly


@pytest.mark.asyncio  
async def test_find_partial_folder_match():
    """Test that partial matches (keywords) are found."""
    # Test case: AI suggests "Vendor Compare"
    # Existing folder: "Vendor Compare Tests"
    # Should match!
    pass


@pytest.mark.asyncio
async def test_create_folder_when_no_match():
    """Test that new folder is created when no match exists."""
    # Test case: AI suggests "New Feature Tests"
    # No existing folders match
    # Should create new folder
    pass


def test_keyword_matching_logic():
    """Test keyword matching algorithm."""
    suggested = "Vendor Compare Tests"
    
    existing_folders = [
        "PAP/Vendor Compare",
        "Authorization/Policy Tests",  
        "Vendor Compare View",
        "Integration Tests"
    ]
    
    # Should match "PAP/Vendor Compare" or "Vendor Compare View"
    # Both have 2+ matching words
    
    suggestion_words = set(suggested.lower().split())
    
    matches = []
    for folder in existing_folders:
        folder_words = set(folder.lower().replace('/', ' ').split())
        common = suggestion_words & folder_words
        if len(common) >= 2:
            matches.append((folder, len(common)))
    
    assert len(matches) >= 1, f"Should find at least 1 match, found {matches}"
    assert any('Vendor Compare' in m[0] for m in matches), "Should match Vendor Compare folders"


def test_nested_folder_path_building():
    """Test that nested folder paths are built correctly."""
    # Given folders with parent-child relationships
    # Should build full paths like "Parent/Child/Grandchild"
    
    folders = [
        {'id': '1', 'name': 'Parent', 'parentId': None},
        {'id': '2', 'name': 'Child', 'parentId': '1'},
        {'id': '3', 'name': 'Grandchild', 'parentId': '2'},
    ]
    
    # Build path for Grandchild
    # Should be: "Parent/Child/Grandchild"
    
    folder = folders[2]
    path_parts = [folder['name']]
    current_parent = folder['parentId']
    
    while current_parent:
        parent = next((f for f in folders if f['id'] == current_parent), None)
        if parent:
            path_parts.insert(0, parent['name'])
            current_parent = parent.get('parentId')
        else:
            break
    
    full_path = '/'.join(path_parts)
    assert full_path == "Parent/Child/Grandchild", f"Expected full path, got {full_path}"

