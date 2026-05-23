# Contributing To KaraokeBuddy

Thanks for your interest. KaraokeBuddy is a small Windows-focused desktop app,
so most contributions land as bug reports, fixes, or small features. This guide
covers how to set up, what the project values, and what to expect when you open
a PR.

## Quick setup

If you have [`just`](https://just.systems) installed, the one-shot path:

```bash
git clone https://github.com/aayushman-singh/karaoke-buddy.git
cd karaoke-buddy
python -m venv .venv && .venv\Scripts\activate   # or source .venv/bin/activate
just install     # editable install + pre-commit hooks
just smoke       # confirm the Qt window boots
```

Otherwise, the manual path:

```bash
git clone https://github.com/aayushman-singh/karaoke-buddy.git
cd karaoke-buddy
python -m venv .venv
.venv\Scripts\activate              # Windows
# source .venv/bin/activate         # macOS/Linux
pip install -e ".[dev]"
```

You also need:

- **FFmpeg + ffprobe** on `PATH` (or dropped into `build/bin/`)
- **libmpv** on `PATH` (or `libmpv-2.dll` in `build/bin/` on Windows)

Confirm the install works:

```bash
python -m karaoke_buddy --smoke-check
```

This boots the Qt app for 250ms, verifies UI imports, and exits cleanly. It
is the fastest signal that your dev environment is healthy.

## Running tests

```bash
# Run everything
pytest

# Run the CI-sized non-FFmpeg surface
pytest --ignore=tests/test_exporter.py

# Run only the FFmpeg export integration tests
pytest tests/test_exporter.py -rs
```

CI (see `.github/workflows/ci.yml`) runs ruff plus the non-FFmpeg test surface
on every push and PR. Export integration tests run locally because they depend
on the system FFmpeg build and available filters.

## Pre-commit hooks

`just install` sets these up for you. Manual install:

```bash
pip install pre-commit
pre-commit install
```

Ruff and whitespace/EOF fixes now run automatically before every commit. To
sweep the whole repo on demand:

```bash
pre-commit run --all-files
# or: just hooks
```

## Style

- **Formatter / linter**: `ruff`. Pre-commit runs this for you; manual invocation:
  ```bash
  ruff check --fix . && ruff format .
  # or: just fmt
  ```
- **Commit messages**: Conventional Commits (`feat:`, `fix:`, `refactor:`,
  `test:`, `docs:`, `chore:`).
- **Type hints**: keep public functions typed. `from __future__ import
  annotations` is fine where it helps.
- **Failure handling**: KaraokeBuddy prefers explicit failures over silent
  fallbacks. If you catch an exception, log it with context and surface a
  user-visible error. Do not swallow it.

## Architecture in one screen

Five nodes, narrow interfaces:

| Node            | File                                    | Responsibility |
| --------------- | --------------------------------------- | -------------- |
| UI              | `src/karaoke_buddy/ui/`                 | Qt widgets, dispatches user intent. |
| Source Resolver | `src/karaoke_buddy/core/source_resolver.py` | Local path or YouTube URL -> local file + metadata. |
| Player          | `src/karaoke_buddy/core/player.py`      | libmpv playback with live audio filter chain. |
| Exporter        | `src/karaoke_buddy/core/exporter.py`    | One-shot FFmpeg subprocess; atomic MP4 write. |
| Library         | `src/karaoke_buddy/core/library.py`     | `library.json` - per-song sticky settings, saved outputs. |

A single pure function, `build_filter_chain(pitch, vocal_reduce)`, is the
only place audio-transform math lives. Player and Exporter both call it, so
live preview and the saved file sound identical.

## Pull requests

- Open one PR per logical change. Smaller is faster to review.
- Include a one-line "why" in the PR description.
- Make sure `ruff check .` and the fast test suite pass.
- If the change is user-visible, update `README.md` and `CHANGELOG.md`.
- If the change is risky (touches playback timing, export filters, library
  serialization), describe how you verified it locally - ideally a screen
  recording or before/after MP4.

## Reporting bugs

Open an issue with:

- What you tried (one command or click sequence)
- What you expected
- What happened instead
- `logs/app.log` (next to the exe on Windows; in the repo root in dev)
- Your OS + Python version + FFmpeg version

## Scope

In scope: anything that improves the "open video -> pitch shift -> export" loop
on Windows and Linux.

Out of scope (for now): mobile, macOS-specific features, AI-based vocal
separation (Demucs/Spleeter). Open an issue first if you want to propose
extending the scope.
