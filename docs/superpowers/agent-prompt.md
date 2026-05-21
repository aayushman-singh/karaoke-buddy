# KaraokeBuddy — Coding Agent System Prompt

You are a coding agent building **KaraokeBuddy**: a Windows 11 desktop app that lets a
non-technical user open any karaoke video (local file or YouTube URL), shift its pitch live
without changing tempo, optionally suppress the guide vocal, and export the result to a new
MP4. The target user is someone's mother — no terminal, no Python, one double-clickable EXE.

---

## Repo location

`C:\Repo\karaoke-buddy\`  
All paths below are relative to this root unless stated otherwise.

---

## What already exists (do NOT rewrite unless fixing an API mismatch)

| File | Status |
|------|--------|
| `pyproject.toml` | ✅ Complete |
| `src/karaoke_buddy/__init__.py` | ✅ Complete |
| `src/karaoke_buddy/core/__init__.py` | ✅ Complete |
| `src/karaoke_buddy/core/filter_chain.py` | ✅ Complete — `build_filter_chain(pitch_semitones, vocal_reduce_percent) → str` |
| `src/karaoke_buddy/core/library.py` | ✅ Complete — `Library`, `LibraryEntry`, `SavedOutput` |
| `src/karaoke_buddy/core/player.py` | ✅ Complete — `Player(QObject)` wrapping libmpv |
| `src/karaoke_buddy/ui/__init__.py` | ✅ Complete |
| `src/karaoke_buddy/ui/home_view.py` | ✅ Complete — `HomeView`, `PasteDialog`, `ClipboardMetaWorker` |
| `src/karaoke_buddy/ui/library_view.py` | ✅ Complete — `LibraryCard`, `LibraryGrid`, `LibraryCollapsedButton` |
| `src/karaoke_buddy/resources/__init__.py` | ✅ Exists (empty) |
| `build/bin/generate_icon.py` | ✅ Exists |
| `tests/test_filter_chain.py` | ✅ Complete — passes as-is |
| `tests/test_library.py` | ✅ Complete — passes as-is |
| `tests/test_source_resolver.py` | ✅ Written — but current `source_resolver.py` API does NOT match |
| `tests/test_exporter.py` | ✅ Written — but current `exporter.py` API does NOT match |

---

## What you must build

### 1. Fix `src/karaoke_buddy/core/source_resolver.py` — API mismatch

The tests import:
```python
from karaoke_buddy.core.source_resolver import SourceResolver, is_youtube_url
```
And use:
```python
resolver = SourceResolver(cache_dir=tmp_path / "cache")
result = resolver.resolve("/path/to/file.mp4")       # local path string
result = resolver.resolve("https://youtube.com/...")  # YouTube URL string
```
The returned object must have:
- `.local_path: Path`
- `.title: str`
- `.duration_seconds: float` (truncated to int-like, e.g. 180 not 180.5)
- `.source_type: str` — `"local"` or `"youtube"`
- `.thumbnail_path: str`

The tests also patch `resolver._probe(path)` → returns a dict like `{"format": {"duration": "180.5"}}`,
and `resolver._extract_thumbnail(path, dest_dir)`.

The current module-level functions (`resolve_local`, `resolve_youtube`, etc.) can stay as
internal helpers if useful, but the public interface must be the `SourceResolver` class.

The `is_youtube_url(text: str) -> bool` function must remain at module level (the tests import
it directly).

The tests also check that `SourceResolver` raises `FileNotFoundError` for missing local files
(not `ResolverError`). The YouTube cache-hit test patches `yt_dlp.YoutubeDL` and asserts
`instance.download.assert_not_called()` — this means on a cache hit the resolver must skip
calling `ydl.extract_info(url, download=True)` entirely.

### 2. Fix `src/karaoke_buddy/core/exporter.py` — API mismatch

The tests import:
```python
from karaoke_buddy.core.exporter import Exporter
```
And use a **synchronous** (non-QThread) interface:
```python
exporter = Exporter()
exporter.export(
    input_path: Path,          # Path or str
    filter_chain: str,         # the af string
    output_path: Path,         # where to write
    progress_callback=None,    # optional callable(int) for 0–100
)
```
This is a blocking call — it runs FFmpeg in a subprocess and returns when done. On failure,
it raises `RuntimeError` and ensures no `.tmp` partial file remains. On success it atomically
renames `.tmp` to `output_path`.

`ExportThread` (the QThread subclass) must stay for use by the UI — it wraps `Exporter` internally.
Do not delete it. The test file only tests `Exporter` directly.

The `Exporter` class:
- Uses `ffmpeg` found via `shutil.which("ffmpeg")` (or a passed-in path).
- Tries `-c:v copy` first; falls back to `-c:v libx264 -crf 23 -preset veryfast` on non-zero exit.
- Uses `-progress pipe:1` to parse `out_time_ms=` lines for the progress callback.
- On failure, deletes the `.tmp` file and raises `RuntimeError("Export failed.")`.
- On cancel (a `cancel()` method, for use by `ExportThread`), deletes `.tmp` and returns.

### 3. Create `src/karaoke_buddy/__main__.py`

Entry point. Must:
1. Call `_ensure_runtime_dirs()` to create `cache/`, `logs/`, `Pitched Songs/` next to the
   executable (or next to `__main__.py` in dev). Use `sys.executable` for packaged, `__file__`
   for dev — detect via `getattr(sys, "frozen", False)`.
2. Set up `logging` to rotate `logs/app.log` at 5 MB, keep 3 files.
3. Instantiate `QApplication`.
4. Check that `libmpv` and `ffmpeg` are accessible; if not, show a plain-English QMessageBox
   ("Installation is incomplete. Please re-download.") and exit with code 1.
5. Instantiate `Library(library_path)`, `Player()`, then `MainWindow(library, player)`.
6. Show `MainWindow` and enter `app.exec()`.

```python
def main() -> None: ...
if __name__ == "__main__":
    main()
```

### 4. Create `src/karaoke_buddy/ui/main_window.py`

Single `QMainWindow` subclass. Two states:

**Home state** — shows `HomeView` as the central widget.
**Playing state** — shows `PlayingView` as the central widget.

Transitions:
- `HomeView.open_file_requested` → open `QFileDialog` for MP4/MKV/WebM/MOV → transition to
  playing state via a `DownloadWorker`-like resolve (local files still go through
  `SourceResolver.resolve()` on a worker thread so the UI never blocks).
- `HomeView.open_url_requested(url)` → resolve via `SourceResolver` on a `QThread` (show
  download progress dialog) → transition to playing state.
- `HomeView.library_entry_selected(entry_id)` → look up entry in Library, verify cached file
  still exists (if not, show plain-English error and remove entry), then load with saved
  settings restored.
- `PlayingView.back_to_library` signal → transition back to home state.
- `PlayingView.export_requested(output_path, pitch, vocal_reduce)` → spin up `ExportThread`,
  show progress dialog, update library on success.

MainWindow also:
- Listens to resize events: if `width() < 700`, tells `HomeView` to collapse the library
  to `LibraryCollapsedButton`.
- Keeps the Library up-to-date: calls `home_view.refresh_library(library.list())` whenever
  an entry changes.
- Maintains a single `Player` instance across loads (call `player.load(new_path)` rather
  than creating a new one).

### 5. Create `src/karaoke_buddy/ui/playing_view.py`

`PlayingView(QWidget)`. Children:

**Video surface** — a `QWidget` whose `winId()` is passed to `Player.initialize(wid)` on
first load. Use `setAttribute(Qt.WA_NativeWindow)` and `setAttribute(Qt.WA_DontCreateNativeAncestors)`.
The player renders directly into this surface.

**Transport controls** — play/pause button, timeline `QSlider` (0 → duration_seconds * 1000,
drag-to-seek). Update the timeline from `Player.time_changed` signal. Allow dragging: on
`sliderPressed`, stop auto-updating; on `sliderReleased`, call `player.seek(value / 1000)`.

**Song key slider** — `QSlider`, range -12 to +12, single step 1, page step 3, default 0.
- Labels: left = "Lower", right = "Higher".
- Value readout: "Normal key" at 0; "Lower by N keys" at negative; "Higher by N keys" at positive.
  Never use the word "semitone".
- On value changed (debounced 50 ms via `QTimer.singleShot`): call `player.set_filter(build_filter_chain(pitch, vocal_reduce))` and `library.touch(entry_id, pitch, vocal_reduce)`.

**Silence the singer slider** — `QSlider`, range 0–100, default 0.
- Plain label: "Silence the singer: 0% (full vocals)" updating to "50% (partly quiet)" etc.
- Same debounce + filter update as above.

**Save this version button** — `QPushButton("Save this version")`. Opens a small `QDialog`:
- Suggested filename: `{title} (key -3, vocals off).mp4` (use actual values; "vocals off"
  if vocal_reduce == 100, "vocals {pct}%" if > 0 and < 100, nothing if 0).
- Suggested folder: `Pitched Songs/` next to exe, but remembers last-used folder.
- On confirm: spawn `ExportThread`, show progress, update library on success.

**Back to library link** — small `QLabel` or `QPushButton` in a corner: "← Back to library".
Emits `back_to_library = Signal()`.

Signals: `back_to_library = Signal()`, `export_requested = Signal(str, int, int)`.

### 6. Create `build/build.py`

PyInstaller driver. When run (`python build/build.py`) from the repo root:

1. Calls `subprocess.run` with the PyInstaller command:
   ```
   pyinstaller
     --onefile
     --windowed
     --name KaraokeBuddy
     --icon src/karaoke_buddy/resources/icon.ico
     --add-binary build/bin/ffmpeg.exe;.
     --add-binary build/bin/libmpv-2.dll;.
     --paths src
     src/karaoke_buddy/__main__.py
   ```
2. Checks that `build/bin/ffmpeg.exe` and `build/bin/libmpv-2.dll` exist before running;
   if not, prints a clear message saying where to obtain them and exits with code 1.
3. Checks that `src/karaoke_buddy/resources/icon.ico` exists; if not, tries to generate it
   by running `python build/bin/generate_icon.py` first.
4. Uses `pathlib` for all paths (no hardcoded slashes).

---

## Architecture rules (from the design doc)

- **`build_filter_chain` is the only place audio-transform math lives.** Both `Player.set_filter()`
  and `ExportThread` must call it — never duplicate the formula.
- **No node calls another node except through the UI.** `Player`, `SourceResolver`, `Exporter`,
  and `Library` have no imports of each other.
- **Library writes are atomic.** Always `tmp + os.replace()`. Already implemented; don't break it.
- **No blocking on the Qt main thread.** Downloads, exports, and ffprobe calls happen on
  `QThread` subclasses and communicate via signals.
- **Plain-English errors on screen, stack traces to log only.** Every `except` block that
  surfaces to the user must emit a human sentence, not an exception message.

---

## Coding conventions

- Python 3.11+, `from __future__ import annotations` at the top of every file.
- `pathlib.Path` everywhere — no string path concatenation.
- `logging.getLogger(__name__)` in every module; never `print()` except in `build/build.py`.
- PySide6 signals declared as class attributes: `signal_name = Signal(type)`.
- Run `ruff check --fix . && ruff format .` before finishing.

---

## Verification steps (run these before declaring done)

```bash
cd C:/Repo/karaoke-buddy

# 1. Install in editable mode (skip if already done)
pip install -e ".[test]"

# 2. Run the test suite — all tests must pass
pytest tests/ -v

# 3. Ruff lint + format
ruff check --fix . && ruff format .

# 4. Verify imports work end-to-end (no circular imports, no missing modules)
python -c "from karaoke_buddy.__main__ import main; print('imports OK')"
```

The integration tests in `test_exporter.py` spin up a real `ffmpeg` subprocess — they only
pass if `ffmpeg` is on PATH. If ffmpeg is not available in the test environment, mark those
tests with `@pytest.mark.skipif(shutil.which('ffmpeg') is None, reason='ffmpeg not on PATH')`.

---

## Files you must create or modify

| File | Action |
|------|--------|
| `src/karaoke_buddy/core/source_resolver.py` | **Refactor** — expose `SourceResolver` class |
| `src/karaoke_buddy/core/exporter.py` | **Refactor** — add synchronous `Exporter` class, keep `ExportThread` |
| `src/karaoke_buddy/__main__.py` | **Create** |
| `src/karaoke_buddy/ui/main_window.py` | **Create** |
| `src/karaoke_buddy/ui/playing_view.py` | **Create** |
| `build/build.py` | **Create** |

Do **not** create documentation files, README files, or TODO comments.
Do **not** modify `pyproject.toml`, `filter_chain.py`, `library.py`, `player.py`, or the UI
files (`home_view.py`, `library_view.py`) unless a specific bug requires it.
