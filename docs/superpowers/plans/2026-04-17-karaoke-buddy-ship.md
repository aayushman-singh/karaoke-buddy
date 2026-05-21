# KaraokeBuddy — Ship Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the remaining 7 tasks that take KaraokeBuddy from "code written, untested, uncommitted" to "all tests green, .exe built, smoke-tested on a clean machine."

**Architecture:** All five core modules and the Qt UI are already written and passing 75 tests. Three code gaps remain (orphaned file, missing property tests, missing async clipboard preview), then binaries must be acquired and the exe built. This plan supersedes all prior plans.

**Tech Stack:** Python 3.14, PySide6 6.11, python-mpv, yt-dlp, FFmpeg GPL static build (bundled), libmpv-2.dll (bundled), PyInstaller 6, pytest 9, hypothesis 6.

---

## Current State Snapshot

| Item | Status |
|------|--------|
| `tests/conftest.py` — autouse fixture removed | ✅ Done |
| `src/karaoke_buddy/__main__.py` — DLL fix + `_setup_dll_search_path` | ✅ Done |
| `tests/test_entrypoint.py` — 6 tests, all pass | ✅ Done |
| All core + UI source files written | ✅ Done (untracked) |
| 75 unit tests pass (43 filter_chain + 13 library + 9 source_resolver + 6 entrypoint + 4 UI) | ✅ Done |
| Hypothesis property tests in `test_filter_chain.py` | ❌ Missing |
| `home_view.py` `_ClipMetaWorker` async title fetch | ❌ Missing |
| `download_worker.py` deleted (orphaned, broken imports) | ❌ Still exists |
| All source code committed to git | ❌ Nothing committed beyond spec |
| `build/bin/ffmpeg.exe`, `ffprobe.exe` | ❌ Missing |
| `build/bin/libmpv-2.dll` | ❌ Missing |
| `KaraokeBuddy.exe` built and smoke-tested | ❌ Missing |

---

## File Map

| File | Action |
|------|--------|
| `src/karaoke_buddy/ui/download_worker.py` | Task 1 — delete |
| `tests/test_filter_chain.py` | Task 2 — append hypothesis property tests |
| `src/karaoke_buddy/ui/home_view.py` | Task 3 — add `_ClipMetaWorker` + async title fetch |
| `src/karaoke_buddy/` (all) | Task 4 — commit in logical chunks |
| `build/bin/ffmpeg.exe`, `ffprobe.exe` | Task 5 — download BtbN GPL build |
| `build/bin/libmpv-2.dll` | Task 6 — acquire + generate icon + build exe |
| `build/dist/KaraokeBuddy.exe` | Task 6 — produced by PyInstaller |

---

## Task 1: Delete orphaned download_worker.py

**Files:**
- Delete: `src/karaoke_buddy/ui/download_worker.py`

`download_worker.py` imports `ResolverError`, `resolve_local`, `resolve_youtube` from
`karaoke_buddy.core.source_resolver` — symbols that do not exist. The file is never imported by
`main_window.py` or any other module. `MainWindow` has its own `_ResolveThread`. Leaving it in
causes PyInstaller to attempt to import it and potentially fail.

- [ ] **Step 1: Confirm nothing imports it**

```bash
grep -r "download_worker" src/ tests/
```

Expected: no output. If any file imports it, read that file and remove the import before proceeding.

- [ ] **Step 2: Delete the file**

```bash
rm src/karaoke_buddy/ui/download_worker.py
```

- [ ] **Step 3: Verify tests still pass**

```bash
cd C:/Repo/karaoke-buddy
python -m pytest tests/test_filter_chain.py tests/test_library.py tests/test_source_resolver.py tests/test_entrypoint.py -q
```

Expected: `75 passed` (or whatever the current count is), 0 errors.

- [ ] **Step 4: Commit**

```bash
git add src/karaoke_buddy/ui/download_worker.py
git commit -m "chore: delete orphaned download_worker.py (broken imports, never imported)"
```

---

## Task 2: Add hypothesis property tests for filter_chain

**Files:**
- Modify: `tests/test_filter_chain.py`

Spec §9.1: *"Filter-chain builder — property tests across the full pitch × vocal-reduce matrix. An audio-math bug is silent and serious; this is the highest-priority test target."*

The existing 43 tests use `@pytest.mark.parametrize` over the full semitone range but not hypothesis. Hypothesis generates random combinations over the entire input space and shrinks failures to minimal cases — much stronger than a fixed parametrize grid. `hypothesis` is already in `pyproject.toml` dev dependencies.

- [ ] **Step 1: Append four hypothesis property tests to tests/test_filter_chain.py**

Open `tests/test_filter_chain.py` and append the following block **after the last existing test**:

```python
# ---------------------------------------------------------------------------
# Hypothesis property tests (spec §9.1)
# ---------------------------------------------------------------------------
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

Note: `math`, `re`, and `build_filter_chain` are already imported at the top of the file — no additional imports needed at the top level.

- [ ] **Step 2: Run test_filter_chain.py to confirm all tests (old + new) pass**

```bash
python -m pytest tests/test_filter_chain.py -v
```

Expected: **47+ tests pass** (43 original parametrized + 4 hypothesis tests × 100 hypothesis trials each shown as single entries). No failures.

If `ImportError: cannot import name 'given'`:
```bash
pip install hypothesis
```

- [ ] **Step 3: Lint and commit**

```bash
ruff check --fix tests/test_filter_chain.py && ruff format tests/test_filter_chain.py
git add tests/test_filter_chain.py
git commit -m "test: add hypothesis property tests for filter_chain (spec §9.1)"
```

---

## Task 3: Add async clipboard title preview to home_view.py

**Files:**
- Modify: `src/karaoke_buddy/ui/home_view.py`

Spec §5.1: *"if the clipboard holds a recognisable YouTube URL when the window gains focus, the Paste button shows an inline preview — 'Paste this? 🎵 {video title}' — populated via a cheap yt-dlp metadata-only call."*

The current `home_view.py` detects YouTube URLs in the clipboard but only shows a static label ("YouTube link detected — click Paste YouTube link to open"). It never fetches the actual title. This task adds `_ClipMetaWorker(QThread)` which fires a `yt_dlp extract_info(download=False)` call when a new URL lands in the clipboard, then updates the label with the real title. Results are per-worker (one worker per new URL), so re-polls of the same URL don't re-fetch.

- [ ] **Step 1: Replace src/karaoke_buddy/ui/home_view.py entirely**

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
            # else: same URL — label already up-to-date
        else:
            self._last_clip_url = ""
            self._clip_label.hide()

    def _on_clip_title(self, title: str, url: str) -> None:
        """Called via Signal — always on the Qt main thread."""
        if url == self._last_clip_url:  # guard against stale workers
            self._clip_label.setText(f"Paste this? \U0001F3B5  {title}")
            self._clip_label.show()
```

- [ ] **Step 2: Run the pure-Python test suite to confirm no regressions (import errors would show here)**

```bash
python -m pytest tests/test_filter_chain.py tests/test_library.py tests/test_source_resolver.py tests/test_entrypoint.py -q
```

Expected: `75 passed` (or current count), 0 errors.

- [ ] **Step 3: Lint and commit**

```bash
ruff check --fix src/karaoke_buddy/ui/home_view.py && ruff format src/karaoke_buddy/ui/home_view.py
git add src/karaoke_buddy/ui/home_view.py
git commit -m "feat: async clipboard title preview via yt-dlp metadata-only call (spec §5.1)"
```

---

## Task 4: Commit all remaining untracked source code

**Files:** Everything under `src/`, `tests/`, `build/`, `pyproject.toml`, `README.md`, `.gitignore`

All code was written but the git history has only one commit (the initial spec). This task creates atomic commits for logical groups.

- [ ] **Step 1: Check what's untracked**

```bash
git status
```

Review the list. Expected untracked groups: `src/karaoke_buddy/core/`, `src/karaoke_buddy/ui/` (excluding already-committed files), `src/karaoke_buddy/__init__.py`, `src/karaoke_buddy/__main__.py`, `tests/`, `build/`, `pyproject.toml`, `README.md`, `.gitignore`.

- [ ] **Step 2: Commit project config**

```bash
git add pyproject.toml .gitignore README.md
git commit -m "chore: pyproject.toml, .gitignore, README"
```

- [ ] **Step 3: Commit core modules**

```bash
git add src/karaoke_buddy/core/
git add src/karaoke_buddy/__init__.py
git commit -m "feat: core modules — filter_chain, library, source_resolver, player, exporter"
```

- [ ] **Step 4: Commit entry point**

```bash
git add src/karaoke_buddy/__main__.py
git commit -m "feat: entry point with rotating log, DLL discovery, startup check"
```

- [ ] **Step 5: Commit UI**

```bash
git add src/karaoke_buddy/ui/
git commit -m "feat: Qt UI — HomeView (async clipboard), LibraryView, PlayingView, MainWindow"
```

- [ ] **Step 6: Commit tests**

```bash
git add tests/
git commit -m "test: filter_chain (43 + hypothesis), library, source_resolver, entrypoint, exporter"
```

- [ ] **Step 7: Commit build tooling**

```bash
git add build/build.py build/bin/README.txt build/__init__.py build/create_fixture.py
git commit -m "chore: PyInstaller build script and fixture generator"
```

- [ ] **Step 8: Verify clean working tree**

```bash
git status
```

Expected: `nothing to commit, working tree clean`.

---

## Task 5: Acquire FFmpeg + run exporter integration tests

**Files produced:**
- `build/bin/ffmpeg.exe`
- `build/bin/ffprobe.exe`

The exporter integration tests (`tests/test_exporter.py`) run real FFmpeg on a 10-second synthetic clip. The filter chain uses `rubberband` for pitch shift — this is only in FFmpeg GPL static builds (not LGPL, not minimal builds).

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

- [ ] **Step 2: Verify rubberband filter is present**

```powershell
.\build\bin\ffmpeg.exe -filters 2>&1 | Select-String "rubberband"
```

Expected: one line containing `rubberband  A->A  Apply time-stretching and pitch-shifting`.

If nothing appears: you have the LGPL build, not GPL. Re-download and ensure the filename contains `gpl`. An LGPL build silently produces corrupted audio on export.

- [ ] **Step 3: Add build/bin to PATH for this shell session**

In Git Bash:
```bash
export PATH="$PATH:/c/Repo/karaoke-buddy/build/bin"
```

- [ ] **Step 4: Generate the test fixture if it doesn't exist**

```bash
python build/create_fixture.py
```

Expected: `tests/fixtures/sample_10s.mp4` created (a 10-second silent video, ~100 KB).

If `build/create_fixture.py` fails with `ffmpeg not found`: confirm Step 3 exported PATH correctly (`which ffmpeg` should return the path).

- [ ] **Step 5: Run exporter integration tests**

```bash
python -m pytest tests/test_exporter.py -v
```

Expected: **6 passed** in ~30 seconds. FFmpeg encoding takes a few seconds per test.

If `test_export_produces_valid_mp4` fails with `filter not found: rubberband`: confirm Step 2 output showed rubberband in the list.

If `test_no_partial_file_on_failure` fails (`.tmp` file not cleaned up after error): open `src/karaoke_buddy/core/exporter.py`, find the `export()` method, and confirm `tmp.unlink(missing_ok=True)` is called in both the stream-copy-fail branch and the re-encode-fail branch.

- [ ] **Step 6: Run the full test suite**

```bash
python -m pytest -v
```

Expected: **81 passed** (75 unit + 6 integration). Zero failures.

If any exporter test needed a code fix, commit it:

```bash
ruff check --fix src/karaoke_buddy/core/exporter.py && ruff format src/karaoke_buddy/core/exporter.py
git add src/karaoke_buddy/core/exporter.py
git commit -m "fix: exporter integration test failures"
```

---

## Task 6: Acquire libmpv-2.dll + build the .exe

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

**Option B — Chocolatey (if choco is installed):**

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

Any file under 1 MB is a failed download — re-download that file before continuing.

- [ ] **Step 3: Verify python-mpv can load the DLL**

```bash
export PATH="$PATH:/c/Repo/karaoke-buddy/build/bin"
python -c "import mpv; print('mpv import ok')"
```

Expected: `mpv import ok`. If you see `OSError: Cannot find mpv-2.dll …`: `build/bin` is not on PATH. Confirm Step 3 in Task 5 was run in this shell.

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

Expected: `icon.ico` written inside `src/karaoke_buddy/resources/`.

- [ ] **Step 6: Add --icon flag to build/build.py**

Open `build/build.py`. Find the `cmd` list (around line 41). Add the `--icon` entry **after the `--add-binary` lines and before the `--hidden-import` lines**:

```python
        "--icon", str(ROOT / "src" / "karaoke_buddy" / "resources" / "icon.ico"),
```

The complete `cmd` list after the edit:

```python
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--onefile",
        "--windowed",
        "--name",
        "KaraokeBuddy",
        "--distpath",
        str(DIST_DIR),
        "--workpath",
        str(ROOT / "build" / "work"),
        "--specpath",
        str(ROOT / "build"),
        "--add-binary",
        f"{BIN_DIR / 'ffmpeg.exe'};.",
        "--add-binary",
        f"{BIN_DIR / 'ffprobe.exe'};.",
        "--add-binary",
        f"{BIN_DIR / 'libmpv-2.dll'};.",
        "--icon",
        str(ROOT / "src" / "karaoke_buddy" / "resources" / "icon.ico"),
        "--hidden-import",
        "yt_dlp",
        "--hidden-import",
        "yt_dlp.extractor",
        str(ENTRY),
    ]
```

- [ ] **Step 7: Run the build**

```bash
python build/build.py
```

Expected output (last two lines):
```
...
Build complete: C:\Repo\karaoke-buddy\build\dist\KaraokeBuddy.exe
```

This takes 2–5 minutes. Common failures:

| Error | Fix |
|---|---|
| `Module not found: yt_dlp.extractor.youtube` | Add `"--hidden-import", "yt_dlp.extractor.youtube"` to cmd |
| `File not found: libmpv-2.dll` | Confirm `build/bin/libmpv-2.dll` exists and is non-empty |
| `File not found: icon.ico` | Re-run `python src/karaoke_buddy/resources/generate_icon.py` |
| `UPX is not available` | Harmless warning — ignore |
| Antivirus blocks the build | Temporarily disable real-time AV, or switch to `--onedir` mode in the cmd |

- [ ] **Step 8: Verify the output file is real**

```powershell
Get-Item build\dist\KaraokeBuddy.exe |
  Select-Object Name, @{N='MB';E={[math]::Round($_.Length/1MB,0)}}
```

Expected: `MB` > 100. Anything smaller means PyInstaller failed mid-way.

- [ ] **Step 9: Commit build tooling changes**

```bash
ruff check --fix build/build.py && ruff format build/build.py
git add build/build.py src/karaoke_buddy/resources/icon.ico
git commit -m "feat: add app icon + --icon flag to PyInstaller build"
```

---

## Task 7: Manual Smoke Test

Verify the exe works end-to-end. This covers spec §9.2 exactly.

> **Do not skip.** Automated tests do not cover the Player ↔ libmpv pipeline, the full
> download-to-play flow, or the async clipboard preview. A bug here means a bad experience for mom.

- [ ] **Step 1: First launch**

Double-click `build\dist\KaraokeBuddy.exe`.

Expected:
- Window opens in ~3 seconds (first launch unpacks to `%TEMP%\_MEI*`).
- Home screen shows: "KaraokeBuddy 🎤" title, two large buttons ("Open a video file", "Paste YouTube link"), empty library grid.
- No error dialogs appear.
- `logs\app.log` is created next to the exe.

If `"Installation is incomplete"` dialog: `ffmpeg.exe` or `ffprobe.exe` was not bundled. Add the missing `--add-binary` entry to `build/build.py` and rebuild (Task 6 Step 7).

If `OSError: Cannot find mpv-2.dll`: `libmpv-2.dll` was not bundled. Confirm the `--add-binary` line for it is present in `build/build.py` and rebuild.

- [ ] **Step 2: Open a local video and test pitch shift**

Use `tests\fixtures\sample_10s.mp4` (run `python build/create_fixture.py` first if it doesn't exist) or any `.mp4` on disk.

1. Click "Open a video file" → select the file.
2. Expected: loading indicator, then Playing view with video playing.
3. Move the **Song key** slider to **-3**.
   - Label reads "Lower by 3 keys".
   - Audio pitch drops noticeably within ~1 second. No stutter or restart.
4. Move **Silence the singer** to **50%**.
   - Audible centre-channel reduction.

- [ ] **Step 3: Save the current version**

1. Click "💾 Save this version".
2. Expected: file picker opens with a suggested name like `sample_10s (key -3).mp4` inside `Pitched Songs\` next to the exe.
3. Confirm the save.
4. Expected: progress bar fills and completes. Success dialog: "Saved to: …".
5. Open the saved file in VLC or Windows Media Player. Verify pitch is shifted down.

- [ ] **Step 4: Library persistence across restarts**

1. Click "← Back to library". The library shows a card for the video with "Lower by 3 keys".
2. Close the exe completely.
3. Reopen the exe.
4. Library card is still present. Click it.
5. Expected: video loads with pitch -3 and vocal reduce 50% restored.

- [ ] **Step 5: Clipboard title preview**

1. Copy `https://www.youtube.com/watch?v=dQw4w9WgXcQ` to the clipboard.
2. Bring the KaraokeBuddy window to focus (or wait up to 1 second for the timer tick).
3. Expected: label shows "🎵 Fetching title…" briefly, then updates to "Paste this? 🎵  Never Gonna Give You Up".
4. Click "Paste YouTube link" — dialog opens with the URL pre-filled.
5. Click OK. Download progress bar appears, then Playing view after download completes.

- [ ] **Step 6: YouTube video pitch shift + save**

(Requires internet connection — completes the §9.2 smoke checklist.)

1. From Step 5, adjust pitch to +2, save. Open saved file in VLC and confirm pitch is shifted up.

- [ ] **Step 7: Clean-machine test** *(required before any distribution)*

Copy `KaraokeBuddy.exe` to a Windows 11 machine (or VM snapshot) that has:
- No Python
- No FFmpeg in PATH
- No mpv / libmpv in PATH
- No Visual C++ Runtime

1. Double-click the exe.
2. Expected: app launches and Steps 1–6 all work identically.
3. If any DLL error: open Windows Event Viewer → Application log, find the DLL name, add it to `build/build.py`'s `--add-binary` list, and rebuild.

- [ ] **Step 8: Final commit**

```bash
ruff check --fix . && ruff format .
git add -p   # stage only real changes (e.g. if you added a hidden-import during troubleshooting)
git commit -m "feat: KaraokeBuddy v1 — all tests pass, exe smoke-tested on clean machine"
```

---

## Self-Review

### Spec Coverage

| Spec Requirement | Task |
|---|---|
| Open local video files (MP4, MKV, WebM, MOV) | Already written; verified Task 7 Step 2 |
| Open YouTube URLs (download → play) | Already written; verified Task 7 Step 5 |
| Live pitch shift −12..+12, tempo preserved | `filter_chain.py` rubberband; Task 2 property tests; Task 7 Step 2 |
| Live vocal reduction 0–100% centre subtraction | `filter_chain.py` pan filter; Task 7 Step 2 |
| Export to MP4 (stream-copy + AAC, libx264 fallback) | `exporter.py`; Task 5 integration tests; Task 7 Step 3 |
| Library with per-song sticky settings | `library.py`; existing unit tests; Task 7 Step 4 |
| Portable single-file .exe, no installer, no admin | Task 6 PyInstaller; Task 7 Step 7 |
| Plain-English errors, no stack traces | `main_window._show_error`; error table in spec §8 |
| Progress bars (download and export) | `_ResolveThread` + `ExportThread` signals |
| Atomic library writes + corruption recovery | `library.py`; existing unit tests |
| Log rotation 5 MB / 3 files | `__main__._setup_logging` RotatingFileHandler |
| Clipboard-aware paste button with real title fetch | Task 3 `_ClipMetaWorker`; verified Task 7 Step 5 |
| "Normal key / Lower by N keys / Higher by N keys" | `playing_view._pitch_label`; Task 7 Step 2 |
| Suggested export filename | `main_window._on_save`; Task 7 Step 3 |
| First-run: create cache/, logs/, library.json | `__main__.main` + `Library.__init__` |
| PyInstaller --onefile DLL discovery | `__main__._locate_bundled` + `_setup_dll_search_path` |
| `rubberband` in bundled FFmpeg | Task 5 Step 2 explicit verification |
| Property tests for filter chain (spec §9.1) | Task 2 hypothesis tests |
| Full automated test suite passing | Tasks 2, 3, 5 |
| Manual smoke test (spec §9.2) | Task 7 |
| Clean-machine test | Task 7 Step 7 |
| Conventional commits | Tasks 1–6 |

### Placeholder Scan

None — all steps contain exact commands, expected output, and complete replacement code.

### Type Consistency

- `build_filter_chain(pitch_semitones: int, vocal_reduce_percent: int) -> str` — same signature throughout `filter_chain.py`, `playing_view.py`, `main_window.py`, `test_filter_chain.py`. No drift.
- `_locate_bundled(name: str) -> Path | None` — in `__main__.py`, tested in `test_entrypoint.py`. ✅
- `_setup_dll_search_path() -> None` — in `__main__.py`, tested in `test_entrypoint.py`. Called in `main()` before any `import mpv`. ✅
- `_ClipMetaWorker.title_ready: Signal(str)` / `.fetch_failed: Signal()` — defined in Task 3, connected in `HomeView._check_clipboard`. ✅
- `LibraryEntry`, `SavedOutput` — unchanged from `library.py`, used in `main_window.py`, `home_view.py`, `library_view.py`, `test_library.py`. No drift. ✅
