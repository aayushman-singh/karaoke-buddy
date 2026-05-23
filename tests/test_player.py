"""Tests for the libmpv player wrapper's failure policy."""

import pytest

from karaoke_buddy.core.player import Player


class _BrokenMpv:
    def command(self, *_args):
        raise RuntimeError("mpv rejected filter")


def test_set_filter_raises_when_mpv_rejects_filter(caplog):
    player = Player.__new__(Player)
    player._mpv = _BrokenMpv()

    with pytest.raises(RuntimeError, match="Could not apply playback filter"):
        player.set_filter("bad-filter")

    assert "mpv af set failed" in caplog.text
    assert "bad-filter" in caplog.text
