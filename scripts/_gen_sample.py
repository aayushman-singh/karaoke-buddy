"""Generate a deterministic test WAV for the benchmark scripts.

No copyrighted audio, no numpy: a fixed-seed sum of sine partials written with
the stdlib ``wave`` module. The same file is the shared input for both
``bench_latency.py`` (fed to mpv) and ``bench_quality.py`` (fed to ffmpeg),
so latency and quality numbers describe the *same* signal.

The signal is a 4-second stereo tone bed:
    - a fundamental that steps through a short pitched phrase (so a pitch
      shift is actually audible / measurable, not a static drone),
    - a few harmonic partials for spectral content,
    - a light stereo offset so the centre-channel vocal-reduce filter in the
      export chain has something to act on.

Run:
    python scripts/_gen_sample.py [output.wav]

Default output: scripts/sample.wav
"""

import math
import struct
import sys
import wave
from pathlib import Path

SAMPLE_RATE = 44_100
DURATION_S = 4.0
AMPLITUDE = 0.35  # headroom so the pitch shift never clips into the artifact floor

# A short, deterministic pitched phrase (semitone offsets from 220 Hz / A3).
# Stepping the pitch makes a shift audible and gives PESQ/STOI real structure.
_PHRASE_SEMITONES = [0, 2, 4, 5, 7, 5, 4, 2]
_BASE_HZ = 220.0
# Relative amplitudes of the fundamental + harmonics (a mild sawtooth-ish timbre).
_PARTIALS = [(1, 1.0), (2, 0.5), (3, 0.33), (4, 0.25)]


def _freq_at(t: float) -> float:
    """Fundamental frequency at time ``t`` seconds, stepping through the phrase."""
    step = int(t / DURATION_S * len(_PHRASE_SEMITONES)) % len(_PHRASE_SEMITONES)
    semis = _PHRASE_SEMITONES[step]
    return _BASE_HZ * (2 ** (semis / 12))


def _sample(t: float, stereo_offset: float) -> float:
    f = _freq_at(t)
    value = 0.0
    for harmonic, weight in _PARTIALS:
        value += weight * math.sin(2 * math.pi * f * harmonic * (t + stereo_offset))
    # Normalise by the summed partial weights so amplitude is bounded.
    norm = sum(w for _, w in _PARTIALS)
    return AMPLITUDE * value / norm


def generate(output: Path) -> Path:
    n_frames = int(SAMPLE_RATE * DURATION_S)
    output.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(output), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)  # 16-bit PCM
        w.setframerate(SAMPLE_RATE)
        frames = bytearray()
        for i in range(n_frames):
            t = i / SAMPLE_RATE
            left = _sample(t, 0.0)
            # Tiny time offset on the right channel -> a non-trivial stereo image.
            right = _sample(t, 0.00012)
            frames += struct.pack(
                "<hh",
                int(max(-1.0, min(1.0, left)) * 32767),
                int(max(-1.0, min(1.0, right)) * 32767),
            )
        w.writeframes(bytes(frames))
    return output


def main() -> int:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("sample.wav")
    path = generate(out)
    size = path.stat().st_size
    print(f"Wrote {path} ({size} bytes, {DURATION_S}s stereo {SAMPLE_RATE} Hz 16-bit PCM)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
