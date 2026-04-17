"""Tests for the pure audio filter-chain builder."""

import math
import re

import pytest
from hypothesis import given
from hypothesis import strategies as st

from karaoke_buddy.core.filter_chain import build_filter_chain


def test_zero_pitch_zero_vocal_has_unity_pitch():
    chain = build_filter_chain(0, 0)
    assert "rubberband=pitch=1.000000" in chain


def test_zero_pitch_zero_vocal_has_zero_mix():
    chain = build_filter_chain(0, 0)
    assert "c0=c0-0.0000*c1" in chain
    assert "c1=c1-0.0000*c0" in chain


def test_octave_up_doubles_pitch():
    chain = build_filter_chain(12, 0)
    assert "rubberband=pitch=2.000000" in chain


def test_octave_down_halves_pitch():
    chain = build_filter_chain(-12, 0)
    assert "rubberband=pitch=0.500000" in chain


def test_full_vocal_reduce_sets_mix_to_0_5():
    chain = build_filter_chain(0, 100)
    assert "c0=c0-0.5000*c1" in chain
    assert "c1=c1-0.5000*c0" in chain


def test_half_vocal_reduce():
    chain = build_filter_chain(0, 50)
    assert "c0=c0-0.2500*c1" in chain


@pytest.mark.parametrize("semitones", range(-12, 13))
def test_all_semitones_produce_valid_rubberband_string(semitones):
    chain = build_filter_chain(semitones, 0)
    assert chain.startswith("rubberband=pitch=")
    assert "pan=stereo" in chain


@pytest.mark.parametrize("pct", range(0, 101, 10))
def test_all_vocal_reduce_percentages_produce_valid_pan_string(pct):
    chain = build_filter_chain(0, pct)
    assert "pan=stereo|c0=c0-" in chain


def test_pitch_scale_formula_is_correct_for_3_semitones():
    expected = 2 ** (3 / 12)
    chain = build_filter_chain(3, 0)
    match = re.search(r"rubberband=pitch=(\d+\.\d+)", chain)
    assert match is not None
    actual = float(match.group(1))
    assert math.isclose(actual, expected, rel_tol=1e-5)


# ---------------------------------------------------------------------------
# Hypothesis property tests (spec §9.1)
# ---------------------------------------------------------------------------


@given(
    semitones=st.integers(min_value=-12, max_value=12),
    vocal_reduce=st.integers(min_value=0, max_value=100),
)
def test_property_output_is_valid_af_string(semitones, vocal_reduce):
    """For any valid inputs the output is a well-formed af= filter string."""
    chain = build_filter_chain(semitones, vocal_reduce)
    assert chain.startswith("rubberband=pitch=")
    assert "pan=stereo|c0=c0-" in chain
    assert "c1=c1-" in chain


@given(semitones=st.integers(min_value=-12, max_value=12))
def test_property_pitch_scale_equals_two_to_the_n_over_twelve(semitones):
    """Pitch scale must equal 2^(n/12) for every semitone value."""
    expected = 2 ** (semitones / 12)
    chain = build_filter_chain(semitones, 0)
    m = re.search(r"rubberband=pitch=(\d+\.\d+)", chain)
    assert m is not None, f"No rubberband pitch found in: {chain}"
    actual = float(m.group(1))
    assert math.isclose(actual, expected, rel_tol=1e-5), (
        f"semitones={semitones}: expected {expected:.6f}, got {actual:.6f}"
    )


@given(vocal_reduce=st.integers(min_value=0, max_value=100))
def test_property_pan_mix_equals_vocal_reduce_over_200(vocal_reduce):
    """Pan mix coefficient must equal (vocal_reduce / 100) * 0.5."""
    expected_mix = (vocal_reduce / 100) * 0.5
    chain = build_filter_chain(0, vocal_reduce)
    m = re.search(r"c0=c0-([\d.]+)\*c1", chain)
    assert m is not None, f"No pan mix found in: {chain}"
    actual = float(m.group(1))
    assert math.isclose(actual, expected_mix, abs_tol=1e-4), (
        f"vocal_reduce={vocal_reduce}: expected {expected_mix:.4f}, got {actual:.4f}"
    )


@given(
    semitones=st.integers(min_value=-12, max_value=12),
    vocal_reduce=st.integers(min_value=0, max_value=100),
)
def test_property_filter_chain_is_pure_function(semitones, vocal_reduce):
    """Same inputs always produce identical output (no side effects)."""
    assert build_filter_chain(semitones, vocal_reduce) == build_filter_chain(
        semitones, vocal_reduce
    )
