# Recon - KaraokeBuddy

## Elevator pitch

KaraokeBuddy is a Windows desktop app for opening a local or YouTube karaoke video, shifting the song key live, reducing guide vocals, and exporting the result as a new MP4. Its strongest portfolio angle is "consumer-simple UI over real media tooling": PySide6 for the app shell, libmpv for live playback, yt-dlp/FFmpeg for resolving and exporting media. The intended user outcome is a non-technical singer can double-click one exe, load a song, adjust it into their vocal range, and save a version that sounds like the preview.

## Live state

- Build: pass. `python build/build.py` completed and produced `C:/Repo/karaoke-buddy/build/dist/KaraokeBuddy.exe`.
- Local dev: fail. `python -m karaoke_buddy` fails before UI launch:

```text
OSError: Cannot find mpv-1.dll, mpv-2.dll or libmpv-2.dll in your system %PATH%.
```

With `build/bin` prepended to `PATH`, it fails later:

```text
ImportError: cannot import name 'QThread' from 'PySide6.QtWidgets'
```

- Deployed URL: none.
- Deployed state: none. A local packaged exe was built, but no public release/demo URL exists; when probed locally, the exe logged startup but no `KaraokeBuddy` main window appeared within 90 seconds.

## What works

- PyInstaller build path - evidence: `python build/build.py` passed, bundling `ffmpeg.exe`, `ffprobe.exe`, and `libmpv-2.dll` from `build/bin`; output was `build/dist/KaraokeBuddy.exe`.
- Unit and integration tests - evidence: default `pytest` passed `79 passed, 6 skipped`; with `C:/Repo/karaoke-buddy/build/bin` on `PATH`, full suite passed `85 passed in 3.06s`.
- Local video resolver backend - evidence: a generated 10-second MP4 resolved through `SourceResolver`, returned title `sample10`, duration `10`, source type `local`, and created a thumbnail.
- YouTube resolver backend - evidence: `SourceResolver` downloaded `https://www.youtube.com/watch?v=jNQXAC9IVRw` ("Me at the zoo"), produced a local MP4, thumbnail, duration `19`, and 17 progress events.
- Export backend - evidence: `tests/test_exporter.py` created synthetic MP4s, applied pitch/vocal filters through FFmpeg, validated outputs with ffprobe, and passed when FFmpeg was on `PATH`.
- Persistent library model - evidence: `tests/test_library.py` covers list ordering, upsert/remove, saved outputs, corrupt-file handling, and atomic JSON writes.
- Shared audio filter function - evidence: `src/karaoke_buddy/core/filter_chain.py` is covered by property-style tests and is used by both playback and export code.

## What is broken or half-built

- Source app cannot launch - evidence: `python -m karaoke_buddy` fails because `src/karaoke_buddy/core/player.py` imports `mpv` before the repo's bundled `build/bin/libmpv-2.dll` is made available - why it matters: an engineer reviewer following the README hits a traceback immediately.
- UI import is broken after fixing `PATH` - evidence: `src/karaoke_buddy/ui/home_view.py:8-16` imports `QThread` from `PySide6.QtWidgets`; PySide6 exposes it from `QtCore` - why it matters: this blocks the main window and explains why tests can be green while the product is dead.
- Packaged exe did not show a usable main window in probe - evidence: `build/dist/KaraokeBuddy.exe` stayed alive for 90 seconds and logged startup, but `MainWindowHandle=0` and `MainWindowTitle=` - why it matters: recruiter double-clicks, sees nothing, closes it.
- README run/build instructions are misleading - evidence: README says `python -m karaoke_buddy` and "output is `dist/KaraokeBuddy.exe`"; actual build script writes `build/dist/KaraokeBuddy.exe`, and source launch needs a libmpv path decision - why it matters: reviewers judge polish by whether instructions match reality.
- Tests miss the shipped failure - evidence: `pytest` passes even though importing the UI through the real entry point fails - why it matters: the repo currently signals confidence while the demo path is untested.
- No public demo or release artifact - evidence: `git remote -v` is empty, README has no GitHub Releases/download/demo link, and no deployed URL exists - why it matters: recruiters rarely build a Windows media app from source.
- No screenshots, GIF, or Loom - evidence: README has no visual assets, and `rg --files -u` found no screenshot/demo media in the repo - why it matters: for a desktop GUI app, visual proof is the fastest trust builder.
- UI polish is unproven and likely plain Qt - evidence: current UI is basic `QLabel`/`QPushButton`/`QSlider` styling, and the app could not be visually inspected through the source entry point - why it matters: first impression is the product here.
- YouTube download emits a yt-dlp runtime warning - evidence: live resolver test printed "No supported JavaScript runtime could be found..." - why it matters: YouTube support is part of the pitch, and flaky media extraction can embarrass a live demo.
- Some failures are hidden rather than loud - evidence: thumbnail generation catches any exception and returns `None`; `Player.set_filter` catches any exception and only logs a warning - why it matters: the key slider could appear to work while silently failing to change audio, which is worse than a clear failure.
- Large local binaries/build artifacts are not productized - evidence: `build/bin` contains untracked FFmpeg/libmpv binaries and `build/dist/KaraokeBuddy.exe` is ignored/local-only - why it matters: the repo can build on this machine, but the distribution story is not reviewer-ready.

## What is missing for hireability

- A one-click public way to try it - recruiters need a GitHub Release or portfolio link before they will invest in local setup.
- A proof-of-life visual - screenshots/GIF/Loom would let non-Windows reviewers understand the product in 10 seconds.
- A tested launch path - a single smoke check importing/starting the real entry point would prevent "green tests, dead app" optics.
- A crisp demo script - "load this sample, drag key slider, export MP4" should be visible in README so the reviewer knows what success looks like.
- UI differentiation - the underlying idea is stronger than the current surface; a polished first screen and playback controls would make the project feel intentional, not tutorial-like.
- Release notes/checksum/basic trust cues - Windows exes trigger caution; a release page with version, date, artifact size, and known requirements reduces friction.
- First-class YouTube reliability - YouTube is part of the hiring demo, so the demo needs current yt-dlp/JS runtime handling rather than treating local files as the only safe path.

## Seniority signal verdict

The core code shows real engineering instincts: narrow modules, pure filter-chain logic shared by preview/export, atomic library writes, a PyInstaller build driver, conventional commits, and a meaningful test suite. The hireability problem is not "junior tutorial code"; it is an unverified product boundary. The repo proves backend pieces, but the actual user contract - double-click or `python -m`, see a window, load a song, adjust audio, export - is currently broken or not demonstrated, and that gap dominates the portfolio impression.

## Stack

- Language / framework / key libs: Python `>=3.11` (tested here with Python `3.14.2`), PySide6 `>=6.6` (installed `6.11.0`), python-mpv `>=1.0.6` (installed `1.0.8`), yt-dlp `>=2024.1.1` (installed `2026.3.17`), FFmpeg/ffprobe, libmpv, PyInstaller `6.19.0`, pytest, pytest-qt, Hypothesis, Ruff.
- Deploy target: current is local-only Windows exe in ignored `build/dist`. Recommended target is both GitHub Releases for the exe and a portfolio page/demo video for proof-of-life; web app hosts like Vercel/Railway are not the right deployment for the app itself.

## Backlog - ranked by hire-impact-per-hour

| # | Task | Effort | Impact | Why hireable |
|---:|---|---|---|---|
| 1 | Fix source and packaged launch so the main window appears reliably | S | high | Nothing matters until a reviewer can open the app and see KaraokeBuddy. |
| 2 | Add a real launch smoke check that imports UI modules and starts the app briefly | S | high | Prevents green tests from missing a dead demo again. |
| 3 | Verify packaged exe reaches the home screen and document the exact launch result | S | high | The deliverable is a Windows exe; this is the recruiter-facing artifact. |
| 4 | Publish a GitHub Release with the exe and link it from README | M | high | Turns the project from "source code" into something a recruiter can actually try. |
| 5 | Add README screenshots/GIF/Loom and a 30-second demo script | S | high | Lets reviewers understand the value before installing anything. |
| 6 | Correct README run/build instructions and artifact path | S | high | Removes immediate reviewer friction and signals care. |
| 7 | Make dependency preflight explicit and loud for libmpv/FFmpeg/yt-dlp runtime needs | S | high | Broken media dependencies should produce a clear message, not a traceback or silent no-window state. |
| 8 | Add a bundled sample or documented tiny test clip workflow | S | medium | Gives reviewers a deterministic way to exercise pitch shift and export. |
| 9 | Polish first screen and playback controls after launch is fixed | M | medium | The project idea is memorable; the UI needs to look as deliberate as the core. |
| 10 | Resolve yt-dlp JavaScript runtime warning and keep YouTube in the main demo | M | high | YouTube is a first-class demo path; flaky extraction undermines trust during the exact flow recruiters will see. |
| 11 | Add one user-flow smoke test for local-file resolve -> play-shell/load -> export | M | medium | Covers the real story without turning the portfolio into a test-heavy exercise. |
| 12 | Make core audio-filter failures fail visibly instead of warning-only | S | medium | A slider that silently does nothing is a demo killer. |
| 13 | Decide what to do with untracked build binaries and generated build outputs | S | medium | Keeps the public repo clean while preserving a reproducible release process. |
| 14 | Add release trust cues: version, date, file size, checksum, Windows note | S | medium | Reduces hesitation around downloading a large Windows executable. |
| 15 | Add lightweight app metadata to `pyproject.toml` | S | low | Nice polish for engineer reviewers, but less important than a working demo. |

## Recommended dispatch order

1. First dispatch bundle: Tasks #1, #2, #3, #6, #7, #10 - fix launch, add a smoke check, verify the exe, correct instructions, make dependency failures loud, and keep YouTube working as a first-class path.
2. Second dispatch bundle: Tasks #4, #5, #14 - publish a GitHub Release, add a portfolio/demo-video proof point, and include release trust cues.
3. Third dispatch bundle: Tasks #8, #9, #11, #12 - add a deterministic demo clip/workflow, polish the first screen/playback controls, add a user-flow smoke test, and make audio-filter failures visible.
4. Cleanup dispatch: Tasks #13, #15 - finalize binary/artifact policy and add lightweight project metadata.

## Dispatch decisions

- Public try-it path: both GitHub Release and portfolio/demo video.
- First hiring demo: include YouTube download as part of the main demo; local-file pitch/export is not enough by itself.
- Binary distribution rule: FFmpeg/libmpv binaries are allowed in release artifacts only, not committed into normal source history.
- GitHub repo: publish under the same project name, `karaoke-buddy`; remote will be created later.
- Hiring audience: optimize the demo for both Python desktop/tooling roles and product-minded full-stack roles.
- Next implementation slice: do all launch plus README/release-demo polish work together, rather than limiting the slice to launch only.
