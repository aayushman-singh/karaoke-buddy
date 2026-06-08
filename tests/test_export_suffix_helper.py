"""Unit tests for _ensure_export_suffix — applies the chosen Qt filter's
extension when the user typed a name without one."""

import pytest

from karaoke_buddy.ui.main_window import _ensure_export_suffix


@pytest.mark.parametrize(
    "path, selected_filter, expected",
    [
        ("/tmp/song", "M4A audio (*.m4a)", "/tmp/song.m4a"),
        ("/tmp/song", "MP3 audio (*.mp3)", "/tmp/song.mp3"),
        ("/tmp/song", "MP4 video (*.mp4)", "/tmp/song.mp4"),
        ("/tmp/song.m4a", "MP3 audio (*.mp3)", "/tmp/song.m4a"),
        ("/tmp/song.mp3", "M4A audio (*.m4a)", "/tmp/song.mp3"),
        ("/tmp/song.MP4", "M4A audio (*.m4a)", "/tmp/song.MP4"),
    ],
)
def test_ensure_export_suffix(path: str, selected_filter: str, expected: str) -> None:
    assert _ensure_export_suffix(path, selected_filter) == expected


def test_ensure_export_suffix_unknown_filter_returns_unchanged() -> None:
    assert _ensure_export_suffix("/tmp/song", "garbage") == "/tmp/song"
