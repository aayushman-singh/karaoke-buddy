# KaraokeBuddy — Design

**Date:** 2026-04-15
**Status:** Draft — awaiting review
**Target platform (v1):** Windows 11

---

## 1. Purpose

A desktop app that lets a non-technical user (the primary example: someone's mother) open any karaoke video — from disk or a YouTube URL — and sing along in their own vocal range. The user drags a **Song key** slider while the video plays; pitch shifts live without changing tempo or drifting the on-screen lyrics. A **Silence the singer** slider optionally removes guide vocals. A single button exports the current settings to a new MP4 for offline playback.

The product replaces a painful manual workflow (extract audio → Audacity → re-overlay in a video editor) with a single app that does the whole round-trip live.

## 2. Users

- **Primary user (mom):** non-technical, uses Windows, wants to sing along at home. Will not install Python, use a terminal, or read documentation. Distribution must be one double-clickable `.exe`.
- **Secondary user (the project owner):** technical, pitches down video audio for other reasons. The same app serves both.

Design decisions resolve in favour of mom's clarity when the two conflict.

## 3. Scope

**In scope for v1:**
- Open local video files.
- Open YouTube URLs (download → play).
- Live pitch shift (-12 to +12 semitones) with tempo preserved.
- Live vocal reduction (0–100%) via centre-channel subtraction.
- Export current settings to a new MP4.
- Library of recently opened and saved videos, with per-song sticky settings.
- Portable single-file `.exe` distribution (no installer, no admin, no external dependencies on the target machine).

**Out of scope for v1:**
- Tempo control independent of pitch.
- AI-based vocal separation (Spleeter / Demucs). Centre-channel subtraction is sufficient for most karaoke videos and keeps the bundle small.
- macOS / Linux builds. The stack is cross-platform but we ship Windows only.
- Batch processing.
- Cloud sync, accounts, telemetry.

## 4. Architecture

Five nodes with narrow interfaces. The design target is the minimal set that separates responsibilities with different lifecycles.

| Node | Purpose | Owns |
|---|---|---|
| **UI** | Renders the video surface and controls; dispatches user intent to the other nodes; presents progress and errors. | Qt widgets. No persistent state beyond what's on-screen. |
| **Source Resolver** | Turns a user input (local path or URL) into a playable local file plus metadata (title, duration, thumbnail). | `yt-dlp` for URLs, `ffprobe` for metadata, a download cache on disk. |
| **Player** | Plays a local file through libmpv with a live audio filter chain. Accepts filter-parameter updates mid-playback. | A libmpv instance bound to a Qt render surface. |
| **Exporter** | Runs a one-shot FFmpeg process to write a new MP4 with the current settings baked in. | A subprocess and a progress parser. |
| **Library** | Tracks every video the user has opened or saved, with per-song settings and file paths. | A single `library.json` file next to the executable. |

### 4.1 Shared filter-chain builder

A pure function that both Player and Exporter call:

```python
def build_filter_chain(pitch_semitones: int, vocal_reduce_percent: int) -> str:
    pitch_scale = 2 ** (pitch_semitones / 12)
    mix = (vocal_reduce_percent / 100) * 0.5
    return (
        f"rubberband=pitch={pitch_scale:.6f},"
        f"pan=stereo|c0=c0-{mix:.4f}*c1|c1=c1-{mix:.4f}*c0"
    )
```

This is the only place audio-transform math lives. Live preview and saved file are guaranteed to sound identical because they use the same string.

### 4.2 Relations

- UI → Source Resolver: `resolve(input) → (local_path, title, duration, thumbnail)`
- UI → Player: `load(local_path)`, `set_filter(chain)`, `play/pause/seek`, and events back for playback state
- UI → Exporter: `export(local_path, chain, output_path) → progress events`
- UI ↔ Library: `list()`, `get(id)`, `upsert(entry)`, `remove(id)`
- Source Resolver → Library: records URL ↔ cached-path mappings
- Exporter → Library: records new saved outputs on entries

No node talks to any node except the UI (and the two sides writing to Library). This keeps the dependency graph a star, not a web.

## 5. UI

Single window. Two states.

### 5.1 Home state

The screen the user sees on launch and whenever no video is loaded.

- Two primary buttons, large and central:
  - **Open a video file** — opens a native file picker (MP4, MKV, WebM, MOV).
  - **Paste YouTube link** — opens a small modal with the clipboard content pre-filled if it parses as a YouTube URL; otherwise an empty text field.
- Below the buttons: **library** grid. Thumbnails, titles, and last-used settings for every recent/saved entry. One click reopens a video with its settings restored.
- **Clipboard affordance:** if the clipboard holds a recognisable YouTube URL when the window gains focus, the Paste button shows an inline preview — "Paste this? 🎵 *{video title}*" — populated via a cheap yt-dlp metadata-only call.

### 5.2 Playing state

After a video is loaded.

- **Video surface** occupies the top of the window. Standard play/pause + timeline overlay.
- **Song key slider** below. Range -12 to +12 semitones. Snaps to whole-number steps (no fractional pitches). Default value is 0.
  - Endpoint labels in plain words: *Lower* ↔ *Higher*.
  - Current value rendered as plain sentence: "Normal key" at 0; "Lower by 3 keys" at -3; "Higher by 2 keys" at +2. The word "semitone" never appears.
- **Silence the singer slider.** Range 0–100%, default 0%. Plain label explains the effect.
- **Save this version button.** Always enabled when a video is loaded. Opens a small dialog: suggested filename (`{title} (key -3, vocals off).mp4`), suggested folder (defaults to `Pitched Songs/` next to the exe, but remembers last-used folder), confirm.
- **Back to library link** in a corner.

### 5.3 "Obviously" touches

Features that should feel inevitable, not clever:

1. **Sticky per-song settings** — slider positions are saved in the library on change (debounced) and restored on reopen.
2. **Live filter swaps** — moving a slider updates audio within one render frame; playback never stutters or restarts.
3. **Clipboard-aware Paste button** — URL in clipboard → preview appears.
4. **Progress for every long op** — downloads and exports both have visible progress bars.
5. **Plain-English errors** — no stack traces on screen ever.
6. **Narrow-window grace** — below ~700 px width, the library collapses to a button; the video never gets squeezed.

## 6. Data flow

### 6.1 Playback pipeline

1. **Input received** — local path, or URL from Paste dialog.
2. **Source Resolver** (worker thread):
   - URL case: `yt-dlp` downloads to `cache/{video_id}/`. Cache hit skips download. Progress emitted to UI.
   - Local case: verify existence; call `ffprobe` for duration; generate thumbnail with a single FFmpeg frame-extract.
3. **Player loads** — `mpv.loadfile(local_path)`. libmpv owns its decode/render threads internally.
4. **Filter applied** — `mpv.command("af", "set", build_filter_chain(pitch, vocal_reduce))`.
5. **Slider moved** — same `af set` call with new values. Audible within ~one frame.

### 6.2 Export pipeline

Runs on Save click, on a worker thread. Playback is not interrupted.

1. **Snapshot settings** — capture pitch and vocal-reduce at the moment of click.
2. **Spawn FFmpeg** —
   ```
   ffmpeg -i <local_path> \
          -c:v copy \
          -af <filter_chain> \
          -c:a aac -b:a 192k \
          <output_path>.tmp
   ```
   Video is stream-copied — no re-encode, so even a 10-minute song exports in seconds with zero visual quality loss. Only audio is re-encoded.
3. **Fallback** — if `-c:v copy` fails (source codec can't be muxed into MP4), retry with `-c:v libx264 -crf 23 -preset veryfast`. Slower but universal.
4. **Progress** — parse FFmpeg's `-progress pipe:2` output for `out_time_ms=`; drive the progress bar.
5. **Atomic finalise** — on success, `os.replace(<output>.tmp, <output>)`. On failure or cancel, delete the tmp file.
6. **Library update** — add saved path to the entry's `saved_outputs[]`.

### 6.3 Library persistence

Single JSON file: `library.json`, next to the exe. Read once at startup, held in memory, written after every mutation.

Entry schema:

```json
{
  "id": "<uuid>",
  "title": "Hotel California - Karaoke Version",
  "source_type": "youtube" | "local",
  "source": "https://youtube.com/watch?v=…" | "C:/path/to/file.mp4",
  "cached_path": "cache/abc123/video.mp4",
  "thumbnail_path": "cache/abc123/thumb.jpg",
  "duration_seconds": 342,
  "last_pitch": -3,
  "last_vocal_reduce": 40,
  "last_opened": "2026-04-15T20:11:00Z",
  "saved_outputs": [
    {"path": "C:/Users/Mom/Desktop/Hotel California (key -3).mp4",
     "pitch": -3, "vocal_reduce": 40,
     "saved_at": "2026-04-15T20:15:00Z"}
  ]
}
```

**Atomic write.** Always `temp_file + os.replace()`. Power-cut mid-write can't corrupt.

**Corruption recovery.** If `library.json` fails to parse at startup, rename it to `library.json.corrupted-{timestamp}` and start fresh. The app never crashes because of a single bad file.

## 7. Threading model

- **Qt main thread:** event loop, all widget interactions. Never blocks.
- **Download thread (`QThread`):** runs yt-dlp via the Python API. Emits `progress(int)` and `finished(local_path)` signals.
- **Export thread (`QThread`):** spawns FFmpeg subprocess, parses its stderr progress lines. Emits the same progress/finished signals.
- **libmpv:** manages its own decode/render threads internally; we only call its API from the main thread.

Multiple background operations can run simultaneously (e.g. download song B while exporting song A). Each has its own thread and progress indicator.

## 8. Error handling

Every failure surfaces as a plain-English message with a clear recovery action. Technical detail goes to `logs/app.log`.

| Surface | User sees | Internal |
|---|---|---|
| Invalid URL | "That doesn't look like a video link I can read." | Pre-validate with yt-dlp URL regex |
| Download fails | "Couldn't download — check your internet." [Retry] | Full yt-dlp traceback to log |
| Video unsupported | "This video type isn't supported." | ffprobe fails, fail fast before loading Player |
| Source file moved | "This file seems to have moved." | Detect on library click, remove stale entry |
| Export folder unwritable / disk full | "Couldn't save here — try a different folder." [Pick folder] | Delete `.tmp` partial |
| Library JSON corrupted | *(silent)* | Rename + start fresh |
| libmpv DLL / FFmpeg missing | "Installation is incomplete. Please re-download." | Startup check; fatal, visible |

**Log hygiene.** `logs/app.log` is rotated at 5 MB, keeping the last 3 files next to the exe.

## 9. Testing

### 9.1 Automated (`pytest`)

- **Filter-chain builder** — property tests across the full pitch × vocal-reduce matrix. An audio-math bug is silent and serious; this is the highest-priority test target.
- **Library persistence** — round-trip, corrupted-file recovery, atomic-write under simulated mid-write crash.
- **Source Resolver** — URL parsing, cache hit/miss. yt-dlp is mocked.
- **Exporter (integration)** — run the real bundled FFmpeg on a 10-second public-domain clip in `tests/fixtures/`. Assert output is a valid MP4, duration matches input, audio pitch shifts by the requested amount (verify via `librosa.pyin` or an FFT check).

### 9.2 Manual smoke (pre-release checklist)

- Open a local MP4, scrub pitch, save → output plays correctly in VLC.
- Paste a YouTube URL, download, play, scrub pitch, save → same.
- Close and reopen the app → library restores, per-song settings restore.
- Copy the built `.exe` to a clean Windows 11 machine (or VM) with no Python, no FFmpeg, no anything → full flow works.

## 10. Packaging and distribution

- **Build tool:** PyInstaller, `--onefile --windowed`.
- **Python:** 3.11 or newer.
- **Bundled binaries inside the exe:**
  - `libmpv-2.dll` (~25 MB)
  - `ffmpeg.exe` (minimal static build, ~40 MB)
  - `yt-dlp` (Python package, bundled as code)
- **PySide6** for Qt bindings.
- **Expected final size:** 100–150 MB single `.exe`.
- **First-run behaviour:** on launch, if `cache/`, `logs/`, or `library.json` are missing next to the exe, create them. No admin rights required.
- **Antivirus fallback:** PyInstaller `--onefile` occasionally trips AV heuristics. If this becomes a real distribution problem, fall back to `--onedir` (a folder containing the exe + DLLs). Still portable, still no installer.

## 11. Directory layout of the built app (runtime)

```
KaraokeBuddy.exe
cache/
  <youtube-id>/
    video.mp4
    thumb.jpg
logs/
  app.log
library.json
Pitched Songs/          # default save folder, created on first export
```

Everything lives next to the exe. Delete the folder → app state is gone. Move the folder to a USB stick → everything goes with it.

## 12. Project layout (source)

```
karaoke-buddy/
  pyproject.toml
  README.md
  src/
    karaoke_buddy/
      __init__.py
      __main__.py          # entry point
      ui/                  # Qt widgets
        main_window.py
        home_view.py
        playing_view.py
        library_view.py
      core/
        filter_chain.py    # the pure filter-builder function
        source_resolver.py # yt-dlp + ffprobe
        player.py          # libmpv wrapper
        exporter.py        # FFmpeg subprocess
        library.py         # library.json persistence
      resources/
        icon.ico
  tests/
    fixtures/
      sample_10s.mp4       # public-domain karaoke clip
    test_filter_chain.py
    test_library.py
    test_source_resolver.py
    test_exporter.py       # integration
  build/
    build.py               # PyInstaller driver
  docs/
    superpowers/
      specs/
        2026-04-15-karaoke-buddy-design.md
```

## 13. Open questions / deferred

- **Default save folder** — currently `Pitched Songs/` next to the exe. Alternative: user's `Videos/` folder. Decide in implementation based on first user test.
- **Library growth** — no limit on recent entries in v1. If it becomes a problem, a simple "keep last 50" rule added later.
- **Cache size** — same. YouTube downloads accumulate. A "Clear cache" button in settings is likely v1.1.
- **Thumbnail generation timing** — extracting a frame adds ~200 ms to first-open latency. Acceptable for v1; may defer to background if it becomes noticeable.
