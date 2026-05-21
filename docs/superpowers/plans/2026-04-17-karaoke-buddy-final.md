# KaraokeBuddy — Final Verification & Ship Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Take the fully-written KaraokeBuddy codebase from "code on disk, all tests broken" to "all tests green, DLL bug fixed, .exe built and smoke-tested."

**Architecture:** All five core modules and the Qt UI are already implemented (filter_chain, library, source_resolver, player, exporter) and wired through MainWindow. Three things block a working build: a conftest fixture that crashes every test, a PyInstaller DLL-path bug in `__main__.py`, and missing binary dependencies in `build/bin/`.

**Tech Stack:** Python 3.14, PySide6 6.11, python-mpv 1.0.8, yt-dlp, FFmpeg (bundled), libmpv (bundled), PyInstaller, pytest 9.

---

## Current State Snapshot

| Item | Status |
|------|--------|
| `src/karaoke_buddy/core/` — all 5 modules | ✓ Written |
| `src/karaoke_buddy/ui/` — all 4 view files + main_window | ✓ Written |
| `src/karaoke_buddy/__main__.py` | ✓ Written (bug in `_locate_bundled`) |
| `tests/test_filter_chain.py` | ✓ Written — **fails at setup** |
| `tests/test_library.py` | ✓ Written — **fails at setup** |
| `tests/test_source_resolver.py` | ✓ Written — **fails at setup** |
| `tests/test_exporter.py` | ✓ Written — **fails at setup** |
| `tests/test_entrypoint.py` | ✗ Does not exist |
| `build/build.py` | ✓ Written |
| `build/bin/ffmpeg.exe` | ✗ Missing |
| `build/bin/ffprobe.exe` | ✗ Missing |
| `build/bin/libmpv-2.dll` | ✗ Missing |
| Git commits | Only initial spec commit |

**Root cause of all 69 test failures:** `tests/conftest.py` declares `sample_video` as a
`scope="session", autouse=True` fixture that runs `ffmpeg` unconditionally — even for
`test_filter_chain.py` which never needs a video file. Because `ffmpeg` is not in `PATH`,
every test crashes at the setup phase with `FileNotFoundError`.

---

## File Map

```
tests/
  conftest.py                   # Task 1 — remove autouse; fixture deleted
  test_entrypoint.py            # Task 3 — new file
src/karaoke_buddy/
  __main__.py                   # Task 3 — fix _locate_bundled + add _setup_dll_search_path
build/
  bin/
    ffmpeg.exe                  # Task 4 — downloaded manually
    ffprobe.exe                 # Task 4 — downloaded manually
    libmpv-2.dll                # Task 5 — downloaded manually
build/dist/
  KaraokeBuddy.exe              # Task 6 — produced by PyInstaller
```

---

## Task 1: Fix conftest.py — unblock all unit tests

**Files:**
- Modify: `tests/conftest.py`

The `sample_video` fixture in `conftest.py` has `autouse=True`, causing it to run for
every test session. It calls `ffmpeg` to generate a fixture file. Since `ffmpeg` is not in
`PATH`, all 69 tests crash at setup before any test body runs.

`test_exporter.py` defines its own local `sample_video` fixture — the conftest version is
unused by any test. The fix is to delete the fixture entirely.

- [ ] **Step 1: Write the fixed conftest.py**

Replace the entire file:

```python
"""Shared pytest fixtures."""
```

That's it. An empty conftest with just the module docstring. No fixtures are shared across
test files.

- [ ] **Step 2: Run the pure-Python unit tests to confirm they now collect and pass**

```bash
cd C:\Repo\karaoke-buddy
python -m pytest tests/test_filter_chain.py tests/test_library.py tests/test_source_resolver.py -v
```

Expected output (abbreviated):
```
tests/test_filter_chain.py::test_zero_pitch_zero_vocal_has_unity_pitch PASSED
tests/test_filter_chain.py::test_zero_pitch_zero_vocal_has_zero_mix PASSED
tests/test_filter_chain.py::test_octave_up_doubles_pitch PASSED
tests/test_filter_chain.py::test_octave_down_halves_pitch PASSED
tests/test_filter_chain.py::test_full_vocal_reduce_sets_mix_to_0_5 PASSED
tests/test_filter_chain.py::test_half_vocal_reduce PASSED
... (43 filter_chain + 13 library + 9 source_resolver) ...
===== 65 passed in X.XXs =====
```

If any test fails (not errors — actual FAIL), investigate before proceeding.
Expected failure modes and fixes:

| Failing test | Likely cause | Fix |
|---|---|---|
| `test_octave_up_doubles_pitch` | Wrong formula | Verify `2 ** (12/12) == 2.0` in filter_chain.py |
| `test_atomic_write_uses_tmp_file` | Monkeypatch target wrong | Confirm library.py does `import os` at module level |
| `test_cache_hit_skips_yt_dlp_download` | Cache path mismatch | Check `video_path = video_dir / "video.mp4"` in source_resolver.py |
| `test_list_is_sorted_most_recently_opened_first` | Sort direction | Verify `reverse=True` in `Library.list()` |

- [ ] **Step 3: Commit**

```bash
git add tests/conftest.py
git commit -m "fix: remove autouse session fixture that blocked all tests (ffmpeg not in PATH)"
```

---

## Task 2: Commit all existing source code

**Files:** Everything under `src/`, `tests/` (except `test_entrypoint.py` which comes in Task 3), `build/build.py`, `pyproject.toml`

The repo has only one commit (the initial spec). All code was written but never committed.

- [ ] **Step 1: Verify working tree is clean after the conftest fix**

```bash
git status
```

Expected: modified `tests/conftest.py` (already staged from Task 1) plus many untracked files in `src/`, `tests/`, `build/`.

- [ ] **Step 2: Stage and commit core modules**

```bash
git add src/karaoke_buddy/core/
git add src/karaoke_buddy/__init__.py
git commit -m "feat: core modules — filter_chain, library, source_resolver, player, exporter"
```

- [ ] **Step 3: Stage and commit UI**

```bash
git add src/karaoke_buddy/ui/
git add src/karaoke_buddy/__main__.py
git commit -m "feat: Qt UI — HomeView, LibraryView, PlayingView, MainWindow, entry point"
```

- [ ] **Step 4: Stage and commit tests and build tooling**

```bash
git add tests/
git add build/build.py build/bin/README.txt build/__init__.py build/create_fixture.py
git add pyproject.toml
git commit -m "chore: tests (filter_chain, library, source_resolver, exporter) and PyInstaller build script"
```

---

## Task 3: Fix PyInstaller DLL discovery + write test_entrypoint.py

**Files:**
- Modify: `src/karaoke_buddy/__main__.py`
- Create: `tests/test_entrypoint.py`

In `--onefile` mode, PyInstaller extracts the archive to a temp directory stored in
`sys._MEIPASS` — not next to the `.exe`. The current `_locate_bundled` checks only
`Path(sys.executable).parent`, so it will never find `ffmpeg.exe` or `libmpv-2.dll` at
runtime, causing an "Installation is incomplete" crash on the very first launch.

Additionally, `os.add_dll_directory(sys._MEIPASS)` must be called before any `import mpv`
so Windows `ctypes` can find `libmpv-2.dll` without it being on `%PATH%`.

- [ ] **Step 1: Write the failing tests**

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
    # exe.parent does NOT contain the DLL — we want _MEIPASS to win
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
python -m pytest tests/test_entrypoint.py -v
```

Expected: `ImportError: cannot import name '_setup_dll_search_path'` for the last two tests.
`test_locate_bundled_finds_dll_in_meipass` and the fallback test will also fail because the
current implementation never checks `sys._MEIPASS`.

- [ ] **Step 3: Replace `src/karaoke_buddy/__main__.py` with the fixed version**

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

- [ ] **Step 4: Run entrypoint tests to confirm they pass**

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

> **If `test_locate_bundled_falls_back_to_exe_parent_if_no_meipass` fails** with
> `AttributeError: _MEIPASS`: Your Python version may handle `monkeypatch.delattr` differently
> for attributes that don't exist at module load time. Wrap with:
> ```python
> try:
>     monkeypatch.delattr(sys, "_MEIPASS")
> except AttributeError:
>     pass
> ```

- [ ] **Step 5: Run the full no-FFmpeg test suite to confirm no regressions**

```bash
python -m pytest tests/test_filter_chain.py tests/test_library.py tests/test_source_resolver.py tests/test_entrypoint.py -v
```

Expected: **71 tests pass** (43 filter_chain + 13 library + 9 source_resolver + 6 entrypoint).

- [ ] **Step 6: Lint and commit**

```bash
ruff check --fix . && ruff format .
git add src/karaoke_buddy/__main__.py tests/test_entrypoint.py
git commit -m "fix: locate bundled DLLs in sys._MEIPASS for PyInstaller --onefile mode"
```

---

## Task 4: Acquire FFmpeg + run exporter integration tests

**Files produced:**
- `build/bin/ffmpeg.exe`
- `build/bin/ffprobe.exe`

The exporter integration tests (`test_exporter.py`) generate a 10-second synthetic clip and
run real FFmpeg on it. The `Exporter` class calls `"ffmpeg"` from `PATH` by default when no
`ffmpeg_exe` is given.

> **Why the BtbN GPL build specifically:** FFmpeg must be compiled with `librubberband` support
> for pitch shifting. Most minimal builds omit it. The BtbN GPL static build includes it.

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

Expected: two files appear in `build\bin\`, each ~100 MB.

- [ ] **Step 2: Verify ffmpeg.exe has rubberband support**

```powershell
.\build\bin\ffmpeg.exe -filters 2>&1 | Select-String "rubberband"
```

Expected: one output line containing `rubberband  A->A  Apply time-stretching and pitch-shifting`.

If nothing appears, this is not the GPL build — re-download. A build without rubberband will
silently produce corrupted audio in the exported files.

- [ ] **Step 3: Add build/bin to PATH for this shell session and run exporter tests**

In Git Bash:
```bash
export PATH="$PATH:/c/Repo/karaoke-buddy/build/bin"
python -m pytest tests/test_exporter.py -v
```

Expected: **6 tests pass**. Allow ~30 seconds (FFmpeg encoding takes a few seconds per test).

If `test_export_produces_valid_mp4` fails with `rubberband filter not found`:
- Confirm Step 2 showed rubberband in the filter list
- Try running FFmpeg manually: `ffmpeg -af rubberband=pitch=1.0 -i NUL -f null NUL 2>&1`

If `test_no_partial_file_on_failure` fails (`.tmp` file not cleaned up):
- Check that `Exporter.export()` calls `tmp.unlink()` in both the copy-fail and encode-fail
  branches in `core/exporter.py`.

- [ ] **Step 4: Commit (only if you had to fix any code)**

If you fixed code to make tests pass:
```bash
ruff check --fix . && ruff format .
git add -p
git commit -m "fix: exporter integration test failures"
```

If all tests passed without changes, no commit needed.

---

## Task 5: Acquire libmpv-2.dll + build the .exe

**Files produced:**
- `build/bin/libmpv-2.dll`
- `build/dist/KaraokeBuddy.exe`

- [ ] **Step 1: Get libmpv-2.dll**

**Option A — Chocolatey (easiest if choco is installed):**
```powershell
choco install mpv
Copy-Item "C:\ProgramData\chocolatey\lib\mpv\tools\libmpv-2.dll" "build\bin\libmpv-2.dll"
```

**Option B — Find it from python-mpv's bundled search:**
```python
import ctypes.util, shutil
dll_path = ctypes.util.find_library("mpv")
if dll_path:
    shutil.copy(dll_path, "build/bin/libmpv-2.dll")
    print(f"Copied from: {dll_path}")
else:
    print("Not found in PATH — download manually")
```
Run with: `python -c "import ctypes.util, shutil; ..."` (paste the snippet above)

**Option C — Manual download:**
Go to https://github.com/shinchiro/mpv-winbuild-cmake/releases and download the latest
`mpv-dev-x86_64-*.7z`. Extract it; the DLL is at `mpv-dev-x86_64-*/libmpv-2.dll`.

- [ ] **Step 2: Add libmpv-2.dll directory to PATH for development**

```bash
# Git Bash — add build/bin to PATH (covers all three binaries)
export PATH="$PATH:/c/Repo/karaoke-buddy/build/bin"
```

Verify python-mpv can now find it:
```bash
python -c "import mpv; print('mpv import ok')"
```

Expected: `mpv import ok` with no errors.

If you see `OSError: Cannot find mpv-1.dll, mpv-2.dll or libmpv-2.dll`: the DLL is not in
PATH. Confirm `build/bin/libmpv-2.dll` exists and that `build/bin` is in `PATH`.

- [ ] **Step 3: Verify all three binaries are present and non-empty**

```powershell
Get-ChildItem build\bin\ | Select-Object Name, @{N='MB';E={[math]::Round($_.Length/1MB,1)}} | Format-Table
```

Expected:
```
Name            MB
ffmpeg.exe      ~100
ffprobe.exe     ~100
libmpv-2.dll    ~25
```

Any file under 1 MB is a failed download — re-download that file.

- [ ] **Step 4: Run the full test suite one final time**

```bash
export PATH="$PATH:/c/Repo/karaoke-buddy/build/bin"
python -m pytest -v
```

Expected: **77 tests pass** (71 from Task 3 + 6 exporter integration tests). Zero failures.

- [ ] **Step 5: Verify PyInstaller is installed**

```bash
pyinstaller --version
```

Expected: `6.x.x`. If not found:
```bash
pip install pyinstaller>=6
```

- [ ] **Step 6: Run the build script**

```bash
python build/build.py
```

Expected output:
```
Running PyInstaller…
...
Build complete: C:\Repo\karaoke-buddy\build\dist\KaraokeBuddy.exe
```

This takes 2–5 minutes.

- [ ] **Step 7: Verify the output file is real**

```powershell
Get-Item build\dist\KaraokeBuddy.exe | Select-Object Name, @{N='MB';E={[math]::Round($_.Length/1MB,0)}}
```

Expected: `Length` > 100 MB. Smaller means PyInstaller failed partway through.

Common build failures and fixes:

| Error | Fix |
|---|---|
| `Module not found: yt_dlp.extractor` | Add `"--hidden-import", "yt_dlp.extractor.youtube"` to the cmd list in `build/build.py` |
| `File not found: libmpv-2.dll` | Confirm `build/bin/libmpv-2.dll` exists (Step 3 above) |
| `UPX is not available` | Harmless warning — ignore it |
| Antivirus blocks the build | Temporarily disable real-time AV during the PyInstaller run |

- [ ] **Step 8: Commit final state**

```bash
ruff check --fix . && ruff format .
git add build/build.py  # in case you added hidden-imports during troubleshooting
git commit -m "feat: verified build — all tests pass, DLL fix applied, exe produced"
```

---

## Task 6: Manual Smoke Test

Verify the exe works end-to-end. This matches spec §9.2 exactly.

> **Do not skip.** Automated tests do not cover the GUI, the full Player ↔ UI integration,
> or the actual libmpv audio pipeline. A bug here means a bad experience for mom.

- [ ] **Step 1: First launch**

Double-click `build\dist\KaraokeBuddy.exe`.

Expected:
- Window opens in ~3 seconds (first launch unpacks to `%TEMP%\_MEI*`).
- Home screen: "KaraokeBuddy 🎤" title, two large buttons ("Open a video file",
  "Paste YouTube link"), empty library grid.
- No error dialogs.
- `logs\app.log` created next to the exe.

If you see "Installation is incomplete": `ffmpeg.exe` or `ffprobe.exe` was not bundled.
Add `--hidden-import` entries and rebuild.

If you see `OSError: Cannot find mpv-2.dll`: `libmpv-2.dll` was not bundled. Check that the
`--add-binary` line for it is in `build/build.py` and rebuild.

- [ ] **Step 2: Open a local video file and test pitch shift**

Have any `.mp4` file ready (e.g. `tests\fixtures\sample_10s.mp4` from the exporter test run,
or any karaoke video from disk).

1. Click "Open a video file" → select the file.
2. Expected: loading spinner, then Playing view with video playing.
3. Move the **Song key** slider to -3.
4. Expected: audio pitch drops noticeably within ~1 second. No stutter, no restart.
   Label reads "Lower by 3 keys".
5. Move the **Silence the singer** slider to 50%.
6. Expected: audible centre-channel reduction.

- [ ] **Step 3: Save the current version**

1. Click "💾 Save this version".
2. Expected: file picker opens with suggested name like `{title} (key -3).mp4` inside
   a `Pitched Songs\` folder next to the exe.
3. Confirm.
4. Expected: progress bar appears and completes. Dialog: "Saved to: …".
5. Open the saved file in VLC or Windows Media Player.
6. Expected: plays correctly with pitch shifted down.

- [ ] **Step 4: Library persistence across restarts**

1. Click "← Back to library".
2. Expected: home screen shows the video you just opened as a card with "Lower by 3 keys" hint.
3. Close the exe.
4. Reopen the exe.
5. Expected: library card is still present. Click it.
6. Expected: video loads with pitch -3 and vocal reduce 50% restored.

- [ ] **Step 5: Paste a YouTube URL**

1. Copy a YouTube URL to the clipboard (e.g. `https://www.youtube.com/watch?v=dQw4w9WgXcQ`).
2. Expected: "Paste YouTube link" button area shows "🎵 YouTube link detected…".
3. Click "Paste YouTube link" → dialog opens with URL pre-filled.
4. Click OK.
5. Expected: download progress bar, then Playing view after download.

- [ ] **Step 6: Clean-machine test** *(required before any distribution)*

Copy `KaraokeBuddy.exe` to a Windows 11 machine (or VM snapshot) that has:
- No Python
- No FFmpeg in PATH
- No mpv / libmpv in PATH
- No Visual C++ Runtime (to test self-contained DLL bundling)

1. Double-click the exe.
2. Expected: app launches and works identically to Steps 1–4.
3. If a DLL error appears: check the Windows Event Log for the DLL name, then add it to
   `build/build.py`'s `--add-binary` list and rebuild.

- [ ] **Step 7: Final commit**

```bash
git add build/build.py  # if you added anything during smoke test troubleshooting
ruff check --fix . && ruff format .
git add -p
git commit -m "feat: KaraokeBuddy v1 — all tests pass, exe smoke-tested on clean machine"
```

---

## Self-Review

### Spec Coverage

| Spec Requirement | Task |
|---|---|
| Open local video files | Code already written; verified in Task 6 Step 2 |
| Open YouTube URLs (download → play) | Code already written; verified in Task 6 Step 5 |
| Live pitch shift -12..+12, tempo preserved | filter_chain.py (rubberband); Task 6 Step 2 |
| Live vocal reduction 0–100% | filter_chain.py (pan filter); Task 6 Step 2 |
| Export to MP4 | exporter.py; Task 4 integration tests; Task 6 Step 3 |
| Library of recent videos, sticky settings | library.py; Task 1 unit tests; Task 6 Step 4 |
| Portable single-file .exe (no installer) | Task 5 Step 6 |
| Plain-English errors, no stack traces | main_window.py _show_error; Task 6 first-launch check |
| Progress bars for download and export | Task 6 Steps 2–5 |
| Atomic library writes | library.py os.replace; Task 1 unit test |
| Corruption recovery | library.py; Task 1 unit test |
| Log rotation 5 MB / 3 files | __main__.py RotatingFileHandler |
| Clipboard-aware paste button | home_view.py _check_clipboard; Task 6 Step 5 |
| "Normal key / Lower by N / Higher by N" | playing_view.py _pitch_label; Task 6 Step 2 |
| Suggested export filename | main_window.py _on_save; Task 6 Step 3 |
| PyInstaller --onefile DLL discovery | Task 3 |
| libmpv-2.dll found at runtime | Task 3 (_setup_dll_search_path); Task 5 Step 2 |
| FFmpeg has rubberband support | Task 4 Step 2 |
| All automated tests verified passing | Tasks 1, 3, 4, 5 |
| Manual smoke test §9.2 | Task 6 |
| Clean machine test | Task 6 Step 6 |
| Git history with conventional commits | Tasks 1–5 |

### Placeholder Scan

None — all steps contain exact commands, expected output, and complete code.

### Type Consistency

- `_locate_bundled(name: str) -> Path | None` — defined in Task 3, tested in `test_entrypoint.py`.
- `_setup_dll_search_path() -> None` — defined in Task 3, tested in `test_entrypoint.py`.
- Both called in `main()` before any lazy imports — correct order preserved.
- `build_filter_chain(pitch_semitones: int, vocal_reduce_percent: int) -> str` — used in
  filter_chain.py, player.py, exporter.py, playing_view.py, main_window.py. No name drift.
