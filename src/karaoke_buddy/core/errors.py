"""Stable error codes for user-facing failure reporting.

Codes are deliberately short, prefixed by subsystem, and stable across releases
so users can quote them to support (`KB-YT-RATELIMIT`) without describing the
underlying stack trace. Each ``KBError`` carries:

* ``code`` — short stable identifier, never reworded
* ``title`` — one-line summary shown in the dialog header
* ``user_message`` — plain-language explanation for the end user
* ``hint`` — concrete next step they can try themselves
* ``raw`` — the original exception text, for the copy-details payload
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class KBError:
    code: str
    title: str
    user_message: str
    hint: str
    raw: str = ""

    def details_block(self) -> str:
        """Multi-line payload for copy-to-clipboard."""
        lines = [
            f"Code:    {self.code}",
            f"Title:   {self.title}",
            f"Message: {self.user_message}",
            f"Hint:    {self.hint}",
        ]
        if self.raw:
            lines.append("")
            lines.append("Raw error:")
            lines.append(self.raw.strip())
        return "\n".join(lines)


# ----------------------------------------------------------------------------
# Resolve / source pipeline
# ----------------------------------------------------------------------------


def file_missing(path: str) -> KBError:
    return KBError(
        code="KB-FILE-MISSING",
        title="That video isn't where we left it",
        user_message="The file used to be here but seems to have been moved, renamed, or deleted.",
        hint="Find the file in File Explorer and open it again from KaraokeBuddy.",
        raw=path,
    )


def file_unreadable(raw: str) -> KBError:
    return KBError(
        code="KB-FILE-OPEN",
        title="Couldn't open this video",
        user_message="KaraokeBuddy could read the file but something inside it is broken.",
        hint="Try a different copy of the video, or convert it to mp4 first.",
        raw=raw,
    )


def yt_runtime(raw: str) -> KBError:
    return KBError(
        code="KB-YT-RUNTIME",
        title="YouTube helper is broken",
        user_message=(
            "The pieces KaraokeBuddy uses to talk to YouTube (Deno and yt-dlp-ejs)"
            " are missing or wouldn't start."
        ),
        hint="Re-download KaraokeBuddy from the original link — your copy may be incomplete.",
        raw=raw,
    )


_YT_RATELIMIT_PATTERNS = (
    "rate-limited",
    "rate limited",
    "too many requests",
    "http error 429",
)

_YT_UNAVAILABLE_PATTERNS = (
    "video unavailable",
    "this video is not available",
    "this content isn't available",
)

_YT_PRIVATE_PATTERNS = (
    "private video",
    "video is private",
    "sign in to confirm your age",
    "members-only",
    "join this channel",
)

_YT_GEO_PATTERNS = (
    "not available in your country",
    "not made this video available in your country",
    "blocked it on copyright grounds",
    "geo restrict",
)

_YT_REMOVED_PATTERNS = (
    "video has been removed",
    "removed by the uploader",
    "terms of service",
    "copyright",
)

_NETWORK_PATTERNS = (
    "name or service not known",
    "temporary failure",
    "network is unreachable",
    "connection refused",
    "connection reset",
    "timed out",
    "timeout",
    "could not resolve host",
    "http error 5",
    "service unavailable",
)


def _classify_youtube_text(text: str) -> Optional[KBError]:
    lower = text.lower()
    if any(p in lower for p in _YT_RATELIMIT_PATTERNS):
        return KBError(
            code="KB-YT-RATELIMIT",
            title="YouTube paused us",
            user_message=(
                "YouTube has temporarily blocked KaraokeBuddy from downloading from your"
                " internet connection. This usually clears within an hour."
            ),
            hint="Wait an hour and try again, or open the same link from a different network.",
            raw=text,
        )
    if any(p in lower for p in _YT_PRIVATE_PATTERNS):
        return KBError(
            code="KB-YT-PRIVATE",
            title="That YouTube video is locked",
            user_message=(
                "This video is private, age-restricted, or members-only, so YouTube won't"
                " let KaraokeBuddy download it."
            ),
            hint="Pick a different public video on YouTube and paste that link instead.",
            raw=text,
        )
    if any(p in lower for p in _YT_GEO_PATTERNS):
        return KBError(
            code="KB-YT-GEO",
            title="YouTube blocked this video in your country",
            user_message="YouTube won't share this video with your region.",
            hint="Pick a different version of the song that's available where you are.",
            raw=text,
        )
    if any(p in lower for p in _YT_REMOVED_PATTERNS):
        return KBError(
            code="KB-YT-REMOVED",
            title="YouTube removed this video",
            user_message="The video has been taken down from YouTube and can no longer be downloaded.",
            hint="Pick a different upload of the same song on YouTube.",
            raw=text,
        )
    if any(p in lower for p in _YT_UNAVAILABLE_PATTERNS):
        return KBError(
            code="KB-YT-UNAVAIL",
            title="YouTube can't open this link right now",
            user_message="YouTube said this video isn't available — it may have just been temporarily withdrawn.",
            hint="Try again in a few minutes, or pick a different video.",
            raw=text,
        )
    if any(p in lower for p in _NETWORK_PATTERNS):
        return KBError(
            code="KB-NET",
            title="Internet hiccup",
            user_message="KaraokeBuddy couldn't reach YouTube. Your internet may be slow or off.",
            hint="Check that web pages open in your browser, then try the link again.",
            raw=text,
        )
    return None


def youtube_failure(raw_exc: BaseException) -> KBError:
    text = str(raw_exc)
    classified = _classify_youtube_text(text)
    if classified is not None:
        return classified
    return KBError(
        code="KB-YT-UNKNOWN",
        title="YouTube download didn't work",
        user_message="KaraokeBuddy couldn't finish downloading this video and YouTube didn't say why.",
        hint="Try the same link again. If it keeps failing, share the error code below with support.",
        raw=text,
    )


# ----------------------------------------------------------------------------
# Export pipeline
# ----------------------------------------------------------------------------


def export_failure(raw_exc: BaseException) -> KBError:
    text = str(raw_exc)
    lower = text.lower()
    if "permission" in lower or "access is denied" in lower or "winerror 5" in lower:
        return KBError(
            code="KB-EXPORT-DENIED",
            title="Windows wouldn't let us save here",
            user_message=(
                "The folder you picked is read-only or protected (often Program Files,"
                " OneDrive locked folders, or a removed USB drive)."
            ),
            hint="Pick a normal folder like Documents or your Desktop and save again.",
            raw=text,
        )
    if "no such file" in lower or "not found" in lower:
        return KBError(
            code="KB-EXPORT-MISSING",
            title="The source video disappeared",
            user_message="The video that was being saved is no longer on disk.",
            hint="Open the song again from the library, then try Save once more.",
            raw=text,
        )
    if "ffmpeg" in lower:
        return KBError(
            code="KB-EXPORT-FFMPEG",
            title="The audio engine wouldn't run",
            user_message="The bundled ffmpeg couldn't process this song.",
            hint="Re-download KaraokeBuddy. If the problem repeats, share the error code with support.",
            raw=text,
        )
    return KBError(
        code="KB-EXPORT-UNKNOWN",
        title="Couldn't save the song",
        user_message="Something went wrong while saving and the reason wasn't clear.",
        hint="Try a different folder. If the problem repeats, share the error code with support.",
        raw=text,
    )


# ----------------------------------------------------------------------------
# Library / entry pipeline
# ----------------------------------------------------------------------------


def cached_path_missing(path: str) -> KBError:
    return KBError(
        code="KB-LIB-MISSING",
        title="That song's file is gone",
        user_message="The video file this library entry points to has been moved or deleted.",
        hint="Open the original file or paste the YouTube link again to re-add it.",
        raw=path,
    )


# Pre-compiled regex used by the dialog to make error codes look like
# a clickable identifier (e.g. for support to grep on).
ERROR_CODE_RE = re.compile(r"\bKB-[A-Z0-9-]+\b")
