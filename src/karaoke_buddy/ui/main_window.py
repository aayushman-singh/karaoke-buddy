"""MainWindow — owns all core components, wires views to business logic."""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from karaoke_buddy.core import errors as kb_errors
from karaoke_buddy.core.errors import KBError
from karaoke_buddy.core.exporter import ExportThread
from karaoke_buddy.core.filter_chain import build_filter_chain
from karaoke_buddy.core.library import Library, LibraryEntry
from karaoke_buddy.core.runtime_paths import default_export_dir
from karaoke_buddy.core.source_resolver import (
    SourceResolver,
    YouTubeRuntimeDependencyError,
    is_youtube_url,
    youtube_runtime_diagnostics,
)
from karaoke_buddy.ui.error_dialog import ErrorDialog
from karaoke_buddy.ui.home_view import HomeView
from karaoke_buddy.ui.playing_view import PlayingView

if TYPE_CHECKING:
    from karaoke_buddy.core.player import Player

log = logging.getLogger(__name__)

_HOME_IDX = 0
_PLAYING_IDX = 1

_DEFAULT_AUDIO_SUFFIX = ".mp3"
_DEFAULT_VIDEO_SUFFIX = ".mp4"

_FILTER_LABELS: dict[str, str] = {
    ".mp4": "MP4 video (*.mp4)",
    ".m4a": "M4A audio (*.m4a)",
    ".mp3": "MP3 audio (*.mp3)",
}


def _ensure_export_suffix(path: str, suffix: str) -> str:
    """Append `suffix` to `path` if it is missing.

    The Save dialog is launched scoped to a single format, but Qt's static
    getSaveFileName does not enforce the active filter's extension when the
    user types a name without one. This keeps the Exporter's suffix contract
    satisfied without surprising the user with a different extension than the
    one they picked.
    """
    if Path(path).suffix.lower() == suffix.lower():
        return path
    return path + suffix


class _FormatCard(QFrame):
    """Big clickable card with a built-in format selector.

    Clicking anywhere on the card body emits ``chose`` with the currently
    selected suffix. The embedded QComboBox absorbs clicks on itself, so
    opening the dropdown does not also trigger a save.
    """

    chose = Signal(str)

    def __init__(
        self,
        emoji: str,
        title: str,
        options: list[tuple[str, str]],
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._suffix = options[0][0]
        self.setObjectName("formatCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumSize(200, 200)
        self.setStyleSheet(
            "#formatCard {"
            "  background: #f4f4f8;"
            "  border: 2px solid #b8b8c4;"
            "  border-radius: 14px;"
            "}"
            "#formatCard:hover {"
            "  background: #e6e8ff;"
            "  border-color: #5a6cff;"
            "}"
            "#formatCard QLabel { color: #14141c; background: transparent; }"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 18, 16, 16)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        emoji_lbl = QLabel(emoji)
        emoji_lbl.setStyleSheet("font-size: 38pt;")
        emoji_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(emoji_lbl)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(
            "font-size: 20pt; font-weight: 800; letter-spacing: 2px; color: #14141c;"
        )
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_lbl)

        layout.addStretch()

        if len(options) > 1:
            self._combo: Optional[QComboBox] = QComboBox()
            for suffix, label in options:
                self._combo.addItem(label, suffix)
            self._combo.currentIndexChanged.connect(self._on_combo_change)
            self._combo.setCursor(Qt.CursorShape.PointingHandCursor)
            self._combo.setStyleSheet(
                "QComboBox {"
                "  background: white;"
                "  color: #14141c;"
                "  border: 1px solid #9a9aaa;"
                "  border-radius: 6px;"
                "  padding: 4px 8px;"
                "  font-size: 11pt;"
                "  min-width: 130px;"
                "}"
                "QComboBox::drop-down { border: none; width: 22px; }"
                "QComboBox QAbstractItemView { background: white; color: #14141c; }"
            )
            layout.addWidget(self._combo, alignment=Qt.AlignmentFlag.AlignCenter)
        else:
            self._combo = None
            static = QLabel(options[0][1])
            static.setStyleSheet("font-size: 11pt; color: #44445a;")
            static.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(static)

    def _on_combo_change(self, idx: int) -> None:
        assert self._combo is not None
        self._suffix = self._combo.itemData(idx)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        # Children (the QComboBox) absorb clicks on themselves before this
        # fires — so this branch runs for clicks on the card body only.
        if event.button() == Qt.MouseButton.LeftButton:
            self.chose.emit(self._suffix)
        super().mousePressEvent(event)


class _ExportFormatDialog(QDialog):
    """Grandma-friendly Save modal.

    Two large AUDIO / VIDEO cards with codec dropdowns embedded inside.
    Click anywhere on the card body to save in the format the dropdown
    is showing. AUDIO defaults to MP3, VIDEO has only MP4.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Save as…")
        self.setModal(True)
        self._chosen_suffix: Optional[str] = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 24, 24, 16)
        outer.setSpacing(14)

        heading = QLabel("How would you like to save this?")
        heading.setStyleSheet("font-size: 15pt; font-weight: 700; color: #14141c;")
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(heading)

        sub = QLabel("Your key and vocal-reduce settings are saved either way.")
        sub.setStyleSheet("color: #5a5a72; font-size: 10pt;")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(sub)

        card_row = QHBoxLayout()
        card_row.setSpacing(18)

        audio_card = _FormatCard(
            "\U0001f3b5",
            "AUDIO",
            [
                (".mp3", "MP3  (default)"),
                (".m4a", "M4A  (smaller)"),
            ],
        )
        audio_card.chose.connect(self._finish)
        card_row.addWidget(audio_card)

        video_card = _FormatCard(
            "\U0001f3ac",
            "VIDEO",
            [(".mp4", "MP4")],
        )
        video_card.chose.connect(self._finish)
        card_row.addWidget(video_card)

        outer.addLayout(card_row)

        footer = QHBoxLayout()
        footer.addStretch()
        cancel = QPushButton("Cancel")
        cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel.clicked.connect(self.reject)
        footer.addWidget(cancel)
        outer.addLayout(footer)

    def _finish(self, suffix: str) -> None:
        self._chosen_suffix = suffix
        self.accept()

    @property
    def chosen_suffix(self) -> Optional[str]:
        return self._chosen_suffix


def _ask_export_format(parent: QWidget) -> Optional[str]:
    """Returns the chosen suffix (one of SUPPORTED_EXPORT_SUFFIXES) or None on cancel."""
    dialog = _ExportFormatDialog(parent)
    if dialog.exec() == QDialog.DialogCode.Accepted:
        return dialog.chosen_suffix
    return None


class _ResolveThread(QThread):
    progress = Signal(int)
    finished = Signal(object)
    error = Signal(object)

    def __init__(self, resolver: SourceResolver, input_str: str, parent=None) -> None:
        super().__init__(parent)
        self._resolver = resolver
        self._input = input_str

    def run(self) -> None:
        try:
            result = self._resolver.resolve(self._input, progress_callback=self.progress.emit)
            self.finished.emit(result)
        except FileNotFoundError:
            log.exception("Local file missing input=%r", self._input)
            self.error.emit(kb_errors.file_missing(self._input))
        except YouTubeRuntimeDependencyError as exc:
            log.exception(
                "YouTube runtime dependency failed input=%r runtime=%s",
                self._input,
                exc.runtime_context,
            )
            self.error.emit(kb_errors.yt_runtime(str(exc)))
        except Exception as exc:  # noqa: BLE001
            if is_youtube_url(self._input):
                log.exception(
                    "YouTube resolve failed input=%r runtime=%s",
                    self._input,
                    youtube_runtime_diagnostics(),
                )
                self.error.emit(kb_errors.youtube_failure(exc))
            else:
                log.exception("Local source resolve failed input=%r", self._input)
                self.error.emit(kb_errors.file_unreadable(str(exc)))


class MainWindow(QMainWindow):
    def __init__(
        self,
        library: Library,
        base_dir: Path,
        ffmpeg_exe: Optional[Path] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("KaraokeBuddy")
        self.setMinimumSize(700, 540)

        self._library = library
        self._base_dir = base_dir
        self._ffmpeg_exe = ffmpeg_exe
        self._current_entry: Optional[LibraryEntry] = None
        self._export_threads: list[ExportThread] = []
        self._resolve_thread: Optional[_ResolveThread] = None

        self._resolver = SourceResolver(
            cache_dir=base_dir / "cache",
            ffmpeg_exe=ffmpeg_exe,
        )

        self._stack = QStackedWidget()
        self.setCentralWidget(self._stack)

        self._home = HomeView(library)
        self._stack.addWidget(self._home)

        self._playing = PlayingView()
        self._stack.addWidget(self._playing)

        self._player: Optional["Player"] = None

        self._home.open_file_requested.connect(self._resolve_input)
        self._home.open_url_requested.connect(self._resolve_input)
        self._home.entry_selected.connect(self._open_entry)

        self._playing.filter_changed.connect(self._apply_filter)
        self._playing.seek_requested.connect(self._on_seek)
        self._playing.play_pause_toggled.connect(self._on_play_pause)
        self._playing.volume_changed.connect(self._on_volume)
        self._playing.speed_changed.connect(self._on_speed)
        self._playing.save_requested.connect(self._on_save)
        self._playing.back_to_library.connect(self._go_home)
        self._playing.settings_changed.connect(self._persist_settings)
        self._playing.fullscreen_toggled.connect(self._on_fullscreen)

        self._was_maximized_before_fullscreen = False

    def _go_home(self) -> None:
        if self._player:
            self._player.stop()
        self._home.refresh_library()
        self._stack.setCurrentIndex(_HOME_IDX)

    def _go_playing(self) -> None:
        self._stack.setCurrentIndex(_PLAYING_IDX)

    def _on_fullscreen(self, is_full: bool) -> None:
        if is_full:
            self._was_maximized_before_fullscreen = self.isMaximized()
            self._playing.set_chrome_visible(False)
            self.showFullScreen()
        else:
            self._playing.set_chrome_visible(True)
            if self._was_maximized_before_fullscreen:
                self.showMaximized()
            else:
                self.showNormal()

    def _resolve_input(self, input_str: str) -> None:
        progress = QProgressDialog("Loading\u2026", "Cancel", 0, 100, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(400)

        thread = _ResolveThread(self._resolver, input_str)
        self._resolve_thread = thread

        thread.progress.connect(progress.setValue)
        thread.finished.connect(lambda r: self._on_resolved(r, progress))
        thread.error.connect(lambda msg: self._show_error(msg, progress))
        progress.canceled.connect(thread.terminate)
        thread.start()

    def _on_resolved(self, resolved, progress) -> None:
        progress.close()

        resolved_posix = resolved.local_path.as_posix()
        existing = next(
            (
                e
                for e in self._library.list()
                if e.source == resolved_posix or e.cached_path == resolved_posix
            ),
            None,
        )
        if existing:
            entry = existing
            entry.title = resolved.title
            entry.duration_seconds = resolved.duration_seconds
            if resolved.thumbnail_path is not None:
                entry.thumbnail_path = str(resolved.thumbnail_path)
        else:
            entry = LibraryEntry(
                title=resolved.title,
                source_type=resolved.source_type,
                source=resolved.source,
                cached_path=resolved_posix,
                thumbnail_path=str(resolved.thumbnail_path) if resolved.thumbnail_path else None,
                duration_seconds=resolved.duration_seconds,
            )
        entry.last_opened = datetime.now(timezone.utc).isoformat()
        self._library.upsert(entry)
        self._current_entry = entry

        self._playing.load_entry(entry)
        self._go_playing()
        self._load_player(resolved.local_path)

    def _open_entry(self, entry: LibraryEntry) -> None:
        cached = entry.cached_path or entry.source
        path = Path(cached)
        if not path.exists():
            self._show_error(kb_errors.cached_path_missing(str(path)))
            self._library.remove(entry.id)
            self._home.refresh_library()
            return
        entry.last_opened = datetime.now(timezone.utc).isoformat()
        self._library.upsert(entry)
        self._current_entry = entry
        self._playing.load_entry(entry)
        self._go_playing()
        self._load_player(path)

    def _load_player(self, path: Path) -> None:
        if self._player is None:
            from karaoke_buddy.core.player import Player

            self._player = Player(self._playing.video_widget)
            self._player.set_volume(100)
            self._player.set_speed(1.0)
            self._player.playback_time_changed.connect(self._playing.update_time)
            self._player.duration_changed.connect(self._playing.update_duration)
            self._player.paused_changed.connect(self._playing.update_paused)

        self._player.load(str(path))
        self._player.set_filter(self._playing.current_filter())
        self._player.play()

    def _apply_filter(self, chain: str) -> None:
        if self._player:
            self._player.set_filter(chain)

    def _on_seek(self, seconds: float) -> None:
        if self._player:
            self._player.seek(seconds)

    def _on_play_pause(self) -> None:
        if self._player:
            self._player.toggle_play_pause()

    def _on_volume(self, percent: int) -> None:
        if self._player:
            self._player.set_volume(percent)

    def _on_speed(self, speed: float) -> None:
        if self._player:
            self._player.set_speed(speed)

    def _persist_settings(self, pitch: int, vocal_reduce: int) -> None:
        if self._current_entry:
            self._library.touch(self._current_entry.id, pitch, vocal_reduce)

    def _on_save(self, pitch: int, vocal_reduce: int) -> None:
        if not self._current_entry:
            return

        chosen_suffix = _ask_export_format(self)
        if chosen_suffix is None:
            return

        default_dir = default_export_dir(chosen_suffix)
        default_dir.mkdir(parents=True, exist_ok=True)

        key_str = f"key {pitch:+d}" if pitch != 0 else "normal key"
        vocal_str = " (vocals reduced)" if vocal_reduce > 0 else ""
        default_name = f"{self._current_entry.title} ({key_str}){vocal_str}{chosen_suffix}"

        output_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save this version",
            str(default_dir / default_name),
            _FILTER_LABELS[chosen_suffix],
        )
        if not output_path:
            return

        output_path = _ensure_export_suffix(output_path, chosen_suffix)

        chain = build_filter_chain(pitch, vocal_reduce)
        cached = Path(self._current_entry.cached_path or self._current_entry.source)

        progress = QProgressDialog("Saving\u2026", "Cancel", 0, 100, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)

        thread = ExportThread(cached, chain, Path(output_path), self._ffmpeg_exe)
        self._export_threads.append(thread)

        thread.progress.connect(progress.setValue)
        thread.finished.connect(lambda p: self._on_export_done(p, pitch, vocal_reduce, progress))
        thread.error.connect(lambda msg: self._show_error(msg, progress))
        progress.canceled.connect(thread.cancel)
        thread.start()

    def _on_export_done(self, output_path: str, pitch: int, vocal_reduce: int, progress) -> None:
        progress.close()
        if self._current_entry:
            self._library.add_saved_output(
                self._current_entry.id,
                output_path,
                pitch,
                vocal_reduce=vocal_reduce,
            )
        QMessageBox.information(self, "Saved", f"Saved to:\n{output_path}")

    def _show_error(self, err: KBError | str, progress=None) -> None:
        if progress:
            progress.close()
        if isinstance(err, str):
            err = KBError(
                code="KB-MISC",
                title="Something went wrong",
                user_message=err,
                hint="Try the action again. If the problem repeats, share the error code with support.",
            )
        log_path = self._base_dir / "logs" / "app.log"
        dialog = ErrorDialog(err, log_path=log_path if log_path.exists() else None, parent=self)
        dialog.exec()

    def closeEvent(self, event) -> None:  # type: ignore[override]
        if self._player:
            self._player.shutdown()
        super().closeEvent(event)
