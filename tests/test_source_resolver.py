"""Tests for SourceResolver — URL detection, local resolution, cache hit."""

from unittest.mock import patch

import pytest

from karaoke_buddy.core.source_resolver import (
    SourceResolver,
    YouTubeRuntimeDependencyError,
    is_youtube_url,
    youtube_extraction_options,
)


@pytest.mark.parametrize(
    "url",
    [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://youtu.be/dQw4w9WgXcQ",
        "https://youtube.com/watch?v=dQw4w9WgXcQ",
        "https://www.youtube.com/shorts/dQw4w9WgXcQ",
    ],
)
def test_valid_youtube_urls_are_recognised(url):
    assert is_youtube_url(url) is True


@pytest.mark.parametrize(
    "not_url",
    [
        "/local/path/to/file.mp4",
        "C:/Users/Mom/karaoke.mp4",
        "https://vimeo.com/123456",
        "not a url at all",
        "",
    ],
)
def test_non_youtube_strings_are_rejected(not_url):
    assert is_youtube_url(not_url) is False


def test_youtube_extraction_options_enable_deno_runtime():
    opts = youtube_extraction_options()

    assert opts["js_runtimes"]["deno"]["path"]
    assert "no_warnings" not in opts
    assert opts["logger"]


def test_youtube_runtime_warnings_fail_loud():
    opts = youtube_extraction_options()

    with pytest.raises(YouTubeRuntimeDependencyError):
        opts["logger"].warning(
            "[youtube] No supported JavaScript runtime could be found"
        )


def test_local_file_resolve_returns_resolved_source(tmp_path):
    fake_mp4 = tmp_path / "song.mp4"
    fake_mp4.write_bytes(b"\x00" * 32)

    resolver = SourceResolver(cache_dir=tmp_path / "cache")

    with patch.object(
        resolver, "_probe", return_value={"format": {"duration": "180.5"}}
    ):
        with patch.object(resolver, "_extract_thumbnail"):
            result = resolver.resolve(str(fake_mp4))

    assert result.local_path == fake_mp4
    assert result.duration_seconds == 180
    assert result.source_type == "local"
    assert result.source == fake_mp4.as_posix()


def test_local_file_title_is_stem(tmp_path):
    fake_mp4 = tmp_path / "Hotel California.mp4"
    fake_mp4.write_bytes(b"\x00")

    resolver = SourceResolver(cache_dir=tmp_path / "cache")
    with patch.object(resolver, "_probe", return_value={"format": {"duration": "0"}}):
        with patch.object(resolver, "_extract_thumbnail"):
            result = resolver.resolve(str(fake_mp4))

    assert result.title == "Hotel California"


def test_local_missing_file_raises(tmp_path):
    resolver = SourceResolver(cache_dir=tmp_path / "cache")
    with pytest.raises(FileNotFoundError):
        resolver.resolve(str(tmp_path / "nonexistent.mp4"))


def test_cache_hit_skips_yt_dlp_download(tmp_path):
    cache_dir = tmp_path / "cache"
    video_id = "dQw4w9WgXcQ"
    cached_video = cache_dir / video_id / "video.mp4"
    cached_video.parent.mkdir(parents=True)
    cached_video.write_bytes(b"\x00")

    resolver = SourceResolver(cache_dir=cache_dir)

    fake_info = {"id": video_id, "title": "Never Gonna Give You Up", "duration": 213}
    with patch("yt_dlp.YoutubeDL") as MockYDL:
        instance = MockYDL.return_value.__enter__.return_value
        instance.extract_info.return_value = fake_info
        with patch.object(
            resolver, "_probe", return_value={"format": {"duration": "213"}}
        ):
            with patch.object(resolver, "_extract_thumbnail"):
                result = resolver.resolve(f"https://www.youtube.com/watch?v={video_id}")

        instance.download.assert_not_called()

    assert result.local_path == cached_video
    assert result.title == "Never Gonna Give You Up"
    assert result.source_type == "youtube"
    assert result.source == f"https://www.youtube.com/watch?v={video_id}"


def test_youtube_download_uses_bundled_ffmpeg_location(tmp_path):
    cache_dir = tmp_path / "cache"
    video_id = "dQw4w9WgXcQ"
    ffmpeg_exe = tmp_path / "bin" / "ffmpeg.exe"
    ffmpeg_exe.parent.mkdir()
    ffmpeg_exe.write_bytes(b"")

    resolver = SourceResolver(cache_dir=cache_dir, ffmpeg_exe=ffmpeg_exe)
    fake_info = {"id": video_id, "title": "Never Gonna Give You Up", "duration": 213}

    with patch("yt_dlp.YoutubeDL") as MockYDL:
        instance = MockYDL.return_value.__enter__.return_value
        instance.extract_info.return_value = fake_info

        def fake_download(_urls):
            cached_video = cache_dir / video_id / "video.mp4"
            cached_video.write_bytes(b"\x00")

        instance.download.side_effect = fake_download

        with patch.object(resolver, "_extract_thumbnail"):
            resolver.resolve(f"https://www.youtube.com/watch?v={video_id}")

    download_opts = MockYDL.call_args_list[1].args[0]
    assert download_opts["ffmpeg_location"] == str(ffmpeg_exe.parent)
