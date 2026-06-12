"""Regression contracts for the coral restyle."""

from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _relative_luminance(hex_color: str) -> float:
    color = hex_color.removeprefix("#")
    channels = []
    for start in (0, 2, 4):
        raw = int(color[start : start + 2], 16) / 255
        channels.append(raw / 12.92 if raw <= 0.04045 else ((raw + 0.055) / 1.055) ** 2.4)
    red, green, blue = channels
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def _contrast_ratio(foreground: str, background: str) -> float:
    fore = _relative_luminance(foreground)
    back = _relative_luminance(background)
    light, dark = max(fore, back), min(fore, back)
    return (light + 0.05) / (dark + 0.05)


def _assert_aa_normal_text(name: str, foreground: str, background: str) -> None:
    ratio = _contrast_ratio(foreground, background)
    assert ratio >= 4.5, f"{name} contrast is {ratio:.2f}:1"


def _web_tokens() -> dict[str, str]:
    styles = (REPO_ROOT / "web" / "styles.css").read_text(encoding="utf-8")
    return dict(re.findall(r"--([a-z0-9-]+):\s*(#[0-9A-Fa-f]{6});", styles))


def _theme_tokens() -> dict[str, str]:
    theme_source = (REPO_ROOT / "src" / "karaoke_buddy" / "ui" / "theme.py").read_text(
        encoding="utf-8"
    )
    return dict(re.findall(r'^([A-Z_0-9]+)\s*=\s*"(#[0-9A-Fa-f]{6})"', theme_source, re.M))


def test_qt_restyle_tokens_keep_normal_text_contrast() -> None:
    """Normal-size restyle text must clear WCAG AA, not only AA-large."""
    tokens = _theme_tokens()
    pairs = [
        ("white text on coral action surfaces", "#FFFFFF", tokens["CORAL"]),
        ("white text on coral hover surfaces", "#FFFFFF", tokens["CORAL_DEEP"]),
        ("error text on coral-soft surfaces", tokens["CORAL_DEEP"], tokens["CORAL_SOFT"]),
        ("quiet text on paper", tokens["INK_3"], tokens["PAPER"]),
        ("quiet text on white", tokens["INK_3"], tokens["SURFACE"]),
        ("gold notice text on gold-soft", tokens["INK_2"], tokens["GOLD_SOFT"]),
    ]
    for name, foreground, background in pairs:
        _assert_aa_normal_text(name, foreground, background)


def test_web_restyle_tokens_keep_normal_text_contrast() -> None:
    tokens = _web_tokens()
    pairs = [
        ("white text on coral action surfaces", "#FFFFFF", tokens["coral"]),
        ("white text on coral hover surfaces", "#FFFFFF", tokens["coral-deep"]),
        ("error text on coral-soft surfaces", tokens["coral-deep"], tokens["coral-soft"]),
        ("quiet text on paper", tokens["ink-3"], tokens["paper"]),
        ("quiet text on white", tokens["ink-3"], tokens["surface"]),
        ("gold notice text on gold-soft", tokens["ink-2"], tokens["gold-soft"]),
    ]
    for name, foreground, background in pairs:
        _assert_aa_normal_text(name, foreground, background)


def test_restyle_does_not_keep_known_low_contrast_gold_text() -> None:
    low_contrast_gold = "#9a6a16"
    paths = [
        REPO_ROOT / "src" / "karaoke_buddy" / "ui" / "theme.py",
        REPO_ROOT / "web" / "index.html",
        REPO_ROOT / "web" / "styles.css",
    ]
    offenders = [
        str(path.relative_to(REPO_ROOT))
        for path in paths
        if low_contrast_gold in path.read_text(encoding="utf-8").lower()
    ]
    assert offenders == []


def test_web_file_rejection_keeps_current_source_instead_of_restoring_demo() -> None:
    app = (REPO_ROOT / "web" / "app.js").read_text(encoding="utf-8")

    assert "function restoreDemo" not in app
    assert "showing the demo song instead" not in app
    assert "function rejectFile(message)" in app
    assert "No change made." in app
