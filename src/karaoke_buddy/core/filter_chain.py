"""Pure audio filter-chain builder.

Both the live Player and the Exporter call this function, guaranteeing that
the live preview and the saved file sound identical.
"""


def build_filter_chain(pitch_semitones: int, vocal_reduce_percent: int) -> str:
    """Return an FFmpeg/libmpv ``af`` filter string.

    Args:
        pitch_semitones: Integer semitone shift in [-12, 12].
        vocal_reduce_percent: Centre-channel subtraction strength in [0, 100].

    Returns:
        A comma-separated filter chain string, e.g.
        ``"rubberband=pitch=1.000000,pan=stereo|c0=c0-0.0000*c1|c1=c1-0.0000*c0"``
    """
    pitch_scale = 2 ** (pitch_semitones / 12)
    mix = (vocal_reduce_percent / 100) * 0.5
    return (
        f"rubberband=pitch={pitch_scale:.6f},"
        f"pan=stereo|c0=c0-{mix:.4f}*c1|c1=c1-{mix:.4f}*c0"
    )
