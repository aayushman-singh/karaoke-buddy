"""Generate the test fixture: tests/fixtures/sample_10s.mp4.

Requires FFmpeg on PATH. Creates a 10-second silent black video.
Run once before running the integration tests:
    python build/create_fixture.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

FIXTURE_DIR = Path(__file__).parent.parent / "tests" / "fixtures"
FIXTURE_PATH = FIXTURE_DIR / "sample_10s.mp4"


def main() -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        print("ERROR: ffmpeg not found on PATH", file=sys.stderr)
        sys.exit(1)

    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)

    cmd = [
        ffmpeg,
        "-y",
        # Silent audio: 10 s of silence at 44.1 kHz stereo
        "-f",
        "lavfi",
        "-i",
        "anullsrc=r=44100:cl=stereo",
        # Black video: 10 s at 25 fps, 320x180
        "-f",
        "lavfi",
        "-i",
        "color=c=black:s=320x180:r=25",
        "-t",
        "10",
        "-c:v",
        "libx264",
        "-crf",
        "28",
        "-preset",
        "ultrafast",
        "-c:a",
        "aac",
        "-b:a",
        "64k",
        str(FIXTURE_PATH),
    ]

    print("Creating fixture:", FIXTURE_PATH)
    result = subprocess.run(cmd)
    if result.returncode == 0:
        print("Done:", FIXTURE_PATH)
    else:
        print("ERROR: ffmpeg returned", result.returncode, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
