# ADR 0004: No ML vocal isolation (deliberate non-goal)

- Status: Accepted
- Date: 2026-06-08

## Context

A reasonable question for a karaoke tool is "why not use a neural source
separator (Demucs, Spleeter) to isolate and remove the vocal cleanly?" ML
separation produces visibly better isolation than centre-channel subtraction
([ADR 0003](0003-vocal-reduction-centre-channel.md)).

## Decision

KaraokeBuddy does **not** ship ML vocal isolation. It stays a small, portable,
real-time desktop app.

## Consequences

The trade-offs that drive this:

- **Weight.** Demucs/Spleeter pull in a deep-learning runtime and hundred-MB
  model weights. That bloats the single-file `.exe`, slows startup, and turns a
  lean download into a heavyweight install.
- **Latency model.** Separation is an *offline*, often GPU-hungry batch step. It
  does not fit the product's core loop — drag a slider, hear the change
  immediately. Centre-channel reduction is instant and runs on the same live
  filter graph as pitch.
- **Different product.** High-quality isolation is its own application
  (stem extraction, remixing), with different UX and expectations, not a toggle
  bolted onto a practice tool.

This is recorded as a non-goal so the boundary is explicit. It can be revisited
if a concrete user need emerges — most likely as an optional, clearly-offline
"export isolated stem" path rather than a change to the real-time engine.
