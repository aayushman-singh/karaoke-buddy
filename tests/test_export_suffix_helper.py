"""Unit tests for _ensure_export_suffix — guarantees the path the Exporter
sees ends with the suffix the user already picked in the format modal."""

import pytest

from karaoke_buddy.ui.main_window import _ensure_export_suffix


@pytest.mark.parametrize(
    "path, suffix, expected",
    [
        ("/tmp/song", ".m4a", "/tmp/song.m4a"),
        ("/tmp/song", ".mp3", "/tmp/song.mp3"),
        ("/tmp/song", ".mp4", "/tmp/song.mp4"),
        ("/tmp/song.m4a", ".m4a", "/tmp/song.m4a"),
        ("/tmp/song.MP4", ".mp4", "/tmp/song.MP4"),
        ("/tmp/song.m4a", ".mp3", "/tmp/song.m4a.mp3"),
    ],
)
def test_ensure_export_suffix(path: str, suffix: str, expected: str) -> None:
    assert _ensure_export_suffix(path, suffix) == expected
