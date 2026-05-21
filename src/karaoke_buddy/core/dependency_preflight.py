"""Runtime dependency preflight for media backends."""

import importlib
import logging
import shutil
from pathlib import Path

log = logging.getLogger(__name__)


class RuntimeDependencyError(RuntimeError):
    """Raised when a required runtime dependency is missing or unusable."""


def preflight_runtime_dependencies(
    *,
    ffmpeg_exe: Path | None,
    ffprobe_exe: Path | None,
    libmpv_dll: Path | None,
    frozen: bool,
) -> None:
    """Fail before startup if required media dependencies are unavailable."""
    missing: list[str] = []

    if frozen:
        if ffmpeg_exe is None:
            missing.append("ffmpeg.exe")
        if ffprobe_exe is None:
            missing.append("ffprobe.exe")
        if libmpv_dll is None:
            missing.append("libmpv-2.dll")
    else:
        if shutil.which("ffmpeg") is None:
            missing.append("ffmpeg on PATH")
        if shutil.which("ffprobe") is None:
            missing.append("ffprobe on PATH")

    missing.extend(_import_problem("yt_dlp", "yt-dlp"))
    if not frozen or libmpv_dll is not None:
        missing.extend(_import_problem("mpv", "libmpv / python-mpv"))

    if missing:
        raise RuntimeDependencyError(
            "Missing required media dependencies: "
            + ", ".join(missing)
            + ". Install FFmpeg, yt-dlp, and libmpv before starting KaraokeBuddy."
        )


def _import_problem(module_name: str, label: str) -> list[str]:
    try:
        importlib.import_module(module_name)
    except Exception as exc:  # noqa: BLE001
        log.exception(
            "Dependency import failed: module=%s label=%s", module_name, label
        )
        return [f"{label} could not be loaded ({type(exc).__name__}: {exc})"]
    return []
