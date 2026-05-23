"""Library - persistent video history with per-song settings.

Backed by a single library.json next to the executable.
Writes are atomic (temp file + os.replace). Invalid library files stop startup
instead of being discarded or replaced with an empty history.
"""

import json
import logging
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)


class LibraryLoadError(RuntimeError):
    """Raised when an existing library file cannot be loaded safely."""


@dataclass
class SavedOutput:
    path: str
    pitch: int
    vocal_reduce: int
    saved_at: str


@dataclass
class LibraryEntry:
    title: str
    source_type: str  # "youtube" | "local"
    source: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    cached_path: Optional[str] = None
    thumbnail_path: Optional[str] = None
    duration_seconds: int = 0
    last_pitch: int = 0
    last_vocal_reduce: int = 0
    last_opened: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    saved_outputs: list[SavedOutput] = field(default_factory=list)


class Library:
    """In-memory view of library.json, written after every mutation."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._entries: dict[str, LibraryEntry] = {}
        self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def list(self) -> list[LibraryEntry]:
        """All entries, most-recently-opened first."""
        return sorted(
            self._entries.values(),
            key=lambda e: e.last_opened,
            reverse=True,
        )

    def get(self, entry_id: str) -> Optional[LibraryEntry]:
        return self._entries.get(entry_id)

    def upsert(self, entry: LibraryEntry) -> None:
        self._entries[entry.id] = entry
        self._save()

    def remove(self, entry_id: str) -> None:
        if entry_id not in self._entries:
            log.error("Cannot remove missing library entry: entry_id=%s", entry_id)
            raise KeyError(entry_id)
        self._entries.pop(entry_id)
        self._save()

    def find_by_source(self, source: str) -> "Optional[LibraryEntry]":
        """Return the first entry whose source or cached_path matches, or None."""
        for entry in self._entries.values():
            if entry.source == source or entry.cached_path == source:
                return entry
        return None

    def touch(self, entry_id: str, pitch: int, vocal_reduce: int) -> None:
        """Update last_opened, last_pitch, last_vocal_reduce; persist."""
        entry = self._entries.get(entry_id)
        if entry is None:
            log.error(
                "Cannot touch missing library entry: entry_id=%s pitch=%s vocal_reduce=%s",
                entry_id,
                pitch,
                vocal_reduce,
            )
            raise KeyError(entry_id)
        entry.last_opened = datetime.now(timezone.utc).isoformat()
        entry.last_pitch = pitch
        entry.last_vocal_reduce = vocal_reduce
        self._save()

    def add_saved_output(
        self, entry_id: str, output_path: str, pitch: int, vocal_reduce: int
    ) -> None:
        """Append a saved output record to an entry; persist."""
        entry = self._entries.get(entry_id)
        if entry is None:
            log.error(
                "Cannot add saved output to missing library entry: entry_id=%s output_path=%s "
                "pitch=%s vocal_reduce=%s",
                entry_id,
                output_path,
                pitch,
                vocal_reduce,
            )
            raise KeyError(entry_id)
        entry.saved_outputs.append(
            SavedOutput(
                path=output_path,
                pitch=pitch,
                vocal_reduce=vocal_reduce,
                saved_at=datetime.now(timezone.utc).isoformat(),
            )
        )
        self._save()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            for raw in data.get("entries", []):
                so_raw = raw.pop("saved_outputs", [])
                entry = LibraryEntry(
                    saved_outputs=[SavedOutput(**o) for o in so_raw],
                    **raw,
                )
                self._entries[entry.id] = entry
        except Exception as exc:  # noqa: BLE001
            log.exception("Could not load library file: path=%s", self._path)
            raise LibraryLoadError(f"Could not load library file: {self._path}") from exc

    def _save(self) -> None:
        payload = json.dumps(
            {"entries": [asdict(e) for e in self._entries.values()]},
            indent=2,
            ensure_ascii=False,
        )
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(payload, encoding="utf-8")
        os.replace(tmp, self._path)
