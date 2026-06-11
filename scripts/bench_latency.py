"""Benchmark: slider-drag -> filter-reconfig latency for live playback.

WHAT THIS MEASURES (and what it deliberately does NOT)
------------------------------------------------------
This measures **command-to-reconfig latency**: the wall-clock time from the
moment the app issues the libmpv ``af set`` command (exactly what
``Player.set_filter`` does in production) to the moment mpv *acknowledges that
its audio filter graph has been rebuilt with the new chain*. Acknowledgement is
observed via the ``af`` property round-trip -- after ``command("af", "set", ...)``
returns, we poll the ``af`` property until mpv reports the new filter list is
installed. That round-trip is the engine confirming "the graph now contains your
filter", which is a strictly tighter and more honest signal than the previous
implementation used.

WHY THE OLD "NEXT PTS TICK" MEASURE WAS WRONG
---------------------------------------------
The earlier version blocked until ``audio-pts`` advanced past its pre-command
value and called that the latency. But ``audio-pts`` advances continuously during
normal playback whether or not the filter graph reconfigured -- so that loop was
really measuring *polling/scheduling jitter until the next audio tick*, not the
cost of the reconfig. It systematically conflated playback cadence with audio
latency and could report a number that has nothing to do with how fast the key
actually changed. We do not do that any more.

COMMAND-TO-RECONFIG IS A LOWER BOUND, NOT THE AUDIBLE LATENCY
------------------------------------------------------------
The number this script prints is a **lower bound on audible latency**. The truly
audible latency -- the delay before a listener *hears* the new key -- additionally
includes: the audio output buffer already queued at the old pitch draining out,
the OS/device buffer, and rubberband's own WSOLA analysis window. None of those
are captured by an in-process property round-trip.

GOLD-STANDARD METHOD (documented, not implemented here)
-------------------------------------------------------
The rigorous, fully-honest measurement is an **acoustic / loopback capture**:
route mpv's output through a virtual audio device (or physical loopback), record
the output stream, and detect the exact sample at which the spectrum shifts to
the new pitch (e.g. track a known partial's frequency, or cross-correlate against
a reference render). The latency is then ``(capture timestamp of spectral
change) - (t0 of the command)``. That captures the entire path through to real
audio. It requires a loopback device and an FFT/pitch-tracking stage and is out
of scope for this in-process micro-benchmark, which measures the best honest
proxy it can: command -> reconfig acknowledged.

HONESTY
-------
Requires the mpv shared library (via python-mpv) AND a working audio output. It
does NOT fabricate a number. If mpv is missing it fails loudly with install
instructions and exits non-zero. The benchmarks doc marks the desktop latency
value "pending hardware run" until this script is run on a machine with mpv + an
audio device, and labels the result "command-to-reconfig latency (lower bound on
audible latency)" -- never "audible latency" outright.

Usage:
    python scripts/bench_latency.py [--trials N] [--pitch SEMITONES] [--sample PATH]
"""

import argparse
import statistics
import sys
import time
from pathlib import Path

# Make the in-repo package importable without an install step.
_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


def _die(msg: str) -> "None":
    """Fail loudly: print a clear diagnostic and exit non-zero. No fallback."""
    print(f"\n[bench_latency] CANNOT RUN: {msg}\n", file=sys.stderr)
    raise SystemExit(2)


def _require_mpv():
    try:
        import mpv  # noqa: PLC0415
    except (ImportError, OSError) as exc:
        _die(
            "the mpv shared library / python-mpv binding is unavailable "
            f"({exc!r}).\n"
            "  Install the mpv runtime (libmpv) and the binding:\n"
            "    - Windows: place mpv-2.dll / libmpv on PATH (or next to python),\n"
            "      download from https://mpv.io / https://sourceforge.net/projects/mpv-player-windows/\n"
            "    - pip install python-mpv\n"
            "  Live pitch latency is a real-time audio measurement; it has no\n"
            "  meaningful value without mpv and an audio output device."
        )
    return mpv


def _ensure_sample(sample: Path) -> Path:
    if sample.exists():
        return sample
    print(f"[bench_latency] sample {sample} missing; generating it...")
    import _gen_sample  # noqa: PLC0415  (sibling script)

    return _gen_sample.generate(sample)


def measure(trials: int, pitch_semitones: int, sample: Path) -> list[float]:
    from karaoke_buddy.core.filter_chain import build_mpv_filter_chain  # noqa: PLC0415

    mpv = _require_mpv()
    chain_shifted = build_mpv_filter_chain(pitch_semitones)
    chain_unity = build_mpv_filter_chain(0)

    player = mpv.MPV(vo="null", audio_display=False, keep_open=True)
    latencies: list[float] = []
    try:
        player.loadfile(str(sample))
        player.pause = False
        # Wait until audio is actually flowing before timing anything: a reconfig
        # of an idle/non-playing graph is not representative of a live key change.
        _wait_for_audio(player)

        for trial in range(trials):
            chain = chain_shifted if trial % 2 == 0 else chain_unity
            t0 = time.perf_counter()
            # Exactly what Player.set_filter issues in production.
            player.command("af", "set", chain)
            # Block until mpv confirms the graph has been rebuilt with this chain
            # (the 'af' property round-trip reflects the new filter list), NOT
            # merely until the next audio tick happens to arrive.
            _wait_for_af_installed(player, chain)
            t1 = time.perf_counter()
            latencies.append((t1 - t0) * 1000.0)  # ms
    finally:
        player.terminate()
    return latencies


def _audio_pts(player) -> float:
    pts = player.audio_pts
    if pts is None:
        _die(
            "mpv exposes no 'audio-pts' property on this build -- cannot confirm "
            "audio is flowing. Latency is meaningless without playing audio."
        )
    return float(pts)


def _wait_for_audio(player, timeout_s: float = 5.0) -> None:
    deadline = time.perf_counter() + timeout_s
    while time.perf_counter() < deadline:
        if _audio_pts(player) > 0.0:
            return
        time.sleep(0.001)
    _die(
        "mpv never produced audio within 5s -- no audio device, or the sample "
        "failed to load. Latency is meaningless without playing audio."
    )


def _af_installed(player, expected_chain: str) -> bool:
    """Has mpv's audio filter graph been rebuilt to include ``expected_chain``?

    mpv exposes the live audio-filter list via the ``af`` property. After an
    ``af set`` the property round-trips through the engine and reflects the new
    graph once the reconfig has actually taken effect. We match on the rubberband
    pitch-scale value, which uniquely identifies the chain we just installed.
    """
    af = player.af  # list[dict] of installed audio filters, or None
    if not af:
        return False

    # The discriminating token in build_mpv_filter_chain output, e.g.
    # "rubberband=pitch-scale=1.122462" -> match "pitch-scale=1.122462".
    needle = expected_chain.split(",", 1)[0]
    token = needle.split("=", 1)[1] if "=" in needle else needle

    def _entry_text(entry) -> str:
        if isinstance(entry, dict):
            return repr(entry)
        return str(entry)

    return any(token in _entry_text(entry) for entry in af)


def _wait_for_af_installed(player, expected_chain: str, timeout_s: float = 5.0) -> None:
    deadline = time.perf_counter() + timeout_s
    while time.perf_counter() < deadline:
        if _af_installed(player, expected_chain):
            return
        time.sleep(0.0002)
    _die(
        "mpv did not report the new audio filter graph (chain "
        f"{expected_chain!r}) installed within 5s after 'af set' -- the filter "
        "reconfig stalled or the 'af' property is unreadable on this build."
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--trials", type=int, default=40)
    ap.add_argument("--pitch", type=int, default=2, help="semitone shift to toggle to")
    ap.add_argument(
        "--sample",
        type=Path,
        default=Path(__file__).with_name("sample.wav"),
    )
    args = ap.parse_args()

    sample = _ensure_sample(args.sample)
    lat = measure(args.trials, args.pitch, sample)

    lat_sorted = sorted(lat)
    p95 = lat_sorted[min(len(lat_sorted) - 1, int(round(0.95 * (len(lat_sorted) - 1))))]
    print("\n=== Slider-drag -> filter-reconfig latency ===")
    print("metric      : command-to-reconfig (lower bound on audible latency)")
    print(f"sample      : {sample}")
    print(f"pitch toggle: 0 <-> {args.pitch:+d} semitones")
    print(f"trials      : {len(lat)}")
    print(f"median      : {statistics.median(lat):.2f} ms")
    print(f"p95         : {p95:.2f} ms")
    print(f"min / max   : {min(lat):.2f} / {max(lat):.2f} ms")
    print(
        "\nNote: this is the time from the 'af set' command to mpv acknowledging\n"
        "the rebuilt filter graph. It is a LOWER BOUND on audible latency; the\n"
        "audible figure additionally includes output-buffer drain, device buffer\n"
        "and rubberband's WSOLA window. The gold-standard measure is a loopback\n"
        "capture detecting the spectral change at the actual audio output."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
