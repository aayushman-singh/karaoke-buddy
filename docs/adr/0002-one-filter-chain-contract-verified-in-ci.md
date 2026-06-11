# ADR 0002: One filter-chain contract, with preview≡export verified in CI

- Status: Accepted
- Date: 2026-06-08

## Context

KaraokeBuddy makes one promise that matters to a singer: **what you hear while
you practise is exactly what gets saved.** Two different engines sit behind that
promise — mpv (native `rubberband`) drives live playback, and FFmpeg
(`rubberband` + `pan` lavfi filters) drives export. If their audio math ever
drifted, the promise would quietly break.

The pitch/vocal math lived in one pure module (`core/filter_chain.py`), but
nothing *proved* the two engines produced the same result; a unit test only
checked the emitted filter *strings*, and the integration test that rendered
real audio was skipped on every CI runner because none installed mpv or a
rubberband-enabled FFmpeg.

## Decision

1. Keep a **single source of truth** for the audio math: `build_filter_chain`
   (export) and `build_mpv_filter_chain` (live) derive from the same semitone
   and centre-channel formulas, for both pitch and vocal reduction.
2. Add `tests/test_preview_export_equivalence.py`, which renders a known clip
   through *both* real engines and asserts their spectra match (peak-frequency
   ratio within tolerance and high spectral cosine similarity), for pitch and
   for vocal reduction.
3. Make that test a **required CI job** on a runner that installs mpv and a
   rubberband-enabled FFmpeg, with a guard that fails the build if the test
   *skips* (so missing tooling can never silently turn the proof off).

## Consequences

- The headline claim is now verified on every push, not merely asserted in prose.
- Adding a new audio transformation means extending one contract and the
  equivalence test, keeping the two engines honest by construction.
- The equivalence job needs a rubberband-enabled FFmpeg; the build installs a
  known static build and verifies the filter is present before relying on it.
