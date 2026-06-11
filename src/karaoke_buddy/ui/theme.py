"""Visual theme for KaraokeBuddy — the "bold & joyful, painfully simple" restyle.

One coral accent on a warm-paper light surface, a warm humanist type pairing
(Fredoka for display, Nunito for UI), and a clean line-icon set that replaces
the old emoji. Everything here is presentation only; no behaviour, signal,
range, or copy from the cited source is changed.

Surface A is Qt Widgets, so the skin is delivered as:
  * a bundled-font loader (QFontDatabase),
  * a single application-wide QSS stylesheet (`STYLESHEET`),
  * `icon()` — renders the line-icon set to a recolourable QIcon via QtSvg.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QFont, QFontDatabase, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

_RES = Path(__file__).resolve().parent.parent / "resources"
_FONTS = _RES / "fonts"

# ---------------------------------------------------------------- palette ----
PAPER = "#FBF5EC"
PAPER_2 = "#F4EADB"
SURFACE = "#FFFFFF"
INSET = "#F1E7D7"
INK = "#241A12"
INK_2 = "#6E6053"
INK_3 = "#A2937F"
LINE = "#E7DAC6"
LINE_2 = "#D9C9B0"

CORAL = "#E8513A"
CORAL_DEEP = "#C73A24"
CORAL_SOFT = "#FCE5DD"
GOLD = "#F2A23C"
GOLD_SOFT = "#FCEDD5"
GREEN = "#1F9D6B"
GREEN_SOFT = "#DEF1E7"

CHIP_BG = "#241A12"
CHIP_AMBER = "#FFB74D"

# Font families (resolved at load time; default to the requested names).
DISPLAY_FAMILY = "Fredoka"
UI_FAMILY = "Nunito"

# ------------------------------------------------------------- line icons ----
# Ported from the design's kb-icons set. Each entry lists stroke paths ("s"),
# filled paths ("f"), circles ("c" as (cx, cy, r)), and extra stroke paths.
_ICON_PATHS: dict[str, dict] = {
    "back": {"s": ["M19 12H5", "M12 19l-7-7 7-7"]},
    "chevronDown": {"s": ["M6 9l6 6 6-6"]},
    "maximize": {
        "s": [
            "M8 3H5a2 2 0 0 0-2 2v3",
            "M21 8V5a2 2 0 0 0-2-2h-3",
            "M3 16v3a2 2 0 0 0 2 2h3",
            "M16 21h3a2 2 0 0 0 2-2v-3",
        ]
    },
    "folder": {
        "s": [
            "M4 20h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.93a2 2 0 0 1-1.66-.9l-.82-1.2A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13c0 1.1.9 2 2 2Z"
        ]
    },
    "link": {"s": ["M9 17H7A5 5 0 0 1 7 7h2", "M15 7h2a5 5 0 1 1 0 10h-2", "M8 12h8"]},
    "play": {"f": ["M7 4.5v15l12-7.5z"]},
    "pause": {"f": ["M7 4h3.2v16H7z", "M13.8 4H17v16h-3.2z"]},
    "volume": {"s": ["M11 5 6 9H2v6h4l5 4z", "M15.5 8.5a5 5 0 0 1 0 7", "M19 5a9 9 0 0 1 0 14"]},
    "music": {"s": ["M9 18V5l11-2v11"], "c": [(6, 18, 3), (17, 16, 3)]},
    "arrowUp": {"s": ["M12 19V5", "M5 12l7-7 7 7"]},
    "arrowDown": {"s": ["M12 5v14", "M19 12l-7 7-7-7"]},
    "save": {
        "s": [
            "M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z",
            "M17 21v-8H7v8",
            "M7 3v5h8",
        ]
    },
    "download": {"s": ["M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4", "M7 10l5 5 5-5", "M12 15V3"]},
    "film": {
        "s": [
            "M19.5 3h-15A1.5 1.5 0 0 0 3 4.5v15A1.5 1.5 0 0 0 4.5 21h15a1.5 1.5 0 0 0 1.5-1.5v-15A1.5 1.5 0 0 0 19.5 3z",
            "M7 3v18",
            "M17 3v18",
            "M3 8h4",
            "M3 16h4",
            "M17 8h4",
            "M17 16h4",
        ]
    },
    "headphones": {
        "s": [
            "M3 14a9 9 0 0 1 18 0",
            "M21 14v3a2 2 0 0 1-2 2h-1a1 1 0 0 1-1-1v-4a1 1 0 0 1 1-1h3z",
            "M3 14v3a2 2 0 0 1 2 2h1a1 1 0 0 0 1-1v-4a1 1 0 0 0-1-1H3z",
        ]
    },
    "alert": {
        "s": [
            "M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h16.9a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z",
            "M12 9v4",
            "M12 17h.01",
        ]
    },
    "check": {"s": ["M20 6 9 17l-5-5"]},
    "copy": {
        "s": [
            "M9 8h9a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H9a2 2 0 0 1-2-2v-9a2 2 0 0 1 2-2z",
            "M5 15a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2",
        ]
    },
    "mic": {
        "s": [
            "M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z",
            "M19 10v2a7 7 0 0 1-14 0v-2",
            "M12 19v3",
        ]
    },
    "arrowRight": {"s": ["M5 12h14", "M13 5l7 7-7 7"]},
    "sparkle": {"s": ["M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z"]},
    "info": {"s": ["M12 16v-4", "M12 8h.01"], "c": [(12, 12, 9.2)]},
}


def _svg_markup(name: str, color: str, stroke: float) -> str:
    spec = _ICON_PATHS[name]
    parts: list[str] = []
    common = (
        f'stroke="{color}" stroke-width="{stroke}" fill="none" '
        'stroke-linecap="round" stroke-linejoin="round"'
    )
    for d in spec.get("s", []):
        parts.append(f'<path d="{d}" {common}/>')
    for d in spec.get("extra", []):
        parts.append(f'<path d="{d}" {common}/>')
    for cx, cy, r in spec.get("c", []):
        parts.append(
            f'<circle cx="{cx}" cy="{cy}" r="{r}" stroke="{color}" '
            f'stroke-width="{stroke}" fill="none"/>'
        )
    for d in spec.get("f", []):
        parts.append(f'<path d="{d}" fill="{color}"/>')
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
        f'fill="none">{"".join(parts)}</svg>'
    )


@lru_cache(maxsize=256)
def icon(name: str, color: str = INK, size: int = 24, stroke: float = 2.1) -> QIcon:
    """A recolourable line icon from the bundled set, rendered crisp via QtSvg."""
    renderer = QSvgRenderer(QByteArray(_svg_markup(name, color, stroke).encode("utf-8")))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter, QRectF(0, 0, size, size))
    painter.end()
    return QIcon(pixmap)


# ----------------------------------------------------------------- fonts -----
def load_fonts() -> None:
    """Register the bundled Fredoka + Nunito families with the app."""
    global DISPLAY_FAMILY, UI_FAMILY
    fredoka = _FONTS / "Fredoka.ttf"
    nunito = _FONTS / "Nunito.ttf"
    if fredoka.is_file():
        fid = QFontDatabase.addApplicationFont(str(fredoka))
        fams = QFontDatabase.applicationFontFamilies(fid)
        if fams:
            DISPLAY_FAMILY = fams[0]
    if nunito.is_file():
        nid = QFontDatabase.addApplicationFont(str(nunito))
        fams = QFontDatabase.applicationFontFamilies(nid)
        if fams:
            UI_FAMILY = fams[0]


def display_font(size: int, weight: QFont.Weight = QFont.Weight.DemiBold) -> QFont:
    f = QFont(DISPLAY_FAMILY, size)
    f.setWeight(weight)
    return f


def ui_font(size: int, weight: QFont.Weight = QFont.Weight.Bold) -> QFont:
    f = QFont(UI_FAMILY, size)
    f.setWeight(weight)
    return f


# ------------------------------------------------------------ stylesheet -----
# Application-wide QSS. Object names below are set by the view modules.
STYLESHEET = f"""
* {{ font-family: "{UI_FAMILY}", "Segoe UI", sans-serif; }}

QMainWindow, QWidget {{ background: {PAPER}; color: {INK}; }}
QStackedWidget > QWidget {{ background: {PAPER}; }}

QLabel {{ color: {INK}; font-size: 14px; background: transparent; }}

/* ---- sliders need a min-height so the round knob isn't clipped ---- */
QSlider {{ min-height: 26px; }}

/* ---- generic buttons ---- */
QPushButton {{
    color: #fff; background: {CORAL}; border: none; border-radius: 12px;
    padding: 11px 20px; font-size: 15px; font-weight: 800;
}}
QPushButton:hover {{ background: {CORAL_DEEP}; }}
QPushButton:disabled {{ background: {LINE_2}; color: #fff; }}

QPushButton#GhostButton {{
    background: {SURFACE}; color: {INK}; border: 2px solid {LINE_2};
}}
QPushButton#GhostButton:hover {{ border-color: {CORAL}; background: {SURFACE}; }}

/* ---- inputs ---- */
QLineEdit {{
    border: 2px solid {LINE_2}; border-radius: 12px; padding: 12px 14px;
    font-size: 16px; font-weight: 700; color: {INK}; background: {SURFACE};
    selection-background-color: {CORAL}; selection-color: #fff;
}}
QLineEdit:focus {{ border-color: {CORAL}; }}

QComboBox {{
    border: 2px solid {LINE_2}; border-radius: 10px; padding: 7px 12px;
    font-size: 14px; font-weight: 800; color: {INK}; background: {SURFACE};
    min-width: 96px;
}}
QComboBox:hover {{ border-color: {CORAL}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{
    border: 1px solid {LINE}; background: {SURFACE}; color: {INK};
    selection-background-color: {CORAL_SOFT}; selection-color: {INK}; outline: none;
}}

/* ---- sliders (coral fill + white knob) ---- */
QSlider::groove:horizontal {{ height: 8px; background: {INSET}; border-radius: 4px; }}
QSlider::sub-page:horizontal {{ background: {CORAL}; border-radius: 4px; }}
QSlider::add-page:horizontal {{ background: {INSET}; border-radius: 4px; }}
QSlider::handle:horizontal {{
    width: 22px; height: 22px; margin: -8px 0; border-radius: 11px;
    background: #fff; border: 3px solid {CORAL};
}}
QSlider::handle:horizontal:hover {{ border-color: {CORAL_DEEP}; }}

/* ---- scroll area ---- */
QScrollArea {{ border: none; background: {PAPER}; }}
QScrollBar:vertical {{ background: transparent; width: 12px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {LINE_2}; border-radius: 5px; min-height: 28px; }}
QScrollBar::handle:vertical:hover {{ background: {INK_3}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}

/* ---- dialogs ---- */
QDialog {{ background: {SURFACE}; }}
QProgressDialog {{ background: {SURFACE}; }}
QProgressBar {{
    border: none; background: {INSET}; border-radius: 6px; height: 12px; text-align: center;
    color: {INK_2}; font-weight: 800; font-size: 11px;
}}
QProgressBar::chunk {{ background: {CORAL}; border-radius: 6px; }}

QMessageBox {{ background: {SURFACE}; }}
QMessageBox QLabel {{ color: {INK}; font-size: 14px; }}

/* ---- home: brand mark ---- */
QLabel#BrandMark {{ background: {CORAL}; border-radius: 18px; }}
QLabel#BrandTag {{ background: transparent; }}

/* ---- home: big action buttons ---- */
QFrame#BigPrimary {{ background: {CORAL}; border: 3px solid {CORAL}; border-radius: 14px; }}
QFrame#BigPrimary:hover {{ background: {CORAL_DEEP}; border-color: {CORAL_DEEP}; }}
QFrame#BigPrimary:focus {{ border-color: {INK}; }}
QFrame#BigGhost {{ background: {SURFACE}; border: 3px solid {LINE_2}; border-radius: 14px; }}
QFrame#BigGhost:hover {{ border-color: {CORAL}; }}
QFrame#BigGhost:focus {{ border-color: {CORAL}; }}
QFrame#BigPrimary QLabel {{ background: transparent; color: #fff; }}
QFrame#BigPrimary QLabel#BigIconChip {{ background: rgba(255,255,255,0.20); border-radius: 12px; }}
QFrame#BigGhost QLabel#BigIconChip {{ background: {GOLD_SOFT}; border-radius: 12px; }}
QLabel#BigTitle {{ font-size: 18px; font-weight: 800; }}
QFrame#BigGhost QLabel#BigTitle {{ color: {INK}; }}
QLabel#BigSubtitle {{ font-size: 13px; font-weight: 700; }}
QFrame#BigGhost QLabel#BigSubtitle {{ color: {INK_2}; }}
QFrame#BigPrimary QLabel#BigSubtitle {{ color: rgba(255,255,255,0.85); }}

/* ---- home: clipboard hint pill ---- */
QLabel#ClipHint {{
    background: {GOLD_SOFT}; color: #9a6a16; border: 1px solid #efd8a8;
    border-radius: 999px; padding: 10px 18px; font-size: 14px; font-weight: 800;
}}

/* ---- library cards ---- */
QFrame#LibCard {{ background: transparent; border: none; }}
QLabel#LibThumb {{ background: {INSET}; border-radius: 12px; color: {INK_3}; }}
QLabel#LibThumbReal {{ background: #3A2A3F; border-radius: 12px; }}
QLabel#LibTitle {{ font-size: 13px; font-weight: 800; color: {INK}; }}
QLabel#LibPitch {{ font-size: 12px; font-weight: 800; color: {CORAL}; }}
QLabel#LibHeading {{
    font-size: 13px; font-weight: 900; color: {INK_2};
    letter-spacing: 1px; padding: 4px 0;
}}
QLabel#LibEmpty {{
    border: 2px dashed {LINE_2}; border-radius: 14px; padding: 22px;
    color: {INK_3}; font-size: 14px; font-weight: 800;
}}

/* ---- playing: header ---- */
QWidget#PlayHeader {{ background: {SURFACE}; border-bottom: 1px solid {LINE}; }}
QPushButton#HeaderButton {{
    background: transparent; color: {INK}; border: none; border-radius: 10px;
    padding: 9px 14px; font-size: 14px; font-weight: 800;
}}
QPushButton#HeaderButton:hover {{ background: {PAPER_2}; }}

/* ---- playing: controls panel ---- */
QWidget#ControlsPanel {{ background: {SURFACE}; border-top: 1px solid {LINE}; }}
QLabel#TimeLabel {{ color: {INK_2}; font-size: 13px; font-weight: 800; }}
QLabel#SpeedLabel {{ color: {INK_2}; font-size: 13px; font-weight: 800; }}
QLabel#SectionLabel {{ color: {INK}; font-size: 14px; font-weight: 900; }}
QLabel#EndCap {{ color: {INK_2}; font-size: 13px; font-weight: 800; }}
QLabel#PitchReadout {{ color: {CORAL}; }}

QPushButton#PlayCircle {{
    background: {CORAL}; border: none; border-radius: 26px;
}}
QPushButton#PlayCircle:hover {{ background: {CORAL_DEEP}; }}

QPushButton#SaveButton {{
    background: {CORAL}; color: #fff; border: none; border-radius: 14px;
    font-size: 16px; font-weight: 900;
}}
QPushButton#SaveButton:hover {{ background: {CORAL_DEEP}; }}
"""


def apply(app) -> None:
    """Load fonts and install the application stylesheet + base font."""
    load_fonts()
    base = QFont(UI_FAMILY, 10)
    base.setWeight(QFont.Weight.DemiBold)
    app.setFont(base)
    # rebuild the stylesheet with the actually-resolved family name
    app.setStyleSheet(STYLESHEET.replace('"Nunito"', f'"{UI_FAMILY}"'))
