"""Exporter - bakes current pitch/vocal-reduce settings into a new MP4."""

import logging
import os
import re
import subprocess
from pathlib import Path
from typing import Callable, Optional

from PySide6.QtCore import QThread, Signal

log = logging.getLogger(__name__)

_PROGRESS_RE = re.compile(r"out_time_ms=(\d+)")
_DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+)\.(\d+)")


def _parse_duration_from_stderr(stderr_head: str) -> Optional[float]:
    m = _DURATION_RE.search(stderr_head)
    if not m:
        return None
    h, mi, s, cs = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
    return h * 3600 + mi * 60 + s + cs / 100


class Exporter:
    """Synchronous exporter. For async/GUI use ExportThread."""

    def __init__(self, ffmpeg_exe: Optional[Path] = None) -> None:
        self._ffmpeg = str(ffmpeg_exe) if ffmpeg_exe else "ffmpeg"

    def export(
        self,
        input_path: Path,
        filter_chain: str,
        output_path: Path,
        progress_callback: Optional[Callable[[int], None]] = None,
    ) -> None:
        """Export input_path with filter_chain applied to output_path."""
        tmp = output_path.with_suffix(".tmp")
        try:
            self._run(input_path, filter_chain, tmp, progress_callback, video_copy=True)
        except FileNotFoundError as exc:
            # ffmpeg binary not found; clean up and surface a plain-English error.
            if tmp.exists():
                tmp.unlink()
            raise RuntimeError("FFmpeg was not found. Please re-download KaraokeBuddy.") from exc
        except subprocess.CalledProcessError as exc:
            log.exception(
                "Export failed: input=%s output=%s tmp=%s filter_chain=%r",
                input_path,
                output_path,
                tmp,
                filter_chain,
            )
            if tmp.exists():
                tmp.unlink()
            raise RuntimeError(f"Export failed: {exc.stderr[-500:] if exc.stderr else ''}") from exc

        os.replace(tmp, output_path)

    def _run(
        self,
        input_path: Path,
        filter_chain: str,
        output_path: Path,
        progress_callback: Optional[Callable[[int], None]],
        video_copy: bool,
    ) -> None:
        video_flags = (
            ["-c:v", "copy"]
            if video_copy
            else ["-c:v", "libx264", "-crf", "23", "-preset", "veryfast"]
        )

        cmd = [
            self._ffmpeg,
            "-y",
            "-i",
            str(input_path),
            *video_flags,
            "-af",
            filter_chain,
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-f",
            "mp4",
            "-progress",
            "pipe:1",
            str(output_path),
        ]

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        duration_s: Optional[float] = None
        stderr_lines: list[str] = []

        assert proc.stdout is not None
        assert proc.stderr is not None

        # Read stderr in a separate thread to avoid deadlock
        import threading

        def _read_stderr() -> None:
            for line in proc.stderr:
                stderr_lines.append(line)

        stderr_thread = threading.Thread(target=_read_stderr, daemon=True)
        stderr_thread.start()

        for line in proc.stdout:
            m = _PROGRESS_RE.search(line)
            if m and progress_callback:
                if duration_s is None:
                    stderr_so_far = "".join(stderr_lines)
                    duration_s = _parse_duration_from_stderr(stderr_so_far)
                if duration_s and duration_s > 0:
                    elapsed_s = int(m.group(1)) / 1_000_000
                    pct = min(100, int(elapsed_s / duration_s * 100))
                    progress_callback(pct)

        proc.wait()
        stderr_thread.join(timeout=2)

        if proc.returncode != 0:
            stderr_text = "".join(stderr_lines)
            raise subprocess.CalledProcessError(proc.returncode, cmd, stderr=stderr_text)

        if progress_callback:
            progress_callback(100)


class ExportThread(QThread):
    """Run Exporter.export() on a background thread."""

    progress = Signal(int)
    finished = Signal(str)
    error = Signal(str)

    def __init__(
        self,
        input_path: Path,
        filter_chain: str,
        output_path: Path,
        ffmpeg_exe: Optional[Path] = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._input = input_path
        self._chain = filter_chain
        self._output = output_path
        self._exporter = Exporter(ffmpeg_exe)
        self._cancelled = False

    def run(self) -> None:
        try:
            self._exporter.export(
                self._input,
                self._chain,
                self._output,
                progress_callback=self.progress.emit,
            )
            if not self._cancelled:
                self.finished.emit(str(self._output))
        except Exception:  # noqa: BLE001
            log.exception("Export failed")
            if not self._cancelled:
                self.error.emit("Couldn't save here — try a different folder.")

    def cancel(self) -> None:
        self._cancelled = True
        self.terminate()
        tmp = self._output.with_suffix(".tmp")
        if tmp.exists():
            tmp.unlink(missing_ok=True)
