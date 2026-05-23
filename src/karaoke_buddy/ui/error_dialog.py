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
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from karaoke_buddy.core.errors import KBError

log = logging.getLogger(__name__)


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
        self.setStyleSheet(
            "QDialog { background: #2b2b2b; color: #eee; }"
            "QLabel { color: #eee; }"
            "QPushButton {"
            "  color: #eee; background: #3a3a3a; border: 1px solid #555;"
            "  padding: 6px 14px; border-radius: 4px;"
            "}"
            "QPushButton:hover { background: #474747; }"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(12)

        title = QLabel(error.title)
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        title.setWordWrap(True)
        root.addWidget(title)

        code_row = QHBoxLayout()
        code_label = QLabel("Error code:")
        code_label.setStyleSheet("color: #aaa;")
        code_row.addWidget(code_label)
        code_badge = QLabel(error.code)
        code_badge.setStyleSheet(
            "background: #1f1f1f; color: #ffb74d; font-family: Consolas, monospace;"
            "padding: 3px 8px; border-radius: 3px; font-weight: bold;"
        )
        code_badge.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        code_row.addWidget(code_badge)
        code_row.addStretch()
        root.addLayout(code_row)

        message = QLabel(error.user_message)
        message.setWordWrap(True)
        root.addWidget(message)

        hint = QLabel(f"→ {error.hint}")
        hint.setStyleSheet("color: #9fcf9f;")
        hint.setWordWrap(True)
        root.addWidget(hint)

        if log_path is not None:
            log_row = QHBoxLayout()
            log_caption = QLabel("Log file:")
            log_caption.setStyleSheet("color: #aaa;")
            log_row.addWidget(log_caption)
            log_value = QLabel(str(log_path))
            log_value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            log_value.setStyleSheet(
                "color: #ccc; font-family: Consolas, monospace; font-size: 11px;"
            )
            log_value.setWordWrap(True)
            log_row.addWidget(log_value, stretch=1)
            root.addLayout(log_row)

        action_row = QHBoxLayout()
        action_row.setSpacing(8)

        copy_btn = QPushButton("\U0001f4cb Copy details")
        copy_btn.setToolTip("Copies error code + log tail to clipboard for support")
        copy_btn.clicked.connect(self._copy_details)
        action_row.addWidget(copy_btn)

        if log_path is not None:
            open_btn = QPushButton("Open log folder")
            open_btn.clicked.connect(lambda: _open_in_explorer(log_path))
            action_row.addWidget(open_btn)

        action_row.addStretch()

        close_btn = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_btn.rejected.connect(self.reject)
        close_btn.accepted.connect(self.accept)
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
