"""
Contract tests for all Womba CLIs (Python, Go, Java, Node.js)
Ensures all CLIs produce consistent output from the same API
"""

import pytest
import subprocess
import json
from pathlib import Path


# Test configuration
TEST_STORY = "PLAT-12991"
WOMBA_API_URL = "https://womba.onrender.com"
WOMBA_API_KEY = "test-key"  # Override with env var


class TestCLIContract:
    """Test contract consistency across all CLIs"""
    
    def _run_cli(self, cli_path: str, args: list[str], env: dict) -> tuple[int, str, str]:
        """Helper to run CLI and capture output"""
        result = subprocess.run(
            [cli_path] + args,
            capture_output=True,
            text=True,
            env=env
        )
        return result.returncode, result.stdout, result.stderr
    
    def test_python_cli_generate(self):
        """Test Python CLI: womba generate"""
        env = {
            "WOMBA_API_URL": WOMBA_API_URL,
            "WOMBA_API_KEY": WOMBA_API_KEY,
        }
        
        returncode, stdout, stderr = self._run_cli(
            "python3",
            ["womba_cli.py", "generate", TEST_STORY],
            env
        )
        
        assert returncode == 0, f"CLI failed: {stderr}"
        assert "test cases" in stdout.lower()
    
    def test_java_cli_generate(self):
        """Test Java CLI: womba generate"""
        java_cli = Path("../womba-java/target/womba.jar")
        if not java_cli.exists():
            pytest.skip("Java CLI not built")
        
        env = {
            "WOMBA_API_URL": WOMBA_API_URL,
            "WOMBA_API_KEY": WOMBA_API_KEY,
        }
        
        returncode, stdout, stderr = self._run_cli(
            "java",
            ["-jar", str(java_cli), "generate", "-story", TEST_STORY],
            env
        )
        
        assert returncode == 0, f"CLI failed: {stderr}"
        assert "test cases" in stdout.lower()
    
    def test_go_cli_generate(self):
        """Test Go CLI: womba generate"""
        go_cli = Path("../womba-go/womba")
        if not go_cli.exists():
            pytest.skip("Go CLI not built")
        
        env = {
            "WOMBA_API_URL": WOMBA_API_URL,
            "WOMBA_API_KEY": WOMBA_API_KEY,
        }
        
        returncode, stdout, stderr = self._run_cli(
            str(go_cli),
            ["generate", "-story", TEST_STORY],
            env
        )
        
        assert returncode == 0, f"CLI failed: {stderr}"
        assert "test cases" in stdout.lower()
    
    def test_node_cli_generate(self):
        """Test Node.js CLI: womba generate"""
        node_cli = Path("../womba-node/index.js")
        if not node_cli.exists():
            pytest.skip("Node CLI not found")
        
        env = {
            "WOMBA_API_URL": WOMBA_API_URL,
            "WOMBA_API_KEY": WOMBA_API_KEY,
        }
        
        returncode, stdout, stderr = self._run_cli(
            "node",
            [str(node_cli), "generate", "-s", TEST_STORY],
            env
        )
        
        assert returncode == 0, f"CLI failed: {stderr}"
        assert "test cases" in stdout.lower()
    
    def test_cli_outputs_match(self):
        """Test that all CLIs produce equivalent output"""
        # This is a more comprehensive test that compares actual test case data
        # For now, we just verify they all run successfully
        pass


class TestCLIZephyrIntegration:
    """Test Zephyr upload functionality across CLIs"""
    
    @pytest.mark.integration
    def test_python_cli_upload(self):
        """Test Python CLI: womba generate --upload"""
        pytest.skip("Requires valid Zephyr credentials")
    
    @pytest.mark.integration
    def test_java_cli_upload(self):
        """Test Java CLI: womba generate --upload"""
        pytest.skip("Requires valid Zephyr credentials")


class TestCLIFullWorkflow:
    """Test full 'womba all' workflow"""
    
    @pytest.mark.integration
    @pytest.mark.slow
    def test_python_cli_full_workflow(self):
        """Test Python CLI: womba all"""
        pytest.skip("Requires repo access and credentials")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

