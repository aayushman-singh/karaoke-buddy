"""MainWindow — owns all core components, wires views to business logic."""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import Qt, QThread, Signal
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
from karaoke_buddy.core.library import Library, LibraryEntry, SavedOutput
from karaoke_buddy.core.runtime_paths import default_export_dir
from karaoke_buddy.core.source_resolver import (
    SourceResolver,
    YouTubeRuntimeDependencyError,
    is_youtube_url,
    youtube_runtime_diagnostics,
)
from karaoke_buddy.ui import theme
from karaoke_buddy.ui.error_dialog import ErrorDialog
from karaoke_buddy.ui.home_view import HomeView
from karaoke_buddy.ui.playing_view import PlayingView

if TYPE_CHECKING:
    from karaoke_buddy.core.player import Player

log = logging.getLogger(__name__)

_HOME_IDX = 0
_PLAYING_IDX = 1

_EXPORT_FORMATS: list[tuple[str, str, str]] = [
    (".mp4", "MP4 video", "Keeps the karaoke video on screen."),
    (".m4a", "M4A audio", "Audio only — small file, plays everywhere modern."),
    (".mp3", "MP3 audio", "Audio only — works on older phones and car stereos."),
]

_SAVE_QSS = f"""
QDialog {{ background: {theme.SURFACE}; }}
QLabel#SaveSub {{ color: {theme.INK_2}; font-size: 14px; font-weight: 600; }}
QFrame#FmtCard {{
    background: {theme.SURFACE}; border: 2px solid {theme.LINE_2}; border-radius: 14px;
}}
QFrame#FmtCard:hover {{ border-color: {theme.CORAL}; }}
QFrame#FmtCard:focus {{ border-color: {theme.CORAL}; }}
QLabel#FmtIcon {{ background: {theme.CORAL_SOFT}; border-radius: 14px; }}
QLabel#FmtDesc {{ color: {theme.INK_2}; font-size: 13px; font-weight: 600; }}
QLabel#FmtSubLbl {{ color: {theme.INK_3}; font-size: 11px; font-weight: 800; }}
QLabel#FmtFixedFormat {{ color: {theme.INK_2}; font-size: 13px; font-weight: 800; }}
"""


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
    """A big, clickable format card. Clicking the card body commits the save;
    child controls (the audio dropdown) handle their own clicks and do not."""

    def __init__(
        self,
        icon_name: str,
        title: str,
        description: str,
        on_commit,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("FmtCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._on_commit = on_commit
        # Keyboard parity with the QMessageBox buttons this card replaced: tab
        # focus + Enter/Space commits the save, announced as a button.
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName(title)
        self.setAccessibleDescription(description)

        col = QVBoxLayout(self)
        col.setContentsMargins(20, 20, 20, 20)
        col.setSpacing(12)

        chip = QLabel()
        chip.setObjectName("FmtIcon")
        chip.setFixedSize(54, 54)
        chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        chip.setPixmap(theme.icon(icon_name, theme.CORAL, 28).pixmap(28, 28))
        col.addWidget(chip)

        title_lbl = QLabel(title)
        title_lbl.setObjectName("FmtTitle")
        title_lbl.setFont(theme.display_font(18))
        col.addWidget(title_lbl)

        desc_lbl = QLabel(description)
        desc_lbl.setObjectName("FmtDesc")
        desc_lbl.setWordWrap(True)
        col.addWidget(desc_lbl)

        self._sub_row = QHBoxLayout()
        self._sub_row.setSpacing(8)
        sub_lbl = QLabel("Format")
        sub_lbl.setObjectName("FmtSubLbl")
        self._sub_row.addWidget(sub_lbl)
        col.addStretch()
        col.addLayout(self._sub_row)

    def add_format_widget(self, widget: QWidget) -> None:
        self._sub_row.addWidget(widget)
        self._sub_row.addStretch()

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            self._on_commit()
            event.accept()
            return
        super().mousePressEvent(event)

    def keyPressEvent(self, event) -> None:  # type: ignore[override]
        if event.key() in (
            Qt.Key.Key_Return,
            Qt.Key.Key_Enter,
            Qt.Key.Key_Space,
        ):
            self._on_commit()
            event.accept()
            return
        super().keyPressEvent(event)


class _SaveFormatDialog(QDialog):
    """Grandma-friendly export chooser: two big cards (Audio with an MP3/M4A
    dropdown, Video = MP4). Same three suffixes as the cited source; only the
    presentation changes. The chosen suffix is read via ``chosen``."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Save as…")
        self.setMinimumWidth(560)
        self.setStyleSheet(_SAVE_QSS)
        self.chosen: Optional[str] = None

        root = QVBoxLayout(self)
        root.setContentsMargins(26, 24, 26, 22)
        root.setSpacing(16)

        title = QLabel("How would you like to save this version?")
        title.setObjectName("SaveTitle")
        title.setFont(theme.display_font(20))
        title.setWordWrap(True)
        root.addWidget(title)

        sub = QLabel("Pick a format. Pitch shift and vocal reduction are baked in either way.")
        sub.setObjectName("SaveSub")
        sub.setWordWrap(True)
        root.addWidget(sub)

        cards = QHBoxLayout()
        cards.setSpacing(16)

        # Audio card — dropdown selects between the two audio suffixes.
        self._audio_combo = QComboBox()
        for suffix, label, _desc in _EXPORT_FORMATS:
            if suffix != ".mp4":
                self._audio_combo.addItem(label.split()[0], suffix)  # "M4A"/"MP3"
        audio_card = _FormatCard(
            "headphones",
            "Audio",
            "Just the sound — great for the car, phone, or a speaker.",
            self._commit_audio,
        )
        audio_card.add_format_widget(self._audio_combo)
        cards.addWidget(audio_card)

        video_card = _FormatCard(
            "film",
            "Video",
            "Keeps the karaoke video on screen. Saved as an MP4.",
            self._commit_video,
        )
        mp4_lbl = QLabel("MP4")
        mp4_lbl.setObjectName("FmtFixedFormat")
        video_card.add_format_widget(mp4_lbl)
        cards.addWidget(video_card)
        root.addLayout(cards)

        actions = QHBoxLayout()
        actions.addStretch()
        cancel = QPushButton("Cancel")
        cancel.setObjectName("GhostButton")
        cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel.clicked.connect(self.reject)
        actions.addWidget(cancel)
        root.addLayout(actions)

        # Land keyboard focus on a commit control, not the Cancel button.
        audio_card.setFocus()

    def _commit_audio(self) -> None:
        self.chosen = self._audio_combo.currentData()
        self.accept()

    def _commit_video(self) -> None:
        self.chosen = ".mp4"
        self.accept()


def _ask_export_format(parent: QWidget) -> Optional[str]:
    """Modal asking the user which container/codec to export to.

    Returns the chosen suffix (one of SUPPORTED_EXPORT_SUFFIXES) or None if
    the user cancelled. The OS file-dialog's filter dropdown is buried in
    its chrome and easy to miss, so we surface the choice as a first-class
    in-app decision instead.
    """
    dialog = _SaveFormatDialog(parent)
    if dialog.exec() == QDialog.DialogCode.Accepted:
        return dialog.chosen
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

    def _persist_settings(self, pitch: int) -> None:
        if self._current_entry:
            self._current_entry.last_pitch = pitch
            self._library.upsert(self._current_entry)

    def _on_save(self, pitch: int) -> None:
        if not self._current_entry:
            return

        chosen_suffix = _ask_export_format(self)
        if chosen_suffix is None:
            return

        default_dir = default_export_dir()
        default_dir.mkdir(parents=True, exist_ok=True)

        key_str = f"key {pitch:+d}" if pitch != 0 else "normal key"
        default_name = f"{self._current_entry.title} ({key_str}){chosen_suffix}"
        filter_label = next(
            f"{label} (*{suffix})"
            for suffix, label, _ in _EXPORT_FORMATS
            if suffix == chosen_suffix
        )

        output_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save this version",
            str(default_dir / default_name),
            filter_label,
        )
        if not output_path:
            return

        output_path = _ensure_export_suffix(output_path, chosen_suffix)

        chain = build_filter_chain(pitch, 0)
        cached = Path(self._current_entry.cached_path or self._current_entry.source)

        progress = QProgressDialog("Saving\u2026", "Cancel", 0, 100, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)

        thread = ExportThread(cached, chain, Path(output_path), self._ffmpeg_exe)
        self._export_threads.append(thread)

        thread.progress.connect(progress.setValue)
        thread.finished.connect(lambda p: self._on_export_done(p, pitch, progress))
        thread.error.connect(lambda msg: self._show_error(msg, progress))
        progress.canceled.connect(thread.cancel)
        thread.start()

    def _on_export_done(self, output_path: str, pitch: int, progress) -> None:
        progress.close()
        if self._current_entry:
            self._current_entry.saved_outputs.append(
                SavedOutput(
                    path=output_path,
                    pitch=pitch,
                    vocal_reduce=0,
                    saved_at=datetime.now(timezone.utc).isoformat(),
                )
            )
            self._library.upsert(self._current_entry)
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
