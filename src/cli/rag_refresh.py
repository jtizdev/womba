from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, Optional

from loguru import logger

from src.config.settings import settings


@dataclass
class RefreshInfo:
    timestamp: datetime

    @classmethod
    def from_str(cls, value: str) -> "RefreshInfo":
        return cls(datetime.fromisoformat(value))

    def to_str(self) -> str:
        return self.timestamp.replace(tzinfo=timezone.utc).isoformat()


class RAGRefreshManager:
    """Tracks RAG refresh timestamps per project/source."""

    def __init__(self, state_path: Optional[Path] = None) -> None:
        self.state_path = state_path or Path(settings.rag_collection_path) / "rag_refresh_state.json"
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self._state: Dict[str, Dict[str, str]] = {}
        self._load()

    def _load(self) -> None:
        if self.state_path.exists():
            try:
                self._state = json.loads(self.state_path.read_text())
            except Exception as exc:
                logger.warning(f"Failed to load refresh state: {exc}. Starting fresh.")
                self._state = {}

    def _save(self) -> None:
        try:
            self.state_path.write_text(json.dumps(self._state, indent=2))
        except Exception as exc:
            logger.error(f"Failed to persist refresh state: {exc}")

    def _project_bucket(self, project_key: str) -> Dict[str, str]:
        bucket = self._state.setdefault(project_key, {})
        return bucket

    def record_refresh(self, project_key: str, sources: Iterable[str]) -> None:
        now = datetime.now(timezone.utc)
        bucket = self._project_bucket(project_key)
        for source in sources:
            bucket[source] = RefreshInfo(now).to_str()
        self._save()

    def get_last_refresh(self, project_key: str, source: str) -> Optional[datetime]:
        bucket = self._state.get(project_key, {})
        value = bucket.get(source)
        if not value:
            return None
        try:
            return RefreshInfo.from_str(value).timestamp
        except Exception:
            return None

    def hours_since_refresh(self, project_key: str, source: str) -> Optional[float]:
        last = self.get_last_refresh(project_key, source)
        if not last:
            return None
        delta = datetime.now(timezone.utc) - last
        return delta.total_seconds() / 3600.0

    def should_refresh(self, project_key: str, source: str, hours: Optional[float]) -> bool:
        if hours is None:
            return True
        last = self.get_last_refresh(project_key, source)
        if not last:
            return True
        return datetime.now(timezone.utc) - last >= timedelta(hours=hours)
