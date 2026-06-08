import sys
from unittest.mock import patch

import pytest


from karaoke_buddy.core.runtime_paths import (
    default_export_dir,
    locate_bundled,
    resolve_deno_executable,
    resolve_ffprobe_executable,
)


def test_locate_bundled_returns_none_in_dev_mode(monkeypatch) -> None:
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    assert locate_bundled("deno.exe") is None


def test_locate_bundled_finds_deno_in_meipass(monkeypatch, tmp_path) -> None:
    meipass = tmp_path / "meipass"
    meipass.mkdir()
    deno = meipass / "deno.exe"
    deno.write_bytes(b"MZ")

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(meipass), raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "KaraokeBuddy.exe"), raising=False)

    assert locate_bundled("deno.exe") == deno


def test_resolve_deno_uses_bundled_when_frozen(monkeypatch, tmp_path) -> None:
    meipass = tmp_path / "meipass"
    meipass.mkdir()
    deno = meipass / "deno.exe"
    deno.write_bytes(b"MZ")

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(meipass), raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "KaraokeBuddy.exe"), raising=False)

    assert resolve_deno_executable() == str(deno)


def test_resolve_deno_falls_back_to_pip_deno(monkeypatch) -> None:
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    with patch("karaoke_buddy.core.runtime_paths.locate_bundled", return_value=None):
        with patch("deno.find_deno_bin", return_value="C:/tools/deno.exe"):
            assert resolve_deno_executable() == "C:/tools/deno.exe"


def test_resolve_ffprobe_uses_bundled_when_frozen(monkeypatch, tmp_path) -> None:
    meipass = tmp_path / "meipass"
    meipass.mkdir()
    ffprobe = meipass / "ffprobe.exe"
    ffprobe.write_bytes(b"MZ")

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(meipass), raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "KaraokeBuddy.exe"), raising=False)

    assert resolve_ffprobe_executable() == str(ffprobe)


def test_resolve_ffprobe_finds_sibling_of_ffmpeg(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    ffmpeg = bin_dir / "ffmpeg.exe"
    ffmpeg.write_bytes(b"")
    ffprobe = bin_dir / "ffprobe.exe"
    ffprobe.write_bytes(b"")

    assert resolve_ffprobe_executable(ffmpeg) == str(ffprobe)


def test_resolve_ffprobe_falls_back_to_path(monkeypatch) -> None:
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    assert resolve_ffprobe_executable() == "ffprobe"


def test_default_export_dir_video_goes_to_videos(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    assert default_export_dir(".mp4") == tmp_path / "Videos" / "KaraokeBuddy"


@pytest.mark.parametrize("suffix", [".mp3", ".m4a", ".MP3", ".M4A"])
def test_default_export_dir_audio_goes_to_music(monkeypatch, tmp_path, suffix) -> None:
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    assert default_export_dir(suffix) == tmp_path / "Music" / "KaraokeBuddy"


def test_default_export_dir_defaults_to_video(monkeypatch, tmp_path) -> None:
    """Backwards-compat: no-arg call still resolves to the Videos folder."""
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    assert default_export_dir() == tmp_path / "Videos" / "KaraokeBuddy"


def test_default_export_dir_is_pure(monkeypatch, tmp_path) -> None:
    """Function must not create directories on the user's filesystem just by being called."""
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    default_export_dir(".mp4")
    default_export_dir(".mp3")
    assert not (tmp_path / "Videos").exists()
    assert not (tmp_path / "Music").exists()
