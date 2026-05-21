"""Tests for __main__ entry point helpers — DLL discovery and path setup."""

import os
import sys


def test_locate_bundled_returns_none_in_dev_mode(monkeypatch):
    """In non-frozen dev mode, _locate_bundled always returns None."""
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    from karaoke_buddy.__main__ import _locate_bundled

    assert _locate_bundled("ffmpeg.exe") is None


def test_locate_bundled_finds_dll_in_meipass(monkeypatch, tmp_path):
    """In frozen --onefile mode, _locate_bundled checks sys._MEIPASS first."""
    meipass = tmp_path / "meipass"
    meipass.mkdir()
    dll = meipass / "libmpv-2.dll"
    dll.write_bytes(b"")

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(meipass), raising=False)
    # exe.parent does NOT contain the DLL — we want _MEIPASS to win
    monkeypatch.setattr(
        sys, "executable", str(tmp_path / "KaraokeBuddy.exe"), raising=False
    )

    from karaoke_buddy.__main__ import _locate_bundled

    result = _locate_bundled("libmpv-2.dll")
    assert result == dll


def test_locate_bundled_falls_back_to_exe_parent_if_no_meipass(monkeypatch, tmp_path):
    """In frozen --onedir mode (no sys._MEIPASS), exe.parent is used."""
    exe_parent = tmp_path / "dist"
    exe_parent.mkdir()
    dll = exe_parent / "libmpv-2.dll"
    dll.write_bytes(b"")

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    try:
        monkeypatch.delattr(sys, "_MEIPASS")
    except AttributeError:
        pass
    monkeypatch.setattr(
        sys, "executable", str(exe_parent / "KaraokeBuddy.exe"), raising=False
    )

    from karaoke_buddy.__main__ import _locate_bundled

    result = _locate_bundled("libmpv-2.dll")
    assert result == dll


def test_locate_bundled_returns_none_when_file_absent(monkeypatch, tmp_path):
    """Returns None if the file doesn't exist in any search location."""
    meipass = tmp_path / "meipass"
    meipass.mkdir()

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(meipass), raising=False)
    monkeypatch.setattr(
        sys, "executable", str(tmp_path / "KaraokeBuddy.exe"), raising=False
    )

    from karaoke_buddy.__main__ import _locate_bundled

    assert _locate_bundled("libmpv-2.dll") is None


def test_missing_bundled_dependency_message_names_missing_files(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    ffmpeg = tmp_path / "ffmpeg.exe"

    from karaoke_buddy.__main__ import _missing_bundled_dependency_message

    message = _missing_bundled_dependency_message(ffmpeg, None)

    assert message is not None
    assert "ffprobe.exe" in message
    assert "ffmpeg.exe" not in message.split("Missing bundled dependencies: ", 1)[1]


def test_missing_bundled_dependency_message_ignores_dev_mode(monkeypatch):
    monkeypatch.setattr(sys, "frozen", False, raising=False)

    from karaoke_buddy.__main__ import _missing_bundled_dependency_message

    assert _missing_bundled_dependency_message(None, None) is None


def test_setup_dll_search_path_adds_meipass_in_frozen_mode(monkeypatch, tmp_path):
    """In frozen mode with sys._MEIPASS, os.add_dll_directory is called."""
    meipass = tmp_path / "meipass"
    meipass.mkdir()

    added: list[str] = []

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(meipass), raising=False)
    monkeypatch.setattr(
        os, "add_dll_directory", lambda d: added.append(d), raising=False
    )

    from karaoke_buddy.__main__ import _setup_dll_search_path

    _setup_dll_search_path()

    assert str(meipass) in added


def test_setup_dll_search_path_adds_exe_parent_in_onedir_mode(monkeypatch, tmp_path):
    """In frozen onedir mode, exe.parent is made available to DLL loaders."""
    exe_parent = tmp_path / "dist"
    exe_parent.mkdir()

    added: list[str] = []

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    try:
        monkeypatch.delattr(sys, "_MEIPASS")
    except AttributeError:
        pass
    monkeypatch.setattr(
        sys, "executable", str(exe_parent / "KaraokeBuddy.exe"), raising=False
    )
    monkeypatch.setattr(
        os, "add_dll_directory", lambda d: added.append(d), raising=False
    )
    monkeypatch.setenv("PATH", "")

    from karaoke_buddy.__main__ import _setup_dll_search_path

    _setup_dll_search_path()

    assert str(exe_parent) in added
    assert str(exe_parent) in os.environ["PATH"].split(os.pathsep)


def test_setup_dll_search_path_is_noop_in_dev_mode(monkeypatch):
    """In non-frozen dev mode, os.add_dll_directory is never called."""
    added: list[str] = []

    monkeypatch.setattr(sys, "frozen", False, raising=False)
    monkeypatch.setattr(
        os, "add_dll_directory", lambda d: added.append(d), raising=False
    )

    from karaoke_buddy.__main__ import _setup_dll_search_path

    _setup_dll_search_path()

    assert added == []


def test_main_window_import_does_not_require_mpv():
    """The app shell can be imported before playback dependencies are present."""
    from karaoke_buddy.ui.main_window import MainWindow

    assert MainWindow.__name__ == "MainWindow"
