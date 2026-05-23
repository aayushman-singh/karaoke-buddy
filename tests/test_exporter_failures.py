"""Unit tests for exporter failure policy."""

import subprocess

import pytest

from karaoke_buddy.core.exporter import Exporter


def test_export_does_not_retry_failed_stream_copy_with_reencode(tmp_path, monkeypatch):
    input_path = tmp_path / "input.mp4"
    input_path.write_bytes(b"fake video")
    output_path = tmp_path / "output.mp4"
    tmp_path_ = output_path.with_suffix(".tmp")
    calls: list[bool] = []

    def fail_stream_copy(
        self,
        input_path,
        filter_chain,
        output_path,
        progress_callback,
        video_copy,
    ) -> None:
        calls.append(video_copy)
        output_path.write_bytes(b"partial")
        raise subprocess.CalledProcessError(
            returncode=1,
            cmd=["ffmpeg"],
            stderr="stream copy failed",
        )

    monkeypatch.setattr(Exporter, "_run", fail_stream_copy)

    with pytest.raises(RuntimeError, match="Export failed"):
        Exporter().export(input_path, "anull", output_path)

    assert calls == [True]
    assert not tmp_path_.exists()
    assert not output_path.exists()
