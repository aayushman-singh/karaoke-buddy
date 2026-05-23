# Binaries for build/build.py (place files here before building)

Required:
  ffmpeg.exe   - GPL static build WITH rubberband (not "essentials")
  ffprobe.exe  - ships in the same FFmpeg release archive as ffmpeg.exe
  libmpv-2.dll - libmpv dev DLL (~30-50 MB typical; avoid huge debug builds)
  deno.exe     - for YouTube URLs (auto-copied on build if you ran: pip install deno)

ffprobe.exe is used for reliable duration probing (structured JSON output).
It is required - duration probing fails loudly if it is missing or unreadable,
so the app never silently records a song as 0:00.

## Smaller portable builds

1. ffmpeg.exe (~200 MB today)
   - You need: rubberband filter for pitch shift
   - Verify: ffmpeg.exe -filters 2>&1 | findstr rubberband
   - Source: https://github.com/BtbN/FFmpeg-Builds/releases
     (ffmpeg-master-latest-win64-gpl.zip - do not use essentials/LGPL)

2. libmpv-2.dll
   - Source: https://sourceforge.net/projects/mpv-player-windows/files/libmpv/
   - Pick a recent x86_64 release; DLL should be tens of MB, not 100+ MB

3. Build
   - python build/build.py
   - Output: build/dist/KaraokeBuddy.exe

4. Share
   - If still too big for WhatsApp, zip build/dist/KaraokeBuddy.exe or use Drive
   - python build/build.py --onedir then zip the KaraokeBuddy folder
