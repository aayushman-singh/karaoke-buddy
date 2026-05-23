"""Bundled binary discovery for dev and PyInstaller builds."""

from __future__ import annotations

import sys
from pathlib import Path


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def locate_bundled(name: str) -> Path | None:
    """Find a file bundled next to the exe or in the one-file extract dir."""
    if not is_frozen():
        return None
    search_dirs: list[Path] = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        search_dirs.append(Path(meipass))
    search_dirs.append(Path(sys.executable).parent)
    for directory in search_dirs:
        candidate = directory / name
        if candidate.exists():
            return candidate
    return None


def resolve_deno_executable() -> str:
    """Return a Deno binary path for yt-dlp (bundled in portable builds)."""
    bundled = locate_bundled("deno.exe")
    if bundled is not None:
        return str(bundled)
    import deno  # noqa: PLC0415

    return deno.find_deno_bin()


def resolve_ffprobe_executable(ffmpeg_exe: Path | None = None) -> str:
    """Return an ffprobe path. Prefer bundled exe sibling to ffmpeg, else PATH."""
    bundled = locate_bundled("ffprobe.exe")
    if bundled is not None:
        return str(bundled)
    if ffmpeg_exe is not None:
        sibling = Path(ffmpeg_exe).with_name(
            "ffprobe.exe" if ffmpeg_exe.name.lower().endswith(".exe") else "ffprobe"
        )
        if sibling.exists():
            return str(sibling)
    return "ffprobe"


def dev_binary_dir(base_dir: Path) -> Path | None:
    """``build/bin`` when running from a source checkout."""
    dev_bin = base_dir / "build" / "bin"
    return dev_bin if dev_bin.is_dir() else None


def default_export_dir() -> Path:
    """User-facing default folder for exported MP4s.

    Resolves to ``~/Videos/KaraokeBuddy``. On Windows this is the standard
    Videos shell folder; on Linux it matches the XDG ``VIDEOS`` default. The
    folder is created lazily by the caller on first export.
    """
    return Path.home() / "Videos" / "KaraokeBuddy"


def runtime_binary_dirs(base_dir: Path | None = None) -> list[Path]:
    """Directories that may contain ffmpeg, libmpv, and deno."""
    if not is_frozen():
        if base_dir is None:
            return []
        dev_bin = dev_binary_dir(base_dir)
        return [dev_bin] if dev_bin else []

    dirs: list[Path] = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        dirs.append(Path(meipass))
    dirs.append(Path(sys.executable).parent)
    return dirs
