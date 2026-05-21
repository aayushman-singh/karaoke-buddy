# KaraokeBuddy — Complete & Ship Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix two latent bugs, commit all untracked source code, acquire runtime binaries, pass all tests, build the distributable `.exe`, and smoke-test it.

**Architecture:** All five core nodes (filter_chain, library, source_resolver, player, exporter) and the Qt UI are fully written and locally correct. Two bugs were found during plan review: a DRY violation (`_pitch_label` duplicated across two UI modules) and a data-integrity bug (YouTube library entries silently store `source=""` instead of the original URL). Everything else is feature-complete; this plan gets to ship.

**Tech Stack:** Python 3.11+, PySide6 6.6+, python-mpv, yt-dlp, FFmpeg GPL static build (bundled), libmpv-2.dll (bundled), PyInstaller 6, pytest 8, hypothesis 6, Pillow (icon generation only).

---

## True Current State (verified 2026-04-17)

| Item | Status |
|------|--------|
| `src/karaoke_buddy/core/` — all 5 modules | ✅ Written & committed |
| `src/karaoke_buddy/ui/` — all views + MainWindow | ✅ Written, **not committed** |
| `src/karaoke_buddy/__main__.py` | ✅ Written, **not committed** |
| `tests/` — filter_chain, library, source_resolver, exporter, entrypoint | ✅ Written, **not committed** |
| `build/build.py`, `build/create_fixture.py` | ✅ Written, **not committed** |
| `src/karaoke_buddy/resources/generate_icon.py` | ✅ Written, **not committed** |
| `src/karaoke_buddy/resources/icon.ico` | ❌ Not generated |
| `_pitch_label` DRY violation (duplicated in 2 UI files) | ❌ Bug — **Task 1** |
| YouTube `source=""` bug in `main_window.py:_on_resolved()` | ❌ Bug — **Task 1** |
| `build/bin/ffmpeg.exe`, `build/bin/ffprobe.exe` | ❌ Not downloaded |
| `build/bin/libmpv-2.dll` | ❌ Not downloaded |
| `build/dist/KaraokeBuddy.exe` | ❌ Not built |

**This plan supersedes all prior plans** (`2026-04-17-karaoke-buddy-ship.md`, etc.). Prior plans' Tasks 1–3 (delete download_worker, add hypothesis tests, add _ClipMetaWorker) are already done in the working tree.

---

## File Map

| File | Action | Task |
|------|--------|------|
| `src/karaoke_buddy/ui/utils.py` | **Create** — shared `pitch_label()` function | 1 |
| `src/karaoke_buddy/ui/playing_view.py` | **Modify** — remove local `_pitch_label`, import from utils | 1 |
| `src/karaoke_buddy/ui/library_view.py` | **Modify** — remove local `_pitch_label`, import from utils | 1 |
| `src/karaoke_buddy/ui/main_window.py` | **Modify** — fix YouTube `source` URL storage | 1 |
| `tests/test_ui_utils.py` | **Create** — tests for `pitch_label()` | 1 |
| All untracked files in `src/`, `tests/`, `build/`, `docs/` | **Commit** | 2 |
| `build/bin/ffmpeg.exe`, `build/bin/ffprobe.exe` | **Download** | 3 |
| `build/bin/libmpv-2.dll` | **Download** | 4 |
| `src/karaoke_buddy/resources/icon.ico` | **Generate** | 4 |
| `build/dist/KaraokeBuddy.exe` | **Build** | 5 |

---

## Task 1: Fix DRY violation + YouTube source URL bug

**Files:**
- Create: `src/karaoke_buddy/ui/utils.py`
- Modify: `src/karaoke_buddy/ui/playing_view.py` (lines 25–31, 193, 196)
- Modify: `src/karaoke_buddy/ui/library_view.py` (lines 112–118, 62)
- Modify: `src/karaoke_buddy/ui/main_window.py` (lines 121–149)
- Create: `tests/test_ui_utils.py`

**Bug 1 — DRY violation:** `_pitch_label(semitones)` is defined identically in both `playing_view.py` (lines 25–31) and `library_view.py` (lines 112–118). Any future wording change (e.g. translating "keys" to "semitones") requires editing two files. The fix: extract to a shared module and import.

**Bug 2 — YouTube source URL lost:** In `main_window.py:_on_resolved()`, YouTube library entries are created with `source=""` (line 143: `source=resolved_posix if resolved.source_type == "local" else ""`). The `source` field is defined in the spec as the original YouTube URL for URL-sourced videos. An empty string means `Library.find_by_source(url)` never matches, and if the user clears the cache they cannot re-download because the URL is gone.

- [ ] **Step 1: Write the failing tests for pitch_label**

Create `tests/test_ui_utils.py`:

```python
"""Tests for shared UI utility functions."""
import pytest

from karaoke_buddy.ui.utils import pitch_label


def test_zero_returns_normal_key():
    assert pitch_label(0) == "Normal key"


def test_positive_one_semitone():
    assert pitch_label(1) == "Higher by 1 key"


def test_positive_plural():
    assert pitch_label(2) == "Higher by 2 keys"


def test_negative_one_semitone():
    assert pitch_label(-1) == "Lower by 1 key"


def test_negative_plural():
    assert pitch_label(-3) == "Lower by 3 keys"


def test_max_up():
    assert pitch_label(12) == "Higher by 12 keys"


def test_max_down():
    assert pitch_label(-12) == "Lower by 12 keys"


@pytest.mark.parametrize("semitones", range(-12, 13))
def test_all_valid_inputs_return_nonempty_string(semitones):
    result = pitch_label(semitones)
    assert isinstance(result, str)
    assert len(result) > 0
```

- [ ] **Step 2: Run test to confirm it fails (module does not exist yet)**

```bash
cd /c/Repo/karaoke-buddy
python -m pytest tests/test_ui_utils.py -v
```

Expected: `ModuleNotFoundError: No module named 'karaoke_buddy.ui.utils'`

- [ ] **Step 3: Create src/karaoke_buddy/ui/utils.py**

```python
"""Shared UI utility functions."""


def pitch_label(semitones: int) -> str:
    """Return a plain-English description of a semitone shift.

    Examples:
        pitch_label(0)   -> "Normal key"
        pitch_label(1)   -> "Higher by 1 key"
        pitch_label(-3)  -> "Lower by 3 keys"
    """
    if semitones == 0:
        return "Normal key"
    direction = "Higher" if semitones > 0 else "Lower"
    abs_s = abs(semitones)
    word = "key" if abs_s == 1 else "keys"
    return f"{direction} by {abs_s} {word}"
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
python -m pytest tests/test_ui_utils.py -v
```

Expected: `25 passed` (7 explicit + 25 parametrize). Zero failures.

- [ ] **Step 5: Update playing_view.py — remove local _pitch_label, import from utils**

In `src/karaoke_buddy/ui/playing_view.py`:

Remove lines 25–31 (the entire `_pitch_label` function definition):
```python
def _pitch_label(semitones: int) -> str:
    if semitones == 0:
        return "Normal key"
    direction = "Higher" if semitones > 0 else "Lower"
    abs_s = abs(semitones)
    word = "key" if abs_s == 1 else "keys"
    return f"{direction} by {abs_s} {word}"
```

Add this import after the existing imports (after `from karaoke_buddy.core.library import LibraryEntry`):
```python
from karaoke_buddy.ui.utils import pitch_label
```

Replace the two call sites that use `_pitch_label`:
- Line ~193 in `_on_pitch_changed`: `self._pitch_label.setText(_pitch_label(value))` → `self._pitch_label.setText(pitch_label(value))`
- Line ~115 where `_pitch_label` is called to set the initial label: `self._pitch_label = QLabel("Normal key")` — no call here, it's a widget name. Search the file for `_pitch_label(` and replace each call.

The exact search/replace pairs:
```
# Old:
self._pitch_label.setText(_pitch_label(value))

# New:
self._pitch_label.setText(pitch_label(value))
```

Note: `self._pitch_label` (with `self.`) is the QLabel widget — do not rename those. Only rename the bare function calls `_pitch_label(value)`.

- [ ] **Step 6: Update library_view.py — remove local _pitch_label, import from utils**

In `src/karaoke_buddy/ui/library_view.py`:

Remove lines 112–118 (the entire `_pitch_label` function at the bottom of the file):
```python
def _pitch_label(semitones: int) -> str:
    if semitones == 0:
        return "Normal key"
    direction = "Higher" if semitones > 0 else "Lower"
    abs_s = abs(semitones)
    word = "key" if abs_s == 1 else "keys"
    return f"{direction} by {abs_s} {word}"
```

Add this import after the existing imports (after `from karaoke_buddy.core.library import Library, LibraryEntry`):
```python
from karaoke_buddy.ui.utils import pitch_label
```

In `_EntryCard.__init__` around line 62, replace:
```python
# Old:
hint = QLabel(_pitch_label(entry.last_pitch))

# New:
hint = QLabel(pitch_label(entry.last_pitch))
```

- [ ] **Step 7: Fix the YouTube source URL bug in main_window.py**

In `src/karaoke_buddy/ui/main_window.py`, find `_resolve_input` (around line 111). Change the `finished` signal connection from:

```python
thread.finished.connect(lambda r: self._on_resolved(r, progress))
```

to (captures `input_str` at lambda creation time, preventing late-binding closure bug):

```python
thread.finished.connect(lambda r, inp=input_str: self._on_resolved(r, inp, progress))
```

Then update `_on_resolved` signature and body. The full replacement for lines 125–156:

```python
def _on_resolved(self, resolved, original_input: str, progress) -> None:
    progress.close()

    resolved_posix = resolved.local_path.as_posix()
    existing = next(
        (
            e
            for e in self._library.list()
            if e.source == original_input
            or e.source == resolved_posix
            or e.cached_path == resolved_posix
        ),
        None,
    )
    if existing:
        entry = existing
    else:
        # For YouTube entries, source is the original URL.
        # For local entries, source is the POSIX path.
        source_str = original_input if resolved.source_type == "youtube" else resolved_posix
        entry = LibraryEntry(
            title=resolved.title,
            source_type=resolved.source_type,
            source=source_str,
            cached_path=resolved_posix,
            thumbnail_path=str(resolved.thumbnail_path)
            if resolved.thumbnail_path
            else None,
            duration_seconds=resolved.duration_seconds,
        )
    entry.last_opened = datetime.now(timezone.utc).isoformat()
    self._library.upsert(entry)
    self._current_entry = entry

    self._playing.load_entry(entry)
    self._go_playing()
    self._load_player(resolved.local_path)
```

- [ ] **Step 8: Run all unit tests to confirm no regressions**

```bash
python -m pytest tests/test_filter_chain.py tests/test_library.py tests/test_source_resolver.py tests/test_entrypoint.py tests/test_ui_utils.py -v
```

Expected: all tests pass (43 filter_chain + 13 library + 9 source_resolver + 6 entrypoint + 25 ui_utils = ~96 tests). Zero failures.

If `ImportError` on playing_view or library_view: a call to `_pitch_label(` was missed — search the file for the old name and replace it.

- [ ] **Step 9: Lint and commit**

```bash
ruff check --fix src/karaoke_buddy/ui/utils.py src/karaoke_buddy/ui/playing_view.py src/karaoke_buddy/ui/library_view.py src/karaoke_buddy/ui/main_window.py tests/test_ui_utils.py
ruff format src/karaoke_buddy/ui/utils.py src/karaoke_buddy/ui/playing_view.py src/karaoke_buddy/ui/library_view.py src/karaoke_buddy/ui/main_window.py tests/test_ui_utils.py
git add src/karaoke_buddy/ui/utils.py src/karaoke_buddy/ui/playing_view.py src/karaoke_buddy/ui/library_view.py src/karaoke_buddy/ui/main_window.py tests/test_ui_utils.py
git commit -m "$(cat <<'EOF'
fix: extract pitch_label to ui/utils, fix YouTube source URL storage

- Extract duplicated _pitch_label() from playing_view.py and library_view.py
  into a shared karaoke_buddy.ui.utils.pitch_label() function.
- Fix main_window._on_resolved() to store the original YouTube URL in
  LibraryEntry.source instead of empty string, enabling cache re-use and
  correct Library.find_by_source() lookups.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Commit all untracked source code

**Files:** All untracked content in `src/`, `tests/`, `build/`, `docs/`

The working tree has all code written but only `core/` committed. This task creates clean atomic commits.

- [ ] **Step 1: Confirm what's untracked**

```bash
git status --short
```

Expected untracked groups: `src/karaoke_buddy/__main__.py`, `src/karaoke_buddy/ui/`, `src/karaoke_buddy/resources/`, `tests/`, `build/`, `docs/superpowers/`.

- [ ] **Step 2: Commit the entry point**

```bash
git add src/karaoke_buddy/__main__.py
git commit -m "feat: entry point — rotating log, DLL discovery, startup check"
```

- [ ] **Step 3: Commit UI layer**

```bash
git add src/karaoke_buddy/ui/
git commit -m "feat: Qt UI — HomeView (async clipboard), LibraryView, PlayingView, MainWindow"
```

- [ ] **Step 4: Commit resources**

```bash
git add src/karaoke_buddy/resources/
git commit -m "chore: icon generator script (requires Pillow, run separately)"
```

- [ ] **Step 5: Commit tests**

```bash
git add tests/
git commit -m "test: filter_chain (43 + 4 hypothesis), library, source_resolver, entrypoint, exporter, ui_utils"
```

- [ ] **Step 6: Commit build tooling**

```bash
git add build/build.py build/__init__.py build/create_fixture.py build/bin/README.txt
git commit -m "chore: PyInstaller build driver + test fixture generator"
```

- [ ] **Step 7: Commit docs/superpowers**

```bash
git add docs/
git commit -m "docs: design spec, implementation plans, agent prompt"
```

- [ ] **Step 8: Verify clean tree**

```bash
git status
```

Expected: `nothing to commit, working tree clean`.

---

## Task 3: Download FFmpeg + run exporter integration tests

**Files produced:**
- `build/bin/ffmpeg.exe`
- `build/bin/ffprobe.exe`

The `rubberband` pitch-shift filter used by the app is only in FFmpeg **GPL** static builds (not LGPL, not minimal builds). A non-GPL build will silently produce corrupted audio.

- [ ] **Step 1: Download the BtbN FFmpeg GPL static build**

Run in PowerShell (not Git Bash — `Invoke-WebRequest` works better for large files):

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

Expected: `build\bin\ffmpeg.exe` and `build\bin\ffprobe.exe` each ~100 MB.

If the zip structure differs (BtbN occasionally changes the folder name), run:
```powershell
Expand-Archive ffmpeg.zip -DestinationPath ffmpeg_extracted -Force
Get-ChildItem ffmpeg_extracted -Recurse -Filter ffmpeg.exe
```
Use the path shown to adjust the `Copy-Item` commands.

- [ ] **Step 2: Verify rubberband support**

```powershell
.\build\bin\ffmpeg.exe -filters 2>&1 | Select-String "rubberband"
```

Expected output (one line):
```
 ... rubberband          A->A       Apply time-stretching and pitch-shifting
```

If no output: you have the LGPL build — re-download. Without rubberband, all exports produce corrupted audio and `test_export_with_pitch_shift_succeeds` will fail.

- [ ] **Step 3: Add build/bin to PATH and run integration tests**

```bash
# Git Bash
export PATH="$PATH:/c/Repo/karaoke-buddy/build/bin"
python -m pytest tests/test_exporter.py -v
```

Expected (allow ~30–60 seconds for FFmpeg encoding):
```
tests/test_exporter.py::test_export_produces_valid_mp4 PASSED
tests/test_exporter.py::test_export_duration_matches_input PASSED
tests/test_exporter.py::test_export_with_pitch_shift_succeeds PASSED
tests/test_exporter.py::test_export_with_vocal_reduce_succeeds PASSED
tests/test_exporter.py::test_no_partial_file_on_failure PASSED
tests/test_exporter.py::test_progress_callback_receives_values PASSED
====== 6 passed ======
```

If `test_export_with_pitch_shift_succeeds` fails with `Unknown filter 'rubberband'`: Step 2 didn't pass — you have the wrong build. Re-download.

If `test_no_partial_file_on_failure` fails (`.tmp` file found after error): open `src/karaoke_buddy/core/exporter.py`, in `export()`, confirm both the stream-copy-fail branch and the re-encode-fail branch each call `tmp.unlink()` before raising. Fix if needed, ruff, commit:
```bash
ruff check --fix src/karaoke_buddy/core/exporter.py && ruff format src/karaoke_buddy/core/exporter.py
git add src/karaoke_buddy/core/exporter.py
git commit -m "fix: ensure .tmp deleted on both exporter failure branches"
```

- [ ] **Step 4: Run the full unit + integration suite together**

```bash
export PATH="$PATH:/c/Repo/karaoke-buddy/build/bin"
python -m pytest -v
```

Expected: **~102 tests pass** (96 unit + 6 integration). Zero failures.

---

## Task 4: Download libmpv-2.dll + generate icon.ico

**Files produced:**
- `build/bin/libmpv-2.dll`
- `src/karaoke_buddy/resources/icon.ico`

- [ ] **Step 1: Get libmpv-2.dll**

Try options in order. Stop when it works.

**Option A — From your own mpv installation (fastest):**
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

**Option C — Manual download from shinchiro's GitHub releases:**
1. Go to `https://github.com/shinchiro/mpv-winbuild-cmake/releases`
2. Download the latest `mpv-dev-x86_64-*.7z`
3. Extract it using 7-Zip (or: `pip install py7zr` then the script below)
4. Copy `libmpv-2.dll` to `build\bin\`

Script for Option C extraction (if 7-Zip is not installed):
```python
import io, urllib.request, json, py7zr, pathlib

BIN = pathlib.Path("build/bin")

api = "https://api.github.com/repos/shinchiro/mpv-winbuild-cmake/releases/latest"
req = urllib.request.Request(api, headers={"User-Agent": "karaoke-buddy"})
with urllib.request.urlopen(req) as r:
    release = json.loads(r.read())

asset = next(
    a for a in release["assets"]
    if "mpv-dev-x86_64" in a["name"] and a["name"].endswith(".7z")
)
print("Downloading", asset["name"], "…")
with urllib.request.urlopen(asset["browser_download_url"]) as r:
    data = r.read()

with py7zr.SevenZipFile(io.BytesIO(data)) as z:
    names = z.getnames()
    dll_entry = next(n for n in names if pathlib.Path(n).name == "libmpv-2.dll")
    result = z.read([dll_entry])
    for name, bio in result.items():
        out = BIN / "libmpv-2.dll"
        out.write_bytes(bio.read())
        print("Extracted →", out)
```

Run as: `pip install py7zr && python <script_file>.py`

- [ ] **Step 2: Verify python-mpv loads the DLL**

```bash
export PATH="$PATH:/c/Repo/karaoke-buddy/build/bin"
python -c "import mpv; print('mpv import ok')"
```

Expected: `mpv import ok`

If `OSError: Cannot find mpv-2.dll or libmpv-2.dll`: confirm `build/bin/libmpv-2.dll` exists and that `build/bin` is in your PATH. The python-mpv library searches `PATH` for the DLL via ctypes.

If python-mpv complains about an incompatible version (`mpv_client_api_version`), you need a newer libmpv. The shinchiro builds are always current — use Option C.

- [ ] **Step 3: Verify all three binaries are present and non-empty**

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

Any file under 1 MB is a corrupted download — re-download that file.

- [ ] **Step 4: Generate the app icon**

```bash
pip install Pillow
python src/karaoke_buddy/resources/generate_icon.py
```

Expected: `Icon written to …/src/karaoke_buddy/resources/icon.ico`

If `FileNotFoundError: seguiemj.ttf`: the script falls back to the default PIL font automatically — the icon will still be written, just without the emoji character. This is acceptable for v1.

- [ ] **Step 5: Commit the generated icon**

```bash
git add src/karaoke_buddy/resources/icon.ico
git commit -m "feat: generate app icon (purple circle + microphone emoji)"
```

---

## Task 5: Build the distributable .exe

**Files produced:** `build/dist/KaraokeBuddy.exe`

- [ ] **Step 1: Verify PyInstaller is installed**

```bash
pyinstaller --version
```

Expected: `6.x.x` or higher.

If not found:
```bash
pip install "pyinstaller>=6"
```

- [ ] **Step 2: Run the build script**

```bash
cd /c/Repo/karaoke-buddy
export PATH="$PATH:/c/Repo/karaoke-buddy/build/bin"
python build/build.py
```

Expected output (last two lines):
```
Running PyInstaller…
...
Build complete: C:\Repo\karaoke-buddy\build\dist\KaraokeBuddy.exe
```

Build takes 2–5 minutes.

Common failures and exact fixes:

| Error message | Fix |
|---|---|
| `ERROR: Missing binaries` | Confirm all three files exist in `build/bin/` (Task 4 Step 3) |
| `ModuleNotFoundError: No module named 'yt_dlp.extractor'` | Add `"--hidden-import", "yt_dlp.extractor.youtube"` to the `cmd` list in `build/build.py` after the existing `--hidden-import yt_dlp.extractor` entry |
| `Cannot find icon.ico` | Re-run `python src/karaoke_buddy/resources/generate_icon.py` |
| `UPX is not available` | Harmless warning — ignore |
| Antivirus kills the process mid-build | Temporarily disable real-time AV scanning for `C:\Repo\karaoke-buddy\build\work\` |
| Antivirus quarantines the finished exe | Switch to `--onedir` by changing `--onefile` to `--onedir` in `build/build.py`; a folder is less suspicious than a single large exe |

- [ ] **Step 3: Verify the output is real**

```powershell
Get-Item build\dist\KaraokeBuddy.exe |
  Select-Object Name, @{N='MB';E={[math]::Round($_.Length/1MB,0)}}
```

Expected: size > 100 MB. Anything smaller means PyInstaller failed mid-run — check the PyInstaller log above the error.

- [ ] **Step 4: Commit any build.py changes needed during troubleshooting**

Only commit if you had to modify `build/build.py` (e.g. added hidden-imports):

```bash
ruff check --fix build/build.py && ruff format build/build.py
git add build/build.py
git commit -m "fix: add missing PyInstaller hidden-imports for yt_dlp extractors"
```

---

## Task 6: Manual Smoke Test

Verify the exe works end-to-end. Covers spec §9.2 exactly. **Do not skip.** Automated tests do not cover the Qt ↔ libmpv pipeline, real download-to-play flow, or filter audio fidelity.

- [ ] **Step 1: First launch**

Double-click `build\dist\KaraokeBuddy.exe`.

Expected:
- Window opens in ~2–5 seconds (first launch extracts to `%TEMP%\_MEI*`).
- Home screen: "KaraokeBuddy 🎤" heading, two large buttons ("Open a video file", "Paste YouTube link"), empty library grid.
- No error dialogs.
- `logs\app.log` is created next to the exe.

| Dialog seen | Fix |
|---|---|
| "Installation is incomplete. Please re-download." | `ffmpeg.exe` or `ffprobe.exe` missing from bundle. Confirm `--add-binary` lines in `build/build.py` and rebuild (Task 5). |
| `OSError: Cannot find mpv-2.dll` | `libmpv-2.dll` not in bundle. Confirm `--add-binary` for it in `build/build.py` and rebuild. |
| Blank black window (app hangs) | libmpv GPU backend issue. Add `"--add-data", "build/bin/libmpv-2.dll;."` and try `vo=sw` as fallback in player.py. |

- [ ] **Step 2: Open a local video + test pitch shift**

Use `tests\fixtures\sample_10s.mp4` (run `python build/create_fixture.py` if it doesn't exist and ffmpeg is in PATH) or any `.mp4` on disk.

1. Click "Open a video file" → select the file.
2. Expected: loading indicator, then Playing view with video playing.
3. Move **Song key** slider to **-3**.
   - Label reads "Lower by 3 keys".
   - Audio pitch drops noticeably within ~1 second. No stutter, no restart.
4. Move **Silence the singer** slider to **50%**.
   - Audible centre-channel reduction.

- [ ] **Step 3: Save the current version**

1. Click "💾 Save this version".
2. Expected: file picker opens with suggested name `{title} (key -3).mp4` inside `Pitched Songs\` next to the exe.
3. Click Save.
4. Expected: progress bar fills, dialog: "Saved to: …".
5. Open saved file in VLC or Windows Media Player.
6. Expected: plays correctly with pitch shifted down and vocals reduced.

- [ ] **Step 4: Library persistence across restarts**

1. Click "← Back to library" — home screen shows a card for the video with "Lower by 3 keys".
2. Close the exe.
3. Reopen the exe — library card is still present.
4. Click the card — video loads with pitch −3 and vocal reduce 50% already restored.

- [ ] **Step 5: Clipboard title preview**

1. Copy `https://www.youtube.com/watch?v=dQw4w9WgXcQ` to clipboard.
2. Bring KaraokeBuddy window to focus (or wait up to 1 second).
3. Expected: label shows "🎵 Fetching title…" briefly, then "Paste this? 🎵  Never Gonna Give You Up".
4. Click "Paste YouTube link" — dialog opens with URL pre-filled.
5. Click OK. Download progress bar appears, then Playing view.

- [ ] **Step 6: YouTube pitch shift + save** *(completes §9.2 smoke checklist)*

1. With the YouTube video loaded, set pitch to **+2**, click Save.
2. Open saved file in VLC — confirm pitch is shifted up.

- [ ] **Step 7: Clean-machine test** *(required before any distribution)*

Copy `KaraokeBuddy.exe` to a Windows 11 machine (or VM snapshot) that has:
- No Python, no FFmpeg in PATH, no mpv/libmpv in PATH, no Visual C++ Runtime

1. Double-click the exe.
2. Expected: app launches and Steps 1–6 all work identically.
3. If a missing DLL error appears: open Windows Event Viewer → Application Log to find the DLL name, then add a `--add-binary` entry for it in `build/build.py`, rebuild (Task 5), re-test.

- [ ] **Step 8: Final commit**

```bash
cd /c/Repo/karaoke-buddy
ruff check --fix . && ruff format .
git status  # confirm only intentional changes
git add -p  # stage only actual code changes (not binaries)
git commit -m "$(cat <<'EOF'
feat: KaraokeBuddy v1 — all tests pass, exe smoke-tested on clean machine

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Self-Review

### Spec Coverage

| Spec Requirement | Task |
|---|---|
| Open local video files (MP4, MKV, WebM, MOV) | Already written; Task 6 Step 2 |
| Open YouTube URLs (download → play) | Already written; Task 6 Step 5 |
| Live pitch shift −12..+12, tempo preserved | `filter_chain.py` rubberband; Task 3 Step 2 (GPL verify); Task 6 Step 2 |
| Live vocal reduction 0–100% centre subtraction | `filter_chain.py` pan filter; Task 6 Step 2 |
| Export to MP4 (stream-copy + AAC; libx264 fallback) | `exporter.py`; Task 3 integration tests; Task 6 Step 3 |
| Library with per-song sticky settings | `library.py`; existing unit tests; Task 6 Step 4 |
| Portable single-file `.exe`, no installer, no admin | Task 5 PyInstaller; Task 6 Step 7 |
| Plain-English errors, no stack traces | `main_window._show_error`; Task 6 Step 1 error table |
| Progress bars for download and export | `_ResolveThread` + `ExportThread` Qt signals; Task 6 Steps 2–5 |
| Atomic library writes + corruption recovery | `library.py`; existing unit tests |
| Log rotation 5 MB / 3 files | `__main__._setup_logging` RotatingFileHandler |
| Clipboard-aware paste button (real title fetch) | `home_view._ClipMetaWorker`; Task 6 Step 5 |
| "Normal key / Lower by N keys / Higher by N keys" | `ui/utils.pitch_label`; Task 1 tests; Task 6 Step 2 |
| Suggested export filename with key info | `main_window._on_save`; Task 6 Step 3 |
| YouTube source URL stored in library | Task 1 (YouTube source bug fix) |
| `rubberband` in bundled FFmpeg | Task 3 Step 2 explicit verification |
| PyInstaller `--onefile` DLL discovery | `__main__._locate_bundled` + `_setup_dll_search_path`; `test_entrypoint.py` |
| Property tests for filter chain (spec §9.1) | Already in `test_filter_chain.py` (hypothesis); Task 3 Step 4 |
| Source Resolver URL detection tests (spec §9.1) | `test_source_resolver.py` |
| Library persistence tests (spec §9.1) | `test_library.py` |
| Exporter integration test on real FFmpeg (spec §9.1) | `test_exporter.py`; Task 3 |
| Manual smoke test (spec §9.2) | Task 6 |
| Clean-machine test (spec §9.2) | Task 6 Step 7 |
| Conventional commits, atomic git history | Tasks 1–5 commit steps |
| DRY — `_pitch_label` single definition | Task 1 (DRY fix) |

### Placeholder Scan

None — all steps contain exact commands, expected output, and complete code.

### Type Consistency

- `pitch_label(semitones: int) -> str` — defined in `ui/utils.py` (Task 1), imported in `playing_view.py` and `library_view.py` (Task 1), tested in `test_ui_utils.py` (Task 1). No drift.
- `_on_resolved(self, resolved, original_input: str, progress)` — updated signature in `main_window.py`, lambda updated to pass `original_input`. Both changed in the same step. ✅
- `build_filter_chain(pitch_semitones: int, vocal_reduce_percent: int) -> str` — used in `filter_chain.py`, `playing_view.py`, `main_window.py`, `exporter.py`, all test files. No drift. ✅
- `LibraryEntry.source: str` — for YouTube entries now stores the original URL (Task 1); for local entries stores the POSIX path. This is consistent with the spec's JSON schema (`"source": "https://youtube.com/watch?v=…" | "C:/path/to/file.mp4"`). ✅
- `ExportThread`, `_ResolveThread` — both emit `progress(int)` and `finished(…)`/`error(str)` signals. Connected in `main_window.py`. No name changes in this plan. ✅
