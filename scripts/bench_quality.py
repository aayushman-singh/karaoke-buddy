"""Benchmark: pitch-shift audio quality (PESQ + STOI), delay-aligned.

WHAT THIS MEASURES
------------------
PESQ and STOI are reference-vs-degraded metrics: they score how a "degraded"
signal compares to a "reference" of the SAME content. A pitch shift is an
*intentional* transform, not noise -- so scoring "original vs shifted" directly
would conflate the intended pitch change with artifacts and be meaningless. We
report two well-defined numbers instead:

  1. SELF-COMPARISON CEILING (sanity check): reference render at 0 semitones vs a
     second render at 0 semitones. Identical intended signal; any score below the
     metric ceiling (PESQ ~4.5, STOI ~1.0) is pure pipeline/codec noise. This
     calibrates the no-op noise floor and validates the harness wiring.

  2. SHIFT COST (round-trip): render +N semitones, then render that back -N
     semitones through the SAME chain. The output is pitch-aligned with the
     0-semitone reference again, so PESQ/STOI measure the residual smearing and
     transient damage rubberband leaves behind across one key change each way.

DELAY ALIGNMENT (why this script changed)
-----------------------------------------
Rubberband (WSOLA / phase-vocoder) introduces a processing latency and group
delay: the round-tripped signal is shifted in time relative to the reference by
some number of samples. The previous version simply truncated both signals to a
common length and scored them -- so a pure time offset was scored as if it were
artifact damage, contaminating the result. PESQ in particular is acutely
sensitive to misalignment.

Before scoring, we now **align the degraded signal to the reference by
cross-correlation**: find the integer-sample lag that maximises the
cross-correlation between the two signals (FFT-based, O(n log n)), shift the
degraded signal by that lag, then trim both to a common length. This removes the
pure-delay bias so the score reflects coloration/artifacts, not latency.

IMPORTANT HONESTY CAVEAT
------------------------
PESQ and STOI are speech metrics. Run on a SYNTHETIC MUSIC sample (a generated
pitched phrase, not speech), the absolute values are only a **rough proxy** for
perceived quality, useful for relative comparison (ceiling vs shift-cost, or
between algorithm settings) -- not an authoritative MOS for music. The
cross-correlation alignment removes pure-delay bias but does not make these
metrics into a music-grade quality judge. Read the gap between the rows, not the
absolute numbers.

HOW IT MEASURES IT
------------------
- The pitch-shift filter is the *real* export chain from
  ``karaoke_buddy.core.filter_chain.build_filter_chain`` (vocal-reduce set to 0
  so we measure pitch artifacts alone, not centre-channel cancellation).
- ffmpeg renders WAV->WAV downmixed to mono 16 kHz (PESQ wideband requires
  16 kHz). We read PCM with stdlib ``wave``.
- PESQ via the ``pesq`` package, STOI via ``pystoi``; numpy does the alignment.

HONESTY
-------
Requires ffmpeg (with the rubberband filter compiled in) AND ``pip install pesq
pystoi``. No audio device needed -- this is an offline render+score. If any
dependency is missing the script fails loudly with install instructions and
exits non-zero; it never invents a score. The benchmarks doc marks the desktop
quality values "pending hardware run" until this is executed where
ffmpeg+pesq+pystoi exist.

Usage:
    python scripts/bench_quality.py [--semitones N] [--sample PATH]
"""

import argparse
import shutil
import subprocess
import sys
import wave
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

PESQ_RATE = 16_000  # PESQ wideband mode operates at 16 kHz mono.


def _die(msg: str) -> None:
    print(f"\n[bench_quality] CANNOT RUN: {msg}\n", file=sys.stderr)
    raise SystemExit(2)


def _require_deps() -> tuple:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        _die(
            "ffmpeg not found on PATH. Quality scoring renders the real export\n"
            "  filter chain through ffmpeg's rubberband filter, so ffmpeg (built\n"
            "  --enable-librubberband) is mandatory.\n"
            "    - Windows: download a full build from https://www.gyan.dev/ffmpeg/builds/\n"
            "      and put ffmpeg.exe on PATH.\n"
            "  Verify rubberband is present: ffmpeg -filters | findstr rubberband"
        )
    try:
        from pesq import pesq  # noqa: PLC0415
    except ImportError as exc:
        _die(f"the 'pesq' package is missing ({exc!r}). Run: pip install pesq")
    try:
        from pystoi import stoi  # noqa: PLC0415
    except ImportError as exc:
        _die(f"the 'pystoi' package is missing ({exc!r}). Run: pip install pystoi")
    try:
        import numpy  # noqa: F401, PLC0415
    except ImportError as exc:
        _die(
            f"numpy is missing ({exc!r}); it is required for cross-correlation "
            "delay alignment. Run: pip install numpy (pesq/pystoi pull it in)."
        )
    return ffmpeg, pesq, stoi


def _ensure_sample(sample: Path) -> Path:
    if sample.exists():
        return sample
    print(f"[bench_quality] sample {sample} missing; generating it...")
    import _gen_sample  # noqa: PLC0415

    return _gen_sample.generate(sample)


def _ffmpeg_render(ffmpeg: str, src: Path, dst: Path, af: str | None) -> None:
    """Render ``src`` -> ``dst`` as mono 16 kHz 16-bit WAV, optionally applying ``af``."""
    cmd = [ffmpeg, "-y", "-i", str(src)]
    if af:
        cmd += ["-af", af]
    cmd += ["-ac", "1", "-ar", str(PESQ_RATE), "-c:a", "pcm_s16le", str(dst)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        _die(
            f"ffmpeg render failed (af={af!r}).\n"
            f"  command: {' '.join(cmd)}\n"
            f"  stderr tail:\n{proc.stderr[-800:]}"
        )


def _read_pcm(path: Path):
    """Read a mono 16-bit PCM WAV into a numpy float array in [-1, 1]."""
    import array  # noqa: PLC0415

    import numpy as np  # noqa: PLC0415

    with wave.open(str(path), "rb") as w:
        if w.getnchannels() != 1 or w.getsampwidth() != 2:
            _die(
                f"expected mono 16-bit WAV, got {w.getnchannels()}ch/{w.getsampwidth() * 8}bit: {path}"
            )
        rate = w.getframerate()
        raw = w.readframes(w.getnframes())
    samples = array.array("h")
    samples.frombytes(raw)
    return np.asarray(samples, dtype=np.float32) / 32768.0, rate


def _best_lag(ref, deg) -> int:
    """Integer-sample lag that maximises cross-correlation of ``deg`` against ``ref``.

    Uses the ``irfft(rfft(ref) * conj(rfft(deg)))`` convention, so a **negative**
    lag means ``deg`` is *delayed* relative to ``ref`` (ref leads) and ``deg``
    must be advanced; a **positive** lag means ``deg`` leads and ``ref`` must be
    advanced. (Verified empirically against a naive O(n^2) reference correlator.)
    FFT-based full cross-correlation: O(n log n) rather than O(n^2). Mean-removed
    so a DC offset does not bias the peak.
    """
    import numpy as np  # noqa: PLC0415

    a = ref - ref.mean()
    b = deg - deg.mean()
    n = int(2 ** np.ceil(np.log2(len(a) + len(b) - 1)))
    fa = np.fft.rfft(a, n)
    fb = np.fft.rfft(b, n)
    corr = np.fft.irfft(fa * np.conj(fb), n)
    # corr is arranged with non-negative lags first, then negative lags wrapped
    # to the tail. Unwrap to a contiguous lag axis centred on zero.
    corr = np.concatenate((corr[-(len(b) - 1) :], corr[: len(a)]))
    lags = np.arange(-(len(b) - 1), len(a))
    return int(lags[int(np.argmax(corr))])


def _align(ref, deg):
    """Delay-align ``deg`` to ``ref`` by cross-correlation, then trim to common length.

    Removes the pure-sample-delay/group-delay rubberband introduces so PESQ/STOI
    score coloration, not latency. Returns ``(ref_trimmed, deg_aligned_trimmed)``.
    """
    import numpy as np  # noqa: PLC0415

    lag = _best_lag(ref, deg)
    if lag < 0:
        # ref leads deg (deg delayed): drop the first `-lag` samples of deg.
        deg = deg[-lag:]
    elif lag > 0:
        # deg leads ref: drop the first `lag` samples of ref.
        ref = ref[lag:]
    n = min(len(ref), len(deg))
    return np.asarray(ref[:n], dtype=np.float32), np.asarray(deg[:n], dtype=np.float32)


def _score(pesq, stoi, ref_path: Path, deg_path: Path) -> tuple[float, float]:
    ref, ref_rate = _read_pcm(ref_path)
    deg, deg_rate = _read_pcm(deg_path)
    assert ref_rate == deg_rate == PESQ_RATE
    ref, deg = _align(ref, deg)  # cross-correlation delay alignment (remove latency bias)
    pesq_score = pesq(PESQ_RATE, ref, deg, "wb")
    stoi_score = stoi(ref, deg, PESQ_RATE, extended=False)
    return float(pesq_score), float(stoi_score)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--semitones", type=int, default=2, help="pitch shift to evaluate")
    ap.add_argument("--sample", type=Path, default=Path(__file__).with_name("sample.wav"))
    args = ap.parse_args()

    from karaoke_buddy.core.filter_chain import build_filter_chain  # noqa: PLC0415

    ffmpeg, pesq, stoi = _require_deps()
    sample = _ensure_sample(args.sample)

    work = sample.parent / "_bench_quality"
    work.mkdir(exist_ok=True)

    # vocal_reduce=0 -> isolate pitch artifacts, not centre-channel cancellation.
    af_shift = build_filter_chain(args.semitones, 0)
    af_unity = build_filter_chain(0, 0)

    ref0 = work / "ref_0st.wav"  # reference: 0-semitone render
    ref0b = work / "ref_0st_b.wav"  # second 0-semitone render (ceiling check)
    shifted = work / f"shift_{args.semitones}st.wav"
    # Round-trip the shifted render back toward unity so PESQ/STOI align in pitch.
    shifted_comp = work / f"shift_{args.semitones}st_comp.wav"

    print(
        f"[bench_quality] rendering through real export chain:\n  shift: {af_shift}\n  unity: {af_unity}"
    )
    _ffmpeg_render(ffmpeg, sample, ref0, af_unity)
    _ffmpeg_render(ffmpeg, sample, ref0b, af_unity)
    _ffmpeg_render(ffmpeg, sample, shifted, af_shift)
    # Compensate by shifting back -N semitones through the same chain.
    af_comp = build_filter_chain(-args.semitones, 0)
    _ffmpeg_render(ffmpeg, shifted, shifted_comp, af_comp)

    ceil_pesq, ceil_stoi = _score(pesq, stoi, ref0, ref0b)
    cost_pesq, cost_stoi = _score(pesq, stoi, ref0, shifted_comp)

    print("\n=== Pitch-shift quality (PESQ wideband + STOI, delay-aligned) ===")
    print(f"sample            : {sample}")
    print(f"shift evaluated   : {args.semitones:+d} semitones (vocal-reduce 0)")
    print("\n-- Self-comparison ceiling (0st vs 0st: pipeline noise floor) --")
    print(f"PESQ : {ceil_pesq:.3f}   (wideband ceiling ~4.5)")
    print(f"STOI : {ceil_stoi:.3f}   (ceiling 1.0)")
    print("\n-- Shift cost (0st vs +N then -N round-trip: rubberband artifacts) --")
    print(f"PESQ : {cost_pesq:.3f}")
    print(f"STOI : {cost_stoi:.3f}")
    print(
        "\nInterpretation: the gap between the ceiling row and the shift-cost row\n"
        "is the artifact/intelligibility cost rubberband adds when changing key.\n"
        "Both signals are delay-aligned by cross-correlation first, so the score\n"
        "reflects coloration, not rubberband's processing latency. NOTE: PESQ/STOI\n"
        "on synthetic music are a ROUGH PROXY only -- read the gap, not the\n"
        "absolute values."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
