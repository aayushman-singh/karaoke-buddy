"""Pure audio filter-chain builder.

``build_mpv_filter_chain`` drives live libmpv playback; ``build_filter_chain``
drives FFmpeg export. Both use the same semitone math so preview and export match.
"""


def _pitch_scale(pitch_semitones: int) -> float:
    return 2 ** (pitch_semitones / 12)


def build_mpv_filter_chain(pitch_semitones: int, vocal_reduce_percent: int = 0) -> str:
    """Return a libmpv ``af set`` filter string for live playback.

    mpv uses its native ``rubberband`` filter (``pitch-scale``), not FFmpeg's
    ``rubberband=pitch=`` lavfi syntax. The ``pan`` centre-channel subtraction
    has no native mpv filter, so it is applied through mpv's libavfilter bridge
    (``lavfi=[pan=...]``).

    Args:
        pitch_semitones: Integer semitone shift in [-12, 12].
        vocal_reduce_percent: Centre-channel subtraction strength in [0, 100].

    Returns:
        When ``vocal_reduce_percent == 0`` the pitch-only string
        ``"rubberband=pitch-scale={scale:.6f}"`` (unchanged, so nothing
        regresses). When reduction is on, the pitch filter followed by a
        lavfi-bridged pan:
        ``"rubberband=pitch-scale={scale:.6f},lavfi=[pan=stereo|c0=c0-{mix:.4f}*c1|c1=c1-{mix:.4f}*c0]"``

    The ``mix = (pct/100)*0.5`` math and the ``pan`` coefficients mirror
    :func:`build_filter_chain` byte-for-byte, so preview == export holds for
    vocal reduction exactly as it does for pitch.
    """
    pitch_scale = _pitch_scale(pitch_semitones)
    pitch = f"rubberband=pitch-scale={pitch_scale:.6f}"
    if vocal_reduce_percent == 0:
        return pitch
    mix = (vocal_reduce_percent / 100) * 0.5
    return f"{pitch},lavfi=[pan=stereo|c0=c0-{mix:.4f}*c1|c1=c1-{mix:.4f}*c0]"


def build_filter_chain(pitch_semitones: int, vocal_reduce_percent: int) -> str:
    """Return an FFmpeg ``-af`` filter string for export.

    Args:
        pitch_semitones: Integer semitone shift in [-12, 12].
        vocal_reduce_percent: Centre-channel subtraction strength in [0, 100].

    Returns:
        A comma-separated filter chain string, e.g.
        ``"rubberband=pitch=1.000000,pan=stereo|c0=c0-0.0000*c1|c1=c1-0.0000*c0"``
    """
    pitch_scale = _pitch_scale(pitch_semitones)
    mix = (vocal_reduce_percent / 100) * 0.5
    return f"rubberband=pitch={pitch_scale:.6f},pan=stereo|c0=c0-{mix:.4f}*c1|c1=c1-{mix:.4f}*c0"
