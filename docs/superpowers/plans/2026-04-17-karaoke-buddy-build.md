# KaraokeBuddy Build Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Take the fully-scaffolded KaraokeBuddy codebase from "all 69 tests broken, three spec features missing" to "all tests green, every spec feature implemented, portable .exe built and smoke-tested."

**Architecture:** Five core modules (filter_chain, library, source_resolver, player, exporter) plus Qt UI are already written and wired through MainWindow. This plan fixes a test-setup blocker, removes stale code, fills three spec gaps, then builds and verifies the exe.

**Tech Stack:** Python 3.14, PySide6 6.11, python-mpv 1.0.8, yt-dlp, FFmpeg static (GPL, bundled), libmpv-2.dll (bundled), PyInstaller 6, pytest 9, hypothesis 6.

> **Note on prior plans:** Four previous plans exist in this folder. This plan supersedes them.
> The `2026-04-17-karaoke-buddy-final.md` plan is the closest predecessor; it handles the
> critical path (conftest fix → DLL fix → binaries → build) but is missing: hypothesis property
> tests (spec §9.1), async clipboard title preview (spec §5.1), and removal of orphaned
> `download_worker.py`. All nine tasks below are in correct execution order.

---

## File Map

| File | Action |
|------|--------|
| `tests/conftest.py` | Task 1 — remove autouse to unblock all tests |
| `src/karaoke_buddy/ui/download_worker.py` | Task 2 — delete (broken imports, never imported) |
| `tests/test_filter_chain.py` | Task 3 — add hypothesis property tests |
| `src/karaoke_buddy/ui/home_view.py` | Task 4 — add `_ClipMetaWorker` + async title fetch |
| `src/karaoke_buddy/__main__.py` | Task 5 — fix `_locate_bundled` for `--onefile` + add `_setup_dll_search_path` |
| `tests/test_entrypoint.py` | Task 5 — new: covers DLL discovery helpers |
| `build/bin/ffmpeg.exe` | Task 7 — downloaded manually |
| `build/bin/ffprobe.exe` | Task 7 — downloaded manually |
| `build/bin/libmpv-2.dll` | Task 8 — downloaded manually |
| `build/dist/KaraokeBuddy.exe` | Task 8 — produced by PyInstaller |

---

## Task 1: Fix conftest.py — unblock all 69 failing tests

**Files:**
- Modify: `tests/conftest.py`

**Root cause:** `conftest.py` declares `sample_video` as `scope="session", autouse=True`. It calls
`ffmpeg` to generate a fixture file. FFmpeg is not on `PATH`, so every test — including pure-Python
tests like `test_filter_chain.py` that never need a video — crashes at setup with
`FileNotFoundError`. `test_exporter.py` defines its own local `sample_video` fixture, so the
conftest version is unused by any test.

- [ ] **Step 1: Replace conftest.py with an empty stub**

Write `tests/conftest.py`:

```python
"""Shared pytest fixtures."""
```

That's the entire file. No autouse fixtures.

- [ ] **Step 2: Run the three pure-Python test modules**

```bash
cd C:/Repo/karaoke-buddy
python -m pytest tests/test_filter_chain.py tests/test_library.py tests/test_source_resolver.py -v
```

Expected:
```
tests/test_filter_chain.py::test_zero_pitch_zero_vocal_has_unity_pitch PASSED
tests/test_filter_chain.py::test_zero_pitch_zero_vocal_has_zero_mix PASSED
...
===== 65 passed in X.XXs =====
```

If any test **fails** (not errors), investigate before continuing:

| Failing test | Likely cause | Fix |
|---|---|---|
| `test_octave_up_doubles_pitch` | Wrong formula | Verify `2 ** (12/12) == 2.0` in `filter_chain.py` |
| `test_atomic_write_uses_tmp_file` | Monkeypatch target wrong | Confirm `library.py` has `import os` at module level |
| `test_cache_hit_skips_yt_dlp_download` | Cache path mismatch | Check `video_path = video_dir / "video.mp4"` in `source_resolver.py` |
| `test_list_is_sorted_most_recently_opened_first` | Sort direction | Verify `reverse=True` in `Library.list()` |

- [ ] **Step 3: Commit**

```bash
git add tests/conftest.py
git commit -m "fix: remove autouse session fixture that crashed every test (ffmpeg not in PATH)"
```

---

## Task 2: Remove orphaned download_worker.py

**Files:**
- Delete: `src/karaoke_buddy/ui/download_worker.py`

`download_worker.py` imports `ResolverError`, `resolve_local`, `resolve_youtube` from
`karaoke_buddy.core.source_resolver`. These symbols do not exist — `source_resolver.py` exposes a
class-based API (`SourceResolver.resolve()`). The file is never imported by `main_window.py` or
any other module. `MainWindow` has its own `_ResolveThread` that covers the same responsibility.

- [ ] **Step 1: Confirm nothing imports download_worker.py**

```bash
grep -r "download_worker" src/ tests/
```

Expected: no output. If any file imports it, note which one before deleting.

- [ ] **Step 2: Delete the file**

```bash
rm src/karaoke_buddy/ui/download_worker.py
```

- [ ] **Step 3: Confirm tests still pass**

```bash
python -m pytest tests/test_filter_chain.py tests/test_library.py tests/test_source_resolver.py -q
```

Expected: 65 passed, 0 errors.

- [ ] **Step 4: Commit**

```bash
git add src/karaoke_buddy/ui/download_worker.py
git commit -m "chore: delete orphaned download_worker.py (broken imports, never used)"
```

---

## Task 3: Add hypothesis property tests for filter_chain

**Files:**
- Modify: `tests/test_filter_chain.py`

Spec §9.1: *"Filter-chain builder — property tests across the full pitch × vocal-reduce matrix.
An audio-math bug is silent and serious; this is the highest-priority test target."*

The existing tests use `@pytest.mark.parametrize` over the full semitone range, but not
hypothesis. Hypothesis generates random combinations over the entire input space and shrinks
failures to minimal cases — much stronger than a fixed parametrize grid.

`hypothesis` is already in `pyproject.toml` dev dependencies.

- [ ] **Step 1: Add hypothesis imports and three property tests to test_filter_chain.py**

Append the following block to the end of `tests/test_filter_chain.py` (after the last existing
test):

```python
# ---------------------------------------------------------------------------
# Hypothesis property tests (spec §9.1)
# ---------------------------------------------------------------------------
import math

from hypothesis import given
from hypothesis import strategies as st


@given(
    semitones=st.integers(min_value=-12, max_value=12),
    vocal_reduce=st.integers(min_value=0, max_value=100),
)
def test_property_output_is_valid_af_string(semitones, vocal_reduce):
    """For any valid inputs the output is a well-formed af= filter string."""
    chain = build_filter_chain(semitones, vocal_reduce)
    assert chain.startswith("rubberband=pitch=")
    assert "pan=stereo|c0=c0-" in chain
    assert "c1=c1-" in chain


@given(semitones=st.integers(min_value=-12, max_value=12))
def test_property_pitch_scale_equals_two_to_the_n_over_twelve(semitones):
    """Pitch scale must equal 2^(n/12) for every semitone value."""
    expected = 2 ** (semitones / 12)
    chain = build_filter_chain(semitones, 0)
    m = re.search(r"rubberband=pitch=(\d+\.\d+)", chain)
    assert m is not None, f"No rubberband pitch found in: {chain}"
    actual = float(m.group(1))
    assert math.isclose(actual, expected, rel_tol=1e-5), (
        f"semitones={semitones}: expected {expected:.6f}, got {actual:.6f}"
    )


@given(vocal_reduce=st.integers(min_value=0, max_value=100))
def test_property_pan_mix_equals_vocal_reduce_over_200(vocal_reduce):
    """Pan mix coefficient must equal (vocal_reduce / 100) * 0.5."""
    expected_mix = (vocal_reduce / 100) * 0.5
    chain = build_filter_chain(0, vocal_reduce)
    m = re.search(r"c0=c0-([\d.]+)\*c1", chain)
    assert m is not None, f"No pan mix found in: {chain}"
    actual = float(m.group(1))
    assert math.isclose(actual, expected_mix, abs_tol=1e-4), (
        f"vocal_reduce={vocal_reduce}: expected {expected_mix:.4f}, got {actual:.4f}"
    )


@given(
    semitones=st.integers(min_value=-12, max_value=12),
    vocal_reduce=st.integers(min_value=0, max_value=100),
)
def test_property_filter_chain_is_pure_function(semitones, vocal_reduce):
    """Same inputs always produce identical output (no side effects)."""
    assert build_filter_chain(semitones, vocal_reduce) == build_filter_chain(
        semitones, vocal_reduce
    )
```

- [ ] **Step 2: Run test_filter_chain.py to confirm all tests (old + new) pass**

```bash
python -m pytest tests/test_filter_chain.py -v
```

Expected: 65+ tests pass (43 original + 4 hypothesis tests × hypothesis trial count).
Hypothesis runs each property test 100 times by default.

If `ImportError: cannot import name 'given'`:
```bash
pip install hypothesis
```

- [ ] **Step 3: Commit**

```bash
ruff check --fix tests/test_filter_chain.py && ruff format tests/test_filter_chain.py
git add tests/test_filter_chain.py
git commit -m "test: add hypothesis property tests for filter_chain (spec §9.1)"
```

---

## Task 4: Async clipboard title preview (spec §5.1)

**Files:**
- Modify: `src/karaoke_buddy/ui/home_view.py`

Spec §5.1: *"if the clipboard holds a recognisable YouTube URL when the window gains focus, the
Paste button shows an inline preview — 'Paste this? 🎵 {video title}' — populated via a cheap
yt-dlp metadata-only call."*

The current implementation shows `"🎵 YouTube link detected — click 'Paste YouTube link' to
open"` but never fetches the title. This task adds a `_ClipMetaWorker(QThread)` that fires a
`yt-dlp extract_info(download=False)` call when a new URL lands in the clipboard, then updates
the label with the real title. Results are cached per-URL so re-polls don't re-fetch.

- [ ] **Step 1: Write the new home_view.py**

Replace `src/karaoke_buddy/ui/home_view.py` entirely with:

```python
"""HomeView — launch screen shown when no video is loaded."""
import logging
from typing import Optional

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QThread,
    QVBoxLayout,
    QWidget,
)

from karaoke_buddy.core.library import Library
from karaoke_buddy.core.source_resolver import is_youtube_url
from karaoke_buddy.ui.library_view import LibraryEntry, LibraryView

log = logging.getLogger(__name__)

_VIDEO_FILTER = "Video files (*.mp4 *.mkv *.webm *.mov);;All files (*)"


class _ClipMetaWorker(QThread):
    """Fetches a YouTube video's title without downloading the video.

    Emits ``title_ready(str)`` on success, ``fetch_failed()`` on any error.
    """

    title_ready = Signal(str)
    fetch_failed = Signal()

    def __init__(self, url: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._url = url

    def run(self) -> None:
        try:
            import yt_dlp  # noqa: PLC0415

            with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
                info = ydl.extract_info(self._url, download=False)
            self.title_ready.emit(info.get("title") or self._url)
        except Exception:  # noqa: BLE001
            self.fetch_failed.emit()


class _PasteDialog(QDialog):
    def __init__(self, prefill: str = "", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Open YouTube link")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Paste a YouTube link:"))

        self._field = QLineEdit(prefill)
        self._field.setPlaceholderText("https://www.youtube.com/watch?v=\u2026")
        layout.addWidget(self._field)

        self._warning = QLabel("")
        self._warning.setStyleSheet("color: #e05c5c; font-size: 11px;")
        layout.addWidget(self._warning)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_accept(self) -> None:
        url = self._field.text().strip()
        if not is_youtube_url(url):
            self._warning.setText("That doesn't look like a YouTube link.")
            return
        self.accept()

    def url(self) -> str:
        return self._field.text().strip()


class HomeView(QWidget):
    open_file_requested = Signal(str)
    open_url_requested = Signal(str)
    entry_selected = Signal(LibraryEntry)

    def __init__(self, library: Library, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._library = library
        self._last_clip_url: str = ""
        self._clip_meta_worker: Optional[_ClipMetaWorker] = None

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)

        title = QLabel("KaraokeBuddy \U0001F3A4")
        title.setStyleSheet("font-size: 28px; font-weight: bold;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(title)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(16)

        self._btn_open = QPushButton("Open a video file")
        self._btn_open.setFixedHeight(56)
        self._btn_open.setStyleSheet("font-size: 15px;")
        self._btn_open.clicked.connect(self._on_open_file)
        btn_row.addWidget(self._btn_open)

        self._btn_paste = QPushButton("Paste YouTube link")
        self._btn_paste.setFixedHeight(56)
        self._btn_paste.setStyleSheet("font-size: 15px;")
        self._btn_paste.clicked.connect(self._on_paste_url)
        btn_row.addWidget(self._btn_paste)

        root.addLayout(btn_row)

        self._clip_label = QLabel("")
        self._clip_label.setStyleSheet("color: #7ec8e3; font-size: 12px;")
        self._clip_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._clip_label.hide()
        root.addWidget(self._clip_label)

        self._library_view = LibraryView(library)
        self._library_view.entry_selected.connect(self.entry_selected)
        root.addWidget(self._library_view, stretch=1)

        self._clip_timer = QTimer(self)
        self._clip_timer.setInterval(1000)
        self._clip_timer.timeout.connect(self._check_clipboard)
        self._clip_timer.start()

    def refresh_library(self) -> None:
        self._library_view.refresh()

    def _on_open_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open video", "", _VIDEO_FILTER)
        if path:
            self.open_file_requested.emit(path)

    def _on_paste_url(self) -> None:
        clipboard_text = QGuiApplication.clipboard().text().strip()
        prefill = clipboard_text if is_youtube_url(clipboard_text) else ""
        dlg = _PasteDialog(prefill=prefill, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.open_url_requested.emit(dlg.url())

    def _check_clipboard(self) -> None:
        if not self.isVisible():
            return
        text = QGuiApplication.clipboard().text().strip()
        if is_youtube_url(text):
            if text != self._last_clip_url:
                # New URL — start async title fetch
                self._last_clip_url = text
                self._clip_label.setText("\U0001F3B5 Fetching title\u2026")
                self._clip_label.show()

                if self._clip_meta_worker and self._clip_meta_worker.isRunning():
                    self._clip_meta_worker.terminate()
                    self._clip_meta_worker.wait(500)

                worker = _ClipMetaWorker(text, parent=self)
                worker.title_ready.connect(
                    lambda title, url=text: self._on_clip_title(title, url)
                )
                worker.fetch_failed.connect(
                    lambda: self._clip_label.setText(
                        "\U0001F3B5 YouTube link detected"
                        " \u2014 click \u201cPaste YouTube link\u201d to open"
                    )
                )
                worker.finished.connect(worker.deleteLater)
                self._clip_meta_worker = worker
                worker.start()
            # else: same URL, label already up-to-date
        else:
            self._last_clip_url = ""
            self._clip_label.hide()

    def _on_clip_title(self, title: str, url: str) -> None:
        """Called from the worker thread via Signal — always on the Qt main thread."""
        if url == self._last_clip_url:  # guard against stale workers
            self._clip_label.setText(f"Paste this? \U0001F3B5  {title}")
            self._clip_label.show()
```

- [ ] **Step 2: Run the pure-Python test suite to confirm no regressions**

```bash
python -m pytest tests/test_filter_chain.py tests/test_library.py tests/test_source_resolver.py -q
```

Expected: 65 passed, 0 errors. (No test covers `home_view.py` directly, so regressions would only
show up as import errors.)

- [ ] **Step 3: Lint and commit**

```bash
ruff check --fix src/karaoke_buddy/ui/home_view.py && ruff format src/karaoke_buddy/ui/home_view.py
git add src/karaoke_buddy/ui/home_view.py
git commit -m "feat: async clipboard title preview via yt-dlp metadata-only call (spec §5.1)"
```

---

## Task 5: Fix PyInstaller DLL discovery + write test_entrypoint.py

**Files:**
- Modify: `src/karaoke_buddy/__main__.py`
- Create: `tests/test_entrypoint.py`

In `--onefile` mode, PyInstaller extracts the bundle to a temp dir stored in `sys._MEIPASS` — not
`Path(sys.executable).parent`. The current `_locate_bundled` only checks the exe's parent, so it
never finds `ffmpeg.exe` or `libmpv-2.dll` at runtime → "Installation is incomplete" crash.
Additionally, `os.add_dll_directory(sys._MEIPASS)` must be called before `import mpv` so Windows
`ctypes` finds `libmpv-2.dll`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_entrypoint.py`:

```python
"""Tests for __main__ entry point helpers — DLL discovery and DLL path setup."""
import os
import sys
from pathlib import Path

import pytest


def test_locate_bundled_returns_none_in_dev_mode(monkeypatch):
    """In non-frozen dev mode, _locate_bundled always returns None."""
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    from karaoke_buddy.__main__ import _locate_bundled  # noqa: PLC0415

    assert _locate_bundled("ffmpeg.exe") is None


def test_locate_bundled_finds_dll_in_meipass(monkeypatch, tmp_path):
    """In frozen --onefile mode, _locate_bundled checks sys._MEIPASS first."""
    meipass = tmp_path / "meipass"
    meipass.mkdir()
    dll = meipass / "libmpv-2.dll"
    dll.write_bytes(b"")

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(meipass), raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "KaraokeBuddy.exe"), raising=False)

    from karaoke_buddy.__main__ import _locate_bundled  # noqa: PLC0415

    result = _locate_bundled("libmpv-2.dll")
    assert result == dll


def test_locate_bundled_falls_back_to_exe_parent_if_no_meipass(monkeypatch, tmp_path):
    """In frozen --onedir mode (no sys._MEIPASS), exe.parent is used."""
    exe_parent = tmp_path / "dist"
    exe_parent.mkdir()
    dll = exe_parent / "libmpv-2.dll"
    dll.write_bytes(b"")

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    try:
        monkeypatch.delattr(sys, "_MEIPASS")
    except AttributeError:
        pass
    monkeypatch.setattr(sys, "executable", str(exe_parent / "KaraokeBuddy.exe"), raising=False)

    from karaoke_buddy.__main__ import _locate_bundled  # noqa: PLC0415

    result = _locate_bundled("libmpv-2.dll")
    assert result == dll


def test_locate_bundled_returns_none_when_file_absent(monkeypatch, tmp_path):
    """Returns None if the file doesn't exist in any search location."""
    meipass = tmp_path / "meipass"
    meipass.mkdir()

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(meipass), raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "KaraokeBuddy.exe"), raising=False)

    from karaoke_buddy.__main__ import _locate_bundled  # noqa: PLC0415

    assert _locate_bundled("libmpv-2.dll") is None


def test_setup_dll_search_path_adds_meipass_in_frozen_mode(monkeypatch, tmp_path):
    """In frozen mode with sys._MEIPASS, os.add_dll_directory is called with it."""
    meipass = tmp_path / "meipass"
    meipass.mkdir()
    added: list[str] = []

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(meipass), raising=False)
    monkeypatch.setattr(os, "add_dll_directory", lambda d: added.append(d), raising=False)

    from karaoke_buddy.__main__ import _setup_dll_search_path  # noqa: PLC0415

    _setup_dll_search_path()
    assert str(meipass) in added


def test_setup_dll_search_path_is_noop_in_dev_mode(monkeypatch):
    """In non-frozen dev mode, os.add_dll_directory is never called."""
    added: list[str] = []

    monkeypatch.setattr(sys, "frozen", False, raising=False)
    monkeypatch.setattr(os, "add_dll_directory", lambda d: added.append(d), raising=False)

    from karaoke_buddy.__main__ import _setup_dll_search_path  # noqa: PLC0415

    _setup_dll_search_path()
    assert added == []
```

- [ ] **Step 2: Run tests to confirm failures**

```bash
python -m pytest tests/test_entrypoint.py -v
```

Expected failures:
- `test_locate_bundled_finds_dll_in_meipass` — FAIL (`_locate_bundled` doesn't check `_MEIPASS`)
- `test_locate_bundled_falls_back_to_exe_parent_if_no_meipass` — FAIL (same reason)
- `test_setup_dll_search_path_*` — ERROR (`ImportError: cannot import name '_setup_dll_search_path'`)

- [ ] **Step 3: Replace src/karaoke_buddy/__main__.py with the fixed version**

```python
"""KaraokeBuddy — entry point."""
import logging
import logging.handlers
import os
import sys
from pathlib import Path


def _setup_logging(log_dir: Path) -> None:
    log_dir.mkdir(exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(
        log_dir / "app.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging.getLogger().addHandler(handler)
    logging.getLogger().setLevel(logging.INFO)


def _locate_bundled(name: str) -> Path | None:
    """Find a binary bundled by PyInstaller.

    Checks ``sys._MEIPASS`` first (populated in ``--onefile`` mode when the archive
    is extracted to a temp directory), then falls back to the directory that contains
    the executable (correct for ``--onedir`` mode).

    Returns ``None`` in development (non-frozen) mode, or if the file does not exist
    in any candidate location.
    """
    if not getattr(sys, "frozen", False):
        return None
    search_dirs: list[Path] = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        search_dirs.append(Path(meipass))
    search_dirs.append(Path(sys.executable).parent)
    for d in search_dirs:
        candidate = d / name
        if candidate.exists():
            return candidate
    return None


def _setup_dll_search_path() -> None:
    """In frozen mode, add the PyInstaller extraction directory to the Windows DLL
    search path so that ``ctypes`` (used by python-mpv) can find ``libmpv-2.dll``
    without it being on the system ``PATH``.

    Must be called before any ``import mpv`` (i.e. before importing ``MainWindow``,
    which transitively imports ``player.py``).

    No-op in development mode and on non-Windows platforms.
    """
    if not getattr(sys, "frozen", False):
        return
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass and hasattr(os, "add_dll_directory"):
        os.add_dll_directory(meipass)


def main() -> None:
    if getattr(sys, "frozen", False):
        base_dir = Path(sys.executable).parent
    else:
        base_dir = Path(__file__).parent.parent.parent

    _setup_logging(base_dir / "logs")
    log = logging.getLogger(__name__)
    log.info("KaraokeBuddy starting \u2014 base_dir=%s", base_dir)

    # Must happen before any import that pulls in python-mpv.
    _setup_dll_search_path()

    from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: PLC0415

    app = QApplication(sys.argv)
    app.setApplicationName("KaraokeBuddy")

    ffmpeg_exe = _locate_bundled("ffmpeg.exe")
    ffprobe_exe = _locate_bundled("ffprobe.exe")

    if getattr(sys, "frozen", False) and (ffmpeg_exe is None or ffprobe_exe is None):
        QMessageBox.critical(
            None,
            "KaraokeBuddy",
            "Installation is incomplete. Please re-download KaraokeBuddy.",
        )
        sys.exit(1)

    from karaoke_buddy.core.library import Library  # noqa: PLC0415
    from karaoke_buddy.ui.main_window import MainWindow  # noqa: PLC0415

    library = Library(base_dir / "library.json")
    window = MainWindow(
        library=library,
        base_dir=base_dir,
        ffmpeg_exe=ffmpeg_exe,
        ffprobe_exe=ffprobe_exe,
    )
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run all entrypoint tests**

```bash
python -m pytest tests/test_entrypoint.py -v
```

Expected:
```
tests/test_entrypoint.py::test_locate_bundled_returns_none_in_dev_mode PASSED
tests/test_entrypoint.py::test_locate_bundled_finds_dll_in_meipass PASSED
tests/test_entrypoint.py::test_locate_bundled_falls_back_to_exe_parent_if_no_meipass PASSED
tests/test_entrypoint.py::test_locate_bundled_returns_none_when_file_absent PASSED
tests/test_entrypoint.py::test_setup_dll_search_path_adds_meipass_in_frozen_mode PASSED
tests/test_entrypoint.py::test_setup_dll_search_path_is_noop_in_dev_mode PASSED
===== 6 passed =====
```

- [ ] **Step 5: Run the full no-FFmpeg suite to confirm no regressions**

```bash
python -m pytest tests/test_filter_chain.py tests/test_library.py tests/test_source_resolver.py tests/test_entrypoint.py -q
```

Expected: **71 passed**, 0 errors.

- [ ] **Step 6: Commit**

```bash
ruff check --fix src/karaoke_buddy/__main__.py tests/test_entrypoint.py
ruff format src/karaoke_buddy/__main__.py tests/test_entrypoint.py
git add src/karaoke_buddy/__main__.py tests/test_entrypoint.py
git commit -m "fix: locate bundled DLLs in sys._MEIPASS for PyInstaller --onefile mode"
```

---

## Task 6: Commit all remaining untracked source code

**Files:** Everything not yet committed under `src/`, `tests/`, `build/`, `pyproject.toml`

- [ ] **Step 1: Check git status**

```bash
git status
```

Review the untracked/modified file list. Expected untracked: all `src/karaoke_buddy/` files,
`tests/test_filter_chain.py`, `tests/test_library.py`, `tests/test_source_resolver.py`,
`tests/test_exporter.py`, `build/build.py`, `build/create_fixture.py`, `pyproject.toml`.

- [ ] **Step 2: Commit core modules**

```bash
git add src/karaoke_buddy/core/
git add src/karaoke_buddy/__init__.py
git commit -m "feat: core modules — filter_chain, library, source_resolver, player, exporter"
```

- [ ] **Step 3: Commit UI**

```bash
git add src/karaoke_buddy/ui/
git add src/karaoke_buddy/__main__.py
git commit -m "feat: Qt UI — HomeView (async clipboard), LibraryView, PlayingView, MainWindow"
```

- [ ] **Step 4: Commit tests and build tooling**

```bash
git add tests/
git add build/build.py build/bin/README.txt build/__init__.py build/create_fixture.py
git add pyproject.toml
git commit -m "chore: tests, hypothesis property tests, and PyInstaller build script"
```

- [ ] **Step 5: Verify clean working tree**

```bash
git status
```

Expected: `nothing to commit, working tree clean`.

---

## Task 7: Acquire FFmpeg + run exporter integration tests

**Files produced:**
- `build/bin/ffmpeg.exe`
- `build/bin/ffprobe.exe`

The exporter integration tests (`test_exporter.py`) run real FFmpeg on a 10-second synthetic clip.
The filter chain uses `rubberband` for pitch shift — only in FFmpeg GPL static builds.

- [ ] **Step 1: Download FFmpeg GPL static build**

Open PowerShell in `C:\Repo\karaoke-buddy`:

```powershell
$url = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
Invoke-WebRequest $url -OutFile ffmpeg.zip
Expand-Archive ffmpeg.zip -DestinationPath ffmpeg_extracted -Force
Copy-Item "ffmpeg_extracted\ffmpeg-master-latest-win64-gpl\bin\ffmpeg.exe" "build\bin\ffmpeg.exe"
Copy-Item "ffmpeg_extracted\ffmpeg-master-latest-win64-gpl\bin\ffprobe.exe" "build\bin\ffprobe.exe"
Remove-Item ffmpeg.zip
Remove-Item ffmpeg_extracted -Recurse
```

- [ ] **Step 2: Verify rubberband support is present**

```powershell
.\build\bin\ffmpeg.exe -filters 2>&1 | Select-String "rubberband"
```

Expected: one line containing `rubberband  A->A  Apply time-stretching and pitch-shifting`.

If nothing appears: re-download and ensure you're using the **GPL** build. An LGPL build omits
rubberband and will silently produce corrupted audio.

- [ ] **Step 3: Add build/bin to PATH for this shell session**

```bash
# Git Bash
export PATH="$PATH:/c/Repo/karaoke-buddy/build/bin"
```

- [ ] **Step 4: Run exporter integration tests**

```bash
python -m pytest tests/test_exporter.py -v
```

Expected: **6 passed** in ~30 seconds.

If `test_export_produces_valid_mp4` fails with `filter not found: rubberband`: the FFmpeg binary
lacks rubberband support — confirm Step 2.

If `test_no_partial_file_on_failure` fails (tmp file left on disk): open `core/exporter.py` and
confirm `tmp.unlink()` is called in BOTH the stream-copy-fail and re-encode-fail branches inside
`Exporter.export()`.

- [ ] **Step 5: Run the complete test suite**

```bash
python -m pytest -v
```

Expected: **77 passed** (71 unit + 6 integration). Zero failures.

---

## Task 8: Acquire libmpv-2.dll + build the .exe

**Files produced:**
- `build/bin/libmpv-2.dll`
- `build/dist/KaraokeBuddy.exe`

- [ ] **Step 1: Get libmpv-2.dll**

**Option A — via ctypes.util (checks your current environment first):**

```bash
python -c "
import ctypes.util, shutil
dll = ctypes.util.find_library('mpv')
if dll:
    shutil.copy(dll, 'build/bin/libmpv-2.dll')
    print('Copied from:', dll)
else:
    print('Not found — use Option B')
"
```

**Option B — Chocolatey:**
```powershell
choco install mpv
Copy-Item "C:\ProgramData\chocolatey\lib\mpv\tools\libmpv-2.dll" "build\bin\libmpv-2.dll"
```

**Option C — manual download:**
Go to `https://github.com/shinchiro/mpv-winbuild-cmake/releases`, download the latest
`mpv-dev-x86_64-*.7z`, extract it, copy `libmpv-2.dll` to `build\bin\`.

- [ ] **Step 2: Verify all three binaries are present and non-empty**

```powershell
Get-ChildItem build\bin\ |
  Where-Object { $_.Name -ne "README.txt" } |
  Select-Object Name, @{N='MB';E={[math]::Round($_.Length/1MB,1)}} |
  Format-Table
```

Expected:
```
Name            MB
ffmpeg.exe     ~100
ffprobe.exe    ~100
libmpv-2.dll   ~25
```

Any file under 1 MB is a failed download — re-download it.

- [ ] **Step 3: Verify python-mpv can import the DLL**

```bash
export PATH="$PATH:/c/Repo/karaoke-buddy/build/bin"
python -c "import mpv; print('mpv import ok')"
```

Expected: `mpv import ok`. If you see `OSError: Cannot find mpv-2.dll …`: `build/bin` is not on
`PATH` in this shell.

- [ ] **Step 4: Verify PyInstaller is installed**

```bash
pyinstaller --version
```

Expected: `6.x.x`. If not found:
```bash
pip install "pyinstaller>=6"
```

- [ ] **Step 5: Generate the app icon**

```bash
pip install Pillow
python src/karaoke_buddy/resources/generate_icon.py
```

Expected: `Icon written to …/resources/icon.ico`

- [ ] **Step 6: Add --icon flag to build/build.py**

Open `build/build.py`. Find the `cmd` list (around line 42). Add this entry after the
`--add-binary` lines and before `str(ENTRY)`:

```python
        "--icon", str(ROOT / "src" / "karaoke_buddy" / "resources" / "icon.ico"),
```

The complete `cmd` list should look like:

```python
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--windowed",
        "--name", "KaraokeBuddy",
        "--distpath", str(DIST_DIR),
        "--workpath", str(ROOT / "build" / "work"),
        "--specpath", str(ROOT / "build"),
        "--add-binary", f"{BIN_DIR / 'ffmpeg.exe'};.",
        "--add-binary", f"{BIN_DIR / 'ffprobe.exe'};.",
        "--add-binary", f"{BIN_DIR / 'libmpv-2.dll'};.",
        "--icon", str(ROOT / "src" / "karaoke_buddy" / "resources" / "icon.ico"),
        "--hidden-import", "yt_dlp",
        "--hidden-import", "yt_dlp.extractor",
        str(ENTRY),
    ]
```

- [ ] **Step 7: Run the build**

```bash
python build/build.py
```

Expected:
```
Running PyInstaller…
...
Build complete: C:\Repo\karaoke-buddy\build\dist\KaraokeBuddy.exe
```

This takes 2–5 minutes.

- [ ] **Step 8: Verify the output is real**

```powershell
Get-Item build\dist\KaraokeBuddy.exe |
  Select-Object Name, @{N='MB';E={[math]::Round($_.Length/1MB,0)}}
```

Expected: `MB` > 100. Anything smaller means PyInstaller failed mid-way.

Common build failures:

| Error | Fix |
|---|---|
| `Module not found: yt_dlp.extractor.youtube` | Add `"--hidden-import", "yt_dlp.extractor.youtube"` to cmd |
| `File not found: libmpv-2.dll` | Check `build/bin/libmpv-2.dll` exists and is non-empty |
| `UPX is not available` | Harmless warning — ignore |
| Antivirus blocks the .exe | Temporarily disable real-time AV, or switch to `--onedir` mode |

- [ ] **Step 9: Commit build tooling changes**

```bash
ruff check --fix build/build.py && ruff format build/build.py
git add build/build.py src/karaoke_buddy/resources/icon.ico
git commit -m "feat: add app icon + --icon flag to PyInstaller build"
```

---

## Task 9: Manual Smoke Test

Verify the exe works end-to-end. This maps directly to spec §9.2.

> Do not skip. Automated tests do not exercise the Player ↔ libmpv pipeline, the full
> download-to-play flow, or the async clipboard preview.

- [ ] **Step 1: First launch**

Double-click `build\dist\KaraokeBuddy.exe`.

Expected:
- Window opens in ~3 seconds (first launch unpacks to `%TEMP%\_MEI*`).
- Home screen: "KaraokeBuddy 🎤" title, two large buttons, empty library grid.
- No error dialogs.
- `logs\app.log` created next to the exe.

If `"Installation is incomplete"`: `ffmpeg.exe` or `ffprobe.exe` was not bundled. Add the missing
`--add-binary` entry and rebuild.

If `OSError: Cannot find mpv-2.dll`: `libmpv-2.dll` was not bundled. Check the `--add-binary`
line for it is present in `build/build.py` and rebuild.

- [ ] **Step 2: Open a local video and test pitch shift**

Use `tests\fixtures\sample_10s.mp4` (create it first with `python build/create_fixture.py` if it
doesn't exist) or any MP4 on disk.

1. Click "Open a video file" → select the file.
2. Video loads, Playing view appears, playback starts.
3. Move the **Song key** slider to -3.
   - Label reads "Lower by 3 keys".
   - Audio pitch drops noticeably within ~1 second. No stutter or restart.
4. Move **Silence the singer** to 50%.
   - Label reads "Guide vocals: 50% audible".
   - Audible centre-channel reduction.

- [ ] **Step 3: Save the current version**

1. Click "💾 Save this version".
2. File picker opens with suggested name like `sample_10s (key -3).mp4` inside `Pitched Songs\`.
3. Confirm.
4. Progress bar completes. Dialog: "Saved to: …"
5. Open the saved file in VLC. Verify pitch is shifted down.

- [ ] **Step 4: Library persistence across restarts**

1. Click "← Back to library". Card for the video appears with "Lower by 3 keys" hint.
2. Close the exe.
3. Reopen the exe.
4. Card is still present. Click it.
5. Video loads with pitch -3 and vocal reduce 50% restored.

- [ ] **Step 5: Clipboard title preview**

1. Copy `https://www.youtube.com/watch?v=dQw4w9WgXcQ` to clipboard.
2. Bring the app window to focus (or wait up to 1 second for the timer).
3. Expected: label shows "🎵 Fetching title…" briefly, then changes to
   "Paste this? 🎵  Never Gonna Give You Up".
4. Click "Paste YouTube link" — dialog opens with URL pre-filled. Click OK.
5. Download progress bar appears, then Playing view after download completes.

- [ ] **Step 6: YouTube video pitch shift + save**

(Requires internet connection and completes the §9.2 smoke checklist.)

1. From Step 5, adjust pitch, save. VLC confirms shifted audio.

- [ ] **Step 7: Clean-machine test (required before any distribution)**

Copy `KaraokeBuddy.exe` to a Windows 11 machine (or VM snapshot) with:
- No Python, no FFmpeg in PATH, no mpv in PATH
- No Visual C++ Runtime

1. Double-click the exe.
2. App launches and all steps 1–6 work identically.
3. If any DLL error: check the Windows Event Log for the DLL name, add it to
   `build/build.py`'s `--add-binary` list, and rebuild.

- [ ] **Step 8: Final commit**

```bash
ruff check --fix . && ruff format .
git add -p   # stage only real changes (e.g. if you added a hidden-import)
git commit -m "feat: KaraokeBuddy v1 — all tests pass, exe smoke-tested on clean machine"
```

---

## Self-Review

### Spec Coverage

| Spec Requirement | Task |
|---|---|
| Open local video files (MP4, MKV, WebM, MOV) | Code already written; verified Task 9 Step 2 |
| Open YouTube URLs (download → play) | Code already written; verified Task 9 Step 5 |
| Live pitch shift −12..+12, tempo preserved | `filter_chain.py` rubberband; Task 3 property tests; Task 9 Step 2 |
| Live vocal reduction 0–100% centre subtraction | `filter_chain.py` pan filter; Task 9 Step 2 |
| Export to MP4 (stream-copy + AAC, libx264 fallback) | `exporter.py`; Task 7 integration tests; Task 9 Step 3 |
| Library with per-song sticky settings | `library.py`; Task 1 unit tests; Task 9 Step 4 |
| Portable single-file .exe, no installer, no admin | Task 8 PyInstaller build; Task 9 Step 7 |
| Plain-English errors, no stack traces | `main_window._show_error`; error table in spec §8 |
| Progress bars (download and export) | `_ResolveThread` + `ExportThread` signals; Task 9 |
| Atomic library writes, corruption recovery | `library.py`; Task 1 unit tests |
| Log rotation 5 MB / 3 files | `__main__._setup_logging` RotatingFileHandler |
| Clipboard-aware paste button with title fetch | Task 4 `_ClipMetaWorker`; verified Task 9 Step 5 |
| "Normal key / Lower by N keys / Higher by N keys" | `playing_view._pitch_label`; Task 9 Step 2 |
| Suggested export filename | `main_window._on_save`; Task 9 Step 3 |
| First-run: create cache/, logs/, library.json | `__main__.main` + `Library.__init__` |
| PyInstaller --onefile DLL discovery | Task 5 `_locate_bundled` + `_setup_dll_search_path` |
| `rubberband` in bundled FFmpeg | Task 7 Step 2 explicit verification |
| Property tests for filter chain (spec §9.1) | Task 3 hypothesis tests |
| Full automated test suite passing | Tasks 1, 3, 5, 7 |
| Manual smoke test (spec §9.2) | Task 9 |
| Clean-machine test | Task 9 Step 7 |
| Conventional commits | Tasks 1–8 |

### Placeholder Scan

None — all steps contain exact commands, expected output, and complete replacement code.

### Type Consistency

- `build_filter_chain(pitch_semitones: int, vocal_reduce_percent: int) -> str` — same signature
  used in `filter_chain.py`, `playing_view.py`, `main_window.py`, `test_filter_chain.py`. No drift.
- `_locate_bundled(name: str) -> Path | None` — defined in Task 5, tested in `test_entrypoint.py`.
- `_setup_dll_search_path() -> None` — defined in Task 5, tested in `test_entrypoint.py`. Called in
  `main()` before any `import mpv`.
- `_ClipMetaWorker.title_ready: Signal(str)` / `.fetch_failed: Signal()` — defined in Task 4,
  connected in `HomeView._check_clipboard`. No name drift.
- `LibraryEntry`, `SavedOutput` — unchanged from `library.py`, used in `main_window.py`,
  `home_view.py`, `library_view.py`, `test_library.py`. No drift.
