"""HomeView — launch screen shown when no video is loaded."""

import logging
from typing import Optional

from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from karaoke_buddy.core.library import Library
from karaoke_buddy.core.source_resolver import is_youtube_url
from karaoke_buddy.ui.library_view import LibraryEntry, LibraryView

log = logging.getLogger(__name__)

_VIDEO_FILTER = "Video files (*.mp4 *.mkv *.webm *.mov);;All files (*)"


class _ClipMetaWorker(QThread):
    """Fetches a YouTube video's title without downloading the video.

    Emits ``title_ready(str)`` on success, ``fetch_failed()`` on any error.
    """

    title_ready = Signal(str)
    fetch_failed = Signal()

    def __init__(self, url: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._url = url

    def run(self) -> None:
        try:
            import yt_dlp  # noqa: PLC0415

            with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
                info = ydl.extract_info(self._url, download=False)
            self.title_ready.emit(info.get("title") or self._url)
        except Exception:  # noqa: BLE001
            self.fetch_failed.emit()


class _PasteDialog(QDialog):
    def __init__(self, prefill: str = "", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Open YouTube link")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Paste a YouTube link:"))

        self._field = QLineEdit(prefill)
        self._field.setPlaceholderText("https://www.youtube.com/watch?v=\u2026")
        layout.addWidget(self._field)

        self._warning = QLabel("")
        self._warning.setStyleSheet("color: #e05c5c; font-size: 11px;")
        layout.addWidget(self._warning)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_accept(self) -> None:
        url = self._field.text().strip()
        if not is_youtube_url(url):
            self._warning.setText("That doesn't look like a YouTube link.")
            return
        self.accept()

    def url(self) -> str:
        return self._field.text().strip()


class HomeView(QWidget):
    open_file_requested = Signal(str)
    open_url_requested = Signal(str)
    entry_selected = Signal(LibraryEntry)

    def __init__(self, library: Library, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._library = library
        self._last_clip_url: str = ""
        self._clip_meta_worker: Optional[_ClipMetaWorker] = None

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)

        title = QLabel("KaraokeBuddy \U0001f3a4")
        title.setStyleSheet("font-size: 28px; font-weight: bold;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(title)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(16)

        self._btn_open = QPushButton("Open a video file")
        self._btn_open.setFixedHeight(56)
        self._btn_open.setStyleSheet("font-size: 15px;")
        self._btn_open.clicked.connect(self._on_open_file)
        btn_row.addWidget(self._btn_open)

        self._btn_paste = QPushButton("Paste YouTube link")
        self._btn_paste.setFixedHeight(56)
        self._btn_paste.setStyleSheet("font-size: 15px;")
        self._btn_paste.clicked.connect(self._on_paste_url)
        btn_row.addWidget(self._btn_paste)

        root.addLayout(btn_row)

        self._clip_label = QLabel("")
        self._clip_label.setStyleSheet("color: #7ec8e3; font-size: 12px;")
        self._clip_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._clip_label.hide()
        root.addWidget(self._clip_label)

        self._library_view = LibraryView(library)
        self._library_view.entry_selected.connect(self.entry_selected)
        root.addWidget(self._library_view, stretch=1)

        self._clip_timer = QTimer(self)
        self._clip_timer.setInterval(1000)
        self._clip_timer.timeout.connect(self._check_clipboard)
        self._clip_timer.start()

    def refresh_library(self) -> None:
        self._library_view.refresh()

    def _on_open_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open video", "", _VIDEO_FILTER)
        if path:
            self.open_file_requested.emit(path)

    def _on_paste_url(self) -> None:
        clipboard_text = QGuiApplication.clipboard().text().strip()
        prefill = clipboard_text if is_youtube_url(clipboard_text) else ""
        dlg = _PasteDialog(prefill=prefill, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.open_url_requested.emit(dlg.url())

    def _check_clipboard(self) -> None:
        if not self.isVisible():
            return
        text = QGuiApplication.clipboard().text().strip()
        if is_youtube_url(text):
            if text != self._last_clip_url:
                # New URL — start async title fetch
                self._last_clip_url = text
                self._clip_label.setText("\U0001f3b5 Fetching title\u2026")
                self._clip_label.show()

                if self._clip_meta_worker and self._clip_meta_worker.isRunning():
                    self._clip_meta_worker.terminate()
                    self._clip_meta_worker.wait(500)

                worker = _ClipMetaWorker(text, parent=self)
                worker.title_ready.connect(
                    lambda title, url=text: self._on_clip_title(title, url)
                )
                worker.fetch_failed.connect(
                    lambda: self._clip_label.setText(
                        "\U0001f3b5 YouTube link detected"
                        " \u2014 click \u201cPaste YouTube link\u201d to open"
                    )
                )
                worker.finished.connect(worker.deleteLater)
                self._clip_meta_worker = worker
                worker.start()
            # else: same URL, label already up-to-date
        else:
            self._last_clip_url = ""
            self._clip_label.hide()

    def _on_clip_title(self, title: str, url: str) -> None:
        """Called from the worker thread via Signal — always on the Qt main thread."""
        if url == self._last_clip_url:  # guard against stale workers
            self._clip_label.setText(f"Paste this? \U0001f3b5  {title}")
            self._clip_label.show()
