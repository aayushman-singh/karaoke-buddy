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

log = logging.getLogger(__name__)

_THUMB_W, _THUMB_H = 160, 90
_COLS = 4


class _EntryCard(QFrame):
    clicked = Signal(LibraryEntry)

    def __init__(self, entry: LibraryEntry, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._entry = entry
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedWidth(_THUMB_W + 8)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        thumb_label = QLabel()
        thumb_label.setFixedSize(_THUMB_W, _THUMB_H)
        thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if entry.thumbnail_path and Path(entry.thumbnail_path).exists():
            pix = QPixmap(entry.thumbnail_path).scaled(
                _THUMB_W,
                _THUMB_H,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            thumb_label.setPixmap(pix)
        else:
            thumb_label.setText("\U0001f3b5")
            thumb_label.setStyleSheet("background: #2a2a2a; font-size: 32px;")
        layout.addWidget(thumb_label)

        title_label = QLabel(entry.title)
        title_label.setWordWrap(True)
        title_label.setMaximumWidth(_THUMB_W)
        title_label.setStyleSheet("font-size: 12px;")
        layout.addWidget(title_label)

        hint = QLabel(_pitch_label(entry.last_pitch))
        hint.setStyleSheet("font-size: 10px; color: #888;")
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

        heading = QLabel("Recent videos")
        heading.setStyleSheet("font-size: 14px; font-weight: bold; padding: 8px 0;")
        outer.addWidget(heading)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(scroll)

        self._container = QWidget()
        self._grid = QGridLayout(self._container)
        self._grid.setSpacing(12)
        scroll.setWidget(self._container)

        self.refresh()

    def refresh(self) -> None:
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        entries = self._library.list()
        for i, entry in enumerate(entries):
            row, col = divmod(i, _COLS)
            card = _EntryCard(entry)
            card.clicked.connect(self.entry_selected)
            self._grid.addWidget(card, row, col)

        self._grid.setRowStretch(max(1, (len(entries) // _COLS) + 1), 1)


def _pitch_label(semitones: int) -> str:
    if semitones == 0:
        return "Normal key"
    direction = "Higher" if semitones > 0 else "Lower"
    abs_s = abs(semitones)
    word = "key" if abs_s == 1 else "keys"
    return f"{direction} by {abs_s} {word}"
