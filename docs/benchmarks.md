# KaraokeBuddy Benchmarks

This document defines **what we measure, why it matters to a singer, and how to
reproduce every number.** It is written to be honest first: where a metric needs
hardware this machine does not have (ffmpeg, an mpv runtime, an audio device),
the value is marked **`pending hardware run`** with the exact command that
produces it. Numbers that can be derived deterministically (the pitch math, the
real filter-chain strings) are computed and shown.

## What we measure and why

A singer cares about two things when they change the key of a backing track:

1. **Latency** — when I drag the key slider, does the new key feel *instant*, or
   is there a laggy delay before I hear it? On the desktop path this is measured
   as the wall-clock time from the app issuing the libmpv `af set` command to mpv
   acknowledging the rebuilt filter graph — a **command-to-reconfig lower bound**
   on audible latency (the full audible figure adds buffer drain and WSOLA
   window; the gold standard is a loopback capture, see Methodology). The browser
   demo's audio-stack floor is measured separately and reported in Results.
2. **Quality** — does shifting the key *wreck the audio*? Pitch-shifting is a
   real DSP transform; done badly it smears transients and adds warble. Measured
   with PESQ (perceptual quality) and STOI (intelligibility) against a
   same-pitch reference render so we isolate the **artifact cost** of the shift.

A third, smaller block of facts — the semitone→pitch-scale mapping and the exact
filter-chain strings — is fully deterministic and computed below. These are real
numbers, not placeholders.

---

## Results

There are **two independent audio paths** in this project and the table keeps
them separate so neither borrows credibility from the other:

- the **browser demo** (`apps/web-demo`, Web Audio + SoundTouch WSOLA) — measured
  live here, see the browser rows below;
- the **desktop app** (libmpv + FFmpeg/rubberband) — needs an mpv runtime,
  ffmpeg, and an audio device this environment lacks, so those cells stay
  `pending hardware run` with the exact repro command rather than fabricated.

### Browser demo (Chromium) — measured

Real measurements of the **browser audio stack's latency floor**, captured live
on this machine via Playwright-driven Chromium with an `AudioContext` running at
48 kHz. These describe the Web Audio engine floor and the slider→engine control
path — **not** the desktop mpv path, and **not** the full audible latency (see
note below the table).

| Metric | Value | How measured |
|---|---|---|
| `AudioContext.baseLatency` | **≈ 10 ms** | read directly from the live `AudioContext` (48 kHz) |
| Render quantum (128 frames / 48 kHz) | **2.67 ms** | `128 / 48000` — the Web Audio block period |
| Slider → engine control-path (input event → worklet `postMessage`) | **≈ 0.2 ms** | timestamped from the slider `input` event to the worklet `postMessage` dispatch |

`AudioContext.outputLatency` read **0** in headless Chromium (no real audio
output device), so it is **excluded honestly** rather than reported as a
meaningful figure. These numbers are the *floor* of the browser audio stack;
**SoundTouch's WSOLA frame buffer adds algorithmic latency on top** (it needs a
window of samples before it can emit pitch-shifted output) — qualitative, not
captured by the control-path number above.

### Desktop app (libmpv + FFmpeg) — pending hardware run

| Metric | Value | How measured | Repro command |
|---|---|---|---|
| Slider-drag → filter-reconfig latency, median (lower bound on audible) | **pending hardware run** | wall-clock from `af set` to mpv acknowledging the rebuilt filter graph (`af` property round-trip), N trials, via real `build_mpv_filter_chain` | `python scripts/bench_latency.py` |
| Slider-drag → filter-reconfig latency, p95 (lower bound on audible) | **pending hardware run** | as above, 95th percentile | `python scripts/bench_latency.py` |
| Pitch-shift PESQ — self-comparison ceiling (0st vs 0st) | **pending hardware run** | pipeline/codec noise floor; PESQ wideband ceiling ≈ 4.5; delay-aligned | `python scripts/bench_quality.py` |
| Pitch-shift STOI — self-comparison ceiling (0st vs 0st) | **pending hardware run** | intelligibility ceiling ≈ 1.0; delay-aligned | `python scripts/bench_quality.py` |
| Pitch-shift PESQ — shift cost (±2 st round-trip) | **pending hardware run** | rubberband artifact cost vs same-pitch reference, cross-correlation delay-aligned | `python scripts/bench_quality.py --semitones 2` |
| Pitch-shift STOI — shift cost (±2 st round-trip) | **pending hardware run** | intelligibility cost of the shift, cross-correlation delay-aligned | `python scripts/bench_quality.py --semitones 2` |
| Semitone → pitch-scale factor | **computed (see table)** | `2^(n/12)` from `filter_chain._pitch_scale` | `python scripts/_gen_sample.py` + table below |
| Export filter chain (+2 st, 80% vocal-reduce) | **computed** | real `build_filter_chain(2, 80)` | see "Deterministic facts" |

> Why the desktop rows say "pending hardware run": this is a **build/CI
> environment with no ffmpeg, no mpv runtime, and no audio device.** Rather than
> print invented numbers, the scripts fail loudly with install instructions when
> their dependencies are absent, and the table stays honest. Run them on a real
> desktop to fill the cells in. The desktop latency number, when filled, is a
> **command-to-reconfig lower bound**, not full audible latency — see the
> methodology section.

---

## Deterministic facts (real, computed now)

### Semitone → pitch-scale mapping

KaraokeBuddy maps an integer semitone shift `n` to a linear pitch-scale factor
`2^(n/12)` — the equal-temperament ratio — in
`karaoke_buddy.core.filter_chain._pitch_scale`. The same value feeds both the
live mpv `rubberband=pitch-scale=…` filter and the FFmpeg export
`rubberband=pitch=…` filter, so **preview and export pitch are identical by
construction.**

The full table over the app's `[-12, +12]` semitone range (computed directly
from the source function):

| Semitones | Pitch scale | | Semitones | Pitch scale |
|---:|---:|---|---:|---:|
| −12 | 0.500000 | | +1  | 1.059463 |
| −11 | 0.529732 | | +2  | 1.122462 |
| −10 | 0.561231 | | +3  | 1.189207 |
| −9  | 0.594604 | | +4  | 1.259921 |
| −8  | 0.629961 | | +5  | 1.334840 |
| −7  | 0.667420 | | +6  | 1.414214 |
| −6  | 0.707107 | | +7  | 1.498307 |
| −5  | 0.749154 | | +8  | 1.587401 |
| −4  | 0.793701 | | +9  | 1.681793 |
| −3  | 0.840896 | | +10 | 1.781797 |
| −2  | 0.890899 | | +11 | 1.887749 |
| −1  | 0.943874 | | +12 | 2.000000 |
| 0   | 1.000000 | |     |          |

Sanity anchors: −12 st halves the frequency (0.5×, one octave down), +12 st
doubles it (2.0×, one octave up), +7 st (a perfect fifth) is ≈ 1.4983×, and +1 st
is the familiar twelfth-root-of-two, ≈ 1.059463.

### Pitch-shift algorithm: rubberband

Both the live path (mpv's native `rubberband` audio filter) and the export path
(FFmpeg's `librubberband`) use the **Rubber Band Library**, a time-domain /
phase-vocoder hybrid (WSOLA-style overlap-add with phase-locking). The property
that matters for karaoke: **rubberband changes pitch while preserving tempo** —
the backing track plays at the same speed, only the key moves. This is why a
singer can drop the key without the song slowing down.

### Export filter-chain strings (real `build_filter_chain` output)

Generated by calling the production function directly:

- `build_filter_chain(2, 80)` (raise +2 semitones, 80% vocal reduction):

  ```text
  rubberband=pitch=1.122462,pan=stereo|c0=c0-0.4000*c1|c1=c1-0.4000*c0
  ```

- `build_filter_chain(0, 0)` (no shift, no vocal reduction — the identity render
  used as the quality-benchmark reference):

  ```text
  rubberband=pitch=1.000000,pan=stereo|c0=c0-0.0000*c1|c1=c1-0.0000*c0
  ```

- `build_mpv_filter_chain(2)` (live preview, +2 semitones):

  ```text
  rubberband=pitch-scale=1.122462
  ```

The `pan` stage subtracts a fraction (`vocal_reduce_percent/100 × 0.5`) of each
channel from the other — centre-channel cancellation, the classic "vocal remove"
trick. The quality benchmark sets vocal-reduce to **0** so it measures pitch
artifacts alone, not cancellation.

---

## Methodology

### 1. Slider-drag → filter-reconfig latency (desktop)

**Definition.** The time from the app issuing the libmpv command
`command("af", "set", <chain>)` — exactly what `Player.set_filter` does in
production (`src/karaoke_buddy/core/player.py`) — to the moment **mpv
acknowledges its audio filter graph has been rebuilt** with the new chain,
observed via the `af` property round-trip. This is **command-to-reconfig
latency: a lower bound on audible latency**, not the audible latency itself.

**Why not "next audio tick".** An earlier version blocked until `audio-pts`
advanced past its pre-command value and called that the latency. That was wrong:
`audio-pts` advances continuously during normal playback whether or not the
filter graph reconfigured, so the loop really measured *polling jitter until the
next audio tick*, conflating playback cadence with reconfig cost. We now wait on
the `af` property reflecting the newly-installed chain — the engine confirming
the graph actually changed — which is a strictly tighter, honest signal.

**Procedure** (`scripts/bench_latency.py`):

1. Build the filter string with the **real** `build_mpv_filter_chain`, so the
   benchmark cannot drift from the shipping UI code path.
2. Start mpv playing the shared deterministic sample (`scripts/sample.wav`,
   generated by `_gen_sample.py`) with `vo=null` (we only care about audio).
3. Wait until audio is actually flowing (`audio-pts` > 0) before timing — a
   reconfig of an idle graph is not representative of a live key change.
4. For each trial, toggle pitch between 0 and the test value:
   - record `t0`,
   - issue `command("af", "set", chain)`,
   - block until the `af` property reflects the new chain (rubberband
     `pitch-scale` token installed in the live filter list),
   - record `t1`; latency = `t1 − t0`.
5. Report **median** and **p95** over N trials (default 40).

**What this does NOT capture, and the gold standard.** The printed number is a
**lower bound**. True audible latency additionally includes the already-queued
output buffer draining at the old pitch, the OS/device buffer, and rubberband's
own WSOLA analysis window — none of which an in-process property round-trip sees.
The rigorous, fully-honest measurement is an **acoustic / loopback capture**:
route mpv's output through a virtual audio device, record the stream, and detect
the exact sample where the spectrum shifts to the new pitch (track a known
partial or cross-correlate against a reference render); latency = (capture
timestamp of the spectral change) − (`t0`). That is the gold standard; it needs a
loopback device and a pitch-tracking stage and is out of scope for this
in-process micro-benchmark, which measures the best honest proxy it can.

The script requires a real mpv runtime and a working audio clock, so it
**refuses to run** (exit 2, with install instructions) when libmpv or audio is
absent rather than emit a fabricated millisecond figure.

### 2. Pitch-shift quality (PESQ / STOI)

**The honesty caveat up front.** PESQ and STOI compare a *degraded* signal to a
*reference* of the **same** content. A pitch shift deliberately changes the
content, so naïvely scoring "original vs shifted" would conflate the intended
pitch change with artifacts and produce a meaningless low score. The script
therefore reports two well-defined numbers:

1. **Self-comparison ceiling** — render the sample through the export chain at
   **0 semitones twice** and score one against the other. The intended signal is
   identical, so any drop below the metric ceiling (PESQ ≈ 4.5, STOI ≈ 1.0) is
   pure pipeline/codec noise. This both calibrates the noise floor and validates
   that the harness is wired correctly.
2. **Shift cost** — render at +N semitones, then render that result back through
   the **same chain at −N semitones** (a pitch round-trip). The output is
   pitch-aligned with the 0-semitone reference again, so PESQ/STOI now measure
   the residual smearing and transient damage rubberband leaves behind — **the
   meaningful karaoke number**: *how much does changing the key cost the audio?*

The gap between the ceiling row and the shift-cost row is the artifact budget of
one key change in each direction.

**Delay alignment (required for an honest score).** Rubberband (WSOLA /
phase-vocoder) introduces processing latency and group delay, so the
round-tripped signal is shifted in time relative to the reference by some number
of samples. Scoring without correcting for that would let a pure time offset
masquerade as artifact damage — PESQ is especially sensitive to misalignment.
Before scoring, the script **aligns the degraded signal to the reference by
cross-correlation**: it finds the integer-sample lag that maximises the
FFT-based cross-correlation between the two signals, shifts the degraded signal
by that lag, then trims both to a common length. This removes the pure-delay bias
so the score reflects coloration/artifacts, not latency.

**Honesty caveat on the absolute numbers.** PESQ and STOI are *speech* metrics.
The benchmark runs on a **synthetic music** sample (a generated pitched phrase,
not speech), so the absolute values are only a **rough proxy** for perceived
quality — useful for *relative* comparison (ceiling vs shift-cost, or across
algorithm settings), not as an authoritative MOS for music. Read the gap between
the rows, not the raw numbers. Cross-correlation alignment removes the delay
bias; it does not turn these into a music-grade quality judge.

**Procedure** (`scripts/bench_quality.py`):

1. Build the filter with the **real** `build_filter_chain(n, 0)` (vocal-reduce
   forced to 0 to isolate pitch artifacts).
2. ffmpeg renders WAV→WAV, downmixed to **mono 16 kHz 16-bit** (PESQ wideband
   requirement).
3. Read PCM with stdlib `wave`, **cross-correlation delay-align** the degraded
   signal to the reference, then score with `pesq` (wideband) and `pystoi`.

Requires ffmpeg built with `librubberband`, plus `pip install pesq pystoi`
(numpy, used for the alignment, comes in transitively). Missing any of these →
loud failure, exit 2, no invented score.

---

## Reproduce locally

All commands assume the repo root and the project virtualenv
(`.venv/Scripts/python.exe` on Windows, `.venv/bin/python` elsewhere).

### Prerequisites

| Need | For | Install |
|---|---|---|
| mpv runtime (libmpv / `mpv-2.dll`) + `python-mpv` | latency | https://mpv.io ; `pip install python-mpv` |
| ffmpeg with `librubberband` | quality | https://www.gyan.dev/ffmpeg/builds/ ; verify `ffmpeg -filters \| findstr rubberband` |
| `pesq`, `pystoi` (pull in `numpy`) | quality | `pip install pesq pystoi` |
| an audio output device | latency only | physical/virtual sound card |

### Scripts

- **`scripts/_gen_sample.py`** — synthesizes the shared deterministic test WAV
  (4 s stereo, 44.1 kHz, 16-bit) from stdlib `wave`+`math`. A fixed pitched
  phrase with harmonic partials and a slight stereo image — no numpy, no
  copyrighted audio. Both benchmarks use this exact file as input.
- **`scripts/bench_latency.py`** — drives mpv, toggles pitch via the real filter
  builder, times command→reconfig (the `af` property reflecting the new graph);
  reports median/p95 as a lower bound on audible latency.
- **`scripts/bench_quality.py`** — renders through the real export chain with
  ffmpeg, cross-correlation delay-aligns, scores PESQ + STOI (ceiling and
  shift-cost; rough proxy on synthetic music).

### Commands

```bash
# 1. Generate the shared sample (no extra deps; runs anywhere).
python scripts/_gen_sample.py

# 2. Latency (needs mpv runtime + audio device).
python scripts/bench_latency.py --trials 40 --pitch 2

# 3. Quality (needs ffmpeg + pesq + pystoi).
pip install pesq pystoi
python scripts/bench_quality.py --semitones 2
```

Each bench script auto-generates `sample.wav` if it is missing, so step 1 is
optional. When a dependency is absent, the script prints a clear `CANNOT RUN:`
diagnostic and exits non-zero — by design, so a missing tool can never be
mistaken for a passing benchmark.
