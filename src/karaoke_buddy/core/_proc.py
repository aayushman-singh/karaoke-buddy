"""Subprocess helpers shared across the exporter, source resolver, and preflight.

The only reason this module exists today is to keep the no-console-window
flag in one place. KaraokeBuddy is a windowed app; launching console
binaries (ffmpeg, ffprobe, yt-dlp via deno) was flashing a black cmd
window on Windows every time we shelled out. CREATE_NO_WINDOW tells
Windows not to allocate a console for the child process. The constant is
0 on non-Windows platforms so callers can pass it unconditionally.
"""

import subprocess

HIDDEN_PROCESS_FLAGS = getattr(subprocess, "CREATE_NO_WINDOW", 0)
