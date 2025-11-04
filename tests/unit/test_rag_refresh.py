import tempfile
from datetime import datetime, timedelta, timezone

from src.cli.rag_refresh import RAGRefreshManager


def test_record_and_read_refresh(tmp_path):
    manager = RAGRefreshManager(state_path=tmp_path / "state.json")
    project = "TEST"
    manager.record_refresh(project, ["index_all", "stories"])

    last = manager.get_last_refresh(project, "index_all")
    assert last is not None
    assert last.tzinfo == timezone.utc

    hours_since = manager.hours_since_refresh(project, "index_all")
    assert hours_since is not None
    assert hours_since >= 0


def test_should_refresh(tmp_path):
    manager = RAGRefreshManager(state_path=tmp_path / "state.json")
    project = "TEST"

    manager.record_refresh(project, ["index_all"])

    # Immediately after recording, shouldn't refresh if window is large
    assert not manager.should_refresh(project, "index_all", hours=12)

    # Simulate old timestamp by subtracting 24 hours
    old_time = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    manager._state[project]["index_all"] = old_time
    manager._save()

    assert manager.should_refresh(project, "index_all", hours=12)
