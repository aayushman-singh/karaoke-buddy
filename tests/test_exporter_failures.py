"""Unit tests for exporter failure policy and format validation."""

import subprocess

import pytest

from karaoke_buddy.core.exporter import SUPPORTED_EXPORT_SUFFIXES, Exporter


def test_export_does_not_retry_failed_stream_copy_with_reencode(tmp_path, monkeypatch):
    input_path = tmp_path / "input.mp4"
    input_path.write_bytes(b"fake video")
    output_path = tmp_path / "output.mp4"
    tmp_path_ = output_path.with_suffix(".tmp")
    calls: list[list[str]] = []

    def fail_stream_copy(
        self,
        input_path,
        filter_chain,
        output_path,
        progress_callback,
        format_flags,
    ) -> None:
        calls.append(format_flags)
        output_path.write_bytes(b"partial")
        raise subprocess.CalledProcessError(
            returncode=1,
            cmd=["ffmpeg"],
            stderr="stream copy failed",
        )

    monkeypatch.setattr(Exporter, "_run", fail_stream_copy)

    with pytest.raises(RuntimeError, match="Export failed"):
        Exporter().export(input_path, "anull", output_path)

    assert len(calls) == 1
    assert "-c:v" in calls[0] and "copy" in calls[0]
    assert not tmp_path_.exists()
    assert not output_path.exists()


def test_export_unsupported_suffix_raises(tmp_path):
    bogus_output = tmp_path / "out.flac"
    with pytest.raises(ValueError, match="Unsupported export format"):
        Exporter().export(tmp_path / "in.mp4", "anull", bogus_output)


@pytest.mark.parametrize("suffix", SUPPORTED_EXPORT_SUFFIXES)
def test_supported_suffixes_pass_validation(tmp_path, monkeypatch, suffix):
    """Each supported suffix should reach _run with format flags chosen for it."""
    captured: list[list[str]] = []

    def capture_then_write(
        self,
        input_path,
        filter_chain,
        output_path,
        progress_callback,
        format_flags,
    ) -> None:
        captured.append(format_flags)
        output_path.write_bytes(b"")

    monkeypatch.setattr(Exporter, "_run", capture_then_write)
    out = tmp_path / f"out{suffix}"
    Exporter().export(tmp_path / "in.mp4", "anull", out)
    assert len(captured) == 1
    assert out.exists()
