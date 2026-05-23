# Security Policy

## Reporting a vulnerability

Please **do not** open a public GitHub issue for security problems.

Email **aayushman2702@gmail.com** with:

- A description of the vulnerability and its impact.
- Steps to reproduce (proof-of-concept code or a sample input is welcome).
- The KaraokeBuddy version and OS where you observed it.

You will get an acknowledgement within **7 days**. A fix or status update
follows within **30 days** for confirmed issues. Coordinated disclosure: please
hold public details for **90 days** from your report, or until a release ships
with a fix, whichever comes first.

## Supported versions

Only the latest minor release is supported. Older versions do not receive
backported security fixes.

| Version | Supported |
| ------- | --------- |
| 0.1.x   | Yes       |
| < 0.1   | No        |

## In scope

- Bugs in KaraokeBuddy's Python source that cause unintended file writes,
  command execution, or credential exposure.
- Vulnerable handling of malicious media files, malicious YouTube URLs, or
  malicious `library.json` contents.
- Issues in the Windows release `.exe` that originate from how KaraokeBuddy
  bundles FFmpeg / libmpv / yt-dlp / deno.

## Out of scope

- Vulnerabilities in upstream dependencies themselves (FFmpeg, libmpv, yt-dlp,
  PySide6) - please report those to the respective projects. We will update
  pinned versions promptly after upstream releases a fix.
- Self-DoS by feeding intentionally massive files to the export pipeline.
- Social-engineering issues outside the running app (e.g., a phishing site
  hosting a fake KaraokeBuddy.exe).
