# KaraokeBuddy

![KaraokeBuddy demo](docs/demo/assets/readme-demo.gif)

## Demo

- Generated demo previews: [library](docs/demo/assets/home-library.png), [player controls](docs/demo/assets/playing-controls.png)
- Loom plan: [30-second script](docs/demo/demo-script.md) and [recording notes](docs/demo/loom.md)
- Run locally: `python -m karaoke_buddy`

## Reliable Launch

Install once: `python -m pip install -e ".[dev]"`
Run source: `python -m karaoke_buddy`
Build package: place `ffmpeg.exe`, `ffprobe.exe`, and `libmpv-2.dll` in `build/bin/`, then run `python build/build.py`.
Run package: `build/dist/KaraokeBuddy.exe`
Smoke check: the main KaraokeBuddy window should appear before any song is opened.
Logs: `logs/app.log`
Screenshot:
![Reliable launch smoke](docs/reliable-launch-smoke.png)

Sing along in your own vocal range. Open any karaoke video — from disk or a YouTube URL — and drag a **Song key** slider while the video plays. Pitch shifts live without changing tempo or drifting the on-screen lyrics. A **Silence the singer** slider optionally removes guide vocals. One button exports the current settings to a new MP4.

**Target platform:** Windows 11  

[Download KaraokeBuddy.exe for Windows](https://github.com/aayushman-singh/karaoke-buddy/releases/download/v0.1.0/KaraokeBuddy.exe)

**Distribution:** Single double-clickable `.exe` — no installer, no admin rights, no external dependencies.

---

## Quick start (development)

### Dependency preflight demo

Run `python -m karaoke_buddy`.
Before the main window opens, KaraokeBuddy now verifies FFmpeg, FFprobe, yt-dlp, and libmpv.
If anything is missing, startup stops with a critical dialog and writes details to `logs/app.log`.
In development, `ffmpeg` and `ffprobe` must be on PATH.
In the packaged app, `ffmpeg.exe`, `ffprobe.exe`, and `libmpv-2.dll` must be bundled beside the exe or in the one-file extraction directory.
This feature has no visual redesign, so there is no screenshot.

### Prerequisites

- Python 3.11+
- FFmpeg on PATH (for metadata, thumbnails, and export)
- libmpv / mpv for video playback

### Install

```bash
pip install -e ".[dev]"
```

### Run

```bash
karaoke-buddy
```

### Run tests

```bash
# Create the 10-second test fixture first (requires FFmpeg)
python build/create_fixture.py

# Run all tests
pytest

# Run only the fast unit tests (no FFmpeg required)
pytest tests/test_filter_chain.py tests/test_library.py tests/test_source_resolver.py
```

---

## Build the `.exe`

1. Place `ffmpeg.exe`, `ffprobe.exe`, and `libmpv-2.dll` in `build/bin/`.
2. Run:

```bash
python build/build.py
```

The output is `build/dist/KaraokeBuddy.exe`. Copy it anywhere - it's fully self-contained.

If AV heuristics flag the single-file exe:

```bash
python build/build.py --onedir
```

## Packaged home verification

Run the recruiter-facing exe verification:

```powershell
powershell -ExecutionPolicy Bypass -File build/verify_packaged_home.ps1
```

Exact result on 2026-05-21: `build/dist/KaraokeBuddy.exe` opened a visible
`KaraokeBuddy` home window and captured [docs/packaged-home.png](docs/packaged-home.png).

---

## Architecture

Five nodes with narrow interfaces:

| Node | Purpose |
|---|---|
| **UI** | Qt widgets; dispatches user intent; presents progress and errors. |
| **Source Resolver** | Turns local path or YouTube URL into a local file + metadata. |
| **Player** | libmpv instance with live audio filter chain. |
| **Exporter** | One-shot FFmpeg subprocess; atomic MP4 write. |
| **Library** | `library.json` — per-song sticky settings and saved outputs. |

A single pure function — `build_filter_chain(pitch, vocal_reduce)` — is the only place audio-transform math lives. Both the Player and the Exporter call it, so live preview and the saved file are guaranteed to sound identical.

---

## Runtime layout

```
KaraokeBuddy.exe
cache/
  <youtube-id>/
    video.mp4
    thumb.jpg
    title.txt
logs/
  app.log
library.json
Pitched Songs/          ← default export folder
```

Everything lives next to the exe. Move the folder to a USB stick → everything goes with it.

---

## Open questions (deferred to v1.1)

- Default save folder: currently `Pitched Songs/` next to the exe. Alternative: user's `Videos/` folder.
- Library growth cap: no limit in v1.
- Cache size: no auto-clean in v1. A "Clear cache" button is likely v1.1.
- AI-based vocal separation (Demucs/Spleeter): out of scope for v1.
