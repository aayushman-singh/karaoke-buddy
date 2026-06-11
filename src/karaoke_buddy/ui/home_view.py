"""HomeView — launch screen shown when no video is loaded."""

import logging
from typing import Optional

from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from karaoke_buddy.core.library import Library
from karaoke_buddy.core.source_resolver import (
    is_youtube_url,
    youtube_extraction_options,
)
from karaoke_buddy.ui import theme
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

            with yt_dlp.YoutubeDL(youtube_extraction_options()) as ydl:
                info = ydl.extract_info(self._url, download=False)
            self.title_ready.emit(info.get("title") or self._url)
        except Exception:  # noqa: BLE001
            log.exception("YouTube clipboard title fetch failed for %s", self._url)
            self.fetch_failed.emit()


class _BigButton(QFrame):
    """Large, friendly action card — icon + bold title + quiet subtitle.

    A QFrame (not QPushButton) so the design's two-line label and icon chip
    compose cleanly; it emits ``clicked`` like a button.
    """

    clicked = Signal()

    def __init__(
        self,
        icon_name: str,
        title: str,
        subtitle: str,
        primary: bool,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("BigPrimary" if primary else "BigGhost")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(84)
        # Keyboard parity with the QPushButton this card replaced: tab focus +
        # Enter/Space activation, announced to screen readers as a button.
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName(title)
        self.setAccessibleDescription(subtitle)

        row = QHBoxLayout(self)
        row.setContentsMargins(18, 16, 18, 16)
        row.setSpacing(14)

        chip = QLabel()
        chip.setObjectName("BigIconChip")
        chip.setFixedSize(46, 46)
        chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_color = "#FFFFFF" if primary else theme.GOLD
        chip.setPixmap(theme.icon(icon_name, icon_color, 26).pixmap(26, 26))
        row.addWidget(chip)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        title_lbl = QLabel(title)
        title_lbl.setObjectName("BigTitle")
        sub_lbl = QLabel(subtitle)
        sub_lbl.setObjectName("BigSubtitle")
        text_col.addWidget(title_lbl)
        text_col.addWidget(sub_lbl)
        row.addLayout(text_col)
        row.addStretch()

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
            event.accept()
            return
        super().mousePressEvent(event)

    def keyPressEvent(self, event) -> None:  # type: ignore[override]
        if event.key() in (
            Qt.Key.Key_Return,
            Qt.Key.Key_Enter,
            Qt.Key.Key_Space,
        ):
            self.clicked.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class _PasteDialog(QDialog):
    def __init__(self, prefill: str = "", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Open YouTube link")
        self.setMinimumWidth(440)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(14)

        heading = QLabel("Open YouTube link")
        heading.setFont(theme.display_font(20))
        layout.addWidget(heading)

        prompt = QLabel("Paste a YouTube link:")
        prompt.setStyleSheet(f"color: {theme.INK_2}; font-size: 15px; font-weight: 700;")
        layout.addWidget(prompt)

        self._field = QLineEdit(prefill)
        self._field.setPlaceholderText("https://www.youtube.com/watch?v=…")
        layout.addWidget(self._field)

        self._warning = QLabel("")
        self._warning.setObjectName("WarnLabel")
        self._warning.setStyleSheet(
            f"color: {theme.CORAL_DEEP}; font-size: 13px; font-weight: 800;"
        )
        layout.addWidget(self._warning)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        ok_btn = buttons.button(QDialogButtonBox.StandardButton.Ok)
        ok_btn.setText("OK")
        cancel_btn = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        cancel_btn.setObjectName("GhostButton")
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
        root.setContentsMargins(34, 30, 34, 26)
        root.setSpacing(22)

        # ---- brand block ----
        brand = QVBoxLayout()
        brand.setSpacing(8)
        brand.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        mark = QLabel()
        mark.setObjectName("BrandMark")
        mark.setFixedSize(60, 60)
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mark.setPixmap(theme.icon("music", "#FFFFFF", 30, stroke=2.3).pixmap(30, 30))
        brand.addWidget(mark, alignment=Qt.AlignmentFlag.AlignHCenter)

        name = QLabel("Karaoke Buddy")
        name.setFont(theme.display_font(34))
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand.addWidget(name)

        tag = QLabel("Open a song. Sing it in your key.")
        tag.setObjectName("BrandTag")
        tag.setStyleSheet(f"color: {theme.INK_2}; font-size: 15px; font-weight: 700;")
        tag.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand.addWidget(tag)
        root.addLayout(brand)

        # ---- big action buttons ----
        btn_row = QHBoxLayout()
        btn_row.setSpacing(16)

        self._btn_open = _BigButton(
            "folder", "Open a video file", "From your computer", primary=True
        )
        self._btn_open.clicked.connect(self._on_open_file)
        btn_row.addWidget(self._btn_open)

        self._btn_paste = _BigButton(
            "link", "Paste YouTube link", "From the internet", primary=False
        )
        self._btn_paste.clicked.connect(self._on_paste_url)
        btn_row.addWidget(self._btn_paste)
        root.addLayout(btn_row)

        # ---- clipboard hint pill (4 states) ----
        self._clip_label = QLabel("")
        self._clip_label.setObjectName("ClipHint")
        self._clip_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._clip_label.hide()
        root.addWidget(self._clip_label, alignment=Qt.AlignmentFlag.AlignHCenter)

        # ---- recent library ----
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
                self._clip_label.setText("Fetching title…")
                self._clip_label.show()

                prev = self._clip_meta_worker
                if prev is not None:
                    try:
                        if prev.isRunning():
                            prev.terminate()
                            prev.wait(500)
                    except RuntimeError:
                        # C++ object already deleted (finished + deleteLater'd)
                        pass

                worker = _ClipMetaWorker(text, parent=self)
                worker.title_ready.connect(lambda title, url=text: self._on_clip_title(title, url))
                worker.fetch_failed.connect(
                    lambda: self._clip_label.setText(
                        "YouTube link detected — click “Paste YouTube link” to open"
                    )
                )
                worker.finished.connect(self._on_clip_worker_finished)
                self._clip_meta_worker = worker
                worker.start()
            # else: same URL, label already up-to-date
        else:
            self._last_clip_url = ""
            self._clip_label.hide()

    def _on_clip_title(self, title: str, url: str) -> None:
        """Called from the worker thread via Signal — always on the Qt main thread."""
        if url == self._last_clip_url:  # guard against stale workers
            self._clip_label.setText(f"Paste this?   {title}")
            self._clip_label.show()

    def _on_clip_worker_finished(self) -> None:
        sender = self.sender()
        if sender is self._clip_meta_worker:
            self._clip_meta_worker = None
        if sender is not None:
            sender.deleteLater()
