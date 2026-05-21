"""Player — libmpv wrapper bound to a PySide6 render widget."""

import logging
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QWidget

log = logging.getLogger(__name__)


class Player(QObject):
    """Thin Qt wrapper around libmpv."""

    playback_time_changed = Signal(float)
    duration_changed = Signal(float)
    paused_changed = Signal(bool)
    end_of_file = Signal()

    def __init__(
        self, render_widget: QWidget, parent: Optional[QObject] = None
    ) -> None:
        super().__init__(parent)
        import mpv  # noqa: PLC0415

        self._widget = render_widget
        self._mpv = mpv.MPV(
            wid=str(int(render_widget.winId())),
            vo="gpu",
            keep_open=True,
            log_handler=self._on_log,
            loglevel="warn",
        )
        self._setup_observers()

    def load(self, path: str | Path) -> None:
        self._mpv.pause = True
        self._mpv.loadfile(str(path))

    def set_filter(self, chain: str) -> None:
        try:
            self._mpv.command("af", "set", chain)
        except Exception as exc:  # noqa: BLE001
            log.warning("af set failed: %s", exc)

    def play(self) -> None:
        self._mpv.pause = False

    def pause(self) -> None:
        self._mpv.pause = True

    def toggle_play_pause(self) -> None:
        self._mpv.pause = not self._mpv.pause

    def seek(self, seconds: float) -> None:
        self._mpv.seek(seconds, "absolute")

    def stop(self) -> None:
        self._mpv.command("stop")

    @property
    def duration(self) -> float:
        return self._mpv.duration or 0.0

    @property
    def current_time(self) -> float:
        return self._mpv.time_pos or 0.0

    @property
    def is_paused(self) -> bool:
        return bool(self._mpv.pause)

    def shutdown(self) -> None:
        self._mpv.terminate()

    def _setup_observers(self) -> None:
        @self._mpv.property_observer("time-pos")
        def _on_time(name: str, value: Optional[float]) -> None:
            if value is not None:
                self.playback_time_changed.emit(float(value))

        @self._mpv.property_observer("duration")
        def _on_duration(name: str, value: Optional[float]) -> None:
            if value is not None:
                self.duration_changed.emit(float(value))

        @self._mpv.property_observer("pause")
        def _on_pause(name: str, value: Optional[bool]) -> None:
            if value is not None:
                self.paused_changed.emit(bool(value))

        @self._mpv.event_callback("end-file")
        def _on_end(event: dict) -> None:
            if event.get("reason") == "eof":
                self.end_of_file.emit()

    @staticmethod
    def _on_log(level: str, component: str, message: str) -> None:
        log.debug("[mpv/%s] %s", component, message)
