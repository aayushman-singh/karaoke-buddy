"""PyInstaller build driver for KaraokeBuddy.

Usage:
    python build/build.py              # single KaraokeBuddy.exe
    python build/build.py --onedir     # folder layout (often zips smaller for sharing)

Expects before running:
    - build/bin/ffmpeg.exe   (GPL build with rubberband - see build/bin/README.txt)
    - build/bin/ffprobe.exe  (ships with the same FFmpeg release as ffmpeg.exe)
    - build/bin/libmpv-2.dll
    - build/bin/deno.exe     (copied from ``pip install deno`` if missing)

Download sources:
    FFmpeg:  https://github.com/BtbN/FFmpeg-Builds/releases (gpl, not essentials)
    libmpv:  https://sourceforge.net/projects/mpv-player-windows/files/libmpv/
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
BIN_DIR = ROOT / "build" / "bin"
ENTRY = ROOT / "src" / "karaoke_buddy" / "__main__.py"
DIST_DIR = ROOT / "build" / "dist"

# Trim unused Qt stacks PyInstaller would otherwise pull from PySide6.
EXCLUDE_MODULES = [
    "PySide6.Qt3DAnimation",
    "PySide6.Qt3DCore",
    "PySide6.Qt3DExtras",
    "PySide6.Qt3DInput",
    "PySide6.Qt3DLogic",
    "PySide6.Qt3DRender",
    "PySide6.QtCharts",
    "PySide6.QtDataVisualization",
    "PySide6.QtGraphs",
    "PySide6.QtGraphsWidgets",
    "PySide6.QtLocation",
    "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets",
    "PySide6.QtNetworkAuth",
    "PySide6.QtNfc",
    "PySide6.QtPositioning",
    "PySide6.QtQuick",
    "PySide6.QtQuick3D",
    "PySide6.QtQuickControls2",
    "PySide6.QtQuickWidgets",
    "PySide6.QtQml",
    "PySide6.QtRemoteObjects",
    "PySide6.QtScxml",
    "PySide6.QtSensors",
    "PySide6.QtSerialPort",
    "PySide6.QtStateMachine",
    "PySide6.QtSvgWidgets",
    "PySide6.QtTextToSpeech",
    "PySide6.QtWebChannel",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineQuick",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebSockets",
    "tkinter",
    "matplotlib",
    "numpy",
    "pandas",
    "scipy",
    "PIL",
]


def ensure_deno_binary() -> Path:
    """Stage deno.exe beside ffmpeg for PyInstaller (YouTube / yt-dlp JS)."""
    dest = BIN_DIR / "deno.exe"
    if dest.exists():
        return dest
    try:
        import deno  # noqa: PLC0415

        src = Path(deno.find_deno_bin())
    except Exception as exc:  # noqa: BLE001
        print(
            "ERROR: deno.exe is required for YouTube in the portable build.\n"
            "  pip install deno\n"
            "  or place deno.exe in build/bin/\n"
            f"  ({exc})"
        )
        sys.exit(1)
    if not src.is_file():
        print(f"ERROR: Deno binary not found at {src}")
        sys.exit(1)
    print(f"Staging deno.exe from {src} ...")
    shutil.copy2(src, dest)
    return dest


def check_binaries() -> None:
    ensure_deno_binary()
    required = ["ffmpeg.exe", "ffprobe.exe", "libmpv-2.dll", "deno.exe"]
    missing = [b for b in required if not (BIN_DIR / b).exists()]
    if missing:
        print(f"ERROR: Missing binaries in {BIN_DIR}:")
        for m in missing:
            print(f"  - {m}")
        print("\nSee build/bin/README.txt for download links.")
        sys.exit(1)


def build(*, onedir: bool) -> None:
    check_binaries()
    DIST_DIR.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
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
        "--add-binary",
        f"{BIN_DIR / 'deno.exe'};.",
        "--icon",
        str(ROOT / "src" / "karaoke_buddy" / "resources" / "icon.ico"),
        "--collect-all",
        "yt_dlp_ejs",
        "--hidden-import",
        "yt_dlp",
        "--hidden-import",
        "yt_dlp.extractor",
        "--hidden-import",
        "yt_dlp_ejs",
    ]
    if onedir:
        cmd.append("--onedir")
    else:
        cmd.append("--onefile")

    for module in EXCLUDE_MODULES:
        cmd.extend(["--exclude-module", module])

    cmd.append(str(ENTRY))

    print("Running PyInstaller\u2026")
    subprocess.run(cmd, check=True, cwd=ROOT)
    if onedir:
        out = DIST_DIR / "KaraokeBuddy" / "KaraokeBuddy.exe"
    else:
        out = DIST_DIR / "KaraokeBuddy.exe"
    size_mb = out.stat().st_size / (1024 * 1024)
    print(f"\nBuild complete: {out} ({size_mb:.1f} MB)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build KaraokeBuddy for Windows")
    parser.add_argument(
        "--onedir",
        action="store_true",
        help="Emit a folder instead of one exe (zip the folder to share)",
    )
    args = parser.parse_args()
    build(onedir=args.onedir)


if __name__ == "__main__":
    main()
