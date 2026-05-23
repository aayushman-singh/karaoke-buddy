"""Integration tests for Exporter - runs real FFmpeg on a synthetic clip."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from karaoke_buddy.core.exporter import Exporter
from karaoke_buddy.core.filter_chain import build_filter_chain

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None,
    reason="ffmpeg not found on PATH; integration tests require a real FFmpeg binary",
)


@pytest.fixture
def sample_video(tmp_path: Path) -> Path:
    """10-second synthetic MP4 with a 440 Hz sine wave."""
    out = tmp_path / "sample.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc=duration=10:size=320x240:rate=30",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=10",
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            str(out),
        ],
        check=True,
        capture_output=True,
    )
    return out


def test_export_produces_valid_mp4(sample_video: Path, tmp_path: Path):
    chain = build_filter_chain(0, 0)
    output = tmp_path / "output.mp4"

    exporter = Exporter()
    progress_values = []
    exporter.export(
        input_path=sample_video,
        filter_chain=chain,
        output_path=output,
        progress_callback=progress_values.append,
    )

    assert output.exists(), "Output file was not created"
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            str(output),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"ffprobe failed: {result.stderr}"


def test_export_duration_matches_input(sample_video: Path, tmp_path: Path):
    chain = build_filter_chain(0, 0)
    output = tmp_path / "output.mp4"

    Exporter().export(sample_video, chain, output)

    probe = subprocess.run(
        [
            "ffprobe",
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            str(output),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    out_duration = float(json.loads(probe.stdout)["format"]["duration"])
    assert abs(out_duration - 10.0) < 1.0


def test_export_with_pitch_shift_succeeds(sample_video: Path, tmp_path: Path):
    chain = build_filter_chain(-3, 0)
    output = tmp_path / "output_shifted.mp4"
    Exporter().export(sample_video, chain, output)
    assert output.exists()


def test_export_with_vocal_reduce_succeeds(sample_video: Path, tmp_path: Path):
    chain = build_filter_chain(0, 50)
    output = tmp_path / "output_vocal.mp4"
    Exporter().export(sample_video, chain, output)
    assert output.exists()


def test_no_partial_file_on_failure(tmp_path: Path):
    chain = build_filter_chain(0, 0)
    bad_input = tmp_path / "nonexistent.mp4"
    output = tmp_path / "output.mp4"
    tmp_file = output.with_suffix(".tmp")

    with pytest.raises(RuntimeError):
        Exporter().export(bad_input, chain, output)

    assert not tmp_file.exists()
    assert not output.exists()


def test_progress_callback_receives_values(sample_video: Path, tmp_path: Path):
    chain = build_filter_chain(0, 0)
    output = tmp_path / "output.mp4"
    values = []
    Exporter().export(sample_video, chain, output, progress_callback=values.append)
    assert len(values) > 0
    assert all(0 <= v <= 100 for v in values)
