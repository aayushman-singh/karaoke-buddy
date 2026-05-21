"""Runtime dependency preflight for media backends."""

import importlib
import logging
import shutil
import subprocess
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
        else:
            missing.extend(_executable_problem("ffmpeg.exe", ffmpeg_exe))
        if ffprobe_exe is None:
            missing.append("ffprobe.exe")
        else:
            missing.extend(_executable_problem("ffprobe.exe", ffprobe_exe))
        if libmpv_dll is None:
            missing.append("libmpv-2.dll")
    else:
        ffmpeg = shutil.which("ffmpeg")
        ffprobe = shutil.which("ffprobe")
        if ffmpeg is None:
            missing.append("ffmpeg on PATH")
        else:
            missing.extend(_executable_problem("ffmpeg on PATH", ffmpeg))
        if ffprobe is None:
            missing.append("ffprobe on PATH")
        else:
            missing.extend(_executable_problem("ffprobe on PATH", ffprobe))

    missing.extend(_import_problem("yt_dlp", "yt-dlp"))
    if not frozen or libmpv_dll is not None:
        missing.extend(_import_problem("mpv", "libmpv / python-mpv"))

    if missing:
        raise RuntimeDependencyError(
            "Required media dependencies are missing or unusable: "
            + ", ".join(missing)
            + ". Install FFmpeg, yt-dlp, and libmpv before starting KaraokeBuddy."
        )


def _executable_problem(label: str, executable: str | Path) -> list[str]:
    command = [str(executable), "-version"]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except Exception as exc:  # noqa: BLE001
        log.exception(
            "Dependency executable failed: label=%s executable=%s command=%s",
            label,
            executable,
            command,
        )
        return [f"{label} could not be executed ({type(exc).__name__}: {exc})"]

    if result.returncode != 0:
        output = (result.stderr or result.stdout or "").strip()
        detail = f"exit code {result.returncode}"
        if output:
            detail = f"{detail}: {output}"
        log.error(
            "Dependency executable returned non-zero: label=%s executable=%s "
            "returncode=%s stdout=%r stderr=%r",
            label,
            executable,
            result.returncode,
            result.stdout,
            result.stderr,
        )
        return [f"{label} could not be executed ({detail})"]

    return []


def _import_problem(module_name: str, label: str) -> list[str]:
    try:
        importlib.import_module(module_name)
    except Exception as exc:  # noqa: BLE001
        log.exception(
            "Dependency import failed: module=%s label=%s", module_name, label
        )
        return [f"{label} could not be loaded ({type(exc).__name__}: {exc})"]
    return []
