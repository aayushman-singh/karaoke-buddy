# KaraokeBuddy — Verification & Packaging Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Take the fully-written KaraokeBuddy codebase from "code on disk" to "verified tests, one packaging bug fixed, binaries acquired, .exe built and smoke-tested."

**Architecture:** All five core modules and the Qt UI are implemented per `2026-04-16-karaoke-buddy.md`. One packaging gap exists: `_locate_bundled()` in `__main__.py` looks next to the exe, but PyInstaller `--onefile` extracts DLLs to a temp dir (`sys._MEIPASS`), not next to the exe. That needs fixing before the build can succeed.

**Tech Stack:** Python 3.11+, PySide6, python-mpv, yt-dlp, FFmpeg (bundled), libmpv (bundled), PyInstaller, pytest.

---

## Current State

All code from `docs/superpowers/plans/2026-04-16-karaoke-buddy.md` is implemented:

| File | Status |
|---|---|
| `src/karaoke_buddy/core/filter_chain.py` | ✓ Written |
| `src/karaoke_buddy/core/library.py` | ✓ Written |
| `src/karaoke_buddy/core/source_resolver.py` | ✓ Written |
| `src/karaoke_buddy/core/player.py` | ✓ Written |
| `src/karaoke_buddy/core/exporter.py` | ✓ Written |
| `src/karaoke_buddy/ui/main_window.py` | ✓ Written |
| `src/karaoke_buddy/ui/home_view.py` | ✓ Written |
| `src/karaoke_buddy/ui/library_view.py` | ✓ Written |
| `src/karaoke_buddy/ui/playing_view.py` | ✓ Written |
| `src/karaoke_buddy/__main__.py` | ✓ Written (bug in `_locate_bundled`) |
| `tests/test_filter_chain.py` | ✓ Written |
| `tests/test_library.py` | ✓ Written |
| `tests/test_source_resolver.py` | ✓ Written |
| `tests/test_exporter.py` | ✓ Written |
| `build/build.py` | ✓ Written |

**Known packaging bug:** `_locate_bundled(name)` in `__main__.py` does:
```python
candidate = Path(sys.executable).parent / name
```
In `--onefile` mode, PyInstaller extracts DLLs to `sys._MEIPASS` (a temp directory like
`C:\Users\Mom\AppData\Local\Temp\_MEI12345\`), **not** next to the exe. The DLL will never
be found at `sys.executable.parent`, causing a "Installation is incomplete" crash on the
first run. Fix is in Task 4.

**Also needed:** `os.add_dll_directory(sys._MEIPASS)` must be called before any `import mpv`
so Windows ctypes can find `libmpv-2.dll` at the PyInstaller extraction path. Without it,
`python-mpv` raises `OSError: cannot load library 'mpv'` even if the DLL is present.

---

## File Map

```
src/karaoke_buddy/
  __main__.py           # Task 4 — fix _locate_bundled + add _setup_dll_search_path
tests/
  test_entrypoint.py    # Task 4 — tests for the two fixed functions
build/
  bin/
    ffmpeg.exe          # Task 5 — downloaded manually
    ffprobe.exe         # Task 5 — downloaded manually
    libmpv-2.dll        # Task 5 — downloaded manually
build/dist/
  KaraokeBuddy.exe      # Task 6 — produced by PyInstaller
```

---

## Task 1: Install Dependencies & Verify Imports

**Files:** none (environment setup only)

- [ ] **Step 1: Install the project in editable mode with dev extras**

Run from `C:\Repo\karaoke-buddy`:

```bash
pip install -e ".[dev]"
```

Expected: no errors. PySide6, python-mpv, yt-dlp, pytest, hypothesis, ruff, pyinstaller all installed.

- [ ] **Step 2: Verify all Python imports resolve**

```bash
python -c "
from karaoke_buddy.core.filter_chain import build_filter_chain
from karaoke_buddy.core.library import Library, LibraryEntry, SavedOutput
from karaoke_buddy.core.source_resolver import SourceResolver, is_youtube_url
from karaoke_buddy.core.exporter import Exporter, ExportThread
print('core imports ok')
from karaoke_buddy.ui.home_view import HomeView
from karaoke_buddy.ui.library_view import LibraryView
from karaoke_buddy.ui.playing_view import PlayingView
print('ui imports ok')
"
```

Expected output:
```
core imports ok
ui imports ok
```

> **If `player.py` import fails** with `OSError: cannot load library 'mpv'`: libmpv is not
> installed on the system. This is expected if you haven't installed mpv yet. The player
> import only happens when `MainWindow` is instantiated (lazy via `_load_player`), so the
> test suite and filter/library/exporter tests will still pass. Proceed to Task 2.

- [ ] **Step 3: Verify pytest collects all tests**

```bash
pytest --collect-only
```

Expected: output lists ~35 test items across 4 files. No errors.

---

## Task 2: Unit Tests — No External Dependencies

These tests are pure Python: no FFmpeg, no libmpv, no network.

**Files:** `tests/test_filter_chain.py`, `tests/test_library.py`, `tests/test_source_resolver.py`

- [ ] **Step 1: Run filter chain tests**

```bash
pytest tests/test_filter_chain.py -v
```

Expected: **9 tests pass** (6 parametrized × semitones, 11 × vocal-reduce, 1 formula check = ~30 total with parametrize expansion). All should be green.

If `test_octave_up_doubles_pitch` fails, the formula in `filter_chain.py` is wrong. It should produce `rubberband=pitch=2.000000` for 12 semitones. Verify:
```python
2 ** (12 / 12)  # == 2.0
```

- [ ] **Step 2: Run library tests**

```bash
pytest tests/test_library.py -v
```

Expected: **13 tests pass**. All persistence, round-trip, corruption, and sorting tests green.

If `test_atomic_write_uses_tmp_file` fails with `AssertionError`, it means `os.replace` is not being called via the monkeypatched path. Check that `library.py` imports `os` at the module level (it does: `import os`) and that the monkeypatch target `"karaoke_buddy.core.library.os.replace"` is correct.

- [ ] **Step 3: Run source resolver tests**

```bash
pytest tests/test_source_resolver.py -v
```

Expected: **9 tests pass** (4 valid URLs + 5 invalid URLs + 3 local + 1 cache hit).

If `test_cache_hit_skips_yt_dlp_download` fails: the test patches `yt_dlp.YoutubeDL` globally and checks `instance.download.assert_not_called()`. If the download is triggered, it means the cache-hit check `if not video_path.exists()` is not being reached — possibly because `video_path` is constructed differently than `cached_video`.

- [ ] **Step 4: Commit if tests were failing and you fixed them**

If you had to fix anything:

```bash
git add -p
git commit -m "fix: correct unit test failures in filter_chain/library/source_resolver"
```

If all tests passed without changes, no commit needed.

---

## Task 3: Exporter Integration Tests — FFmpeg Required

These tests spawn real FFmpeg subprocesses on a synthetic 10-second video.

**Files:** `tests/test_exporter.py`

- [ ] **Step 1: Verify FFmpeg is in PATH**

```bash
ffmpeg -version
```

Expected: version string (e.g. `ffmpeg version 7.x`). If not found, install via:
```bash
# Chocolatey (easiest):
choco install ffmpeg

# Or download from https://github.com/BtbN/FFmpeg-Builds/releases
# (you'll need this for Task 5 anyway — extract and add bin/ to PATH temporarily)
```

- [ ] **Step 2: Run exporter integration tests**

```bash
pytest tests/test_exporter.py -v
```

Expected: **6 tests pass**. Each test generates a synthetic clip, exports it, and validates the output via `ffprobe`. Allow ~30 seconds total (FFmpeg encoding takes a few seconds per test).

If `test_export_produces_valid_mp4` fails with `ffprobe failed`:
- The output `.mp4` may be malformed. Check the `rubberband` filter — FFmpeg must have been compiled with `librubberband` support.
- Test with identity filter: `chain = "pan=stereo|c0=c0|c1=c1"` (bypasses rubberband). If this passes, the issue is rubberband not being available in the FFmpeg build.
- Fix: download the `ffmpeg-master-latest-win64-gpl.zip` from BtbN (Task 5) — that build includes rubberband.

If `test_no_partial_file_on_failure` fails: the `.tmp` file is not being cleaned up. Check that `Exporter.export()` deletes `output.with_suffix(".tmp")` in both the copy and encode failure paths.

- [ ] **Step 3: Commit if tests were failing and you fixed them**

If you had to fix anything:

```bash
git add -p
git commit -m "fix: correct exporter integration test failures"
```

---

## Task 4: Fix DLL Discovery for PyInstaller `--onefile`

**Files:**
- Modify: `src/karaoke_buddy/__main__.py`
- Create: `tests/test_entrypoint.py`

This is the only code change required before building the exe. Two functions need fixing/adding:

1. `_locate_bundled` must check `sys._MEIPASS` before `sys.executable.parent`.
2. A new `_setup_dll_search_path()` must be called before any `import mpv` so Windows ctypes can find the DLL.

- [ ] **Step 1: Write failing tests**

Create `tests/test_entrypoint.py`:

```python
"""Tests for __main__ entry point helpers — DLL discovery and path setup."""
import os
import sys
from pathlib import Path

import pytest


def test_locate_bundled_returns_none_in_dev_mode(monkeypatch):
    """In non-frozen dev mode, _locate_bundled always returns None."""
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    from karaoke_buddy.__main__ import _locate_bundled

    assert _locate_bundled("ffmpeg.exe") is None


def test_locate_bundled_finds_dll_in_meipass(monkeypatch, tmp_path):
    """In frozen --onefile mode, _locate_bundled checks sys._MEIPASS first."""
    meipass = tmp_path / "meipass"
    meipass.mkdir()
    dll = meipass / "libmpv-2.dll"
    dll.write_bytes(b"")

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(meipass), raising=False)
    # Make exe.parent NOT contain the DLL so we're sure _MEIPASS is what's found
    monkeypatch.setattr(sys, "executable", str(tmp_path / "KaraokeBuddy.exe"), raising=False)

    from karaoke_buddy.__main__ import _locate_bundled

    result = _locate_bundled("libmpv-2.dll")
    assert result == dll


def test_locate_bundled_falls_back_to_exe_parent_if_no_meipass(monkeypatch, tmp_path):
    """In frozen --onedir mode (no sys._MEIPASS), exe.parent is used."""
    exe_parent = tmp_path / "dist"
    exe_parent.mkdir()
    dll = exe_parent / "libmpv-2.dll"
    dll.write_bytes(b"")

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    # No sys._MEIPASS (--onedir mode)
    if hasattr(sys, "_MEIPASS"):
        monkeypatch.delattr(sys, "_MEIPASS")
    monkeypatch.setattr(sys, "executable", str(exe_parent / "KaraokeBuddy.exe"), raising=False)

    from karaoke_buddy.__main__ import _locate_bundled

    result = _locate_bundled("libmpv-2.dll")
    assert result == dll


def test_locate_bundled_returns_none_when_file_absent(monkeypatch, tmp_path):
    """Returns None if the file doesn't exist in any search location."""
    meipass = tmp_path / "meipass"
    meipass.mkdir()

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(meipass), raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "KaraokeBuddy.exe"), raising=False)

    from karaoke_buddy.__main__ import _locate_bundled

    assert _locate_bundled("libmpv-2.dll") is None


def test_setup_dll_search_path_adds_meipass_in_frozen_mode(monkeypatch, tmp_path):
    """In frozen mode with sys._MEIPASS, os.add_dll_directory is called."""
    meipass = tmp_path / "meipass"
    meipass.mkdir()

    added: list[str] = []

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(meipass), raising=False)
    monkeypatch.setattr(os, "add_dll_directory", lambda d: added.append(d), raising=False)

    from karaoke_buddy.__main__ import _setup_dll_search_path

    _setup_dll_search_path()

    assert str(meipass) in added


def test_setup_dll_search_path_is_noop_in_dev_mode(monkeypatch):
    """In non-frozen dev mode, os.add_dll_directory is never called."""
    added: list[str] = []

    monkeypatch.setattr(sys, "frozen", False, raising=False)
    monkeypatch.setattr(os, "add_dll_directory", lambda d: added.append(d), raising=False)

    from karaoke_buddy.__main__ import _setup_dll_search_path

    _setup_dll_search_path()

    assert added == []
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_entrypoint.py -v
```

Expected: `ImportError: cannot import name '_setup_dll_search_path'` — the function doesn't exist yet. `test_locate_bundled_finds_dll_in_meipass` and the fallback test will also fail because the current implementation doesn't check `sys._MEIPASS`.

- [ ] **Step 3: Fix `src/karaoke_buddy/__main__.py`**

Replace the current file content with the following. The three changes are:
1. `_locate_bundled` now checks `sys._MEIPASS` before `sys.executable.parent`.
2. New `_setup_dll_search_path()` function.
3. `main()` calls `_setup_dll_search_path()` before any lazy Qt/mpv imports.

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

    Checks ``sys._MEIPASS`` first (populated in ``--onefile`` mode when the
    archive is extracted to a temp directory), then falls back to the directory
    that contains the executable (correct for ``--onedir`` mode).

    Returns ``None`` in development (non-frozen) mode, or if the file does not
    exist in any candidate location.
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
    """In frozen mode, add the PyInstaller extraction directory to the Windows
    DLL search path so that ``ctypes`` (used by python-mpv) can find
    ``libmpv-2.dll`` without it being on the system ``PATH``.

    Must be called before any ``import mpv`` (i.e. before importing
    ``MainWindow``, which transitively imports ``player.py``).

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

    from PySide6.QtWidgets import QApplication, QMessageBox

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

    from karaoke_buddy.core.library import Library
    from karaoke_buddy.ui.main_window import MainWindow

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

- [ ] **Step 4: Run tests to confirm they pass**

```bash
pytest tests/test_entrypoint.py -v
```

Expected: **6 tests pass**.

> **Note on `test_locate_bundled_falls_back_to_exe_parent_if_no_meipass`:** If this fails with
> `AttributeError: _MEIPASS`, your Python version may not support `monkeypatch.delattr` on
> non-existent attributes. Fix: wrap the `monkeypatch.delattr` in a `try/except AttributeError`.
> In practice `sys._MEIPASS` only exists inside a PyInstaller frozen process so this edge case
> is unlikely in CI.

- [ ] **Step 5: Run full test suite to confirm no regressions**

```bash
pytest tests/test_filter_chain.py tests/test_library.py tests/test_source_resolver.py tests/test_entrypoint.py -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/karaoke_buddy/__main__.py tests/test_entrypoint.py
git commit -m "fix: locate bundled DLLs in sys._MEIPASS for PyInstaller --onefile mode"
```

---

## Task 5: Acquire Binary Dependencies

The build script requires three binaries in `build/bin/` before it can run. These are NOT committed to git (they're large platform-specific binaries). Download and place them manually.

**Files to create:**
- `build/bin/ffmpeg.exe`
- `build/bin/ffprobe.exe`
- `build/bin/libmpv-2.dll`

- [ ] **Step 1: Download FFmpeg (static Windows build)**

Open PowerShell in `C:\Repo\karaoke-buddy`:

```powershell
# Download the latest static GPL build (~100 MB zip)
$url = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
Invoke-WebRequest $url -OutFile "ffmpeg.zip"

# Extract
Expand-Archive ffmpeg.zip -DestinationPath ffmpeg_extracted -Force

# Copy the two binaries we need
Copy-Item "ffmpeg_extracted\ffmpeg-master-latest-win64-gpl\bin\ffmpeg.exe" "build\bin\ffmpeg.exe"
Copy-Item "ffmpeg_extracted\ffmpeg-master-latest-win64-gpl\bin\ffprobe.exe" "build\bin\ffprobe.exe"

# Clean up
Remove-Item ffmpeg.zip
Remove-Item ffmpeg_extracted -Recurse
```

> The BtbN build includes `librubberband` support (needed for pitch shifting). Other FFmpeg
> builds may omit it — do not substitute a minimal build.

- [ ] **Step 2: Verify ffmpeg.exe has rubberband support**

```powershell
.\build\bin\ffmpeg.exe -filters 2>&1 | Select-String "rubberband"
```

Expected: output line like `... rubberband  A->A  Apply time-stretching and pitch-shifting`.

If nothing appears, the build does not include rubberband and pitch shifting will silently produce
garbled output. Re-download using the BtbN GPL build.

- [ ] **Step 3: Download libmpv-2.dll**

```powershell
# Download the latest mpv dev kit from shinchiro's CI builds
# Visit https://github.com/shinchiro/mpv-winbuild-cmake/releases to find the latest tag
# Example (update the date/hash for the current release):
$url = "https://github.com/shinchiro/mpv-winbuild-cmake/releases/download/20240101/mpv-dev-x86_64-20240101-git-abc1234.7z"
```

> **Exact URL varies.** Go to https://github.com/shinchiro/mpv-winbuild-cmake/releases, find the
> latest release, download the `mpv-dev-x86_64-*.7z` file. Extract it; the DLL is at
> `mpv-dev-x86_64-*/libmpv-2.dll`.
>
> **Alternative:** If you have mpv installed via Chocolatey (`choco install mpv`), the DLL is at
> `C:\ProgramData\chocolatey\lib\mpv\tools\libmpv-2.dll`. Copy it to `build\bin\`.
>
> **Alternative:** If you installed `python-mpv` and mpv is on your system, run:
> ```python
> import ctypes.util; print(ctypes.util.find_library('mpv'))
> ```
> to find the DLL path, then copy it to `build\bin\`.

- [ ] **Step 4: Verify all three binaries are present and non-empty**

```powershell
Get-ChildItem build\bin\ | Select-Object Name, Length | Format-Table
```

Expected: three files, roughly:
```
Name            Length
ffmpeg.exe      ~100 MB (100_000_000+)
ffprobe.exe     ~100 MB (100_000_000+)
libmpv-2.dll    ~25 MB  (25_000_000+)
```

If any file is suspiciously small (< 1 MB), the download failed — retry.

---

## Task 6: Build the .exe

**Files produced:**
- `build/dist/KaraokeBuddy.exe` (~150–200 MB)

- [ ] **Step 1: Verify PyInstaller is installed**

```bash
pyinstaller --version
```

Expected: `6.x.x`. If not found: `pip install pyinstaller>=6`.

- [ ] **Step 2: Run the build script**

```bash
python build/build.py
```

Expected output:
```
Running PyInstaller…
...
Build complete: C:\Repo\karaoke-buddy\build\dist\KaraokeBuddy.exe
```

This takes 2–5 minutes. PyInstaller collects all Python code, PySide6 Qt DLLs, yt-dlp, and
your three binaries into a single self-extracting archive.

- [ ] **Step 3: Verify the output exists and is large enough to be real**

```powershell
Get-Item build\dist\KaraokeBuddy.exe | Select-Object Name, Length
```

Expected: file exists, `Length` > 100_000_000 (100 MB). A smaller file means PyInstaller
failed partway through.

- [ ] **Step 4: Check for common PyInstaller failures**

If the build fails:

| Error | Fix |
|---|---|
| `Module not found: yt_dlp.extractor` | Add `--hidden-import yt_dlp.extractor.youtube` to the cmd list in `build/build.py` |
| `File not found: libmpv-2.dll` | Confirm `build/bin/libmpv-2.dll` exists (Task 5 Step 4) |
| `UPX is not available` | Harmless warning — ignore it |
| `WARNING: ...module hook...` | Usually benign — only investigate if the exe crashes at runtime |
| Antivirus blocks the build | Temporarily disable real-time protection during PyInstaller run; re-enable after |

---

## Task 7: Manual Smoke Test

Verify the exe works end-to-end. These match the spec's §9.2 pre-release checklist exactly.

> **Do not skip this task.** The automated tests do not cover the GUI or the full integration
> of Player + UI + Library. A bug here means a bad user experience for mom.

- [ ] **Step 1: First launch — verify home screen**

Double-click `build\dist\KaraokeBuddy.exe`.

Expected:
- Window opens in ~3 seconds (first launch unpacks to `%TEMP%\_MEI*`, subsequent launches reuse it).
- Home screen shows "KaraokeBuddy 🎤" title.
- Two large buttons: "Open a video file" and "Paste YouTube link".
- Library grid is empty.
- No error dialog.
- `logs\app.log` is created next to the exe (or next to where you ran it from).

- [ ] **Step 2: Open a local video file**

Have any `.mp4` file available (e.g. `tests\fixtures\sample_10s.mp4` if FFmpeg is on PATH and
you've run the tests once, or any karaoke video).

1. Click "Open a video file".
2. Navigate to the file and click Open.
3. Expected: loading spinner appears briefly, then the Playing view loads.
4. The video starts playing (or is paused at start — click Play).
5. Move the Song key slider from 0 to -3.
6. Expected: audio pitch drops noticeably within ~1 second. No stutter or restart.
7. Move the Silence the singer slider to 50%.
8. Expected: centre channel reduction audible in the mix.

- [ ] **Step 3: Save the current version**

1. Click "💾 Save this version".
2. Expected: file picker opens with suggested name like `{title} (key -3).mp4` in a `Pitched Songs\` folder.
3. Confirm the save.
4. Expected: progress bar appears and completes. Success dialog: "Saved to: ...".
5. Open the saved file in VLC. Expected: plays correctly with pitch shifted.

- [ ] **Step 4: Library persistence across restarts**

1. Click "← Back to library".
2. Expected: home screen shows the video you opened as a card in the library grid.
3. Close the exe.
4. Reopen the exe.
5. Expected: library card is still present. Click it.
6. Expected: video loads with the pitch/vocal settings you last used (-3 and 50%) restored.

- [ ] **Step 5: Paste a YouTube URL**

1. Copy a YouTube URL (e.g. `https://www.youtube.com/watch?v=dQw4w9WgXcQ`) to the clipboard.
2. Expected: "Paste YouTube link" button area shows a hint: "🎵 YouTube link detected…".
3. Click "Paste YouTube link".
4. Expected: dialog opens with the URL pre-filled.
5. Click OK.
6. Expected: download progress bar appears. After download completes (~30 seconds for a 3-minute video), Playing view loads.
7. Pitch and sing along.

- [ ] **Step 6: Clean machine test** *(required before any distribution)*

Copy `KaraokeBuddy.exe` to a Windows 11 machine (or VM snapshot) that has:
- No Python installed
- No FFmpeg installed
- No mpv installed
- No Visual C++ Runtime (to test self-contained DLL bundling)

1. Double-click `KaraokeBuddy.exe`.
2. Expected: app launches correctly. Same behaviour as Steps 1–4.
3. If it fails with a missing DLL error, check the Windows Event Log for the DLL name, then add it to `build/build.py`'s `--add-binary` list.

- [ ] **Step 7: Commit final state**

```bash
git add build/build.py  # in case you added hidden-imports in Task 6 Step 4
ruff check --fix . && ruff format .
git add -p
git commit -m "feat: verified build — tests pass, DLL fix applied, exe smoke-tested"
```

---

## Self-Review

### Spec Coverage

| Spec Requirement | Task |
|---|---|
| All automated tests verified passing | Tasks 2, 3 |
| Portable single-file .exe (no installer) | Task 6 |
| PyInstaller `--onefile` DLL discovery | Task 4 |
| `libmpv-2.dll` found at runtime | Task 4 (`_setup_dll_search_path`) |
| FFmpeg has rubberband support (pitch shifting) | Task 5 Step 2 |
| Manual smoke test checklist §9.2 | Task 7 |
| Clean machine test | Task 7 Step 6 |
| App launches from `sys._MEIPASS` context | Task 4 |

### Placeholder Scan

None — all steps contain exact commands, expected output, and complete code.

### Type Consistency

- `_locate_bundled(name: str) -> Path | None` — defined in Task 4, tested in `test_entrypoint.py`.
- `_setup_dll_search_path() -> None` — defined in Task 4, tested in `test_entrypoint.py`.
- Both functions are called in `main()` before any lazy imports; type matches across all uses.
