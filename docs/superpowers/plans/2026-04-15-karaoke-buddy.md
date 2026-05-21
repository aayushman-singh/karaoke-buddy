# KaraokeBuddy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Windows desktop app that opens local or YouTube karaoke videos, live-shifts pitch (-12 to +12 semitones), reduces vocals (0–100%), and exports the result to MP4 — distributed as a single double-clickable `.exe`.

**Architecture:** Five nodes in a star topology, all wired through the Qt UI: Source Resolver (yt-dlp + ffprobe), Player (libmpv embedded in a Qt widget), Exporter (FFmpeg subprocess on a QThread), Library (atomic JSON file). A single pure function `build_filter_chain` drives both live playback and export, so preview and saved file are guaranteed to sound identical.

**Tech Stack:** Python 3.11+, PySide6 (Qt6), python-mpv (libmpv), yt-dlp, FFmpeg (subprocess), PyInstaller (packaging), pytest + hypothesis (tests)

---

## File Map

```
pyproject.toml
src/karaoke_buddy/
  __init__.py
  __main__.py                  # boot: startup checks, dirs, Qt app, MainWindow
  core/
    __init__.py
    filter_chain.py            # PURE: build_filter_chain(pitch, vocal) -> str
    library.py                 # LibraryEntry, SavedOutput, Library (atomic JSON)
    source_resolver.py         # SourceResolver, VideoMeta, DownloadThread
    player.py                  # VideoWidget (libmpv embedded in QWidget)
    exporter.py                # ExportThread (FFmpeg subprocess)
  ui/
    __init__.py
    main_window.py             # MainWindow: QStackedWidget routing HomeView/PlayingView
    home_view.py               # HomeView: open-file button, paste-URL button, library grid
    library_view.py            # LibraryGrid: thumbnail cards
    playing_view.py            # PlayingView: video surface, sliders, save button
tests/
  fixtures/
    sample_10s.mp4             # generate once with ffmpeg (see Task 6)
  test_filter_chain.py
  test_library.py
  test_source_resolver.py
  test_exporter.py
build/
  build.py                     # PyInstaller driver
```

---

## Task 1: Project scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `src/karaoke_buddy/__init__.py`
- Create: `src/karaoke_buddy/core/__init__.py`
- Create: `src/karaoke_buddy/ui/__init__.py`
- Create: `src/karaoke_buddy/__main__.py`
- Create: `tests/__init__.py`
- Create: `tests/fixtures/.gitkeep`
- Create: `build/.gitkeep`

- [ ] **Step 1: Create pyproject.toml**

```toml
[project]
name = "karaoke-buddy"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "PySide6>=6.7",
    "mpv>=1.0.7",
    "yt-dlp>=2024.1.1",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-qt>=4.4",
    "hypothesis>=6.0",
    "pyinstaller>=6.8",
    "ruff>=0.4",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/karaoke_buddy"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]

[tool.ruff]
line-length = 100
```

- [ ] **Step 2: Create package init files (all empty)**

```python
# src/karaoke_buddy/__init__.py
# src/karaoke_buddy/core/__init__.py
# src/karaoke_buddy/ui/__init__.py
# tests/__init__.py
```
Each file should be empty (0 bytes is fine).

- [ ] **Step 3: Create `src/karaoke_buddy/__main__.py` stub**

```python
"""KaraokeBuddy entry point."""
import sys


def main() -> None:
    from PySide6.QtWidgets import QApplication, QLabel

    app = QApplication(sys.argv)
    app.setApplicationName("KaraokeBuddy")
    app.setApplicationVersion("0.1.0")

    # Temporary placeholder until MainWindow is built in Task 9
    w = QLabel("KaraokeBuddy — coming soon")
    w.setMinimumSize(400, 200)
    w.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Create remaining stub files**

Create `tests/fixtures/.gitkeep` (empty) and `build/.gitkeep` (empty).

- [ ] **Step 5: Install dev dependencies**

```
pip install -e ".[dev]"
```

Expected output ends with: `Successfully installed karaoke-buddy-0.1.0 ...`

> **Note — libmpv-2.dll for development:**
> `python-mpv` needs `libmpv-2.dll` to import. For development:
> 1. Download a Windows libmpv build from https://github.com/zhongfly/mpv-winbuild/releases (look for `mpv-dev-x86_64-*.7z`)
> 2. Extract `libmpv-2.dll` and place it in the project root **or** `C:\Windows\System32`.
> Without this, `import mpv` will raise `OSError`.
>
> **FFmpeg for development:**
> Download a Windows static build from https://www.gyan.dev/ffmpeg/builds/ (`ffmpeg-release-essentials.zip`).
> Add the `bin/` folder to your system PATH.

- [ ] **Step 6: Verify the app stub launches**

```
python -m karaoke_buddy
```

Expected: A small window appears with the text "KaraokeBuddy — coming soon".

- [ ] **Step 7: Run an empty test suite**

```
pytest -v
```

Expected: `no tests ran` (exit 0).

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml src/ tests/ build/
git commit -m "chore: scaffold karaoke-buddy project structure"
```

---

## Task 2: Filter chain + property tests

**Files:**
- Create: `src/karaoke_buddy/core/filter_chain.py`
- Create: `tests/test_filter_chain.py`

This is the highest-priority module. A math error here is inaudible during development but corrupts every exported file and live preview.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_filter_chain.py
"""Property tests for the audio filter chain builder."""
import re

import pytest
from hypothesis import given
from hypothesis.strategies import integers

from karaoke_buddy.core.filter_chain import build_filter_chain


@given(pitch=integers(min_value=-12, max_value=12), vocal=integers(min_value=0, max_value=100))
def test_returns_string(pitch, vocal):
    assert isinstance(build_filter_chain(pitch, vocal), str)


@given(pitch=integers(min_value=-12, max_value=12), vocal=integers(min_value=0, max_value=100))
def test_contains_rubberband_and_pan(pitch, vocal):
    chain = build_filter_chain(pitch, vocal)
    assert "rubberband=pitch=" in chain
    assert "pan=stereo" in chain


@given(pitch=integers(min_value=-12, max_value=12), vocal=integers(min_value=0, max_value=100))
def test_deterministic(pitch, vocal):
    assert build_filter_chain(pitch, vocal) == build_filter_chain(pitch, vocal)


def test_zero_pitch_unity_scale():
    assert "rubberband=pitch=1.000000" in build_filter_chain(0, 0)


def test_negative_octave_halves_frequency():
    expected = 2 ** (-12 / 12)  # 0.5
    assert f"rubberband=pitch={expected:.6f}" in build_filter_chain(-12, 0)


def test_positive_octave_doubles_frequency():
    expected = 2 ** (12 / 12)  # 2.0
    assert f"rubberband=pitch={expected:.6f}" in build_filter_chain(12, 0)


@given(a=integers(min_value=-12, max_value=11), b=integers(min_value=-11, max_value=12))
def test_pitch_scale_monotonically_increases(a, b):
    if a >= b:
        return
    def _scale(s: int) -> float:
        m = re.search(r"rubberband=pitch=([0-9.]+)", build_filter_chain(s, 0))
        assert m
        return float(m.group(1))
    assert _scale(a) < _scale(b)


def test_zero_vocal_zero_mix():
    assert "pan=stereo|c0=c0-0.0000*c1|c1=c1-0.0000*c0" in build_filter_chain(0, 0)


def test_full_vocal_half_mix():
    assert "pan=stereo|c0=c0-0.5000*c1|c1=c1-0.5000*c0" in build_filter_chain(0, 100)


@given(a=integers(min_value=0, max_value=99), b=integers(min_value=1, max_value=100))
def test_vocal_mix_monotonically_increases(a, b):
    if a >= b:
        return
    def _mix(v: int) -> float:
        m = re.search(r"c0=c0-([0-9.]+)\*c1", build_filter_chain(0, v))
        assert m
        return float(m.group(1))
    assert _mix(a) <= _mix(b)
```

- [ ] **Step 2: Run tests — verify they FAIL**

```
pytest tests/test_filter_chain.py -v
```

Expected: `ImportError: cannot import name 'build_filter_chain'`

- [ ] **Step 3: Implement `filter_chain.py`**

```python
# src/karaoke_buddy/core/filter_chain.py
"""Shared audio filter chain builder.

Both Player (live preview) and Exporter (bake to file) call this function,
so the audio transform is defined in exactly one place.
"""


def build_filter_chain(pitch_semitones: int, vocal_reduce_percent: int) -> str:
    """Return an FFmpeg/libmpv audio filter chain string.

    Args:
        pitch_semitones: Pitch shift in whole semitones, -12 to +12.
        vocal_reduce_percent: Vocal reduction 0–100 via centre-channel subtraction.

    Returns:
        String suitable for ``ffmpeg -af`` or mpv ``af set``.
    """
    pitch_scale = 2 ** (pitch_semitones / 12)
    mix = (vocal_reduce_percent / 100) * 0.5
    return (
        f"rubberband=pitch={pitch_scale:.6f},"
        f"pan=stereo|c0=c0-{mix:.4f}*c1|c1=c1-{mix:.4f}*c0"
    )
```

- [ ] **Step 4: Run tests — verify they PASS**

```
pytest tests/test_filter_chain.py -v
```

Expected: All tests pass. Hypothesis runs 100 examples per property test.

- [ ] **Step 5: Commit**

```bash
git add src/karaoke_buddy/core/filter_chain.py tests/test_filter_chain.py
git commit -m "feat: add filter chain builder with property tests"
```

---

## Task 3: Library persistence

**Files:**
- Create: `src/karaoke_buddy/core/library.py`
- Create: `tests/test_library.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_library.py
"""Tests for Library persistence: round-trip, corruption recovery, atomic write."""
import json
from pathlib import Path

import pytest

from karaoke_buddy.core.library import Library, LibraryEntry, SavedOutput


def _entry(id: str = "abc-123", title: str = "Test Song") -> LibraryEntry:
    return LibraryEntry(
        id=id,
        title=title,
        source_type="local",
        source="/path/to/video.mp4",
        cached_path="/path/to/video.mp4",
        thumbnail_path="/path/to/thumb.jpg",
        duration_seconds=180,
        last_pitch=-3,
        last_vocal_reduce=40,
        last_opened="2026-04-15T20:11:00Z",
        saved_outputs=[],
    )


def test_empty_on_new_file(tmp_path):
    lib = Library(tmp_path / "library.json")
    assert lib.list() == []


def test_upsert_roundtrip(tmp_path):
    path = tmp_path / "library.json"
    Library(path).upsert(_entry())

    lib2 = Library(path)
    assert len(lib2.list()) == 1
    e = lib2.list()[0]
    assert e.title == "Test Song"
    assert e.last_pitch == -3
    assert e.last_vocal_reduce == 40


def test_upsert_updates_existing(tmp_path):
    path = tmp_path / "library.json"
    lib = Library(path)
    lib.upsert(_entry())
    updated = _entry()
    updated.last_pitch = 5
    lib.upsert(updated)
    assert len(lib.list()) == 1
    assert lib.list()[0].last_pitch == 5


def test_remove(tmp_path):
    path = tmp_path / "library.json"
    lib = Library(path)
    lib.upsert(_entry(id="keep", title="Keep"))
    lib.upsert(_entry(id="gone", title="Gone"))
    lib.remove("gone")
    ids = [e.id for e in lib.list()]
    assert "gone" not in ids
    assert "keep" in ids


def test_corruption_recovery(tmp_path):
    path = tmp_path / "library.json"
    path.write_text("{invalid{{", encoding="utf-8")
    lib = Library(path)
    assert lib.list() == []
    assert len(list(tmp_path.glob("library.json.corrupted-*"))) == 1


def test_atomic_write_no_tmp_files(tmp_path):
    path = tmp_path / "library.json"
    Library(path).upsert(_entry())
    assert list(tmp_path.glob("*.tmp")) == []


def test_saved_outputs_roundtrip(tmp_path):
    path = tmp_path / "library.json"
    lib = Library(path)
    e = _entry()
    e.saved_outputs = [SavedOutput(path="/out.mp4", pitch=-3, vocal_reduce=40, saved_at="2026-04-15T20:15:00Z")]
    lib.upsert(e)
    saved = Library(path).list()[0].saved_outputs
    assert len(saved) == 1
    assert saved[0].path == "/out.mp4"
    assert saved[0].pitch == -3


def test_get_by_source(tmp_path):
    path = tmp_path / "library.json"
    lib = Library(path)
    lib.upsert(_entry())
    assert lib.get_by_source("/path/to/video.mp4") is not None
    assert lib.get_by_source("/other.mp4") is None


def test_json_valid_after_upsert(tmp_path):
    path = tmp_path / "library.json"
    Library(path).upsert(_entry())
    data = json.loads(path.read_text())
    assert isinstance(data, list)
    assert data[0]["id"] == "abc-123"
```

- [ ] **Step 2: Run tests — verify FAIL**

```
pytest tests/test_library.py -v
```

Expected: `ImportError: cannot import name 'Library'`

- [ ] **Step 3: Implement `library.py`**

```python
# src/karaoke_buddy/core/library.py
"""Library persistence. Read once at startup, written atomically on every mutation."""
import json
import os
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class SavedOutput:
    path: str
    pitch: int
    vocal_reduce: int
    saved_at: str


@dataclass
class LibraryEntry:
    id: str
    title: str
    source_type: str        # "youtube" | "local"
    source: str             # original URL or absolute path
    cached_path: str
    thumbnail_path: str
    duration_seconds: int
    last_pitch: int
    last_vocal_reduce: int
    last_opened: str
    saved_outputs: list[SavedOutput] = field(default_factory=list)

    @staticmethod
    def new(
        title: str,
        source_type: str,
        source: str,
        cached_path: str,
        thumbnail_path: str,
        duration_seconds: int,
    ) -> "LibraryEntry":
        return LibraryEntry(
            id=str(uuid.uuid4()),
            title=title,
            source_type=source_type,
            source=source,
            cached_path=cached_path,
            thumbnail_path=thumbnail_path,
            duration_seconds=duration_seconds,
            last_pitch=0,
            last_vocal_reduce=0,
            last_opened=_now_iso(),
            saved_outputs=[],
        )


class Library:
    """In-memory store backed by an atomic JSON file."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._entries: list[LibraryEntry] = []
        self._load()

    def list(self) -> list[LibraryEntry]:
        return list(self._entries)

    def get(self, entry_id: str) -> Optional[LibraryEntry]:
        return next((e for e in self._entries if e.id == entry_id), None)

    def get_by_source(self, source: str) -> Optional[LibraryEntry]:
        return next((e for e in self._entries if e.source == source), None)

    def upsert(self, entry: LibraryEntry) -> None:
        idx = next((i for i, e in enumerate(self._entries) if e.id == entry.id), None)
        if idx is not None:
            self._entries[idx] = entry
        else:
            self._entries.insert(0, entry)
        self._save()

    def remove(self, entry_id: str) -> None:
        self._entries = [e for e in self._entries if e.id != entry_id]
        self._save()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            data: list[dict] = json.loads(self._path.read_text(encoding="utf-8"))
            self._entries = [
                LibraryEntry(
                    **{k: v for k, v in row.items() if k != "saved_outputs"},
                    saved_outputs=[SavedOutput(**s) for s in row.get("saved_outputs", [])],
                )
                for row in data
            ]
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
            self._path.rename(self._path.with_name(f"library.json.corrupted-{ts}"))
            self._entries = []

    def _save(self) -> None:
        content = json.dumps([asdict(e) for e in self._entries], indent=2, ensure_ascii=False)
        tmp = self._path.with_suffix(".json.tmp")
        tmp.write_text(content, encoding="utf-8")
        os.replace(tmp, self._path)
```

- [ ] **Step 4: Run tests — verify PASS**

```
pytest tests/test_library.py -v
```

Expected: All 9 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/karaoke_buddy/core/library.py tests/test_library.py
git commit -m "feat: add library persistence with atomic write and corruption recovery"
```

---

## Task 4: Source resolver

**Files:**
- Create: `src/karaoke_buddy/core/source_resolver.py`
- Create: `tests/test_source_resolver.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_source_resolver.py
"""Unit tests for SourceResolver. yt-dlp and subprocess are mocked throughout."""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from karaoke_buddy.core.source_resolver import SourceResolver, SourceResolverError


def test_is_youtube_url_standard():
    assert SourceResolver.is_youtube_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")


def test_is_youtube_url_short():
    assert SourceResolver.is_youtube_url("https://youtu.be/dQw4w9WgXcQ")


def test_is_youtube_url_rejects_non_youtube():
    assert not SourceResolver.is_youtube_url("https://vimeo.com/123456")
    assert not SourceResolver.is_youtube_url("not a url at all")


def test_extract_video_id_standard(tmp_path):
    r = SourceResolver(tmp_path / "cache")
    assert r._extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"


def test_extract_video_id_short(tmp_path):
    r = SourceResolver(tmp_path / "cache")
    assert r._extract_video_id("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"


def test_resolve_local_missing_file(tmp_path):
    r = SourceResolver(tmp_path / "cache")
    with pytest.raises(SourceResolverError, match="File not found"):
        r.resolve_local(tmp_path / "ghost.mp4")


@patch("karaoke_buddy.core.source_resolver.subprocess.run")
def test_probe_duration_parses_correctly(mock_run, tmp_path):
    mock_run.return_value = MagicMock(returncode=0, stdout='{"format": {"duration": "342.7"}}')
    r = SourceResolver(tmp_path / "cache")
    assert r._probe_duration(tmp_path / "fake.mp4") == 342


@patch("karaoke_buddy.core.source_resolver.subprocess.run")
def test_probe_duration_raises_on_ffprobe_error(mock_run, tmp_path):
    mock_run.return_value = MagicMock(returncode=1, stdout="")
    r = SourceResolver(tmp_path / "cache")
    with pytest.raises(SourceResolverError, match="isn't supported"):
        r._probe_duration(tmp_path / "bad.mp4")


def test_resolve_url_cache_hit(tmp_path):
    cache = tmp_path / "cache"
    vid_dir = cache / "dQw4w9WgXcQ"
    vid_dir.mkdir(parents=True)
    (vid_dir / "video.mp4").write_bytes(b"fake")
    (vid_dir / "title.txt").write_text("Never Gonna Give You Up", encoding="utf-8")

    r = SourceResolver(cache)
    with (
        patch.object(r, "_probe_duration", return_value=213),
        patch.object(r, "_extract_thumbnail", return_value=vid_dir / "thumb.jpg"),
    ):
        meta = r.resolve_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

    assert meta.title == "Never Gonna Give You Up"
    assert meta.source_type == "youtube"
    assert meta.duration_seconds == 213


def test_resolve_url_download(tmp_path):
    cache = tmp_path / "cache"
    vid_dir = cache / "dQw4w9WgXcQ"

    def fake_extract_info(url, download):
        vid_dir.mkdir(parents=True, exist_ok=True)
        (vid_dir / "video.mp4").write_bytes(b"fake")
        return {"title": "Rick Roll", "duration": 213}

    mock_ydl = MagicMock()
    mock_ydl.__enter__ = lambda s: mock_ydl
    mock_ydl.__exit__ = MagicMock(return_value=False)
    mock_ydl.extract_info = fake_extract_info

    r = SourceResolver(cache)
    with (
        patch("karaoke_buddy.core.source_resolver.yt_dlp.YoutubeDL", return_value=mock_ydl),
        patch.object(r, "_extract_thumbnail", return_value=vid_dir / "thumb.jpg"),
    ):
        meta = r.resolve_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

    assert meta.title == "Rick Roll"
    assert meta.duration_seconds == 213
    assert (vid_dir / "title.txt").read_text() == "Rick Roll"
```

- [ ] **Step 2: Run tests — verify FAIL**

```
pytest tests/test_source_resolver.py -v
```

Expected: `ImportError: cannot import name 'SourceResolver'`

- [ ] **Step 3: Implement `source_resolver.py`**

```python
# src/karaoke_buddy/core/source_resolver.py
"""Source resolver: local path or YouTube URL → local video file + metadata."""
from __future__ import annotations

import json
import re
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import yt_dlp
from PySide6.QtCore import QThread, Signal


@dataclass
class VideoMeta:
    local_path: Path
    title: str
    duration_seconds: int
    thumbnail_path: Path
    source_type: str    # "local" | "youtube"
    source: str         # original path or URL


class SourceResolverError(Exception):
    """User-facing resolution error."""


class SourceResolver:
    def __init__(self, cache_dir: Path, ffmpeg_path: str = "ffmpeg") -> None:
        self._cache = cache_dir
        self._cache.mkdir(parents=True, exist_ok=True)
        self._ffmpeg = ffmpeg_path

    def resolve_local(self, path: Path, progress_cb: Optional[Callable[[int], None]] = None) -> VideoMeta:
        if not path.exists():
            raise SourceResolverError(f"File not found: {path}")
        duration = self._probe_duration(path)
        thumb = self._extract_thumbnail(path, path.parent / f"{path.stem}_thumb.jpg")
        return VideoMeta(
            local_path=path,
            title=path.stem,
            duration_seconds=duration,
            thumbnail_path=thumb,
            source_type="local",
            source=str(path),
        )

    def resolve_url(self, url: str, progress_cb: Optional[Callable[[int], None]] = None) -> VideoMeta:
        video_id = self._extract_video_id(url)
        vid_dir = self._cache / video_id
        vid_dir.mkdir(parents=True, exist_ok=True)
        video_path = vid_dir / "video.mp4"
        title_path = vid_dir / "title.txt"
        thumb_path = vid_dir / "thumb.jpg"

        if video_path.exists():
            title = title_path.read_text(encoding="utf-8") if title_path.exists() else video_id
            duration = self._probe_duration(video_path)
            return VideoMeta(
                local_path=video_path,
                title=title,
                duration_seconds=duration,
                thumbnail_path=thumb_path,
                source_type="youtube",
                source=url,
            )

        ydl_opts = {
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "outtmpl": str(video_path),
            "quiet": True,
            "no_warnings": True,
            "progress_hooks": [self._make_hook(progress_cb)],
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
            title = info.get("title", video_id)
            duration = int(info.get("duration") or 0)
        except Exception as exc:
            raise SourceResolverError("Couldn't download — check your internet.") from exc

        if not video_path.exists():
            raise SourceResolverError("Couldn't download — check your internet.")

        title_path.write_text(title, encoding="utf-8")
        thumb = self._extract_thumbnail(video_path, thumb_path)
        return VideoMeta(
            local_path=video_path,
            title=title,
            duration_seconds=duration,
            thumbnail_path=thumb,
            source_type="youtube",
            source=url,
        )

    def fetch_title(self, url: str) -> Optional[str]:
        """Fetch video title without downloading (for clipboard preview)."""
        try:
            with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
                info = ydl.extract_info(url, download=False)
            return info.get("title")
        except Exception:
            return None

    @staticmethod
    def is_youtube_url(text: str) -> bool:
        return bool(re.search(
            r"(?:https?://)?(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)[\w-]{11}",
            text,
        ))

    def _extract_video_id(self, url: str) -> str:
        m = re.search(r"(?:v=|youtu\.be/)([\w-]{11})", url)
        return m.group(1) if m else uuid.uuid5(uuid.NAMESPACE_URL, url).hex

    def _probe_duration(self, path: Path) -> int:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(path)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise SourceResolverError("This video type isn't supported.")
        data = json.loads(result.stdout)
        return int(float(data["format"].get("duration", 0)))

    def _extract_thumbnail(self, video_path: Path, thumb_path: Path) -> Path:
        if thumb_path.exists():
            return thumb_path
        subprocess.run(
            [self._ffmpeg, "-y", "-i", str(video_path),
             "-ss", "00:00:05", "-vframes", "1", "-q:v", "2", str(thumb_path)],
            capture_output=True,
        )
        return thumb_path

    @staticmethod
    def _make_hook(cb: Optional[Callable[[int], None]]):
        def hook(d: dict) -> None:
            if d["status"] == "downloading" and cb is not None:
                total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
                downloaded = d.get("downloaded_bytes", 0)
                if total > 0:
                    cb(int(downloaded / total * 100))
        return hook


class DownloadThread(QThread):
    """Downloads a YouTube URL on a background thread."""

    progress = Signal(int)       # 0–100
    finished = Signal(object)    # VideoMeta
    error = Signal(str)          # user-friendly message

    def __init__(self, url: str, resolver: SourceResolver) -> None:
        super().__init__()
        self._url = url
        self._resolver = resolver

    def run(self) -> None:
        try:
            meta = self._resolver.resolve_url(self._url, self.progress.emit)
            self.finished.emit(meta)
        except SourceResolverError as exc:
            self.error.emit(str(exc))
        except Exception:
            self.error.emit("Couldn't download — check your internet.")
```

- [ ] **Step 4: Run tests — verify PASS**

```
pytest tests/test_source_resolver.py -v
```

Expected: All 9 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/karaoke_buddy/core/source_resolver.py tests/test_source_resolver.py
git commit -m "feat: add source resolver with yt-dlp download and cache"
```

---

## Task 5: Player wrapper (libmpv + Qt)

**Files:**
- Create: `src/karaoke_buddy/core/player.py`

No automated tests: libmpv requires a real GPU/display and a valid HWND. This module is covered by the manual smoke test checklist in the spec (§9.2).

- [ ] **Step 1: Implement `player.py`**

```python
# src/karaoke_buddy/core/player.py
"""libmpv player embedded in a PySide6 widget."""
from __future__ import annotations

import mpv
from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QPaintEvent
from PySide6.QtWidgets import QWidget


class _Signals(QObject):
    state_changed = Signal(str)       # "playing" | "paused" | "idle" | "ended"
    position_changed = Signal(float)  # seconds
    duration_changed = Signal(float)  # seconds


class VideoWidget(QWidget):
    """Qt surface that embeds an mpv render context.

    Call ``initialize_player()`` once after the widget has been shown
    (needs a valid native HWND). Then control via ``load()``, ``set_filter()``,
    ``play_pause()``, ``seek()``.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_NativeWindow)
        self.setAttribute(Qt.WidgetAttribute.WA_PaintOnScreen)
        self.setMinimumSize(400, 225)
        self.signals = _Signals()
        self._player: mpv.MPV | None = None

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        # mpv renders directly into the HWND; suppress Qt's default fill.
        pass

    def initialize_player(self) -> None:
        """Bind mpv to this widget's HWND. Call after first show(). Safe to call multiple times."""
        if self._player is not None:
            return

        self._player = mpv.MPV(
            wid=str(int(self.winId())),
            vo="gpu",
            hwdec="auto-safe",
            keep_open="yes",
            log_handler=lambda level, component, message: None,
        )

        @self._player.property_observer("pause")
        def _on_pause(name: str, value: bool | None) -> None:
            if value is not None:
                self.signals.state_changed.emit("paused" if value else "playing")

        @self._player.property_observer("time-pos")
        def _on_time(name: str, value: float | None) -> None:
            if value is not None:
                self.signals.position_changed.emit(float(value))

        @self._player.property_observer("duration")
        def _on_duration(name: str, value: float | None) -> None:
            if value is not None:
                self.signals.duration_changed.emit(float(value))

        @self._player.event_callback("end-file")
        def _on_end(event: dict) -> None:
            self.signals.state_changed.emit("ended")

    def load(self, path: str) -> None:
        if self._player:
            self._player.loadfile(path)

    def set_filter(self, chain: str) -> None:
        """Apply audio filter chain mid-playback — audible within ~one frame, no stutter."""
        if self._player:
            self._player.command("af", "set", chain)

    def play_pause(self) -> None:
        if self._player:
            self._player.command("cycle", "pause")

    def seek(self, seconds: float) -> None:
        if self._player:
            self._player.command("seek", str(seconds), "absolute+exact")

    def stop(self) -> None:
        if self._player:
            self._player.command("stop")

    def cleanup(self) -> None:
        """Terminate mpv. Must be called before the window closes."""
        if self._player:
            self._player.terminate()
            self._player = None
```

- [ ] **Step 2: Verify import succeeds**

```
python -c "from karaoke_buddy.core.player import VideoWidget; print('OK')"
```

Expected: `OK` (requires `libmpv-2.dll` to be present — see Task 1 setup note).

- [ ] **Step 3: Commit**

```bash
git add src/karaoke_buddy/core/player.py
git commit -m "feat: add libmpv VideoWidget with live filter support"
```

---

## Task 6: Exporter + integration test

**Files:**
- Create: `src/karaoke_buddy/core/exporter.py`
- Create: `tests/test_exporter.py`
- Obtain: `tests/fixtures/sample_10s.mp4`

- [ ] **Step 1: Generate the test fixture**

Run once in the project root (requires FFmpeg in PATH):

```
ffmpeg -f lavfi -i "sine=frequency=440:duration=10" -f lavfi -i "color=c=blue:size=640x360:duration=10" -shortest tests/fixtures/sample_10s.mp4
```

Expected: `tests/fixtures/sample_10s.mp4` created (~150 KB).

- [ ] **Step 2: Write failing integration tests**

```python
# tests/test_exporter.py
"""Integration tests for ExportThread. Skip automatically if FFmpeg or fixture is absent."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from PySide6.QtCore import QEventLoop, Qt
from PySide6.QtWidgets import QApplication

from karaoke_buddy.core.exporter import ExportThread
from karaoke_buddy.core.filter_chain import build_filter_chain

FIXTURE = Path(__file__).parent / "fixtures" / "sample_10s.mp4"
FFMPEG = os.environ.get("FFMPEG_PATH", "ffmpeg")

needs_fixture = pytest.mark.skipif(not FIXTURE.exists(), reason="fixture sample_10s.mp4 not present")
needs_ffmpeg = pytest.mark.skipif(not shutil.which(FFMPEG), reason="FFmpeg not in PATH")


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication(sys.argv)


def _run(thread: ExportThread) -> tuple[list[str], list[str], list[int]]:
    """Drive an ExportThread to completion via a QEventLoop."""
    loop = QEventLoop()
    paths: list[str] = []
    errors: list[str] = []
    progress: list[int] = []
    thread.finished.connect(lambda p: (paths.append(p), loop.quit()), Qt.ConnectionType.QueuedConnection)
    thread.error.connect(lambda e: (errors.append(e), loop.quit()), Qt.ConnectionType.QueuedConnection)
    thread.progress.connect(lambda v: progress.append(v), Qt.ConnectionType.QueuedConnection)
    thread.start()
    loop.exec()
    return paths, errors, progress


@needs_fixture
@needs_ffmpeg
def test_export_creates_valid_mp4(app, tmp_path):
    output = tmp_path / "out.mp4"
    paths, errors, progress = _run(ExportThread(FIXTURE, output, build_filter_chain(0, 0), 10, FFMPEG))
    assert not errors, f"Export failed: {errors}"
    assert output.exists()
    assert output.stat().st_size > 0
    assert paths == [str(output)]
    assert 100 in progress


@needs_fixture
@needs_ffmpeg
def test_export_duration_matches_input(app, tmp_path):
    output = tmp_path / "out.mp4"
    paths, errors, _ = _run(ExportThread(FIXTURE, output, build_filter_chain(-3, 0), 10, FFMPEG))
    assert not errors
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(output)],
        capture_output=True, text=True,
    )
    duration = float(json.loads(result.stdout)["format"]["duration"])
    assert abs(duration - 10.0) < 1.5, f"Expected ~10s, got {duration:.2f}s"


@needs_fixture
@needs_ffmpeg
def test_export_no_tmp_file_left(app, tmp_path):
    output = tmp_path / "out.mp4"
    _run(ExportThread(FIXTURE, output, build_filter_chain(0, 0), 10, FFMPEG))
    assert list(tmp_path.glob("*.tmp")) == []
```

- [ ] **Step 3: Run tests — verify FAIL**

```
pytest tests/test_exporter.py -v
```

Expected: `ImportError: cannot import name 'ExportThread'`

- [ ] **Step 4: Implement `exporter.py`**

```python
# src/karaoke_buddy/core/exporter.py
"""FFmpeg-based exporter running on a QThread."""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QThread, Signal


class ExportThread(QThread):
    """Runs FFmpeg in a subprocess; emits progress (0–100), finished, and error.

    Tries ``-c:v copy`` first (fast, stream-copy). Falls back to
    ``-c:v libx264`` if the source codec can't be muxed into MP4.
    The output is written to a ``.tmp`` file and atomically renamed on success.
    """

    progress = Signal(int)   # 0–100
    finished = Signal(str)   # absolute output path on success
    error = Signal(str)      # user-friendly message on failure

    def __init__(
        self,
        input_path: Path,
        output_path: Path,
        filter_chain: str,
        duration_seconds: int,
        ffmpeg_path: str = "ffmpeg",
    ) -> None:
        super().__init__()
        self._input = input_path
        self._output = output_path
        self._filter = filter_chain
        self._duration = max(duration_seconds, 1)
        self._ffmpeg = ffmpeg_path
        self._cancelled = False
        self._proc: Optional[subprocess.Popen] = None

    def run(self) -> None:
        tmp = self._output.with_suffix(".mp4.tmp")
        try:
            ok = self._run_ffmpeg(tmp, copy_video=True)
            if not ok and not self._cancelled:
                ok = self._run_ffmpeg(tmp, copy_video=False)
            if ok and not self._cancelled:
                os.replace(tmp, self._output)
                self.finished.emit(str(self._output))
            elif not self._cancelled:
                self.error.emit("Couldn't save here — try a different folder.")
        except Exception:
            self.error.emit("Couldn't save here — try a different folder.")
        finally:
            if tmp.exists():
                tmp.unlink(missing_ok=True)

    def cancel(self) -> None:
        self._cancelled = True
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()

    def _run_ffmpeg(self, tmp: Path, copy_video: bool) -> bool:
        v_codec = (
            ["-c:v", "copy"]
            if copy_video
            else ["-c:v", "libx264", "-crf", "23", "-preset", "veryfast"]
        )
        cmd = [
            self._ffmpeg, "-y",
            "-i", str(self._input),
            "-af", self._filter,
            *v_codec,
            "-c:a", "aac", "-b:a", "192k",
            "-loglevel", "quiet",
            "-progress", "pipe:2",
            str(tmp),
        ]
        self._proc = subprocess.Popen(
            cmd, stderr=subprocess.PIPE, stdout=subprocess.DEVNULL,
            text=True, encoding="utf-8", errors="replace",
        )
        for line in self._proc.stderr:  # type: ignore[union-attr]
            if self._cancelled:
                self._proc.terminate()
                return False
            m = re.match(r"out_time_ms=(\d+)", line.strip())
            if m:
                # Despite the name, out_time_ms is in microseconds
                elapsed_us = int(m.group(1))
                pct = min(99, int(elapsed_us / 1_000_000 / self._duration * 100))
                self.progress.emit(pct)
        self._proc.wait()
        if self._proc.returncode == 0:
            self.progress.emit(100)
            return True
        return False
```

- [ ] **Step 5: Run tests — verify PASS**

```
pytest tests/test_exporter.py -v
```

Expected: All 3 integration tests pass (or are skipped if FFmpeg not in PATH).

- [ ] **Step 6: Commit**

```bash
git add src/karaoke_buddy/core/exporter.py tests/test_exporter.py tests/fixtures/sample_10s.mp4
git commit -m "feat: add FFmpeg exporter with progress and atomic output"
```

---

## Task 7: Main window + home and library views

**Files:**
- Create: `src/karaoke_buddy/ui/main_window.py`
- Create: `src/karaoke_buddy/ui/home_view.py`
- Create: `src/karaoke_buddy/ui/library_view.py`

No automated tests. Covered by manual smoke tests.

- [ ] **Step 1: Implement `library_view.py`**

```python
# src/karaoke_buddy/ui/library_view.py
"""Thumbnail grid of library entries."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from karaoke_buddy.core.library import LibraryEntry


class _Card(QFrame):
    """Single library entry card: thumbnail + title + last-used settings."""

    clicked = Signal(str)  # entry_id

    def __init__(self, entry: LibraryEntry, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._entry_id = entry.id
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedWidth(160)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)

        # Thumbnail
        thumb = QLabel()
        thumb.setFixedSize(148, 83)
        thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thumb.setStyleSheet("background: #111;")
        pix = QPixmap(entry.thumbnail_path)
        if not pix.isNull():
            thumb.setPixmap(pix.scaled(148, 83, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        layout.addWidget(thumb)

        # Title
        title = QLabel(entry.title)
        title.setWordWrap(True)
        title.setMaximumWidth(148)
        title.setStyleSheet("font-weight: bold; font-size: 11px;")
        layout.addWidget(title)

        # Settings badge
        pitch_str = _format_pitch(entry.last_pitch)
        vocal_str = f"Vocals: {entry.last_vocal_reduce}%" if entry.last_vocal_reduce else ""
        badge_parts = [s for s in [pitch_str, vocal_str] if s]
        if badge_parts:
            badge = QLabel(" · ".join(badge_parts))
            badge.setStyleSheet("font-size: 10px; color: #888;")
            layout.addWidget(badge)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        self.clicked.emit(self._entry_id)


def _format_pitch(semitones: int) -> str:
    if semitones == 0:
        return ""
    direction = "Higher" if semitones > 0 else "Lower"
    n = abs(semitones)
    return f"{direction} by {n} {'key' if n == 1 else 'keys'}"


class LibraryGrid(QScrollArea):
    """Scrollable grid of library entry cards."""

    entry_clicked = Signal(str)  # entry_id

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self._container = QWidget()
        self._grid = QGridLayout(self._container)
        self._grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._grid.setSpacing(12)
        self.setWidget(self._container)

    def refresh(self, entries: list[LibraryEntry]) -> None:
        # Clear old cards
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        cols = max(1, self.width() // 180)
        for i, entry in enumerate(entries):
            card = _Card(entry)
            card.clicked.connect(self.entry_clicked)
            self._grid.addWidget(card, i // cols, i % cols)
```

- [ ] **Step 2: Implement `home_view.py`**

```python
# src/karaoke_buddy/ui/home_view.py
"""Home screen: open-file button, paste-URL button/dialog, library grid."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from karaoke_buddy.core.library import Library
from karaoke_buddy.core.source_resolver import DownloadThread, SourceResolver, VideoMeta
from karaoke_buddy.ui.library_view import LibraryGrid


class HomeView(QWidget):
    open_file_requested = Signal()
    open_url_requested = Signal(str)
    library_entry_requested = Signal(str)  # entry_id

    def __init__(self, library: Library, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._library = library
        self._download_thread: DownloadThread | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 32, 32, 32)
        root.setSpacing(24)

        # Title
        title = QLabel("KaraokeBuddy")
        title.setStyleSheet("font-size: 28px; font-weight: bold;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(title)

        # Primary action buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(16)

        self._btn_open = QPushButton("Open a video file")
        self._btn_open.setMinimumHeight(56)
        self._btn_open.setStyleSheet("font-size: 15px;")
        self._btn_open.clicked.connect(self.open_file_requested)
        btn_row.addWidget(self._btn_open)

        self._btn_paste = QPushButton("Paste YouTube link")
        self._btn_paste.setMinimumHeight(56)
        self._btn_paste.setStyleSheet("font-size: 15px;")
        self._btn_paste.clicked.connect(self._show_url_dialog)
        btn_row.addWidget(self._btn_paste)

        root.addLayout(btn_row)

        # Clipboard preview label (shown when clipboard has a YouTube URL)
        self._clipboard_label = QLabel()
        self._clipboard_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._clipboard_label.setStyleSheet("color: #888; font-size: 12px;")
        self._clipboard_label.hide()
        root.addWidget(self._clipboard_label)

        # Download progress (shown during active download)
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.hide()
        self._progress_label = QLabel("Downloading…")
        self._progress_label.hide()
        root.addWidget(self._progress_label)
        root.addWidget(self._progress_bar)

        # Library grid
        lib_header = QLabel("Recent videos")
        lib_header.setStyleSheet("font-size: 14px; font-weight: bold;")
        root.addWidget(lib_header)

        self._grid = LibraryGrid()
        self._grid.entry_clicked.connect(self.library_entry_requested)
        root.addWidget(self._grid, stretch=1)

        self.refresh()

    def refresh(self) -> None:
        self._grid.refresh(self._library.list())
        self._check_clipboard()

    def _check_clipboard(self) -> None:
        from PySide6.QtWidgets import QApplication
        from karaoke_buddy.core.source_resolver import SourceResolver
        text = QApplication.clipboard().text().strip()
        if SourceResolver.is_youtube_url(text):
            self._clipboard_label.setText(f"🎵 Clipboard: {text[:60]}…" if len(text) > 60 else f"🎵 Clipboard: {text}")
            self._clipboard_label.show()
        else:
            self._clipboard_label.hide()

    def _show_url_dialog(self) -> None:
        from PySide6.QtWidgets import QApplication
        clipboard_text = QApplication.clipboard().text().strip()
        from karaoke_buddy.core.source_resolver import SourceResolver
        prefill = clipboard_text if SourceResolver.is_youtube_url(clipboard_text) else ""

        dlg = QDialog(self)
        dlg.setWindowTitle("Paste YouTube link")
        dlg.setMinimumWidth(400)
        layout = QVBoxLayout(dlg)
        layout.addWidget(QLabel("YouTube URL:"))
        edit = QLineEdit(prefill)
        layout.addWidget(edit)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        layout.addWidget(btns)

        if dlg.exec() == QDialog.DialogCode.Accepted:
            url = edit.text().strip()
            if url:
                self.open_url_requested.emit(url)

    def show_download_progress(self, url: str) -> None:
        self._progress_label.setText(f"Downloading: {url[:50]}…" if len(url) > 50 else f"Downloading: {url}")
        self._progress_label.show()
        self._progress_bar.setValue(0)
        self._progress_bar.show()
        self._btn_open.setEnabled(False)
        self._btn_paste.setEnabled(False)

    def hide_download_progress(self) -> None:
        self._progress_bar.hide()
        self._progress_label.hide()
        self._btn_open.setEnabled(True)
        self._btn_paste.setEnabled(True)

    def start_download(
        self,
        url: str,
        resolver: SourceResolver,
        on_success,
        on_error,
    ) -> None:
        self._download_thread = DownloadThread(url, resolver)
        self._download_thread.progress.connect(self._progress_bar.setValue)
        self._download_thread.finished.connect(lambda meta: (self.hide_download_progress(), on_success(meta)))
        self._download_thread.error.connect(lambda msg: (self.hide_download_progress(), on_error(msg)))
        self._download_thread.start()
```

- [ ] **Step 3: Implement `main_window.py`**

```python
# src/karaoke_buddy/ui/main_window.py
"""Top-level window. Routes between HomeView and PlayingView."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QFileDialog, QMainWindow, QMessageBox, QStackedWidget

from karaoke_buddy.core.library import Library, LibraryEntry
from karaoke_buddy.core.source_resolver import SourceResolver, SourceResolverError, VideoMeta
from karaoke_buddy.ui.home_view import HomeView


class MainWindow(QMainWindow):
    def __init__(self, library: Library, resolver: SourceResolver) -> None:
        super().__init__()
        self._library = library
        self._resolver = resolver
        self.setWindowTitle("KaraokeBuddy")
        self.setMinimumSize(700, 500)
        self.resize(1000, 650)

        self._stack = QStackedWidget()
        self.setCentralWidget(self._stack)

        self._home = HomeView(library)
        self._stack.addWidget(self._home)

        # PlayingView imported lazily to avoid circular import at module load
        self._playing = None

        self._home.open_file_requested.connect(self._open_file_dialog)
        self._home.open_url_requested.connect(self._start_url_load)
        self._home.library_entry_requested.connect(self._open_library_entry)

    def _get_playing(self):
        """Lazily create PlayingView on first use."""
        if self._playing is None:
            from karaoke_buddy.ui.playing_view import PlayingView
            self._playing = PlayingView(self._library)
            self._stack.addWidget(self._playing)
            self._playing.back_requested.connect(self._go_home)
        return self._playing

    def _go_home(self) -> None:
        self._get_playing().cleanup()
        self._home.refresh()
        self._stack.setCurrentWidget(self._home)

    def _show_playing(self, meta: VideoMeta, entry_id: str) -> None:
        playing = self._get_playing()
        playing.load(meta, entry_id)
        self._stack.setCurrentWidget(playing)
        QTimer.singleShot(0, playing.initialize_player)

    def _open_file_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open a video file", "",
            "Video files (*.mp4 *.mkv *.webm *.mov);;All files (*.*)",
        )
        if path:
            self._load_local(Path(path))

    def _load_local(self, path: Path) -> None:
        try:
            meta = self._resolver.resolve_local(path)
        except SourceResolverError as exc:
            QMessageBox.warning(self, "KaraokeBuddy", str(exc))
            return
        entry = self._library.get_by_source(str(path))
        if entry is None:
            entry = LibraryEntry.new(
                title=meta.title, source_type="local", source=str(path),
                cached_path=str(meta.local_path), thumbnail_path=str(meta.thumbnail_path),
                duration_seconds=meta.duration_seconds,
            )
            self._library.upsert(entry)
        self._show_playing(meta, entry.id)

    def _start_url_load(self, url: str) -> None:
        self._home.show_download_progress(url)
        self._home.start_download(url, self._resolver, self._on_url_loaded, self._on_url_error)

    def _on_url_loaded(self, meta: VideoMeta) -> None:
        entry = self._library.get_by_source(meta.source)
        if entry is None:
            entry = LibraryEntry.new(
                title=meta.title, source_type="youtube", source=meta.source,
                cached_path=str(meta.local_path), thumbnail_path=str(meta.thumbnail_path),
                duration_seconds=meta.duration_seconds,
            )
        else:
            entry.cached_path = str(meta.local_path)
            entry.thumbnail_path = str(meta.thumbnail_path)
        self._library.upsert(entry)
        self._show_playing(meta, entry.id)

    def _on_url_error(self, message: str) -> None:
        QMessageBox.warning(self, "KaraokeBuddy", message)

    def _open_library_entry(self, entry_id: str) -> None:
        entry = self._library.get(entry_id)
        if entry is None:
            return
        cached = Path(entry.cached_path)
        if not cached.exists():
            if entry.source_type == "youtube":
                self._start_url_load(entry.source)
            else:
                QMessageBox.warning(self, "KaraokeBuddy", "This file seems to have moved.")
                self._library.remove(entry_id)
                self._home.refresh()
            return
        if entry.source_type == "local":
            try:
                meta = self._resolver.resolve_local(cached)
            except SourceResolverError as exc:
                QMessageBox.warning(self, "KaraokeBuddy", str(exc))
                return
        else:
            meta = VideoMeta(
                local_path=cached, title=entry.title, duration_seconds=entry.duration_seconds,
                thumbnail_path=Path(entry.thumbnail_path), source_type=entry.source_type, source=entry.source,
            )
        self._show_playing(meta, entry.id)

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._playing:
            self._playing.cleanup()
        super().closeEvent(event)
```

- [ ] **Step 4: Verify the app shows the home view**

```
python -m karaoke_buddy
```

Expected: A window with "KaraokeBuddy" heading, two large buttons, and an empty library grid. No errors in the terminal.

- [ ] **Step 5: Commit**

```bash
git add src/karaoke_buddy/ui/
git commit -m "feat: add home view with library grid and URL paste dialog"
```

---

## Task 8: Playing view

**Files:**
- Create: `src/karaoke_buddy/ui/playing_view.py`

- [ ] **Step 1: Implement `playing_view.py`**

```python
# src/karaoke_buddy/ui/playing_view.py
"""Playing state: video surface + pitch/vocal sliders + save button."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from karaoke_buddy.core.exporter import ExportThread
from karaoke_buddy.core.filter_chain import build_filter_chain
from karaoke_buddy.core.library import Library, SavedOutput
from karaoke_buddy.core.player import VideoWidget
from karaoke_buddy.core.source_resolver import VideoMeta


def _format_pitch(semitones: int) -> str:
    if semitones == 0:
        return "Normal key"
    direction = "Higher" if semitones > 0 else "Lower"
    n = abs(semitones)
    return f"{direction} by {n} {'key' if n == 1 else 'keys'}"


class PlayingView(QWidget):
    back_requested = Signal()

    def __init__(self, library: Library, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._library = library
        self._entry_id: str | None = None
        self._meta: VideoMeta | None = None
        self._export_thread: ExportThread | None = None
        self._save_debounce = QTimer()
        self._save_debounce.setSingleShot(True)
        self._save_debounce.setInterval(800)
        self._save_debounce.timeout.connect(self._persist_settings)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Video surface
        self._video = VideoWidget()
        self._video.setSizePolicy(
            self._video.sizePolicy().horizontalPolicy(),
            self._video.sizePolicy().verticalPolicy(),
        )
        root.addWidget(self._video, stretch=1)

        # Transport bar
        transport = QHBoxLayout()
        transport.setContentsMargins(12, 6, 12, 6)
        self._btn_play = QPushButton("⏸")
        self._btn_play.setFixedWidth(40)
        self._btn_play.clicked.connect(self._video.play_pause)
        transport.addWidget(self._btn_play)

        self._timeline = QSlider(Qt.Orientation.Horizontal)
        self._timeline.setRange(0, 1000)
        self._timeline.sliderPressed.connect(lambda: setattr(self, "_seeking", True))
        self._timeline.sliderReleased.connect(self._on_seek)
        transport.addWidget(self._timeline, stretch=1)

        self._time_label = QLabel("0:00 / 0:00")
        transport.addWidget(self._time_label)
        root.addLayout(transport)

        # Controls panel
        controls = QWidget()
        controls.setStyleSheet("background: #1a1a1a;")
        ctrl_layout = QVBoxLayout(controls)
        ctrl_layout.setContentsMargins(24, 16, 24, 16)
        ctrl_layout.setSpacing(12)

        # Song key slider
        key_row = QHBoxLayout()
        key_row.addWidget(QLabel("Song key"))
        key_row.addWidget(QLabel("Lower"), 0)
        self._pitch_slider = QSlider(Qt.Orientation.Horizontal)
        self._pitch_slider.setRange(-12, 12)
        self._pitch_slider.setValue(0)
        self._pitch_slider.setTickInterval(1)
        self._pitch_slider.setSingleStep(1)
        self._pitch_slider.setPageStep(1)
        self._pitch_slider.valueChanged.connect(self._on_pitch_changed)
        key_row.addWidget(self._pitch_slider, stretch=1)
        key_row.addWidget(QLabel("Higher"), 0)
        self._pitch_label = QLabel("Normal key")
        self._pitch_label.setMinimumWidth(120)
        key_row.addWidget(self._pitch_label)
        ctrl_layout.addLayout(key_row)

        # Vocal reduction slider
        vocal_row = QHBoxLayout()
        vocal_row.addWidget(QLabel("Silence the singer"))
        self._vocal_slider = QSlider(Qt.Orientation.Horizontal)
        self._vocal_slider.setRange(0, 100)
        self._vocal_slider.setValue(0)
        self._vocal_slider.setSingleStep(5)
        self._vocal_slider.valueChanged.connect(self._on_vocal_changed)
        vocal_row.addWidget(self._vocal_slider, stretch=1)
        self._vocal_label = QLabel("Off")
        self._vocal_label.setMinimumWidth(60)
        vocal_row.addWidget(self._vocal_label)
        ctrl_layout.addLayout(vocal_row)

        # Export row
        export_row = QHBoxLayout()
        self._btn_save = QPushButton("Save this version")
        self._btn_save.setMinimumHeight(40)
        self._btn_save.setStyleSheet("font-size: 13px;")
        self._btn_save.clicked.connect(self._on_save_clicked)
        export_row.addWidget(self._btn_save)

        self._export_progress = QProgressBar()
        self._export_progress.setRange(0, 100)
        self._export_progress.hide()
        export_row.addWidget(self._export_progress, stretch=1)

        btn_back = QPushButton("← Back to library")
        btn_back.setFlat(True)
        btn_back.setStyleSheet("color: #888; font-size: 12px;")
        btn_back.clicked.connect(self.back_requested)
        export_row.addWidget(btn_back)
        ctrl_layout.addLayout(export_row)

        root.addWidget(controls)

        # Connect player signals
        self._video.signals.state_changed.connect(self._on_state)
        self._video.signals.position_changed.connect(self._on_position)
        self._video.signals.duration_changed.connect(self._on_duration)
        self._duration_sec: float = 0.0
        self._seeking = False

    def initialize_player(self) -> None:
        self._video.initialize_player()

    def load(self, meta: VideoMeta, entry_id: str) -> None:
        self._meta = meta
        self._entry_id = entry_id

        # Restore per-song settings
        entry = self._library.get(entry_id)
        if entry:
            self._pitch_slider.blockSignals(True)
            self._vocal_slider.blockSignals(True)
            self._pitch_slider.setValue(entry.last_pitch)
            self._vocal_slider.setValue(entry.last_vocal_reduce)
            self._pitch_slider.blockSignals(False)
            self._vocal_slider.blockSignals(False)
            self._pitch_label.setText(_format_pitch(entry.last_pitch))
            self._vocal_label.setText(f"{entry.last_vocal_reduce}%" if entry.last_vocal_reduce else "Off")

        self._video.load(str(meta.local_path))
        self._apply_filter()

    def cleanup(self) -> None:
        self._video.stop()
        self._video.cleanup()

    # --- Slider handlers ---

    def _on_pitch_changed(self, value: int) -> None:
        self._pitch_label.setText(_format_pitch(value))
        self._apply_filter()
        self._save_debounce.start()

    def _on_vocal_changed(self, value: int) -> None:
        self._vocal_label.setText(f"{value}%" if value else "Off")
        self._apply_filter()
        self._save_debounce.start()

    def _apply_filter(self) -> None:
        chain = build_filter_chain(self._pitch_slider.value(), self._vocal_slider.value())
        self._video.set_filter(chain)

    def _persist_settings(self) -> None:
        if self._entry_id is None:
            return
        entry = self._library.get(self._entry_id)
        if entry is None:
            return
        entry.last_pitch = self._pitch_slider.value()
        entry.last_vocal_reduce = self._vocal_slider.value()
        self._library.upsert(entry)

    # --- Player signal handlers ---

    def _on_state(self, state: str) -> None:
        self._btn_play.setText("▶" if state in ("paused", "idle", "ended") else "⏸")

    def _on_position(self, pos: float) -> None:
        if not self._seeking and self._duration_sec > 0:
            self._timeline.blockSignals(True)
            self._timeline.setValue(int(pos / self._duration_sec * 1000))
            self._timeline.blockSignals(False)
        self._time_label.setText(f"{_fmt_time(pos)} / {_fmt_time(self._duration_sec)}")

    def _on_duration(self, dur: float) -> None:
        self._duration_sec = dur

    def _on_seek(self) -> None:
        self._seeking = False
        if self._duration_sec > 0:
            target = self._timeline.value() / 1000 * self._duration_sec
            self._video.seek(target)

    # --- Export ---

    def _on_save_clicked(self) -> None:
        if self._meta is None:
            return

        pitch = self._pitch_slider.value()
        vocal = self._vocal_slider.value()
        pitch_str = _format_pitch(pitch).lower().replace(" ", "-") if pitch != 0 else "normal-key"
        suggestion = f"{self._meta.title} ({pitch_str}, vocals-{vocal}pct).mp4"

        default_dir = Path(os.path.abspath("Pitched Songs"))
        default_dir.mkdir(exist_ok=True)

        out_path, _ = QFileDialog.getSaveFileName(
            self, "Save this version",
            str(default_dir / suggestion),
            "MP4 video (*.mp4)",
        )
        if not out_path:
            return

        chain = build_filter_chain(pitch, vocal)
        self._export_thread = ExportThread(
            self._meta.local_path, Path(out_path), chain, self._meta.duration_seconds
        )
        self._export_thread.progress.connect(self._on_export_progress)
        self._export_thread.finished.connect(self._on_export_done)
        self._export_thread.error.connect(self._on_export_error)
        self._btn_save.setEnabled(False)
        self._export_progress.setValue(0)
        self._export_progress.show()
        self._export_thread.start()

    def _on_export_progress(self, pct: int) -> None:
        self._export_progress.setValue(pct)

    def _on_export_done(self, path: str) -> None:
        self._export_progress.hide()
        self._btn_save.setEnabled(True)
        if self._entry_id:
            entry = self._library.get(self._entry_id)
            if entry:
                entry.saved_outputs.append(SavedOutput(
                    path=path,
                    pitch=self._pitch_slider.value(),
                    vocal_reduce=self._vocal_slider.value(),
                    saved_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                ))
                self._library.upsert(entry)
        QMessageBox.information(self, "KaraokeBuddy", f"Saved to:\n{path}")

    def _on_export_error(self, message: str) -> None:
        self._export_progress.hide()
        self._btn_save.setEnabled(True)
        QMessageBox.warning(self, "KaraokeBuddy", message)


def _fmt_time(seconds: float) -> str:
    s = int(seconds)
    return f"{s // 60}:{s % 60:02d}"
```

- [ ] **Step 2: Verify the import**

```
python -c "from karaoke_buddy.ui.playing_view import PlayingView; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/karaoke_buddy/ui/playing_view.py
git commit -m "feat: add playing view with pitch/vocal sliders, timeline, and export"
```

---

## Task 9: Startup checks, logging, and full wiring

**Files:**
- Modify: `src/karaoke_buddy/__main__.py`

This replaces the stub from Task 1 with the real boot sequence.

- [ ] **Step 1: Implement `__main__.py`**

```python
# src/karaoke_buddy/__main__.py
"""KaraokeBuddy entry point.

Boot sequence:
1. Resolve app directory (exe parent when frozen, project root in dev).
2. Create runtime directories: cache/, logs/, Pitched Songs/
3. Set up rotating log file.
4. Check libmpv + FFmpeg are present — show fatal dialog and exit if not.
5. Load library.json.
6. Start Qt application and show MainWindow.
"""
from __future__ import annotations

import logging
import logging.handlers
import shutil
import sys
from pathlib import Path


def _app_dir() -> Path:
    """Directory that acts as the 'install root' for runtime files."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    # Development: 3 levels up from src/karaoke_buddy/__main__.py
    return Path(__file__).resolve().parent.parent.parent


def _resource(name: str) -> Path:
    """Resolve a bundled resource path (handles PyInstaller _MEIPASS)."""
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass) / name
    return Path(name)


def _find_ffmpeg() -> str:
    """Return ffmpeg executable path (bundled > PATH)."""
    bundled = _resource("ffmpeg.exe")
    if bundled.exists():
        return str(bundled)
    found = shutil.which("ffmpeg")
    return found if found else "ffmpeg"


def _setup_logging(log_dir: Path) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(
        log_dir / "app.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        handlers=[handler],
    )


def _check_requirements() -> list[str]:
    """Return list of user-facing error strings; empty means all OK."""
    errors: list[str] = []
    try:
        import mpv  # noqa: F401  – triggers DLL load
    except OSError:
        errors.append("libmpv-2.dll is missing.")
    if not shutil.which("ffmpeg") and not _resource("ffmpeg.exe").exists():
        errors.append("ffmpeg.exe is missing.")
    if errors:
        errors.append("Please re-download KaraokeBuddy.")
    return errors


def main() -> None:
    app_dir = _app_dir()

    # Create runtime directories
    (app_dir / "cache").mkdir(exist_ok=True)
    (app_dir / "logs").mkdir(exist_ok=True)
    (app_dir / "Pitched Songs").mkdir(exist_ok=True)

    _setup_logging(app_dir / "logs")
    log = logging.getLogger(__name__)
    log.info("KaraokeBuddy starting. app_dir=%s", app_dir)

    # Qt must exist before showing any dialog
    from PySide6.QtWidgets import QApplication, QMessageBox
    app = QApplication(sys.argv)
    app.setApplicationName("KaraokeBuddy")
    app.setApplicationVersion("0.1.0")

    errors = _check_requirements()
    if errors:
        QMessageBox.critical(None, "KaraokeBuddy — installation incomplete", "\n".join(errors))
        sys.exit(1)

    from karaoke_buddy.core.library import Library
    from karaoke_buddy.core.source_resolver import SourceResolver
    from karaoke_buddy.ui.main_window import MainWindow

    library = Library(app_dir / "library.json")
    resolver = SourceResolver(app_dir / "cache", ffmpeg_path=_find_ffmpeg())

    window = MainWindow(library, resolver)
    window.show()
    log.info("MainWindow shown")

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the full app and verify home view loads**

```
python -m karaoke_buddy
```

Expected:
- Window opens with home view
- No errors in terminal
- `logs/app.log` created next to project root with "MainWindow shown" entry

- [ ] **Step 3: Verify library persistence**

1. Open a local MP4 (any video on disk)
2. Close and reopen the app
3. Confirm the file appears in the library grid

- [ ] **Step 4: Run the full test suite**

```
pytest -v
```

Expected: All unit tests pass. Integration tests pass if FFmpeg is in PATH.

- [ ] **Step 5: Commit**

```bash
git add src/karaoke_buddy/__main__.py
git commit -m "feat: wire full boot sequence with startup checks and logging"
```

---

## Task 10: Build script

**Files:**
- Create: `build/build.py`

- [ ] **Step 1: Obtain bundled binaries**

Before building, collect:
1. `libmpv-2.dll` — from mpv-winbuild releases (Task 1 note)
2. `ffmpeg.exe` — minimal static build from gyan.dev
   Place both at `build/bin/libmpv-2.dll` and `build/bin/ffmpeg.exe`.

> **FFmpeg minimal build:** gyan.dev's "essentials" build is ~75 MB. For a smaller bundle, build FFmpeg from source with only `--enable-libopus --enable-libvpx --enable-librubberband --enable-libx264` — but the essentials build is the pragmatic choice.

- [ ] **Step 2: Implement `build/build.py`**

```python
# build/build.py
"""PyInstaller driver for KaraokeBuddy.

Usage:
    cd <project-root>
    python build/build.py

Output: dist/KaraokeBuddy.exe (~100-150 MB)
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BIN = ROOT / "build" / "bin"
ENTRY = ROOT / "src" / "karaoke_buddy" / "__main__.py"
ICON = ROOT / "src" / "karaoke_buddy" / "resources" / "icon.ico"


def main() -> None:
    libmpv = BIN / "libmpv-2.dll"
    ffmpeg = BIN / "ffmpeg.exe"

    if not libmpv.exists():
        sys.exit(f"ERROR: {libmpv} not found. See build/README or Task 10 in the plan.")
    if not ffmpeg.exists():
        sys.exit(f"ERROR: {ffmpeg} not found. See build/README or Task 10 in the plan.")

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--windowed",
        "--name", "KaraokeBuddy",
        "--add-binary", f"{libmpv};.",
        "--add-binary", f"{ffmpeg};.",
    ]

    if ICON.exists():
        cmd += ["--icon", str(ICON)]

    # Collect yt-dlp and its dependencies explicitly (PyInstaller may miss them)
    cmd += [
        "--collect-all", "yt_dlp",
        "--hidden-import", "PySide6.QtCore",
        "--hidden-import", "PySide6.QtWidgets",
        "--hidden-import", "PySide6.QtGui",
        "--hidden-import", "mpv",
    ]

    cmd.append(str(ENTRY))

    print("Running PyInstaller…")
    print(" ".join(cmd))
    subprocess.run(cmd, check=True, cwd=ROOT)
    print(f"\nBuild complete: {ROOT / 'dist' / 'KaraokeBuddy.exe'}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Build**

```
cd C:\Repo\karaoke-buddy
python build/build.py
```

Expected: `dist/KaraokeBuddy.exe` created (~100–150 MB). Build takes 1–3 minutes.

- [ ] **Step 4: Smoke-test the built exe**

Copy `dist/KaraokeBuddy.exe` to a clean directory (no Python, no FFmpeg in PATH) and run it. If it launches and the home view appears, packaging is correct.

If AV flags it as suspicious (common with PyInstaller `--onefile`), switch to `--onedir` by replacing `--onefile` with `--onedir` in `build.py`. The output becomes a folder (`dist/KaraokeBuddy/`) instead of a single exe — still portable, still no installer.

- [ ] **Step 5: Commit**

```bash
git add build/build.py
git commit -m "feat: add PyInstaller build script for single-exe distribution"
```

---

## Spec Coverage Check

| Spec section | Covered by |
|---|---|
| Open local video files | Task 7 (`_open_file_dialog`, `_load_local`) |
| Open YouTube URLs (download → play) | Task 4 (`DownloadThread`), Task 7 (`_start_url_load`) |
| Live pitch shift -12 to +12, tempo preserved | Task 2 (`build_filter_chain` rubberband), Task 8 (`_on_pitch_changed`) |
| Live vocal reduction 0–100% | Task 2 (pan filter), Task 8 (`_on_vocal_changed`) |
| Export to MP4 | Task 6 (`ExportThread`), Task 8 (`_on_save_clicked`) |
| Library with sticky per-song settings | Task 3 (`Library`), Task 8 (`_persist_settings`, `load`) |
| Portable single-file exe | Task 10 |
| Home state: open file + paste URL buttons | Task 7 (`HomeView`) |
| Playing state: video, sliders, save, back link | Task 8 (`PlayingView`) |
| Clipboard affordance | Task 7 (`_check_clipboard`) |
| Sticky settings restored on reopen | Task 8 (`load` → restores `last_pitch`, `last_vocal_reduce`) |
| Progress bars for download + export | Task 7 (`show_download_progress`), Task 8 (`_on_export_progress`) |
| Plain-English errors, no stack traces | Task 7 (`_on_url_error`), Task 8 (`_on_export_error`), Task 9 (`_check_requirements`) |
| Log rotation 5 MB / 3 files | Task 9 (`_setup_logging`) |
| Atomic library JSON write | Task 3 (`Library._save`) |
| Corruption recovery | Task 3 (`Library._load`) |
| Startup check: libmpv + FFmpeg | Task 9 (`_check_requirements`) |
| First-run directory creation | Task 9 (`main()`) |
| Export video stream-copy + libx264 fallback | Task 6 (`_run_ffmpeg copy_video=True/False`) |
| Filter chain identical for preview and export | Tasks 2+6+8 (both call `build_filter_chain`) |
| Pytest: filter chain property tests | Task 2 |
| Pytest: library persistence | Task 3 |
| Pytest: source resolver (mocked) | Task 4 |
| Pytest: exporter integration | Task 6 |

**Gaps vs spec:**
- `§5.3 pt.6` — Narrow-window grace (library collapses below 700 px): `LibraryGrid` is inside a `QScrollArea` which gracefully handles narrow widths; a full collapsible-to-button implementation is polish that can be added after the manual smoke tests confirm layout.
- Clipboard title preview (fetching the actual title with yt-dlp before confirming paste): `HomeView._check_clipboard` shows the URL but does not fetch the title. Fetching requires a network call; wire a `TitleFetchThread` (wrapping `SourceResolver.fetch_title`) to populate the label asynchronously as a follow-on polish task.
