from pathlib import Path
import subprocess
from unittest.mock import patch

import pytest

from karaoke_buddy.core.dependency_preflight import (
    RuntimeDependencyError,
    preflight_runtime_dependencies,
)


def test_preflight_reports_missing_bundled_files() -> None:
    with pytest.raises(RuntimeDependencyError) as exc_info:
        preflight_runtime_dependencies(
            ffmpeg_exe=None,
            ffprobe_exe=Path("ffprobe.exe"),
            libmpv_dll=None,
            frozen=True,
        )

    message = str(exc_info.value)
    assert "ffmpeg.exe" in message
    assert "libmpv-2.dll" in message


def test_preflight_reports_missing_dev_path_tools() -> None:
    with patch("shutil.which", return_value=None):
        with pytest.raises(RuntimeDependencyError) as exc_info:
            preflight_runtime_dependencies(
                ffmpeg_exe=None,
                ffprobe_exe=None,
                libmpv_dll=None,
                frozen=False,
            )

    message = str(exc_info.value)
    assert "ffmpeg on PATH" in message
    assert "ffprobe on PATH" in message


def test_preflight_reports_unloadable_python_dependency() -> None:
    def _import_module(name: str):
        if name == "mpv":
            raise OSError("libmpv not found")
        return object()

    with patch("shutil.which", return_value="tool.exe"):
        with patch("importlib.import_module", side_effect=_import_module):
            with pytest.raises(RuntimeDependencyError) as exc_info:
                preflight_runtime_dependencies(
                    ffmpeg_exe=None,
                    ffprobe_exe=None,
                    libmpv_dll=None,
                    frozen=False,
                )

    assert "libmpv / python-mpv" in str(exc_info.value)
    assert "libmpv not found" in str(exc_info.value)


def test_preflight_reports_non_runnable_bundled_ffmpeg(tmp_path) -> None:
    ffmpeg = tmp_path / "ffmpeg.exe"
    ffprobe = tmp_path / "ffprobe.exe"
    libmpv = tmp_path / "libmpv-2.dll"
    ffmpeg.write_bytes(b"")
    ffprobe.write_bytes(b"")
    libmpv.write_bytes(b"")

    def _run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        if command[0] == str(ffmpeg):
            return subprocess.CompletedProcess(
                command,
                returncode=3221225781,
                stdout="",
                stderr="bad image",
            )
        return subprocess.CompletedProcess(command, returncode=0, stdout="", stderr="")

    with patch("subprocess.run", side_effect=_run):
        with patch("importlib.import_module", return_value=object()):
            with pytest.raises(RuntimeDependencyError) as exc_info:
                preflight_runtime_dependencies(
                    ffmpeg_exe=ffmpeg,
                    ffprobe_exe=ffprobe,
                    libmpv_dll=libmpv,
                    frozen=True,
                )

    message = str(exc_info.value)
    assert "ffmpeg.exe could not be executed" in message
    assert "exit code 3221225781" in message
    assert "bad image" in message


def test_preflight_reports_non_runnable_dev_ffprobe() -> None:
    def _which(name: str) -> str:
        return f"C:/tools/{name}.exe"

    def _run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        if command[0] == "C:/tools/ffprobe.exe":
            raise OSError("not a valid Win32 application")
        return subprocess.CompletedProcess(command, returncode=0, stdout="", stderr="")

    with patch("shutil.which", side_effect=_which):
        with patch("subprocess.run", side_effect=_run):
            with patch("importlib.import_module", return_value=object()):
                with pytest.raises(RuntimeDependencyError) as exc_info:
                    preflight_runtime_dependencies(
                        ffmpeg_exe=None,
                        ffprobe_exe=None,
                        libmpv_dll=None,
                        frozen=False,
                    )

    message = str(exc_info.value)
    assert "ffprobe on PATH could not be executed" in message
    assert "not a valid Win32 application" in message


def test_preflight_passes_when_runtime_is_available() -> None:
    with patch("shutil.which", return_value="tool.exe"):
        with patch("subprocess.run") as run:
            run.return_value = subprocess.CompletedProcess(
                ["tool.exe", "-version"],
                returncode=0,
                stdout="version",
                stderr="",
            )
            with patch(
                "importlib.import_module", return_value=object()
            ) as import_module:
                preflight_runtime_dependencies(
                    ffmpeg_exe=None,
                    ffprobe_exe=None,
                    libmpv_dll=None,
                    frozen=False,
                )

    assert import_module.call_count == 2
