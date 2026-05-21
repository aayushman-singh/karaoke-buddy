"""MainWindow — owns all core components, wires views to business logic."""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QProgressDialog,
    QStackedWidget,
    QWidget,
)

from karaoke_buddy.core.exporter import ExportThread
from karaoke_buddy.core.filter_chain import build_filter_chain
from karaoke_buddy.core.library import Library, LibraryEntry, SavedOutput
from karaoke_buddy.core.source_resolver import (
    SourceResolver,
    YouTubeRuntimeDependencyError,
    is_youtube_url,
    youtube_runtime_diagnostics,
)
from karaoke_buddy.ui.home_view import HomeView
from karaoke_buddy.ui.playing_view import PlayingView

if TYPE_CHECKING:
    from karaoke_buddy.core.player import Player

log = logging.getLogger(__name__)

_HOME_IDX = 0
_PLAYING_IDX = 1


class _ResolveThread(QThread):
    progress = Signal(int)
    finished = Signal(object)
    error = Signal(str)

    def __init__(self, resolver: SourceResolver, input_str: str, parent=None) -> None:
        super().__init__(parent)
        self._resolver = resolver
        self._input = input_str

    def run(self) -> None:
        try:
            result = self._resolver.resolve(
                self._input, progress_callback=self.progress.emit
            )
            self.finished.emit(result)
        except FileNotFoundError:
            self.error.emit("This file seems to have moved.")
        except YouTubeRuntimeDependencyError as exc:
            log.exception(
                "YouTube runtime dependency failed input=%r runtime=%s",
                self._input,
                exc.runtime_context,
            )
            self.error.emit(
                "YouTube setup problem: Deno or yt-dlp-ejs is missing, "
                "incompatible, or could not run. Check the logs for the exact "
                "runtime details."
            )
        except Exception:  # noqa: BLE001
            if is_youtube_url(self._input):
                log.exception(
                    "YouTube resolve failed input=%r runtime=%s",
                    self._input,
                    youtube_runtime_diagnostics(),
                )
                self.error.emit(
                    "Couldn't download this YouTube video. yt-dlp failed; "
                    "check the logs for the URL and runtime details."
                )
            else:
                log.exception("Local source resolve failed input=%r", self._input)
                self.error.emit("Couldn't open this file. Check the logs for details.")


class MainWindow(QMainWindow):
    def __init__(
        self,
        library: Library,
        base_dir: Path,
        ffmpeg_exe: Optional[Path] = None,
        ffprobe_exe: Optional[Path] = None,
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
            ffprobe_exe=ffprobe_exe,
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
        self._playing.save_requested.connect(self._on_save)
        self._playing.back_to_library.connect(self._go_home)
        self._playing.settings_changed.connect(self._persist_settings)

    def _go_home(self) -> None:
        if self._player:
            self._player.stop()
        self._home.refresh_library()
        self._stack.setCurrentIndex(_HOME_IDX)

    def _go_playing(self) -> None:
        self._stack.setCurrentIndex(_PLAYING_IDX)

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
        else:
            entry = LibraryEntry(
                title=resolved.title,
                source_type=resolved.source_type,
                source=resolved.source,
                cached_path=resolved_posix,
                thumbnail_path=str(resolved.thumbnail_path)
                if resolved.thumbnail_path
                else None,
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
            self._show_error("This file seems to have moved.")
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

    def _persist_settings(self, pitch: int, vocal_reduce: int) -> None:
        if self._current_entry:
            self._current_entry.last_pitch = pitch
            self._current_entry.last_vocal_reduce = vocal_reduce
            self._library.upsert(self._current_entry)

    def _on_save(self, pitch: int, vocal_reduce: int) -> None:
        if not self._current_entry:
            return

        default_dir = self._base_dir / "Pitched Songs"
        default_dir.mkdir(exist_ok=True)

        key_str = f"key {pitch:+d}" if pitch != 0 else "normal key"
        default_name = f"{self._current_entry.title} ({key_str}).mp4"

        output_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save this version",
            str(default_dir / default_name),
            "MP4 video (*.mp4)",
        )
        if not output_path:
            return

        chain = build_filter_chain(pitch, vocal_reduce)
        cached = Path(self._current_entry.cached_path or self._current_entry.source)

        progress = QProgressDialog("Saving\u2026", "Cancel", 0, 100, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)

        thread = ExportThread(cached, chain, Path(output_path), self._ffmpeg_exe)
        self._export_threads.append(thread)

        thread.progress.connect(progress.setValue)
        thread.finished.connect(
            lambda p: self._on_export_done(p, pitch, vocal_reduce, progress)
        )
        thread.error.connect(lambda msg: self._show_error(msg, progress))
        progress.canceled.connect(thread.cancel)
        thread.start()

    def _on_export_done(
        self, output_path: str, pitch: int, vocal_reduce: int, progress
    ) -> None:
        progress.close()
        if self._current_entry:
            self._current_entry.saved_outputs.append(
                SavedOutput(
                    path=output_path,
                    pitch=pitch,
                    vocal_reduce=vocal_reduce,
                    saved_at=datetime.now(timezone.utc).isoformat(),
                )
            )
            self._library.upsert(self._current_entry)
        QMessageBox.information(self, "Saved", f"Saved to:\n{output_path}")

    def _show_error(self, message: str, progress=None) -> None:
        if progress:
            progress.close()
        QMessageBox.warning(self, "KaraokeBuddy", message)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        if self._player:
            self._player.shutdown()
        super().closeEvent(event)
