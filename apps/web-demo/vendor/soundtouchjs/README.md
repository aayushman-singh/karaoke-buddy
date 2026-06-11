# Vendored dependency: SoundTouchJS

| | |
| --- | --- |
| **Name** | `soundtouchjs` |
| **Version** | `0.3.0` |
| **License** | GNU Lesser General Public License v2.1 (LGPL-2.1) — see [`LICENSE`](./LICENSE) |
| **Source** | npm: <https://www.npmjs.com/package/soundtouchjs> · upstream: <https://github.com/cutterbl/SoundTouchJS> |
| **npm package** | `soundtouchjs@0.3.0` |
| **npm tarball** | `soundtouchjs-0.3.0.tgz` |
| **Obtained via** | `npm pack soundtouchjs@0.3.0` → extracted `package/dist/` |
| **Integrity** | sha256 of every shipped file is pinned in [`SHA256SUMS`](./SHA256SUMS) |

## Files

- `soundtouch.js` — the unmodified ES-module dist from the npm package.
- `soundtouch.js.map` — its source map.
- `SHA256SUMS` — sha256 digests of `soundtouch.js` and `soundtouch.js.map`.
- `LICENSE` — the upstream LGPL-2.1 license text.
- `UPSTREAM-README.md` — the package's own README, for reference.

## Integrity

These files are not "trust me, they're pristine" — their exact bytes are pinned
in [`SHA256SUMS`](./SHA256SUMS). CI runs `sha256sum -c SHA256SUMS` in this
directory on every push/PR (see the `verify-vendor` job in
`.github/workflows/ci.yml`), so any drift, tampering, or accidental re-vendoring
that changes a byte fails the build. To re-vendor: replace the files, then
regenerate the digests with `sha256sum soundtouch.js soundtouch.js.map > SHA256SUMS`.

## Why this library

SoundTouchJS is a pure-JavaScript implementation of the **WSOLA** (Waveform
Similarity Overlap-Add) time/pitch algorithm. It lets us shift musical key in
real time **without changing tempo**, which is exactly the desktop app's "Song
key" behaviour.

We deliberately did **not** use `ffmpeg.wasm`: it is GPL-licensed and would
contaminate this otherwise-permissive portfolio repo. LGPL allows us to ship
SoundTouchJS alongside our own code as long as the library itself stays
replaceable and its license travels with it — which is what this folder does.

## How we use it (no fork)

The file here is byte-for-byte the upstream dist. We do **not** patch it.
The AudioWorklet processor (`../../pitch-worklet.js`) `import`s the core
`SoundTouch` and `SimpleFilter` classes directly from this module and drives
them on the audio thread, instead of using the bundled `PitchShifter` helper
(which relies on the deprecated, main-thread `ScriptProcessorNode`).

If you replace this library, drop a new `soundtouch.js` here, update the
version above, regenerate `SHA256SUMS`, and keep the matching `LICENSE`.
