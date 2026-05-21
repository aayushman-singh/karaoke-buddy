# KaraokeBuddy — Final Build Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Take the nearly-complete KaraokeBuddy codebase from "source untracked, three spec features missing, no binaries" to "all tests green, every spec feature implemented, portable .exe built and smoke-tested."

**Architecture:** Five core modules (`filter_chain`, `library`, `source_resolver`, `player`, `exporter`) plus Qt UI are already written. `__main__.py` DLL helpers are done. This plan deletes one orphaned file, fills three spec gaps (hypothesis tests, async clipboard title, commit history), then acquires binaries and produces the `.exe`.

**Tech Stack:** Python 3.14, PySide6 6.11, python-mpv, yt-dlp, FFmpeg static GPL (bundled), libmpv-2.dll (bundled), PyInstaller 6, pytest 9, hypothesis 6.

> **Prior plans:** Five previous plans exist in this folder. This plan supersedes all of them.
> **Already done:** `conftest.py` autouse fixture removed (tests pass), `_locate_bundled` +
> `_setup_dll_search_path` in `__main__.py`, `test_entrypoint.py` (6 passing tests).
> **Still needed:** Tasks 1–7 below, in order.

---

## File Map

| File | Action |
|------|--------|
| `src/karaoke_buddy/ui/download_worker.py` | Task 1 — delete (broken imports, never imported) |
| `tests/test_filter_chain.py` | Task 2 — append hypothesis property tests |
| `src/karaoke_buddy/ui/home_view.py` | Task 3 — add `_ClipMetaWorker` + async title fetch |
| All of `src/`, `tests/`, `build/`, `pyproject.toml` | Task 4 — commit everything |
| `build/bin/ffmpeg.exe`, `build/bin/ffprobe.exe` | Task 5 — download GPL static build |
| `build/bin/libmpv-2.dll` | Task 6 — acquire and verify |
| `build/dist/KaraokeBuddy.exe` | Task 6 — produced by PyInstaller |

---

## Task 1: Delete orphaned download_worker.py

**Files:**
- Delete: `src/karaoke_buddy/ui/download_worker.py`

`download_worker.py` imports `ResolverError`, `resolve_local`, `resolve_youtube` from
`karaoke_buddy.core.source_resolver`. Those symbols do not exist — the resolver exposes a
class-based API (`SourceResolver.resolve()`). The file is never imported anywhere. `MainWindow`
already has its own `_ResolveThread` covering the same responsibility.

- [ ] **Step 1: Confirm nothing imports download_worker.py**

```bash
grep -r "download_worker" src/ tests/
```

Expected: no output. If any file imports it, fix that import before deleting.

- [ ] **Step 2: Delete the file**

```bash
rm src/karaoke_buddy/ui/download_worker.py
```

- [ ] **Step 3: Confirm tests still pass**

```bash
cd C:/Repo/karaoke-buddy
python -m pytest tests/test_filter_chain.py tests/test_library.py tests/test_source_resolver.py tests/test_entrypoint.py -q
```

Expected: 75 passed, 0 errors.

---

## Task 2: Add hypothesis property tests for filter_chain

**Files:**
- Modify: `tests/test_filter_chain.py`

Spec §9.1: *"Filter-chain builder — property tests across the full pitch × vocal-reduce matrix.
An audio-math bug is silent and serious; this is the highest-priority test target."*

The existing tests use parametrize over specific values but not randomised hypothesis trials.
Hypothesis finds edge cases that a fixed grid misses and shrinks failures to minimal inputs.

- [ ] **Step 1: Append hypothesis property tests to tests/test_filter_chain.py**

Open `tests/test_filter_chain.py`. The file already has `import math` and `import re` at the top.
Append the following block **after the last existing test** (after line 63):

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

- [ ] **Step 2: Run test_filter_chain.py to confirm all tests pass**

```bash
python -m pytest tests/test_filter_chain.py -v
```

Expected: all original parametrized tests + 4 hypothesis tests pass. Hypothesis runs each
property test 100 times by default. Total count: 63 + 400 hypothesis examples = reported as
"63 passed" (hypothesis examples are fused into 4 test entries, each shown as PASSED).

If `ModuleNotFoundError: No module named 'hypothesis'`:
```bash
pip install hypothesis
```
Then re-run the test command.

---

## Task 3: Add async clipboard title preview (spec §5.1)

**Files:**
- Modify: `src/karaoke_buddy/ui/home_view.py`

Spec §5.1: *"if the clipboard holds a recognisable YouTube URL when the window gains focus, the
Paste button shows an inline preview — 'Paste this? 🎵 {video title}' — populated via a cheap
yt-dlp metadata-only call."*

The current implementation polls the clipboard every second and shows
`'🎵 YouTube link detected — click "Paste YouTube link" to open'` as static text. It never
fetches the title. Two missing pieces:

1. A `_ClipMetaWorker(QThread)` that fires `yt-dlp extract_info(download=False)` and emits
   `title_ready(str)` or `fetch_failed()`.
2. `_check_clipboard` tracks the last-seen URL so it only starts one worker per new URL. Stale
   worker results are discarded via a URL-equality guard.

`QThread` must be added to the PySide6 imports.

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

        title = QLabel("KaraokeBuddy \U0001f3a4")
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
                self._clip_label.setText("\U0001f3b5 Fetching title\u2026")
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
                        "\U0001f3b5 YouTube link detected"
                        " \u2014 click \u201cPaste YouTube link\u201d to open"
                    )
                )
                worker.finished.connect(worker.deleteLater)
                self._clip_meta_worker = worker
                worker.start()
            # else: same URL already shown, no re-fetch needed
        else:
            self._last_clip_url = ""
            self._clip_label.hide()

    def _on_clip_title(self, title: str, url: str) -> None:
        """Called via Signal on the Qt main thread — guard against stale workers."""
        if url == self._last_clip_url:
            self._clip_label.setText(f"Paste this? \U0001f3b5  {title}")
            self._clip_label.show()
```

- [ ] **Step 2: Run the pure-Python test suite to confirm no regressions**

```bash
python -m pytest tests/test_filter_chain.py tests/test_library.py tests/test_source_resolver.py tests/test_entrypoint.py -q
```

Expected: 75 passed, 0 errors. (No automated test covers `home_view.py` directly; regressions
would surface as import errors from other UI modules.)

- [ ] **Step 3: Lint**

```bash
ruff check --fix src/karaoke_buddy/ui/home_view.py && ruff format src/karaoke_buddy/ui/home_view.py
```

Expected: no errors or `All checks passed.`

---

## Task 4: Commit all source code

**Files:** Everything untracked under `src/`, `tests/`, `build/`, `pyproject.toml`, `.gitignore`

Nothing has been committed beyond the design spec. This task groups all source into three
logical commits.

- [ ] **Step 1: Verify working tree**

```bash
cd C:/Repo/karaoke-buddy
git status --short
```

Expected output (abridged):
```
?? .gitignore
?? README.md
?? build/
?? pyproject.toml
?? src/
?? tests/
```

- [ ] **Step 2: Commit core modules**

```bash
ruff check --fix src/karaoke_buddy/core/ && ruff format src/karaoke_buddy/core/
git add src/karaoke_buddy/core/ src/karaoke_buddy/__init__.py src/karaoke_buddy/__main__.py
git commit -m "feat: core modules — filter_chain, library, source_resolver, player, exporter"
```

- [ ] **Step 3: Commit UI**

```bash
ruff check --fix src/karaoke_buddy/ui/ && ruff format src/karaoke_buddy/ui/
git add src/karaoke_buddy/ui/ src/karaoke_buddy/resources/
git commit -m "feat: Qt UI — HomeView (async clipboard), LibraryView, PlayingView, MainWindow"
```

- [ ] **Step 4: Commit tests and build tooling**

```bash
ruff check --fix tests/ build/ && ruff format tests/ build/
git add tests/ build/ pyproject.toml .gitignore README.md
git commit -m "chore: tests, hypothesis property tests, and PyInstaller build script"
```

- [ ] **Step 5: Verify clean working tree**

```bash
git status
```

Expected: `nothing to commit, working tree clean`.

---

## Task 5: Download FFmpeg GPL + run exporter integration tests

**Files produced:**
- `build/bin/ffmpeg.exe`
- `build/bin/ffprobe.exe`

The exporter integration tests run real FFmpeg on a 10-second synthetic clip. The rubberband
pitch-shift filter is **only in GPL static builds** — LGPL builds omit it and the filter
silently produces corrupted audio.

- [ ] **Step 1: Download the GPL static build (PowerShell)**

```powershell
cd C:\Repo\karaoke-buddy
$url = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
Invoke-WebRequest $url -OutFile ffmpeg.zip
Expand-Archive ffmpeg.zip -DestinationPath ffmpeg_extracted -Force
Copy-Item "ffmpeg_extracted\ffmpeg-master-latest-win64-gpl\bin\ffmpeg.exe" "build\bin\ffmpeg.exe"
Copy-Item "ffmpeg_extracted\ffmpeg-master-latest-win64-gpl\bin\ffprobe.exe" "build\bin\ffprobe.exe"
Remove-Item ffmpeg.zip
Remove-Item ffmpeg_extracted -Recurse
```

- [ ] **Step 2: Verify rubberband is present**

```powershell
.\build\bin\ffmpeg.exe -filters 2>&1 | Select-String "rubberband"
```

Expected: one line containing `rubberband  A->A  Apply time-stretching and pitch-shifting`.

If no output: you downloaded the LGPL build. Re-download using the URL in Step 1 (contains
`-gpl` in the filename).

- [ ] **Step 3: Add build/bin to PATH for this shell session (Git Bash)**

```bash
export PATH="$PATH:/c/Repo/karaoke-buddy/build/bin"
```

Verify:
```bash
ffmpeg -version | head -1
```

Expected: `ffmpeg version N-...`

- [ ] **Step 4: Create the test fixture if missing**

```bash
ls tests/fixtures/
```

If `sample_10s.mp4` is not present (only `.gitkeep` is there):

```bash
python build/create_fixture.py
```

Expected: `Fixture created: tests/fixtures/sample_10s.mp4`

If `create_fixture.py` itself fails because ffmpeg is not found: ensure Step 3 was run in this
same shell session.

- [ ] **Step 5: Run exporter integration tests**

```bash
python -m pytest tests/test_exporter.py -v
```

Expected: **6 passed** in ~30 seconds.

Common failures:

| Error | Cause | Fix |
|---|---|---|
| `filter not found: rubberband` | LGPL build | Re-download GPL build (Step 1) |
| `FileNotFoundError` for ffmpeg | Not on PATH | Re-run Step 3 in this shell |
| `test_no_partial_file_on_failure` FAIL | `.tmp` not cleaned up | Open `exporter.py`, confirm `tmp.unlink(missing_ok=True)` is in both the stream-copy-fail and re-encode-fail branches |

- [ ] **Step 6: Run the full test suite**

```bash
python -m pytest -v
```

Expected: **81 passed**, 0 failures, 0 errors.

(75 unit + 6 integration. The count is higher than before Task 2 because hypothesis now adds
4 property tests.)

---

## Task 6: Acquire libmpv-2.dll + build the .exe

**Files produced:**
- `build/bin/libmpv-2.dll`
- `build/dist/KaraokeBuddy.exe`

- [ ] **Step 1: Get libmpv-2.dll**

**Option A — check current Python environment first:**

```bash
python -c "
import ctypes.util, shutil, pathlib
dll = ctypes.util.find_library('mpv')
if dll:
    shutil.copy(dll, 'build/bin/libmpv-2.dll')
    print('Copied from:', dll)
else:
    print('Not found — use Option B')
"
```

**Option B — manual download:**

1. Go to `https://github.com/shinchiro/mpv-winbuild-cmake/releases`
2. Download the latest `mpv-dev-x86_64-*.7z`
3. Extract; copy `libmpv-2.dll` to `build\bin\libmpv-2.dll`

- [ ] **Step 2: Verify all three binaries are present and non-empty**

```powershell
Get-ChildItem build\bin\ |
  Where-Object { $_.Name -ne "README.txt" } |
  Select-Object Name, @{N='MB';E={[math]::Round($_.Length/1MB,1)}}
```

Expected:

```
Name            MB
ffmpeg.exe     ~100
ffprobe.exe    ~100
libmpv-2.dll   ~25
```

Any file under 1 MB is a failed download — re-acquire it.

- [ ] **Step 3: Verify python-mpv can load the DLL**

```bash
export PATH="$PATH:/c/Repo/karaoke-buddy/build/bin"
python -c "import mpv; print('mpv import ok')"
```

Expected: `mpv import ok`.

If `OSError: Cannot find mpv-2.dll …`: `build/bin` is not on PATH in this shell — re-run the
export above.

- [ ] **Step 4: Verify PyInstaller is installed**

```bash
pyinstaller --version
```

Expected: `6.x.x`. If missing:
```bash
pip install "pyinstaller>=6"
```

- [ ] **Step 5: Generate the app icon**

```bash
pip install Pillow
python src/karaoke_buddy/resources/generate_icon.py
```

Expected: `Icon written to …/resources/icon.ico`

If the script does not exist, create `src/karaoke_buddy/resources/icon.ico` by running:

```python
# one-liner alternative using Pillow
python -c "
from PIL import Image, ImageDraw
img = Image.new('RGBA', (256, 256), (30, 30, 30, 255))
d = ImageDraw.Draw(img)
d.ellipse([40, 40, 216, 216], fill=(100, 180, 255, 255))
d.polygon([(90, 80), (90, 176), (186, 128)], fill=(255, 255, 255, 255))
img.save('src/karaoke_buddy/resources/icon.ico', format='ICO', sizes=[(256,256),(64,64),(32,32),(16,16)])
print('icon.ico written')
"
```

- [ ] **Step 6: Add --icon flag to build/build.py**

Open `build/build.py`. The `cmd` list currently ends with two `--hidden-import` entries and
`str(ENTRY)`. Insert the `--icon` line after the last `--add-binary` entry and before the
first `--hidden-import` entry:

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

Expected output ends with:
```
Build complete: C:\Repo\karaoke-buddy\build\dist\KaraokeBuddy.exe
```

Takes 2–5 minutes. Common failures:

| Error | Fix |
|---|---|
| `Module not found: yt_dlp.extractor.youtube` | Add `"--hidden-import", "yt_dlp.extractor.youtube"` to cmd and rebuild |
| `File not found: libmpv-2.dll` | Check `build/bin/libmpv-2.dll` exists and is non-empty |
| `UPX is not available` | Harmless warning — ignore |
| AV blocks the exe | Temporarily disable real-time AV, or switch to `--onedir` mode in build.py |

- [ ] **Step 8: Verify the output size**

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

## Task 7: Manual smoke test (spec §9.2)

This task maps directly to the spec §9.2 pre-release checklist. Do not skip — automated tests
do not exercise the Player ↔ libmpv pipeline, the full download-to-play flow, or the async
clipboard preview.

- [ ] **Step 1: First launch**

Double-click `build\dist\KaraokeBuddy.exe`.

Expected:
- Window opens in ~3 seconds (first launch unpacks to `%TEMP%\_MEI*`).
- Home screen: "KaraokeBuddy 🎤" title, two large buttons, empty library grid.
- No error dialogs.
- `logs\app.log` created next to the exe.

If `"Installation is incomplete"`: `ffmpeg.exe` or `ffprobe.exe` was not bundled. Confirm the
`--add-binary` entries in `build/build.py` use `;.` (not `;bin` or `;ffmpeg`) and rebuild.

If `OSError: Cannot find mpv-2.dll`: `libmpv-2.dll` was not bundled. Check its `--add-binary`
line is present in `build/build.py` and rebuild.

- [ ] **Step 2: Open a local video, test pitch shift + vocal reduce**

Use `tests\fixtures\sample_10s.mp4` or any MP4 on disk.

1. Click "Open a video file" → select the file.
2. Playing view appears; playback starts.
3. Move the **Song key** slider to **-3**.
   - Label reads `"Lower by 3 keys"`.
   - Audio pitch drops noticeably within ~1 second. No stutter, no restart.
4. Move **Silence the singer** to **50%**.
   - Centre-channel audio audibly reduces.

- [ ] **Step 3: Save the current version**

1. Click "💾 Save this version".
2. File picker opens — suggested name `sample_10s (key -3).mp4` inside `Pitched Songs\`.
3. Confirm.
4. Progress bar completes. Success dialog shows saved path.
5. Open the saved file in VLC; confirm pitch is shifted down.

- [ ] **Step 4: Library persistence across restarts**

1. Click "← Back to library". Card for the video appears with "Lower by 3 keys" hint.
2. Close the exe.
3. Reopen the exe.
4. Card is still present. Click it.
5. Video loads with pitch -3 and vocal reduce 50% restored.

- [ ] **Step 5: Clipboard title preview**

1. Copy `https://www.youtube.com/watch?v=dQw4w9WgXcQ` to clipboard.
2. Bring the app to focus (or wait up to 1 second for the timer).
3. Expected: label shows `"🎵 Fetching title…"` briefly, then `"Paste this? 🎵  Never Gonna Give You Up"`.
4. Click "Paste YouTube link" — dialog opens with URL pre-filled. Click OK.
5. Download progress bar appears; Playing view after download completes.

- [ ] **Step 6: YouTube video pitch shift + save**

1. From Step 5, adjust pitch, save. VLC confirms shifted audio.

- [ ] **Step 7: Clean-machine test (required before any distribution)**

Copy `KaraokeBuddy.exe` to a Windows 11 machine (or VM snapshot) with **no Python, no FFmpeg
in PATH, no mpv in PATH, no Visual C++ Runtime**.

1. Double-click the exe.
2. App launches; all of Steps 1–6 work identically.
3. If any DLL error: open the Windows Event Log, find the DLL name, add it to
   `build/build.py`'s `--add-binary` list, rebuild, and re-test.

- [ ] **Step 8: Final commit**

```bash
ruff check --fix . && ruff format .
git add -p   # stage only real changes (e.g. if you added a hidden-import to fix a bundling issue)
git commit -m "feat: KaraokeBuddy v1 — all tests pass, exe smoke-tested on clean machine"
```

---

## Self-Review

### Spec Coverage

| Spec Requirement | Task |
|---|---|
| Open local video files (MP4, MKV, WebM, MOV) | Code written; Task 7 Step 2 |
| Open YouTube URLs (download → play) | Code written; Task 7 Step 5 |
| Live pitch shift −12..+12, tempo preserved | `filter_chain.py` rubberband; Task 2 property tests; Task 7 Step 2 |
| Live vocal reduction 0–100% centre subtraction | `filter_chain.py` pan; Task 7 Step 2 |
| Export to MP4 (stream-copy + AAC, libx264 fallback) | `exporter.py`; Task 5 integration tests; Task 7 Step 3 |
| Library with per-song sticky settings | `library.py`; existing unit tests; Task 7 Step 4 |
| Portable single-file .exe, no installer, no admin | Task 6 PyInstaller; Task 7 Step 7 |
| Plain-English errors, no stack traces | `main_window._show_error`; spec §8 error table |
| Progress bars (download and export) | `_ResolveThread` + `ExportThread` signals |
| Atomic library writes, corruption recovery | `library.py`; existing unit tests |
| Log rotation 5 MB / 3 files | `__main__._setup_logging` RotatingFileHandler |
| Clipboard-aware Paste button with live title fetch | Task 3 `_ClipMetaWorker`; Task 7 Step 5 |
| "Normal key / Lower by N keys / Higher by N keys" | `playing_view._pitch_label`; Task 7 Step 2 |
| Suggested export filename | `main_window._on_save`; Task 7 Step 3 |
| First-run: create cache/, logs/, library.json | `__main__.main` + `Library.__init__` |
| PyInstaller --onefile DLL discovery | Already done — `_locate_bundled` + `_setup_dll_search_path` |
| `rubberband` in bundled FFmpeg | Task 5 Step 2 explicit verification |
| Property tests for filter chain (spec §9.1) | Task 2 hypothesis tests |
| Full automated test suite passing | Tasks 1, 2, 5 |
| Manual smoke test (spec §9.2) | Task 7 |
| Clean-machine test | Task 7 Step 7 |
| Conventional commits | Tasks 1–6 |

### Placeholder Scan

None — every step has exact commands, expected output, and complete replacement code.

### Type Consistency

- `build_filter_chain(pitch_semitones: int, vocal_reduce_percent: int) -> str` — same signature
  used in `filter_chain.py`, `playing_view.py`, `main_window.py`, `test_filter_chain.py`. No drift.
- `_ClipMetaWorker.title_ready: Signal(str)` / `.fetch_failed: Signal()` — defined in Task 3,
  connected in `HomeView._check_clipboard`. Name matches exactly in both places.
- `_locate_bundled(name: str) -> Path | None` — already in `__main__.py`, tested in
  `test_entrypoint.py`. Not touched by this plan.
- `LibraryEntry`, `SavedOutput` — unchanged from `library.py`, used across `main_window.py`,
  `home_view.py`, `library_view.py`, `test_library.py`. No drift.
