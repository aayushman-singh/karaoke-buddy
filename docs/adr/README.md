# Architecture Decision Records

Short, durable records of the non-obvious engineering decisions behind
KaraokeBuddy — the *why*, not the *how*. Each is self-contained.

| ADR | Decision |
| --- | --- |
| [0001](0001-browser-demo-soundtouch-not-ffmpeg-wasm.md) | Browser demo uses SoundTouch (WSOLA), not `ffmpeg.wasm` |
| [0002](0002-one-filter-chain-contract-verified-in-ci.md) | A single filter-chain contract, with preview≡export verified in CI |
| [0003](0003-vocal-reduction-centre-channel.md) | Vocal reduction via centre-channel subtraction, live and on export |
| [0004](0004-no-ml-vocal-isolation.md) | No ML vocal isolation (deliberate non-goal) |
