"""End-to-end proof that the live preview and the exported file apply the *same*
pitch shift.

This is the project's headline architectural claim: ``build_mpv_filter_chain``
(live, mpv native ``rubberband`` with ``pitch-scale=``) and
``build_filter_chain`` (export, FFmpeg lavfi ``rubberband=pitch=,pan=...``) are
two different filter *syntaxes* that must produce *acoustically identical*
output because they share the same ``pitch_scale = 2**(semitones/12)`` math.

Unit tests in ``test_filter_chain.py`` already prove the two builders emit the
expected *strings*. They do NOT prove that mpv's ``rubberband`` and FFmpeg's
``rubberband`` actually shift pitch the same way once those strings hit the real
binaries. This file closes that gap by rendering a known clip through BOTH real
pipelines and comparing the resulting audio spectra.

Method
------
1. Synthesize a deterministic stereo WAV (sum of pure sine tones, 48 kHz,
   16-bit) with the stdlib ``wave`` + ``math`` — no numpy needed to *generate*.
2. Export path: run the real ``ffmpeg`` with ``-af "<build_filter_chain(p,0)>"``
   (vocal_reduce=0 so the pan stage is an identity passthrough and we compare
   pure pitch). ``input.wav -> export.wav``.
3. Preview path: run the real ``mpv`` with ``--af=<build_mpv_filter_chain(p)>``,
   encoding to ``preview.wav`` (the exact native filter the Player applies via
   ``af set``). ``input.wav -> preview.wav``.
4. Compare in the frequency domain:
   - Each rendered tone should sit at ``f_in * 2**(p/12)``. We locate the
     dominant spectral peak of one input tone in each output and assert the
     measured *fundamental ratio* matches ``2**(p/12)`` within ~1.5% — tight
     enough that an off-by-one-semitone error (a ~5.9% ratio change) fails
     loudly, loose enough to absorb FFT bin quantization and encoder dither.
   - A whole-spectrum distance: cosine similarity of the two magnitude spectra
     (export vs preview) must be >= 0.97. Cosine similarity is invariant to
     overall gain, so it isolates "is the spectral *shape* the same" — i.e. did
     both pipelines move every partial to the same place — from loudness
     differences between the two encoders.

Robustness
----------
Spectra are gain-normalized (cosine sim) and both signals are trimmed to a
common length before the FFT, so differing latency/length between encoders does
not bias the result. The peak-ratio assertion guards against the comparison
being *too* loose: a wrong pitch shifts the peak out of tolerance and fails.

Skips
-----
This is test infrastructure, not runtime code, so explicit pytest skips for
genuinely-absent dependencies are required (the binaries are not installed in
CI). The test SKIPS — never silently passes — when ``ffmpeg`` is not on PATH,
``mpv`` is not on PATH, or ``numpy`` is unavailable. It never skips to dodge a
real assertion failure. Run with ``-rs`` to see the skip reason.
"""

import math
import shutil
import struct
import subprocess
import wave
from pathlib import Path

import pytest

from karaoke_buddy.core.filter_chain import build_filter_chain, build_mpv_filter_chain

# --- Dependency gates (loud, explicit, infra-only) -------------------------
FFMPEG = shutil.which("ffmpeg")
MPV = shutil.which("mpv")

if FFMPEG is None:
    pytest.skip(
        "ffmpeg binary not found on PATH; cannot render the export pipeline. "
        "Install ffmpeg to run the preview/export equivalence test.",
        allow_module_level=True,
    )
if MPV is None:
    pytest.skip(
        "mpv binary not found on PATH; cannot render the live preview pipeline. "
        "Install mpv to run the preview/export equivalence test.",
        allow_module_level=True,
    )

# numpy is only needed for the FFT/comparison, never for generation.
np = pytest.importorskip(
    "numpy",
    reason="numpy is required for the FFT spectral comparison; install numpy to run this test.",
)

# --- Test signal definition ------------------------------------------------
SAMPLE_RATE = 48_000
DURATION_S = 4.0
# Three well-separated tones so the spectrum has unambiguous peaks. We track the
# lowest tone (440 Hz) as the "fundamental" for the peak-ratio check.
INPUT_TONES_HZ = (440.0, 880.0, 1320.0)
FUNDAMENTAL_HZ = INPUT_TONES_HZ[0]

# Tolerances (see module docstring for rationale).
PEAK_RATIO_REL_TOL = 0.015  # 1.5% — far tighter than one semitone (~5.9%).
MIN_COSINE_SIMILARITY = 0.97


def _write_sine_wav(path: Path) -> None:
    """Write a deterministic 16-bit stereo WAV summing INPUT_TONES_HZ.

    Pure stdlib (wave + math). Left and right channels are identical so the
    export pan stage (identity at vocal_reduce=0) cannot perturb the result.
    """
    n_samples = int(SAMPLE_RATE * DURATION_S)
    amplitude = 0.3 / len(INPUT_TONES_HZ)  # headroom so the sum never clips.
    frames = bytearray()
    two_pi = 2 * math.pi
    for n in range(n_samples):
        t = n / SAMPLE_RATE
        s = sum(math.sin(two_pi * f * t) for f in INPUT_TONES_HZ) * amplitude
        sample = int(max(-1.0, min(1.0, s)) * 32767)
        frame = struct.pack("<h", sample)
        frames += frame  # left
        frames += frame  # right (identical)

    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(bytes(frames))


# --- Vocal-reduction test signal -------------------------------------------
# A centre-panned (identical L/R) "vocal" tone plus a left-only "side" tone.
# Centre-channel subtraction (out_L = L - mix*R) attenuates the centre tone by
# (1 - mix) while leaving the left-only tone in L untouched, so the reduction
# is directly measurable in the L-channel spectrum.
CENTRE_TONE_HZ = 660.0  # the "singer" — identical in L and R.
SIDE_TONE_HZ = 1500.0  # left-only — survives centre subtraction.
VOCAL_REDUCE_PCT = 60  # mix = 0.30 -> centre tone scaled by 0.70.


def _write_vocal_stereo_wav(path: Path) -> None:
    """Write a 16-bit stereo WAV: centre-panned vocal tone + left-only side tone."""
    n_samples = int(SAMPLE_RATE * DURATION_S)
    amp = 0.3
    two_pi = 2 * math.pi
    frames = bytearray()
    for n in range(n_samples):
        t = n / SAMPLE_RATE
        centre = math.sin(two_pi * CENTRE_TONE_HZ * t) * amp
        side = math.sin(two_pi * SIDE_TONE_HZ * t) * amp
        left = max(-1.0, min(1.0, centre + side))
        right = max(-1.0, min(1.0, centre))
        frames += struct.pack("<h", int(left * 32767))
        frames += struct.pack("<h", int(right * 32767))

    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(bytes(frames))


def _read_wav_left(path: Path) -> "np.ndarray":
    """Read a 16-bit PCM stereo WAV and return the LEFT channel as float64."""
    with wave.open(str(path), "rb") as w:
        n_channels = w.getnchannels()
        sampwidth = w.getsampwidth()
        raw = w.readframes(w.getnframes())
    assert sampwidth == 2, f"expected 16-bit PCM, got sampwidth={sampwidth} for {path}"
    assert n_channels == 2, f"expected stereo, got {n_channels} channels for {path}"
    data = np.frombuffer(raw, dtype="<i2").astype(np.float64) / 32768.0
    return data.reshape(-1, 2)[:, 0]


def _tone_magnitude(signal: "np.ndarray", freq_hz: float) -> float:
    """Return the FFT magnitude in a narrow band around freq_hz."""
    spectrum = np.abs(np.fft.rfft(signal))
    freqs = np.fft.rfftfreq(signal.size, d=1.0 / SAMPLE_RATE)
    band = (freqs >= freq_hz * 0.97) & (freqs <= freq_hz * 1.03)
    band_idx = np.where(band)[0]
    assert band_idx.size > 0, f"no FFT bins around {freq_hz} Hz"
    return float(np.max(spectrum[band_idx]))


def _read_wav_mono(path: Path) -> "np.ndarray":
    """Read a 16-bit PCM WAV and return a mono float64 array in [-1, 1]."""
    with wave.open(str(path), "rb") as w:
        n_channels = w.getnchannels()
        sampwidth = w.getsampwidth()
        n_frames = w.getnframes()
        raw = w.readframes(n_frames)
    assert sampwidth == 2, f"expected 16-bit PCM, got sampwidth={sampwidth} for {path}"
    data = np.frombuffer(raw, dtype="<i2").astype(np.float64) / 32768.0
    if n_channels > 1:
        data = data.reshape(-1, n_channels).mean(axis=1)
    return data


def _dominant_freq(signal: "np.ndarray", search_hz: tuple[float, float]) -> float:
    """Return the frequency (Hz) of the largest magnitude bin within a band."""
    spectrum = np.abs(np.fft.rfft(signal))
    freqs = np.fft.rfftfreq(signal.size, d=1.0 / SAMPLE_RATE)
    band = (freqs >= search_hz[0]) & (freqs <= search_hz[1])
    band_idx = np.where(band)[0]
    assert band_idx.size > 0, f"no FFT bins in band {search_hz}"
    peak_local = np.argmax(spectrum[band_idx])
    return float(freqs[band_idx[peak_local]])


def _cosine_similarity(a: "np.ndarray", b: "np.ndarray") -> float:
    """Cosine similarity of two magnitude spectra (gain-invariant)."""
    sa, sb = np.abs(np.fft.rfft(a)), np.abs(np.fft.rfft(b))
    n = min(sa.size, sb.size)
    sa, sb = sa[:n], sb[:n]
    denom = float(np.linalg.norm(sa) * np.linalg.norm(sb))
    assert denom > 0, "degenerate (all-zero) spectrum"
    return float(np.dot(sa, sb) / denom)


def _render_export(input_wav: Path, out_wav: Path, pitch: int, vocal_reduce: int = 0) -> None:
    """Render the EXPORT pipeline: real ffmpeg with build_filter_chain(pitch, vocal)."""
    chain = build_filter_chain(pitch, vocal_reduce)
    cmd = [
        FFMPEG,
        "-y",
        "-i",
        str(input_wav),
        "-af",
        chain,
        "-c:a",
        "pcm_s16le",
        "-ar",
        str(SAMPLE_RATE),
        str(out_wav),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        pytest.fail(f"ffmpeg export render failed (chain={chain!r}):\n{proc.stderr[-1500:]}")


def _render_preview(input_wav: Path, out_wav: Path, pitch: int, vocal_reduce: int = 0) -> None:
    """Render the PREVIEW pipeline: real mpv with build_mpv_filter_chain(pitch, vocal)."""
    chain = build_mpv_filter_chain(pitch, vocal_reduce)
    cmd = [
        MPV,
        str(input_wav),
        "--no-video",
        "--no-config",
        f"--af={chain}",
        "--oac=pcm_s16le",
        "--of=wav",
        f"--audio-samplerate={SAMPLE_RATE}",
        f"--o={out_wav}",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not out_wav.exists():
        pytest.fail(f"mpv preview render failed (chain={chain!r}):\n{proc.stderr[-1500:]}")


@pytest.mark.parametrize("pitch", [-3, 2, 5])
def test_preview_and_export_apply_the_same_pitch_shift(tmp_path: Path, pitch: int) -> None:
    """Preview (mpv) and export (ffmpeg) must shift pitch identically.

    Renders one synthesized clip through both real pipelines and asserts:
    (1) each output's fundamental moved to f_in * 2**(pitch/12), and
    (2) the two output spectra are near-identical in shape (cosine sim >= 0.97).
    """
    input_wav = tmp_path / "input.wav"
    export_wav = tmp_path / "export.wav"
    preview_wav = tmp_path / "preview.wav"

    _write_sine_wav(input_wav)
    _render_export(input_wav, export_wav, pitch)
    _render_preview(input_wav, preview_wav, pitch)

    export_sig = _read_wav_mono(export_wav)
    preview_sig = _read_wav_mono(preview_wav)

    # Trim to a common interior window (drop the first/last 0.25 s to avoid any
    # encoder warm-up / flush edge artifacts), then to equal length.
    edge = int(0.25 * SAMPLE_RATE)
    export_sig = export_sig[edge:-edge]
    preview_sig = preview_sig[edge:-edge]
    n = min(export_sig.size, preview_sig.size)
    assert n > SAMPLE_RATE, "rendered audio unexpectedly short"
    export_sig = export_sig[:n]
    preview_sig = preview_sig[:n]

    expected_ratio = 2 ** (pitch / 12)
    expected_fundamental = FUNDAMENTAL_HZ * expected_ratio
    # Search a generous band around the expected shifted fundamental.
    band = (expected_fundamental * 0.85, expected_fundamental * 1.15)

    export_peak = _dominant_freq(export_sig, band)
    preview_peak = _dominant_freq(preview_sig, band)

    export_ratio = export_peak / FUNDAMENTAL_HZ
    preview_ratio = preview_peak / FUNDAMENTAL_HZ

    assert math.isclose(export_ratio, expected_ratio, rel_tol=PEAK_RATIO_REL_TOL), (
        f"export fundamental ratio {export_ratio:.4f} != expected "
        f"{expected_ratio:.4f} for pitch={pitch}"
    )
    assert math.isclose(preview_ratio, expected_ratio, rel_tol=PEAK_RATIO_REL_TOL), (
        f"preview fundamental ratio {preview_ratio:.4f} != expected "
        f"{expected_ratio:.4f} for pitch={pitch}"
    )

    # The two pipelines must agree with each other.
    assert math.isclose(export_ratio, preview_ratio, rel_tol=PEAK_RATIO_REL_TOL), (
        f"export and preview disagree on pitch: export={export_ratio:.4f} "
        f"preview={preview_ratio:.4f} (pitch={pitch})"
    )

    similarity = _cosine_similarity(export_sig, preview_sig)
    assert similarity >= MIN_COSINE_SIMILARITY, (
        f"export vs preview spectra diverge: cosine similarity {similarity:.4f} "
        f"< {MIN_COSINE_SIMILARITY} for pitch={pitch}"
    )


def test_preview_and_export_apply_the_same_vocal_reduction(tmp_path: Path) -> None:
    """Preview (mpv lavfi pan) and export (ffmpeg pan) must reduce the centre
    (vocal) tone identically — the headline Phase-2 feature, end-to-end.

    Renders a stereo clip (centre-panned vocal + left-only side tone) through
    BOTH real pipelines with pitch=+2, vocal_reduce=60 and asserts:
    (1) the centre tone is measurably attenuated in BOTH outputs vs a no-reduce
        export baseline (the pan actually fired through mpv's lavfi bridge), and
    (2) preview and export agree: their centre/side attenuation ratios match.

    This is the gate that proves the mpv ``lavfi=[pan=...]`` chain produced by
    ``build_mpv_filter_chain`` does the same centre subtraction ffmpeg bakes in.
    """
    pitch = 2
    input_wav = tmp_path / "vocal_input.wav"
    export_wav = tmp_path / "vocal_export.wav"
    preview_wav = tmp_path / "vocal_preview.wav"
    baseline_wav = tmp_path / "vocal_baseline.wav"  # export with NO reduction.

    _write_vocal_stereo_wav(input_wav)
    _render_export(input_wav, baseline_wav, pitch, vocal_reduce=0)
    _render_export(input_wav, export_wav, pitch, vocal_reduce=VOCAL_REDUCE_PCT)
    _render_preview(input_wav, preview_wav, pitch, vocal_reduce=VOCAL_REDUCE_PCT)

    # Pitch shifts both tones; measure them at their shifted frequencies.
    ratio = 2 ** (pitch / 12)
    centre_shifted = CENTRE_TONE_HZ * ratio
    side_shifted = SIDE_TONE_HZ * ratio

    baseline_left = _read_wav_left(baseline_wav)
    export_left = _read_wav_left(export_wav)
    preview_left = _read_wav_left(preview_wav)

    # Centre/side magnitude ratios isolate the reduction from encoder gain:
    # both pipelines should pull the centre tone down relative to the side tone.
    def centre_over_side(sig: "np.ndarray") -> float:
        return _tone_magnitude(sig, centre_shifted) / _tone_magnitude(sig, side_shifted)

    baseline_ratio = centre_over_side(baseline_left)
    export_ratio = centre_over_side(export_left)
    preview_ratio = centre_over_side(preview_left)

    # (1) Reduction actually happened in BOTH pipelines (centre pulled down).
    assert export_ratio < baseline_ratio * 0.85, (
        f"ffmpeg export did not reduce the centre tone: "
        f"centre/side {export_ratio:.4f} vs baseline {baseline_ratio:.4f}"
    )
    assert preview_ratio < baseline_ratio * 0.85, (
        f"mpv preview lavfi pan did not reduce the centre tone: "
        f"centre/side {preview_ratio:.4f} vs baseline {baseline_ratio:.4f}"
    )

    # (2) Preview and export agree on HOW MUCH they reduced it.
    assert math.isclose(export_ratio, preview_ratio, rel_tol=0.10), (
        f"export and preview disagree on vocal reduction: "
        f"export centre/side={export_ratio:.4f} preview={preview_ratio:.4f}"
    )
