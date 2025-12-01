"""
Unit tests for Zephyr test cycle functionality.
Tests the new methods: get_test_cycle_folders, add_test_cases_to_cycle, 
link_cycle_to_issue, and upload_to_cycle.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import Response

from src.integrations.zephyr_integration import ZephyrIntegration


class TestZephyrCycleFunctionality:
    """Test suite for Zephyr test cycle methods."""

    @pytest.fixture
    def zephyr(self):
        """Create a ZephyrIntegration instance for testing."""
        return ZephyrIntegration(
            api_key="test-key", 
            base_url="https://api.zephyrscale.smartbear.com/v2"
        )

    @pytest.mark.asyncio
    async def test_get_test_cycle_folders(self, zephyr, monkeypatch):
        """Test fetching test cycle folders."""
        mock_folders = [
            {'id': '1', 'name': 'Sprint 1', 'parentId': None, 'children': []},
            {'id': '2', 'name': 'Sprint 2', 'parentId': None, 'children': [
                {'id': '3', 'name': 'Backend', 'parentId': '2', 'children': []}
            ]}
        ]
        
        async def mock_get(*args, **kwargs):
            response = MagicMock()
            response.status_code = 200
            response.json.return_value = {'values': mock_folders}
            response.raise_for_status = MagicMock()
            return response
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value.get = AsyncMock(side_effect=mock_get)
            
            folders = await zephyr.get_test_cycle_folders('PROJ')
            
            assert len(folders) == 2
            assert folders[0]['name'] == 'Sprint 1'

    @pytest.mark.asyncio
    async def test_get_folders_with_paths(self, zephyr, monkeypatch):
        """Test get_folders returns folders with full paths."""
        mock_folders = [
            {'id': '1', 'name': 'Parent', 'parentId': None, 'children': [
                {'id': '2', 'name': 'Child', 'parentId': '1', 'children': []}
            ]}
        ]
        
        async def mock_get(*args, **kwargs):
            response = MagicMock()
            response.status_code = 200
            response.json.return_value = {'values': mock_folders}
            response.raise_for_status = MagicMock()
            return response
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value.get = AsyncMock(side_effect=mock_get)
            
            folders = await zephyr.get_folders('PROJ', 'TEST_CASE')
            
            # Should have 2 folders (Parent and Child)
            assert len(folders) == 2
            
            # Find the child folder and check its path
            child_folder = next((f for f in folders if f['name'] == 'Child'), None)
            assert child_folder is not None
            assert child_folder['path'] == 'Parent/Child'

    @pytest.mark.asyncio
    async def test_add_test_cases_to_cycle(self, zephyr):
        """Test adding test cases to a test cycle."""
        async def mock_post(*args, **kwargs):
            response = MagicMock()
            response.status_code = 201
            response.json.return_value = {'key': 'PROJ-E1'}
            response.raise_for_status = MagicMock()
            return response
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value.post = AsyncMock(side_effect=mock_post)
            
            result = await zephyr.add_test_cases_to_cycle(
                cycle_key='PROJ-R1',
                test_case_keys=['PROJ-T1', 'PROJ-T2'],
                project_key='PROJ'
            )
            
            assert result['cycle_key'] == 'PROJ-R1'
            assert len(result['successful']) == 2
            assert len(result['failed']) == 0

    @pytest.mark.asyncio
    async def test_add_test_cases_to_cycle_partial_failure(self, zephyr):
        """Test adding test cases when some fail."""
        call_count = [0]
        
        async def mock_post(*args, **kwargs):
            call_count[0] += 1
            response = MagicMock()
            if call_count[0] == 1:
                # First call succeeds
                response.status_code = 201
                response.json.return_value = {'key': 'PROJ-E1'}
                response.raise_for_status = MagicMock()
            else:
                # Second call fails
                response.status_code = 400
                response.text = "Bad Request"
                from httpx import HTTPStatusError
                response.raise_for_status = MagicMock(
                    side_effect=HTTPStatusError("Error", request=MagicMock(), response=response)
                )
            return response
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value.post = AsyncMock(side_effect=mock_post)
            
            result = await zephyr.add_test_cases_to_cycle(
                cycle_key='PROJ-R1',
                test_case_keys=['PROJ-T1', 'PROJ-T2'],
                project_key='PROJ'
            )
            
            assert len(result['successful']) == 1
            assert len(result['failed']) == 1

    @pytest.mark.asyncio
    async def test_link_cycle_to_issue(self, zephyr):
        """Test linking a test cycle to a Jira issue."""
        async def mock_get(*args, **kwargs):
            response = MagicMock()
            response.status_code = 200
            response.json.return_value = {'id': '12345', 'key': 'PROJ-100'}
            return response
        
        async def mock_post(*args, **kwargs):
            response = MagicMock()
            response.status_code = 201
            response.raise_for_status = MagicMock()
            return response
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_instance.get = AsyncMock(side_effect=mock_get)
            mock_instance.post = AsyncMock(side_effect=mock_post)
            
            # Should not raise
            await zephyr.link_cycle_to_issue('PROJ-R1', 'PROJ-100')
            
            # Verify POST was called for linking
            assert mock_instance.post.called

    @pytest.mark.asyncio
    async def test_ensure_cycle_folder_uses_existing(self, zephyr, monkeypatch):
        """Test that ensure_cycle_folder uses existing folder."""
        async def fake_get_folders(project_key):
            return [{
                'id': '10',
                'name': 'Existing',
                'parentId': None,
                'children': []
            }]
        
        async def fake_create(*args, **kwargs):
            raise AssertionError("Should not create folder when it already exists")
        
        monkeypatch.setattr(zephyr, "get_test_cycle_folders", fake_get_folders)
        monkeypatch.setattr(zephyr, "_create_cycle_folder", fake_create)
        
        folder_id = await zephyr.ensure_cycle_folder('PROJ', 'Existing')
        assert folder_id == '10'

    @pytest.mark.asyncio
    async def test_ensure_cycle_folder_creates_missing(self, zephyr, monkeypatch):
        """Test that ensure_cycle_folder creates missing folder."""
        async def fake_get_folders(project_key):
            return [{
                'id': '10',
                'name': 'Existing',
                'parentId': None,
                'children': []
            }]
        
        created = []
        
        async def fake_create(project_key, name, parent_id):
            created.append((name, parent_id))
            return '20'
        
        monkeypatch.setattr(zephyr, "get_test_cycle_folders", fake_get_folders)
        monkeypatch.setattr(zephyr, "_create_cycle_folder", fake_create)
        
        folder_id = await zephyr.ensure_cycle_folder('PROJ', 'Existing/NewChild')
        assert folder_id == '20'
        assert created == [('NewChild', '10')]


class TestUploadToCycleWorkflow:
    """Test the complete upload_to_cycle workflow."""

    @pytest.fixture
    def zephyr(self):
        """Create a ZephyrIntegration instance for testing."""
        return ZephyrIntegration(
            api_key="test-key", 
            base_url="https://api.zephyrscale.smartbear.com/v2"
        )

    @pytest.fixture
    def sample_test_plan(self):
        """Create a sample test plan for testing."""
        from datetime import datetime
        from src.models.test_plan import TestPlan, TestPlanMetadata
        from src.models.test_case import TestCase, TestStep
        from src.models.story import JiraStory
        
        story = JiraStory(
            key="PROJ-100",
            summary="Test Story",
            description="A test story",
            issue_type="Story",
            status="In Progress",
            priority="High",
            reporter="test@example.com",
            created=datetime.now(),
            updated=datetime.now()
        )
        
        test_cases = [
            TestCase(
                title="Test Case 1",
                description="First test case",
                priority="high",
                expected_result="First expected result",
                steps=[
                    TestStep(step_number=1, action="Do something", expected_result="Something happens")
                ]
            ),
            TestCase(
                title="Test Case 2",
                description="Second test case",
                priority="medium",
                expected_result="Second expected result",
                steps=[
                    TestStep(step_number=1, action="Do another thing", expected_result="Another thing happens")
                ]
            )
        ]
        
        metadata = TestPlanMetadata(
            ai_model="test-model",
            source_story_key="PROJ-100",
            total_test_cases=2
        )
        
        return TestPlan(story=story, test_cases=test_cases, metadata=metadata, summary="Test plan summary")

    @pytest.mark.asyncio
    async def test_upload_to_cycle_success(self, zephyr, sample_test_plan, monkeypatch):
        """Test successful upload_to_cycle workflow."""
        # Mock all the dependent methods
        test_case_keys = ['PROJ-T1', 'PROJ-T2']
        tc_index = [0]
        
        async def mock_find_folder(*args, **kwargs):
            return ('10', 'ExistingFolder')
        
        async def mock_create_test_case(*args, **kwargs):
            key = test_case_keys[tc_index[0]]
            tc_index[0] += 1
            return key
        
        async def mock_create_cycle(*args, **kwargs):
            return 'PROJ-R1'
        
        async def mock_add_to_cycle(*args, **kwargs):
            return {
                'successful': [{'test_case_key': k, 'execution_key': f'PROJ-E{i}'} 
                              for i, k in enumerate(test_case_keys)],
                'failed': [],
                'cycle_key': 'PROJ-R1'
            }
        
        async def mock_link_cycle(*args, **kwargs):
            pass
        
        monkeypatch.setattr(zephyr, "find_best_matching_folder", mock_find_folder)
        monkeypatch.setattr(zephyr, "create_test_case", mock_create_test_case)
        monkeypatch.setattr(zephyr, "create_test_cycle", mock_create_cycle)
        monkeypatch.setattr(zephyr, "add_test_cases_to_cycle", mock_add_to_cycle)
        monkeypatch.setattr(zephyr, "link_cycle_to_issue", mock_link_cycle)
        
        result = await zephyr.upload_to_cycle(
            test_plan=sample_test_plan,
            project_key='PROJ',
            cycle_name='Sprint 10 Cycle',
            test_case_folder_path='TestFolder',
            story_key='PROJ-100'
        )
        
        assert result['cycle_key'] == 'PROJ-R1'
        assert result['cycle_name'] == 'Sprint 10 Cycle'
        assert len(result['test_case_keys']) == 2
        assert result['linked_to_story'] == True
        assert result['story_key'] == 'PROJ-100'
        assert len(result['errors']) == 0

    @pytest.mark.asyncio
    async def test_upload_to_cycle_no_story_link(self, zephyr, sample_test_plan, monkeypatch):
        """Test upload_to_cycle without linking to story."""
        tc_index = [0]
        test_case_keys = ['PROJ-T1', 'PROJ-T2']
        
        async def mock_create_test_case(*args, **kwargs):
            key = test_case_keys[tc_index[0]]
            tc_index[0] += 1
            return key
        
        async def mock_create_cycle(*args, **kwargs):
            return 'PROJ-R1'
        
        async def mock_add_to_cycle(*args, **kwargs):
            return {
                'successful': [{'test_case_key': k, 'execution_key': f'PROJ-E{i}'} 
                              for i, k in enumerate(test_case_keys)],
                'failed': [],
                'cycle_key': 'PROJ-R1'
            }
        
        monkeypatch.setattr(zephyr, "create_test_case", mock_create_test_case)
        monkeypatch.setattr(zephyr, "create_test_cycle", mock_create_cycle)
        monkeypatch.setattr(zephyr, "add_test_cases_to_cycle", mock_add_to_cycle)
        
        result = await zephyr.upload_to_cycle(
            test_plan=sample_test_plan,
            project_key='PROJ',
            cycle_name='Sprint 10 Cycle',
            story_key=None  # No story to link
        )
        
        assert result['cycle_key'] == 'PROJ-R1'
        assert result['linked_to_story'] == False
        assert result['story_key'] is None


class TestCycleFolderTypes:
    """Test that TEST_CYCLE folders are used correctly for cycles (not TEST_CASE folders)."""

    @pytest.fixture
    def zephyr(self):
        return ZephyrIntegration(
            api_key="test-key", 
            base_url="https://api.zephyrscale.smartbear.com/v2"
        )

    @pytest.mark.asyncio
    async def test_create_cycle_folder_uses_test_cycle_type(self, zephyr):
        """Test that _create_cycle_folder uses folderType=TEST_CYCLE."""
        async def mock_post(*args, **kwargs):
            # Verify the payload uses TEST_CYCLE folder type
            payload = kwargs.get('json', {})
            assert payload.get('folderType') == 'TEST_CYCLE', \
                f"Expected TEST_CYCLE folder type, got {payload.get('folderType')}"
            
            response = MagicMock()
            response.status_code = 201
            response.json.return_value = {'id': '999', 'name': 'NewFolder'}
            response.raise_for_status = MagicMock()
            return response
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value.post = AsyncMock(side_effect=mock_post)
            
            folder_id = await zephyr._create_cycle_folder('PROJ', 'NewFolder', None)
            
            assert folder_id == '999'

    @pytest.mark.asyncio
    async def test_get_folders_with_test_cycle_type(self, zephyr):
        """Test get_folders correctly passes TEST_CYCLE folder type to API."""
        mock_folders = [
            {'id': '1', 'name': 'CycleFolder', 'parentId': None, 'children': []}
        ]
        
        async def mock_get(*args, **kwargs):
            params = kwargs.get('params', {})
            assert params.get('folderType') == 'TEST_CYCLE', \
                f"Expected TEST_CYCLE folder type, got {params.get('folderType')}"
            
            response = MagicMock()
            response.status_code = 200
            response.json.return_value = {'values': mock_folders}
            response.raise_for_status = MagicMock()
            return response
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value.get = AsyncMock(side_effect=mock_get)
            
            folders = await zephyr.get_folders('PROJ', 'TEST_CYCLE')
            
            assert len(folders) == 1
            assert folders[0]['name'] == 'CycleFolder'

    @pytest.mark.asyncio
    async def test_upload_to_cycle_uses_cycle_folder_for_cycle(self, zephyr, monkeypatch):
        """Test that upload_to_cycle uses cycle_folder_path for TEST_CYCLE folders."""
        from datetime import datetime
        from src.models.test_plan import TestPlan, TestPlanMetadata
        from src.models.test_case import TestCase, TestStep
        from src.models.story import JiraStory
        
        story = JiraStory(
            key="PROJ-100",
            summary="Test Story",
            description="A test story",
            issue_type="Story",
            status="In Progress",
            priority="High",
            reporter="test@example.com",
            created=datetime.now(),
            updated=datetime.now()
        )
        
        test_cases = [
            TestCase(
                title="Test Case 1",
                description="First test case",
                priority="high",
                expected_result="Test expected result",
                steps=[TestStep(step_number=1, action="Do something", expected_result="Result")]
            )
        ]
        
        metadata = TestPlanMetadata(
            ai_model="test-model",
            source_story_key="PROJ-100",
            total_test_cases=1
        )
        
        test_plan = TestPlan(story=story, test_cases=test_cases, metadata=metadata, summary="Test plan summary")
        
        # Track which methods are called
        calls = []
        
        async def mock_ensure_folder(project_key, folder_path):
            calls.append(('ensure_folder', folder_path))
            return '100'  # TEST_CASE folder
        
        async def mock_ensure_cycle_folder(project_key, folder_path):
            calls.append(('ensure_cycle_folder', folder_path))
            return '200'  # TEST_CYCLE folder
        
        async def mock_create_test_case(*args, **kwargs):
            return 'PROJ-T1'
        
        async def mock_create_cycle(project_key, name, description, folder_id):
            calls.append(('create_cycle', folder_id))
            return 'PROJ-R1'
        
        async def mock_add_to_cycle(*args, **kwargs):
            return {'successful': [], 'failed': [], 'cycle_key': 'PROJ-R1'}
        
        async def mock_link(*args, **kwargs):
            pass
        
        monkeypatch.setattr(zephyr, "ensure_folder", mock_ensure_folder)
        monkeypatch.setattr(zephyr, "ensure_cycle_folder", mock_ensure_cycle_folder)
        monkeypatch.setattr(zephyr, "create_test_case", mock_create_test_case)
        monkeypatch.setattr(zephyr, "create_test_cycle", mock_create_cycle)
        monkeypatch.setattr(zephyr, "add_test_cases_to_cycle", mock_add_to_cycle)
        monkeypatch.setattr(zephyr, "link_cycle_to_issue", mock_link)
        
        # Call with cycle_folder_path only (new UI flow)
        result = await zephyr.upload_to_cycle(
            test_plan=test_plan,
            project_key='PROJ',
            cycle_name='Sprint Cycle',
            test_case_folder_path=None,  # Not using test case folder
            cycle_folder_path='SprintCycles/Sprint10',  # TEST_CYCLE folder for the cycle
            story_key='PROJ-100'
        )
        
        # Verify ensure_cycle_folder was called (not ensure_folder for cycle)
        assert ('ensure_cycle_folder', 'SprintCycles/Sprint10') in calls, \
            f"ensure_cycle_folder should be called for cycle_folder_path. Calls: {calls}"
        
        # Verify cycle was created with the cycle folder ID
        assert ('create_cycle', '200') in calls, \
            f"create_cycle should use the cycle folder ID. Calls: {calls}"


class TestCreateTestCycle:
    """Test create_test_cycle method."""

    @pytest.fixture
    def zephyr(self):
        return ZephyrIntegration(
            api_key="test-key", 
            base_url="https://api.zephyrscale.smartbear.com/v2"
        )

    @pytest.mark.asyncio
    async def test_create_test_cycle_with_folder(self, zephyr):
        """Test creating a test cycle with a folder ID."""
        async def mock_post(*args, **kwargs):
            # Verify the payload includes folderId
            payload = kwargs.get('json', {})
            assert 'folderId' in payload
            assert payload['folderId'] == 123
            
            response = MagicMock()
            response.status_code = 201
            response.json.return_value = {'key': 'PROJ-R1', 'id': '67890'}
            response.raise_for_status = MagicMock()
            return response
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value.post = AsyncMock(side_effect=mock_post)
            
            cycle_key = await zephyr.create_test_cycle(
                project_key='PROJ',
                name='Sprint 10',
                description='Sprint 10 test cycle',
                folder_id='123'
            )
            
            assert cycle_key == 'PROJ-R1'

    @pytest.mark.asyncio
    async def test_create_test_cycle_without_folder(self, zephyr):
        """Test creating a test cycle without a folder."""
        async def mock_post(*args, **kwargs):
            payload = kwargs.get('json', {})
            assert 'folderId' not in payload
            
            response = MagicMock()
            response.status_code = 201
            response.json.return_value = {'key': 'PROJ-R2', 'id': '67891'}
            response.raise_for_status = MagicMock()
            return response
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value.post = AsyncMock(side_effect=mock_post)
            
            cycle_key = await zephyr.create_test_cycle(
                project_key='PROJ',
                name='Sprint 11',
                description='Sprint 11 test cycle'
            )
            
            assert cycle_key == 'PROJ-R2'

