# ADR 0003: Vocal reduction via centre-channel subtraction, live and on export

- Status: Accepted
- Date: 2026-06-08

## Context

Karaoke tracks usually place the guide vocal in the centre of the stereo image
and the backing instruments wider. A singer practising wants to turn that guide
vocal *down* without losing the music. The data model and export math already
supported a `vocal_reduce` parameter, but it was not wired to any UI control,
the live preview ignored it, and export hard-coded it to zero — so the product
advertised a feature it could not actually apply.

## Decision

Implement vocal reduction **end to end** using centre-channel subtraction, the
classic, real-time, zero-dependency technique: with `mix = (percent/100) * 0.5`,

```
out_L = L - mix * R
out_R = R - mix * L
```

This removes content common to both channels (the centred vocal) while leaving
panned material largely intact. It is applied:

- **live**, via a "Silence the singer" slider that updates mpv's filter chain
  (rubberband + a libavfilter `pan`);
- **on export**, via the same `pan` in the FFmpeg chain;
- **persistently**, stored per song alongside the key so a practice setup is
  restored next time.

Both paths derive from the one contract in [ADR 0002](0002-one-filter-chain-contract-verified-in-ci.md),
and the equivalence test covers the reduced-vocal case.

## Consequences

- The "Silence the singer" control is honest: the reduction you preview is the
  reduction you export.
- Centre-channel subtraction is not source separation — a vocal that is panned,
  reverberant, or doubled is only partially removed. This is the right trade for
  a real-time, offline-free desktop tool; see [ADR 0004](0004-no-ml-vocal-isolation.md)
  for why we do not reach for ML separation.
