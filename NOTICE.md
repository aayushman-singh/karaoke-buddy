# Third-Party Notices

KaraokeBuddy is MIT-licensed (see `LICENSE`). It depends on and, when packaged
as a `.exe`, bundles the following third-party components. Each retains its
own license; the terms below apply to those components, not to KaraokeBuddy's
own source code.

## Python runtime dependencies

| Component   | License            | Project                                       |
| ----------- | ------------------ | --------------------------------------------- |
| PySide6     | LGPL v3 / GPL v2+  | https://wiki.qt.io/Qt_for_Python              |
| python-mpv  | AGPLv3 / GPL v2+   | https://github.com/jaseg/python-mpv           |
| yt-dlp      | Unlicense          | https://github.com/yt-dlp/yt-dlp              |
| yt-dlp-ejs  | MIT                | https://github.com/yt-dlp/yt-dlp-ejs          |
| deno (pip)  | MIT                | https://pypi.org/project/deno/                |

PySide6 is used as a library via its Python bindings; this is the LGPL usage
mode (dynamic linking, replaceable Qt libraries). python-mpv is a thin Python
wrapper around libmpv and is also used as a library.

## Bundled native binaries (release artifacts only)

The `KaraokeBuddy.exe` distributed via GitHub Releases bundles the following
binaries. They are **not** stored in this source repository; they are
downloaded and embedded at build time.

| Binary        | License        | Source                                                          |
| ------------- | -------------- | --------------------------------------------------------------- |
| `ffmpeg.exe`  | GPL v3 (GPL build with rubberband) | https://www.gyan.dev/ffmpeg/builds/ |
| `ffprobe.exe` | GPL v3         | same build as `ffmpeg.exe`                                      |
| `libmpv-2.dll`| GPL v2+ / LGPL v2.1+ | https://sourceforge.net/projects/mpv-player-windows/      |
| `deno.exe`    | MIT            | https://github.com/denoland/deno                                |

Because the GPL build of FFmpeg is GPL v3, the distributed `.exe` is itself
distributed under terms compatible with GPL v3 for the bundle as a whole.
Anyone redistributing the bundled `.exe` must comply with GPL v3 for the
FFmpeg portion. The KaraokeBuddy source code remains MIT-licensed and can be
combined with non-GPL FFmpeg builds (e.g. LGPL FFmpeg) if you build your own
distribution.

## Attribution

Full license texts for these components are available at the project URLs
listed above. The `.exe` release page links to each component's license.
