"""Source Resolver - turns a local path or YouTube URL into a local file + metadata."""

import hashlib
import json
import logging
import re
import shutil
import subprocess
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Callable, Optional

import yt_dlp

from karaoke_buddy.core.runtime_paths import (
    resolve_deno_executable,
    resolve_ffprobe_executable,
)

log = logging.getLogger(__name__)

_YT_PATTERNS = [
    re.compile(r"(?:https?://)?(?:www\.)?youtube\.com/watch\?.*v=[\w-]+"),
    re.compile(r"(?:https?://)?youtu\.be/[\w-]+"),
    re.compile(r"(?:https?://)?(?:www\.)?youtube\.com/shorts/[\w-]+"),
]

_RUNTIME_WARNING_MARKERS = (
    "javascript runtime",
    "js runtime",
    "[jsc",
    "deno",
    "yt-dlp-ejs",
    "ejs",
    "remote components challenge solver",
)


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
    source: str


class YouTubeRuntimeDependencyError(RuntimeError):
    def __init__(self, message: str, runtime_context: dict[str, object]) -> None:
        super().__init__(message)
        self.runtime_context = runtime_context


class _YtDlpLogger:
    def __init__(self, runtime_context: dict[str, object]) -> None:
        self._runtime_context = runtime_context

    def debug(self, message: str) -> None:
        log.debug("yt-dlp: %s", message)

    def info(self, message: str) -> None:
        log.info("yt-dlp: %s", message)

    def warning(self, message: str) -> None:
        log.warning("yt-dlp warning: %s", message)
        if any(marker in message.lower() for marker in _RUNTIME_WARNING_MARKERS):
            raise YouTubeRuntimeDependencyError(
                f"yt-dlp reported a YouTube runtime dependency problem: {message}",
                self._runtime_context,
            )

    def error(self, message: str) -> None:
        log.error("yt-dlp error: %s", message)


def youtube_runtime_diagnostics() -> dict[str, object]:
    context: dict[str, object] = {}
    for package_name in ("yt-dlp", "yt-dlp-ejs"):
        try:
            context[f"{package_name}_version"] = version(package_name)
        except PackageNotFoundError:
            context[f"{package_name}_version"] = "not installed"

    try:
        deno_path = resolve_deno_executable()
    except Exception as exc:  # noqa: BLE001
        context["deno_error"] = repr(exc)
        return context

    context["deno_path"] = str(deno_path)
    context["deno_path_exists"] = Path(deno_path).exists()
    return context


def youtube_extraction_options(*, quiet: bool = True) -> dict:
    """Return yt-dlp options required for full YouTube extraction."""
    runtime_context = youtube_runtime_diagnostics()

    if runtime_context.get("yt-dlp-ejs_version") == "not installed":
        raise YouTubeRuntimeDependencyError(
            "yt-dlp-ejs is not installed for YouTube challenge solving",
            runtime_context,
        )

    if "deno_error" in runtime_context:
        raise YouTubeRuntimeDependencyError(
            "Deno JavaScript runtime is unavailable for yt-dlp",
            runtime_context,
        )

    deno_path = runtime_context["deno_path"]
    if not runtime_context["deno_path_exists"]:
        raise YouTubeRuntimeDependencyError(
            f"Deno JavaScript runtime not found at {deno_path}",
            runtime_context,
        )

    try:
        deno_version = subprocess.run(
            [str(deno_path), "--version"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.splitlines()[0]
    except Exception as exc:  # noqa: BLE001
        raise YouTubeRuntimeDependencyError(
            f"Deno JavaScript runtime could not be executed at {deno_path}",
            runtime_context,
        ) from exc
    runtime_context["deno_version"] = deno_version

    return {
        "quiet": quiet,
        "logger": _YtDlpLogger(runtime_context),
        "noprogress": True,
        "noplaylist": True,
        "js_runtimes": {"deno": {"path": deno_path}},
    }


class SourceResolver:
    """Resolves user input to a local playable file."""

    def __init__(
        self,
        cache_dir: Path,
        ffmpeg_exe: Optional[Path] = None,
        ffprobe_exe: Optional[Path] = None,
    ) -> None:
        self._cache_dir = cache_dir
        resolved_ffmpeg = self._resolve_ffmpeg(ffmpeg_exe)
        self._ffmpeg = str(resolved_ffmpeg) if resolved_ffmpeg else "ffmpeg"
        self._ffmpeg_dir = str(resolved_ffmpeg.parent) if resolved_ffmpeg else None
        self._ffprobe = str(ffprobe_exe) if ffprobe_exe else resolve_ffprobe_executable(ffmpeg_exe)

    @staticmethod
    def _resolve_ffmpeg(ffmpeg_exe: Optional[Path]) -> Optional[Path]:
        if ffmpeg_exe:
            return ffmpeg_exe
        which = shutil.which("ffmpeg")
        return Path(which) if which else None

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

        duration = self._probe_duration_seconds(path)

        cache_dir = self._local_cache_dir(path)
        thumb_path = self._ensure_thumbnail(path, cache_dir / "thumb.jpg")

        return ResolvedSource(
            local_path=path,
            title=path.stem,
            duration_seconds=duration,
            thumbnail_path=thumb_path,
            source_type="local",
            source=path.as_posix(),
        )

    def _resolve_url(
        self,
        url: str,
        progress_callback: Optional[Callable[[int], None]] = None,
    ) -> "ResolvedSource":
        try:
            ydl_opts_info = youtube_extraction_options()

            with yt_dlp.YoutubeDL(ydl_opts_info) as ydl:
                info = ydl.extract_info(url, download=False)
        except YouTubeRuntimeDependencyError:
            log.exception(
                "YouTube runtime dependency failed for url=%r runtime=%s",
                url,
                youtube_runtime_diagnostics(),
            )
            raise
        except Exception:
            log.exception(
                "YouTube metadata resolve failed for url=%r runtime=%s",
                url,
                youtube_runtime_diagnostics(),
            )
            raise

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
                **youtube_extraction_options(),
                "outtmpl": str(video_dir / "video.%(ext)s"),
                "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
                "merge_output_format": "mp4",
                "progress_hooks": hooks,
            }
            if self._ffmpeg_dir:
                ydl_opts_dl["ffmpeg_location"] = self._ffmpeg_dir
            try:
                with yt_dlp.YoutubeDL(ydl_opts_dl) as ydl:
                    ydl.download([url])
            except YouTubeRuntimeDependencyError:
                log.exception(
                    "YouTube runtime dependency failed during download for url=%r "
                    "video_id=%s runtime=%s",
                    url,
                    video_id,
                    youtube_runtime_diagnostics(),
                )
                raise
            except Exception:
                log.exception(
                    "YouTube download failed for url=%r video_id=%s runtime=%s",
                    url,
                    video_id,
                    youtube_runtime_diagnostics(),
                )
                raise

        thumb_path = self._ensure_thumbnail(video_path, video_dir / "thumb.jpg")

        return ResolvedSource(
            local_path=video_path,
            title=title,
            duration_seconds=duration,
            thumbnail_path=thumb_path,
            source_type="youtube",
            source=url,
        )

    def _probe_duration_seconds(self, path: Path) -> int:
        """Read duration via ffprobe JSON. Raises on failure (no silent fallback)."""
        command = [
            self._ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(path),
        ]
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=True,
                timeout=30,
            )
        except subprocess.CalledProcessError as exc:
            log.error(
                "ffprobe failed: path=%s returncode=%s stdout=%r stderr=%r",
                path,
                exc.returncode,
                exc.stdout,
                exc.stderr,
            )
            raise
        except (OSError, subprocess.TimeoutExpired):
            log.exception("ffprobe could not be invoked: path=%s ffprobe=%s", path, self._ffprobe)
            raise

        try:
            data = json.loads(result.stdout)
            duration = float(data["format"]["duration"])
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            log.error(
                "ffprobe returned unparseable duration: path=%s stdout=%r error=%r",
                path,
                result.stdout,
                exc,
            )
            raise RuntimeError(
                f"Could not read duration of {path.name}: ffprobe output unparseable"
            ) from exc

        return int(duration)

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

    def _ensure_thumbnail(self, video: Path, out: Path) -> Path:
        if out.exists():
            return out
        try:
            out.parent.mkdir(parents=True, exist_ok=True)
            self._extract_thumbnail(video, out)
            return out
        except Exception as exc:  # noqa: BLE001
            log.exception(
                "Thumbnail generation failed: video=%s output=%s ffmpeg=%s",
                video,
                out,
                self._ffmpeg,
            )
            raise RuntimeError(f"Could not generate thumbnail for {video}") from exc

    def _local_cache_dir(self, path: Path) -> Path:
        h = hashlib.md5(str(path.resolve()).encode()).hexdigest()[:8]
        return self._cache_dir / "_local" / f"{path.stem}_{h}"
