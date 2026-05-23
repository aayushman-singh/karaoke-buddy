# Changelog

All notable changes to KaraokeBuddy are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project
follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-05-23

### Fixed
- CI now installs the project package with its development dependencies before
  running tests, so the tested import surface matches a real checkout.
- Thumbnail generation, unreadable library files, missing library mutation
  targets, playback filter failures, and stream-copy export failures now stop
  the dependent workflow instead of continuing with degraded behavior.

### Changed
- Reworked the README for open-source review: clearer user story, setup path,
  architecture summary, and honest test-strategy notes.
- Default export folder is now `~/Videos/KaraokeBuddy/` on both Windows and
  Linux (previously `Pitched Songs/` next to the exe). The folder is created
  on first export.
- Ignored local export folders and coverage data so release commits do not
  accidentally include generated artifacts.

### Added
- `LICENSE` (MIT) and `NOTICE.md` documenting bundled-binary licenses.
- `CONTRIBUTING.md` with dev setup and PR guidance.
- GitHub Actions CI: ruff + non-FFmpeg tests on every push and PR.
- `SECURITY.md` with a coordinated-disclosure policy and contact.
- GitHub issue templates (`bug_report.yml`, `feature_request.yml`, `config.yml`)
  and a pull-request template.
- `.github/CODEOWNERS`, `.github/FUNDING.yml` placeholder, and
  `.github/dependabot.yml` (daily pip updates, weekly github-actions).
- `.pre-commit-config.yaml` - ruff + whitespace/EOF/yaml/toml checks on every commit.
- `justfile` for one-command workflows (`just install`, `just test`, `just build`,
  `just smoke`, `just fmt`, `just hooks`, etc.).
- Windows release workflow that builds and attaches `KaraokeBuddy.exe` when a
  `v*` tag is pushed, with manual dispatch for rebuilding an existing tag.
- `CODE_OF_CONDUCT.md` using Contributor Covenant 2.1.

## [0.1.0] - 2026-04-17

Initial public release.

### Added
- Open a local video file or paste a YouTube URL.
- Live pitch shift via a "Song key" slider (semitones, no tempo change).
- "Silence the singer" slider for center-channel vocal reduction.
- Export current settings to a new MP4 via FFmpeg.
- Library view that remembers previous videos and saved outputs with sticky
  per-song settings.
- Single-file Windows `.exe` via PyInstaller, bundling FFmpeg, ffprobe,
  libmpv-2.dll, and deno.
- Dependency preflight: missing FFmpeg / libmpv / yt-dlp surface as a clear
  dialog instead of a traceback.
- Launch smoke check: `python -m karaoke_buddy --smoke-check` boots the Qt
  window briefly to catch UI import or startup regressions in CI.

[Unreleased]: https://github.com/aayushman-singh/karaoke-buddy/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/aayushman-singh/karaoke-buddy/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/aayushman-singh/karaoke-buddy/releases/tag/v0.1.0
