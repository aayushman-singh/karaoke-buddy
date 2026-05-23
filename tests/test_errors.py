"""Stable error code classifier tests.

The strings under test are real fragments seen in yt-dlp / ffmpeg output so we
can be confident the classifier sticks the right code on the right failure when
a user hits it in the wild.
"""

from __future__ import annotations

import pytest

from karaoke_buddy.core import errors as kb_errors
from karaoke_buddy.core.errors import KBError


def _code(exc_text: str) -> str:
    return kb_errors.youtube_failure(RuntimeError(exc_text)).code


@pytest.mark.parametrize(
    "text",
    [
        "ERROR: [youtube] DU1: ... The current session has been rate-limited by YouTube for up to an hour.",
        "HTTP Error 429: Too Many Requests",
    ],
)
def test_youtube_ratelimit_classified(text: str) -> None:
    assert _code(text) == "KB-YT-RATELIMIT"


@pytest.mark.parametrize(
    "text",
    [
        "Private video. Sign in to confirm your age",
        "This video is private",
        "Join this channel to get access to members-only content",
    ],
)
def test_youtube_private_classified(text: str) -> None:
    assert _code(text) == "KB-YT-PRIVATE"


@pytest.mark.parametrize(
    "text",
    [
        "The uploader has not made this video available in your country",
        "geo restricted by the uploader",
    ],
)
def test_youtube_geo_classified(text: str) -> None:
    assert _code(text) == "KB-YT-GEO"


@pytest.mark.parametrize(
    "text",
    [
        "This video has been removed by the uploader",
        "removed for violating YouTube's Terms of Service",
    ],
)
def test_youtube_removed_classified(text: str) -> None:
    assert _code(text) == "KB-YT-REMOVED"


def test_youtube_unavailable_falls_below_more_specific_codes() -> None:
    assert _code("Video unavailable. Try again later.") == "KB-YT-UNAVAIL"


@pytest.mark.parametrize(
    "text",
    [
        "Could not resolve host: www.youtube.com",
        "Connection timed out",
        "HTTP Error 503: Service Unavailable",
    ],
)
def test_network_classified(text: str) -> None:
    assert _code(text) == "KB-NET"


def test_unknown_youtube_returns_unknown_code() -> None:
    err = kb_errors.youtube_failure(RuntimeError("Something nobody has seen before"))
    assert err.code == "KB-YT-UNKNOWN"
    assert "Something nobody has seen before" in err.raw


def test_export_denied_classified() -> None:
    err = kb_errors.export_failure(OSError("[Errno 13] Permission denied: 'C:/Program Files/...'"))
    assert err.code == "KB-EXPORT-DENIED"


def test_export_winerror_5_is_denied() -> None:
    err = kb_errors.export_failure(OSError("WinError 5: Access is denied"))
    assert err.code == "KB-EXPORT-DENIED"


def test_export_ffmpeg_classified() -> None:
    err = kb_errors.export_failure(RuntimeError("ffmpeg crashed with code 255"))
    assert err.code == "KB-EXPORT-FFMPEG"


def test_export_unknown_returns_unknown_code() -> None:
    err = kb_errors.export_failure(RuntimeError("mystery"))
    assert err.code == "KB-EXPORT-UNKNOWN"


def test_kberror_details_block_contains_code_and_raw() -> None:
    err = KBError(
        code="KB-TEST",
        title="t",
        user_message="m",
        hint="h",
        raw="raw payload here",
    )
    payload = err.details_block()
    assert "KB-TEST" in payload
    assert "raw payload here" in payload
    assert "Hint:    h" in payload


def test_file_missing_carries_path() -> None:
    err = kb_errors.file_missing("C:/Videos/song.mp4")
    assert err.code == "KB-FILE-MISSING"
    assert "song.mp4" in err.raw
