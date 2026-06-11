"""Error dialog with a stable error code, friendly explanation, and one-click
copy-details payload so end users can paste a useful report into chat or email.

The dialog is intentionally noisy on purpose — old-user audience needs an
identifier they can read aloud, plus a clear "what to try next" line, plus a
log path so support can find the original traceback.
"""

from __future__ import annotations

import logging
import platform
import subprocess
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from karaoke_buddy.core.errors import KBError
from karaoke_buddy.ui import theme

log = logging.getLogger(__name__)

_ERROR_QSS = f"""
QDialog {{ background: {theme.SURFACE}; }}
QFrame#ErrBand {{ background: {theme.CORAL}; }}
QLabel#ErrTitle {{ color: #fff; }}
QFrame#ErrBand QLabel {{ background: transparent; }}
QLabel#ErrCodeLbl {{ color: {theme.INK_2}; font-size: 13px; font-weight: 700; }}
QLabel#CodeBadge {{
    background: {theme.CHIP_BG}; color: {theme.CHIP_AMBER};
    font-family: Consolas, "Courier New", monospace; font-weight: 800; font-size: 13px;
    padding: 5px 12px; border-radius: 8px;
}}
QLabel#ErrMsg {{ color: {theme.INK}; font-size: 15px; font-weight: 600; }}
QLabel#ErrHint {{ color: {theme.GREEN}; font-size: 14px; font-weight: 800; }}
QLabel#ErrLogLbl {{ color: {theme.INK_3}; font-size: 12px; font-weight: 800; }}
QLabel#ErrLogPath {{
    color: {theme.INK_3}; font-family: Consolas, "Courier New", monospace; font-size: 11px;
}}
"""


def _read_log_tail(log_path: Path, max_lines: int = 80) -> str:
    if not log_path.is_file():
        return ""
    try:
        with log_path.open("r", encoding="utf-8", errors="replace") as fh:
            lines = fh.readlines()
    except OSError:
        return ""
    return "".join(lines[-max_lines:])


def _open_in_explorer(path: Path) -> None:
    if not path.exists():
        return
    try:
        if platform.system() == "Windows":
            subprocess.Popen(["explorer", "/select,", str(path)])
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", "-R", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path.parent)])
    except OSError:
        log.exception("Failed to open file location: %s", path)


class ErrorDialog(QDialog):
    def __init__(
        self,
        error: KBError,
        log_path: Optional[Path] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._error = error
        self._log_path = log_path

        self.setWindowTitle("KaraokeBuddy — something went wrong")
        self.setMinimumWidth(480)
        self.setStyleSheet(_ERROR_QSS)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ---- coral band with title ----
        band = QFrame()
        band.setObjectName("ErrBand")
        band_row = QHBoxLayout(band)
        band_row.setContentsMargins(24, 20, 24, 20)
        band_row.setSpacing(14)
        band_ic = QLabel()
        band_ic.setPixmap(theme.icon("alert", "#FFFFFF", 26).pixmap(26, 26))
        band_row.addWidget(band_ic, alignment=Qt.AlignmentFlag.AlignTop)
        title = QLabel(error.title)
        title.setObjectName("ErrTitle")
        title.setFont(theme.display_font(19))
        title.setWordWrap(True)
        band_row.addWidget(title, stretch=1)
        root.addWidget(band)

        # ---- body ----
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(24, 22, 24, 8)
        body_layout.setSpacing(14)

        code_row = QHBoxLayout()
        code_row.setSpacing(10)
        code_label = QLabel("Error code:")
        code_label.setObjectName("ErrCodeLbl")
        code_row.addWidget(code_label)
        code_badge = QLabel(error.code)
        code_badge.setObjectName("CodeBadge")
        code_badge.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        code_row.addWidget(code_badge)
        code_row.addStretch()
        body_layout.addLayout(code_row)

        message = QLabel(error.user_message)
        message.setObjectName("ErrMsg")
        message.setWordWrap(True)
        body_layout.addWidget(message)

        hint_row = QHBoxLayout()
        hint_row.setSpacing(8)
        hint_ic = QLabel()
        hint_ic.setPixmap(theme.icon("arrowRight", theme.GREEN, 18).pixmap(18, 18))
        hint_row.addWidget(hint_ic, alignment=Qt.AlignmentFlag.AlignTop)
        hint = QLabel(error.hint)
        hint.setObjectName("ErrHint")
        hint.setWordWrap(True)
        hint_row.addWidget(hint, stretch=1)
        body_layout.addLayout(hint_row)

        if log_path is not None:
            log_row = QHBoxLayout()
            log_caption = QLabel("Log file:")
            log_caption.setObjectName("ErrLogLbl")
            log_row.addWidget(log_caption, alignment=Qt.AlignmentFlag.AlignTop)
            log_value = QLabel(str(log_path))
            log_value.setObjectName("ErrLogPath")
            log_value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            log_value.setWordWrap(True)
            log_row.addWidget(log_value, stretch=1)
            body_layout.addLayout(log_row)

        root.addWidget(body)

        # ---- actions ----
        action_row = QHBoxLayout()
        action_row.setContentsMargins(24, 6, 24, 22)
        action_row.setSpacing(10)

        copy_btn = QPushButton("  Copy details")
        copy_btn.setIcon(theme.icon("copy", "#FFFFFF", 17))
        copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        copy_btn.setToolTip("Copies error code + log tail to clipboard for support")
        copy_btn.clicked.connect(self._copy_details)
        action_row.addWidget(copy_btn)

        if log_path is not None:
            open_btn = QPushButton("  Open log folder")
            open_btn.setObjectName("GhostButton")
            open_btn.setIcon(theme.icon("folder", theme.INK, 17))
            open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            open_btn.clicked.connect(lambda: _open_in_explorer(log_path))
            action_row.addWidget(open_btn)

        action_row.addStretch()

        close_btn = QPushButton("Close")
        close_btn.setObjectName("GhostButton")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.reject)
        action_row.addWidget(close_btn)

        root.addLayout(action_row)

    def _copy_details(self) -> None:
        payload = self._error.details_block()
        if self._log_path is not None:
            payload += f"\n\nLog file: {self._log_path}"
            tail = _read_log_tail(self._log_path)
            if tail:
                payload += "\n\nLog tail (last 80 lines):\n" + tail
        QGuiApplication.clipboard().setText(payload)
