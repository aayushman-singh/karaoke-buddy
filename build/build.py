"""PyInstaller build driver for KaraokeBuddy.

Usage:
    python build/build.py

Expects the following binaries to exist before running:
    - build/bin/ffmpeg.exe
    - build/bin/ffprobe.exe
    - build/bin/libmpv-2.dll

Download sources:
    FFmpeg:  https://github.com/BtbN/FFmpeg-Builds/releases
    libmpv:  https://sourceforge.net/projects/mpv-player-windows/files/libmpv/
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
BIN_DIR = ROOT / "build" / "bin"
ENTRY = ROOT / "src" / "karaoke_buddy" / "__main__.py"
DIST_DIR = ROOT / "build" / "dist"


def check_binaries() -> None:
    required = ["ffmpeg.exe", "ffprobe.exe", "libmpv-2.dll"]
    missing = [b for b in required if not (BIN_DIR / b).exists()]
    if missing:
        print(f"ERROR: Missing binaries in {BIN_DIR}:")
        for m in missing:
            print(f"  - {m}")
        print("\nSee the docstring in build/build.py for download links.")
        sys.exit(1)


def build() -> None:
    check_binaries()
    DIST_DIR.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--onefile",
        "--windowed",
        "--name",
        "KaraokeBuddy",
        "--distpath",
        str(DIST_DIR),
        "--workpath",
        str(ROOT / "build" / "work"),
        "--specpath",
        str(ROOT / "build"),
        "--add-binary",
        f"{BIN_DIR / 'ffmpeg.exe'};.",
        "--add-binary",
        f"{BIN_DIR / 'ffprobe.exe'};.",
        "--add-binary",
        f"{BIN_DIR / 'libmpv-2.dll'};.",
        "--icon",
        str(ROOT / "src" / "karaoke_buddy" / "resources" / "icon.ico"),
        "--hidden-import",
        "yt_dlp",
        "--hidden-import",
        "yt_dlp.extractor",
        str(ENTRY),
    ]

    print("Running PyInstaller\u2026")
    subprocess.run(cmd, check=True, cwd=ROOT)
    print(f"\nBuild complete: {DIST_DIR / 'KaraokeBuddy.exe'}")


if __name__ == "__main__":
    build()
