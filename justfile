# KaraokeBuddy task runner. Install `just` from https://just.systems and run
# `just` to list recipes, or `just <recipe>` to invoke one.
#
# Why `just` instead of `make`: cross-platform on Windows without msys, and the
# syntax is sane.

set windows-shell := ["pwsh", "-NoLogo", "-Command"]

# Default recipe: list everything.
default:
    @just --list

# One-shot dev install: editable package + dev tools + pre-commit hooks.
install:
    python -m pip install -e ".[dev]"
    python -m pip install pre-commit
    pre-commit install

# Run the app from source.
run:
    python -m karaoke_buddy

# Boot the Qt window for 250ms then exit. Fastest "did I break startup?" check.
smoke:
    python -m karaoke_buddy --smoke-check

# CI-equivalent test surface: everything except the FFmpeg export integration.
test:
    pytest --ignore=tests/test_exporter.py

# Full suite including FFmpeg export tests. Requires ffmpeg + ffprobe on PATH.
test-full:
    pytest

# Lint + format check (read-only, what CI runs).
lint:
    ruff check .
    ruff format --check .

# Auto-fix lint and format issues in-place.
fmt:
    ruff check --fix .
    ruff format .

# Run all pre-commit hooks across the whole repo.
hooks:
    pre-commit run --all-files

# Single-file PyInstaller build. Requires build/bin/ffmpeg.exe + ffprobe.exe + libmpv-2.dll.
build:
    python build/build.py

# Folder-layout build (smaller when zipped, friendlier to AV heuristics).
build-dir:
    python build/build.py --onedir

# Verify the packaged .exe shows the home window. Saves docs/packaged-home.png.
verify-packaged:
    powershell -ExecutionPolicy Bypass -File build/verify_packaged_home.ps1

# Remove caches, build artifacts, and the test fixture.
clean:
    Remove-Item -Recurse -Force .pytest_cache, .ruff_cache, .hypothesis, build/dist, build/work, dist -ErrorAction SilentlyContinue
