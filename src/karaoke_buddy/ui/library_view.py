"""LibraryView — thumbnail grid of recent/saved entries."""

import logging
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from karaoke_buddy.core.library import Library, LibraryEntry
from karaoke_buddy.ui import theme

log = logging.getLogger(__name__)

_THUMB_W, _THUMB_H = 168, 95
_COLS = 4


class _EntryCard(QFrame):
    clicked = Signal(LibraryEntry)

    def __init__(self, entry: LibraryEntry, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._entry = entry
        self.setObjectName("LibCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedWidth(_THUMB_W + 6)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        thumb_label = QLabel()
        thumb_label.setFixedSize(_THUMB_W, _THUMB_H)
        thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if entry.thumbnail_path and Path(entry.thumbnail_path).exists():
            pix = QPixmap(entry.thumbnail_path).scaled(
                _THUMB_W,
                _THUMB_H,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            thumb_label.setObjectName("LibThumbReal")
            thumb_label.setPixmap(pix)
            thumb_label.setScaledContents(False)
        else:
            # missing thumbnail → music placeholder (replaces the 🎵 emoji)
            thumb_label.setObjectName("LibThumb")
            thumb_label.setPixmap(theme.icon("music", theme.INK_3, 30, stroke=2.0).pixmap(30, 30))
        layout.addWidget(thumb_label)

        title_label = QLabel(entry.title)
        title_label.setObjectName("LibTitle")
        title_label.setWordWrap(True)
        title_label.setMaximumWidth(_THUMB_W)
        layout.addWidget(title_label)

        hint = QLabel(_pitch_label(entry.last_pitch))
        hint.setObjectName("LibPitch")
        layout.addWidget(hint)

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        self.clicked.emit(self._entry)


class LibraryView(QWidget):
    entry_selected = Signal(LibraryEntry)

    def __init__(self, library: Library, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._library = library

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(10)

        heading = QLabel("Recent videos")
        heading.setObjectName("LibHeading")
        outer.addWidget(heading)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(scroll)

        self._container = QWidget()
        self._grid = QGridLayout(self._container)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setSpacing(16)
        scroll.setWidget(self._container)

        self._empty: Optional[QLabel] = None

        self.refresh()

    def refresh(self) -> None:
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        entries = self._library.list()

        if not entries:
            empty = QLabel("Songs you open will show up here.")
            empty.setObjectName("LibEmpty")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._grid.addWidget(empty, 0, 0, 1, _COLS)
            self._grid.setRowStretch(1, 1)
            return

        for i, entry in enumerate(entries):
            row, col = divmod(i, _COLS)
            card = _EntryCard(entry)
            card.clicked.connect(self.entry_selected)
            self._grid.addWidget(card, row, col, Qt.AlignmentFlag.AlignTop)

        self._grid.setRowStretch(max(1, (len(entries) // _COLS) + 1), 1)


def _pitch_label(semitones: int) -> str:
    if semitones == 0:
        return "Normal key"
    direction = "Higher" if semitones > 0 else "Lower"
    abs_s = abs(semitones)
    word = "key" if abs_s == 1 else "keys"
    return f"{direction} by {abs_s} {word}"
