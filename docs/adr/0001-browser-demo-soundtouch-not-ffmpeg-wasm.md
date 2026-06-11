# ADR 0001: Browser demo uses SoundTouch (WSOLA), not `ffmpeg.wasm`

- Status: Accepted
- Date: 2026-06-08

## Context

The desktop app shifts pitch with the Rubber Band library (via FFmpeg's
`rubberband` filter for export and mpv's native `rubberband` for live
playback). To give reviewers a zero-install, clickable surface, we wanted the
same *experience* — drag a key slider, hear the pitch move in real time — to
run as a static web page on GitHub Pages.

Two browser options were considered:

1. **`ffmpeg.wasm` with the `rubberband` filter.** Default `ffmpeg.wasm` builds
   do not include `rubberband`; enabling it means a bespoke Emscripten build,
   and FFmpeg's `rubberband` path is GPL. A hosted page shipping that artifact
   would inherit GPL obligations for the whole site.
2. **A JavaScript pitch shifter in a Web Audio AudioWorklet.** SoundTouchJS is a
   mature LGPL implementation of WSOLA time/pitch shifting that runs on the
   audio thread.

## Decision

The browser demo uses **SoundTouchJS in an AudioWorklet** for pitch shifting,
plus the same centre-channel subtraction math the desktop uses for vocal
reduction. `ffmpeg.wasm` is explicitly rejected.

## Consequences

- The hosted demo carries **no GPL obligation**; SoundTouchJS is LGPL and is
  vendored as readable source (integrity pinned by `SHA256SUMS`, verified in
  CI; see `apps/web-demo/vendor/soundtouchjs/`).
- The browser uses WSOLA (SoundTouch), while the desktop uses Rubber Band, so
  the demo is a faithful *preview of the experience*, not a byte-identical twin
  of the desktop engine. This is stated plainly in the demo UI and README.
- The byte-for-byte "what you preview is what you export" guarantee is scoped to
  the desktop pipeline and proven there (see [ADR 0002](0002-one-filter-chain-contract-verified-in-ci.md)).
