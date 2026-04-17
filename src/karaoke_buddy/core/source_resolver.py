"""Source Resolver — turns a local path or YouTube URL into a local file + metadata."""

import hashlib
import json
import logging
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import yt_dlp

log = logging.getLogger(__name__)

_YT_PATTERNS = [
    re.compile(r"(?:https?://)?(?:www\.)?youtube\.com/watch\?.*v=[\w-]+"),
    re.compile(r"(?:https?://)?youtu\.be/[\w-]+"),
    re.compile(r"(?:https?://)?(?:www\.)?youtube\.com/shorts/[\w-]+"),
]


def is_youtube_url(s: str) -> bool:
    """Return True if *s* looks like a YouTube video URL."""
    return any(p.search(s) for p in _YT_PATTERNS)


@dataclass
class ResolvedSource:
    local_path: Path
    title: str
    duration_seconds: int
    thumbnail_path: Optional[Path]
    source_type: str  # "local" | "youtube"


class SourceResolver:
    """Resolves user input to a local playable file."""

    def __init__(
        self,
        cache_dir: Path,
        ffmpeg_exe: Optional[Path] = None,
        ffprobe_exe: Optional[Path] = None,
    ) -> None:
        self._cache_dir = cache_dir
        self._ffmpeg = str(ffmpeg_exe) if ffmpeg_exe else "ffmpeg"
        self._ffprobe = str(ffprobe_exe) if ffprobe_exe else "ffprobe"

    def resolve(
        self,
        input_str: str,
        progress_callback: Optional[Callable[[int], None]] = None,
    ) -> "ResolvedSource":
        s = input_str.strip()
        if is_youtube_url(s):
            return self._resolve_url(s, progress_callback)
        return self._resolve_local(Path(s))

    def _resolve_local(self, path: Path) -> "ResolvedSource":
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        probe = self._probe(path)
        duration = int(float(probe.get("format", {}).get("duration", 0)))

        cache_dir = self._local_cache_dir(path)
        thumb_path = self._ensure_thumbnail(path, cache_dir / "thumb.jpg")

        return ResolvedSource(
            local_path=path,
            title=path.stem,
            duration_seconds=duration,
            thumbnail_path=thumb_path,
            source_type="local",
        )

    def _resolve_url(
        self,
        url: str,
        progress_callback: Optional[Callable[[int], None]] = None,
    ) -> "ResolvedSource":
        ydl_opts_info: dict = {"quiet": True, "no_warnings": True}

        with yt_dlp.YoutubeDL(ydl_opts_info) as ydl:
            info = ydl.extract_info(url, download=False)

        video_id: str = info["id"]
        title: str = info.get("title", "Unknown")
        duration: int = int(info.get("duration", 0))
        video_dir = self._cache_dir / video_id
        video_path = video_dir / "video.mp4"

        if not video_path.exists():
            video_dir.mkdir(parents=True, exist_ok=True)
            hooks = []
            if progress_callback:

                def _hook(d: dict) -> None:
                    if d.get("status") == "downloading":
                        total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
                        if total:
                            progress_callback(int(d["downloaded_bytes"] / total * 100))

                hooks = [_hook]

            ydl_opts_dl: dict = {
                "outtmpl": str(video_dir / "video.%(ext)s"),
                "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
                "merge_output_format": "mp4",
                "progress_hooks": hooks,
                "quiet": True,
            }
            with yt_dlp.YoutubeDL(ydl_opts_dl) as ydl:
                ydl.download([url])

        thumb_path = self._ensure_thumbnail(video_path, video_dir / "thumb.jpg")

        return ResolvedSource(
            local_path=video_path,
            title=title,
            duration_seconds=duration,
            thumbnail_path=thumb_path,
            source_type="youtube",
        )

    def _probe(self, path: Path) -> dict:
        result = subprocess.run(
            [
                self._ffprobe,
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_format",
                str(path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(result.stdout)

    def _extract_thumbnail(self, video: Path, out: Path) -> None:
        subprocess.run(
            [
                self._ffmpeg,
                "-y",
                "-ss",
                "5",
                "-i",
                str(video),
                "-frames:v",
                "1",
                "-q:v",
                "3",
                str(out),
            ],
            capture_output=True,
            check=True,
        )

    def _ensure_thumbnail(self, video: Path, out: Path) -> Optional[Path]:
        if out.exists():
            return out
        try:
            out.parent.mkdir(parents=True, exist_ok=True)
            self._extract_thumbnail(video, out)
            return out
        except Exception as exc:  # noqa: BLE001
            log.warning("Thumbnail generation failed for %s: %s", video, exc)
            return None

    def _local_cache_dir(self, path: Path) -> Path:
        h = hashlib.md5(str(path.resolve()).encode()).hexdigest()[:8]
        return self._cache_dir / "_local" / f"{path.stem}_{h}"
