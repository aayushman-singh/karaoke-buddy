from pathlib import Path
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


def test_preflight_passes_when_runtime_is_available() -> None:
    with patch("shutil.which", return_value="tool.exe"):
        with patch("importlib.import_module", return_value=object()) as import_module:
            preflight_runtime_dependencies(
                ffmpeg_exe=None,
                ffprobe_exe=None,
                libmpv_dll=None,
                frozen=False,
            )

    assert import_module.call_count == 2
