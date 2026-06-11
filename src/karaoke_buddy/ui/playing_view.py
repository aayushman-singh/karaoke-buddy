"""PlayingView — header bar, video surface, transport + pitch + save panel."""

import logging
from typing import Optional

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from karaoke_buddy.core.filter_chain import build_mpv_filter_chain
from karaoke_buddy.core.library import LibraryEntry
from karaoke_buddy.ui.video_surface import (
    PLAYBACK_SPEEDS,
    ClickJumpSlider,
    VideoSurface,
    format_time,
)

log = logging.getLogger(__name__)

_DEBOUNCE_MS = 120


def _pitch_label(semitones: int) -> str:
    if semitones == 0:
        return "Normal key"
    direction = "Higher" if semitones > 0 else "Lower"
    abs_s = abs(semitones)
    word = "key" if abs_s == 1 else "keys"
    return f"{direction} by {abs_s} {word}"


def _vocal_label(percent: int) -> str:
    if percent == 0:
        return "Singer at full volume"
    if percent >= 100:
        return "Singer almost gone"
    return f"Singer turned down {percent}%"


class PlayingView(QWidget):
    filter_changed = Signal(str)
    seek_requested = Signal(float)
    play_pause_toggled = Signal()
    volume_changed = Signal(int)
    speed_changed = Signal(float)
    save_requested = Signal(int, int)
    back_to_library = Signal()
    settings_changed = Signal(int, int)
    fullscreen_toggled = Signal(bool)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._pitch = 0
        self._vocal_reduce = 0
        self._duration = 0.0
        self._paused = True
        self._fullscreen = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._header = self._build_header()
        root.addWidget(self._header)

        self._video_surface = VideoSurface()
        self._video_surface.setMinimumHeight(300)
        self._video_surface.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._video_surface.clicked.connect(self.play_pause_toggled.emit)
        root.addWidget(self._video_surface, stretch=1)

        self._controls_panel = self._build_controls_panel()
        root.addWidget(self._controls_panel)

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(_DEBOUNCE_MS)
        self._debounce.timeout.connect(self._emit_filter)

        self._settings_debounce = QTimer(self)
        self._settings_debounce.setSingleShot(True)
        self._settings_debounce.setInterval(800)
        self._settings_debounce.timeout.connect(
            lambda: self.settings_changed.emit(self._pitch, self._vocal_reduce)
        )

    def _build_header(self) -> QWidget:
        header = QWidget()
        header.setFixedHeight(48)
        header.setStyleSheet(
            "QWidget { background: #1e1e1e; }"
            "QPushButton {"
            "  color: #ddd; background: transparent; border: none;"
            "  font-size: 14px; padding: 6px 14px;"
            "}"
            "QPushButton:hover { background: rgba(255,255,255,0.08); border-radius: 4px; }"
        )
        layout = QHBoxLayout(header)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)

        back_btn = QPushButton("←  Back to library")
        back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        back_btn.clicked.connect(self.back_to_library.emit)
        layout.addWidget(back_btn)

        layout.addStretch()

        self._fullscreen_btn = QPushButton("⛶  Full screen")
        self._fullscreen_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._fullscreen_btn.setToolTip("Toggle full screen (Esc to exit)")
        self._fullscreen_btn.clicked.connect(self._toggle_fullscreen)
        layout.addWidget(self._fullscreen_btn)

        return header

    def _build_controls_panel(self) -> QWidget:
        panel = QWidget()
        panel.setStyleSheet(
            "QWidget { background: #1e1e1e; }"
            "QLabel { color: #ddd; font-size: 12px; }"
            "QPushButton {"
            "  color: #eee; background: rgba(255,255,255,0.06); border: none;"
            "  font-size: 14px; min-width: 36px; padding: 6px 10px; border-radius: 4px;"
            "}"
            "QPushButton:hover { background: rgba(255,255,255,0.14); }"
            "QComboBox {"
            "  color: #eee; background: #2a2a2a; border: 1px solid #444;"
            "  padding: 4px 8px; min-width: 80px;"
            "}"
            "QSlider::groove:horizontal {"
            "  height: 6px; background: #444; border-radius: 3px;"
            "}"
            "QSlider::handle:horizontal {"
            "  width: 14px; margin: -5px 0; background: #fff; border-radius: 7px;"
            "}"
            "QSlider::sub-page:horizontal { background: #e53935; border-radius: 3px; }"
        )
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 10, 16, 12)
        layout.setSpacing(10)

        timeline_row = QHBoxLayout()
        self._time_label = QLabel("0:00")
        self._time_label.setFixedWidth(44)
        timeline_row.addWidget(self._time_label)
        self._timeline = ClickJumpSlider(Qt.Orientation.Horizontal)
        self._timeline.setRange(0, 1000)
        self._timeline.sliderMoved.connect(self._on_seek_slider)
        timeline_row.addWidget(self._timeline, stretch=1)
        self._duration_label = QLabel("0:00")
        self._duration_label.setFixedWidth(44)
        self._duration_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        timeline_row.addWidget(self._duration_label)
        layout.addLayout(timeline_row)

        transport_row = QHBoxLayout()
        transport_row.setSpacing(10)
        self._play_btn = QPushButton("▶")
        self._play_btn.setFixedWidth(48)
        self._play_btn.setToolTip("Play / pause (Space)")
        self._play_btn.clicked.connect(self.play_pause_toggled.emit)
        transport_row.addWidget(self._play_btn)

        vol_icon = QLabel("\U0001f50a")
        vol_icon.setFixedWidth(24)
        transport_row.addWidget(vol_icon)
        self._volume = QSlider(Qt.Orientation.Horizontal)
        self._volume.setRange(0, 100)
        self._volume.setValue(100)
        self._volume.setFixedWidth(120)
        self._volume.valueChanged.connect(self.volume_changed.emit)
        transport_row.addWidget(self._volume)

        transport_row.addSpacing(20)

        transport_row.addWidget(QLabel("Speed"))
        self._speed = QComboBox()
        for label, _ in PLAYBACK_SPEEDS:
            self._speed.addItem(label)
        self._speed.setCurrentIndex(2)
        self._speed.currentIndexChanged.connect(self._on_speed_index)
        transport_row.addWidget(self._speed)

        transport_row.addStretch()
        layout.addLayout(transport_row)

        pitch_section = QLabel("Song key")
        pitch_section.setStyleSheet("font-weight: bold; color: #ddd; font-size: 13px;")
        layout.addWidget(pitch_section)

        pitch_row = QHBoxLayout()
        pitch_row.addWidget(QLabel("Lower"))
        self._pitch_slider = ClickJumpSlider(Qt.Orientation.Horizontal)
        self._pitch_slider.setRange(-12, 12)
        self._pitch_slider.setValue(0)
        self._pitch_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._pitch_slider.setTickInterval(1)
        self._pitch_slider.setSingleStep(1)
        self._pitch_slider.valueChanged.connect(self._on_pitch_changed)
        pitch_row.addWidget(self._pitch_slider, stretch=1)
        pitch_row.addWidget(QLabel("Higher"))
        layout.addLayout(pitch_row)

        self._pitch_label = QLabel("Normal key")
        self._pitch_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._pitch_label.setStyleSheet("color: #aaa;")
        layout.addWidget(self._pitch_label)

        vocal_section = QLabel("Silence the singer")
        vocal_section.setStyleSheet("font-weight: bold; color: #ddd; font-size: 13px;")
        layout.addWidget(vocal_section)

        vocal_row = QHBoxLayout()
        vocal_row.addWidget(QLabel("Off"))
        self._vocal_slider = ClickJumpSlider(Qt.Orientation.Horizontal)
        self._vocal_slider.setRange(0, 100)
        self._vocal_slider.setValue(0)
        self._vocal_slider.setSingleStep(5)
        self._vocal_slider.valueChanged.connect(self._on_vocal_changed)
        vocal_row.addWidget(self._vocal_slider, stretch=1)
        vocal_row.addWidget(QLabel("Max"))
        layout.addLayout(vocal_row)

        self._vocal_label = QLabel("Singer at full volume")
        self._vocal_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._vocal_label.setStyleSheet("color: #aaa;")
        layout.addWidget(self._vocal_label)

        self._save_btn = QPushButton("\U0001f4be  Save this version")
        self._save_btn.setFixedHeight(44)
        self._save_btn.setStyleSheet(
            "QPushButton {"
            "  font-size: 13px; background: #2a2a2a; color: #eee;"
            "  border: 1px solid #444; border-radius: 4px;"
            "}"
            "QPushButton:hover { background: #353535; }"
        )
        self._save_btn.clicked.connect(self._on_save)
        layout.addWidget(self._save_btn)

        return panel

    @property
    def video_widget(self) -> QWidget:
        return self._video_surface.video_widget

    def set_chrome_visible(self, visible: bool) -> None:
        """Hide header + controls panel for fullscreen; restore on exit."""
        self._header.setVisible(visible)
        self._controls_panel.setVisible(visible)

    def load_entry(self, entry: LibraryEntry) -> None:
        self._pitch_slider.setValue(entry.last_pitch)
        self._vocal_slider.setValue(entry.last_vocal_reduce)

    def update_time(self, seconds: float) -> None:
        self._time_label.setText(format_time(seconds))
        if self._duration > 0:
            pos = int(seconds / self._duration * 1000)
            self._timeline.blockSignals(True)
            self._timeline.setValue(pos)
            self._timeline.blockSignals(False)

    def update_duration(self, seconds: float) -> None:
        self._duration = seconds
        self._duration_label.setText(format_time(seconds))

    def update_paused(self, paused: bool) -> None:
        self._paused = paused
        self._play_btn.setText("▶" if paused else "⏸")

    def set_volume(self, percent: int) -> None:
        self._volume.blockSignals(True)
        self._volume.setValue(max(0, min(100, percent)))
        self._volume.blockSignals(False)

    def set_speed(self, speed: float) -> None:
        for index, (_, value) in enumerate(PLAYBACK_SPEEDS):
            if abs(value - speed) < 0.01:
                self._speed.blockSignals(True)
                self._speed.setCurrentIndex(index)
                self._speed.blockSignals(False)
                return

    def current_filter(self) -> str:
        return build_mpv_filter_chain(self._pitch, self._vocal_reduce)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # type: ignore[override]
        if event.key() == Qt.Key.Key_Escape and self._fullscreen:
            self._set_fullscreen(False)
            event.accept()
            return
        if event.key() == Qt.Key.Key_Space:
            self.play_pause_toggled.emit()
            event.accept()
            return
        super().keyPressEvent(event)

    def _on_seek_slider(self, position: int) -> None:
        if self._duration > 0:
            self.seek_requested.emit(position / 1000 * self._duration)

    def _on_speed_index(self, index: int) -> None:
        if 0 <= index < len(PLAYBACK_SPEEDS):
            self.speed_changed.emit(PLAYBACK_SPEEDS[index][1])

    def _on_pitch_changed(self, value: int) -> None:
        self._pitch = value
        self._pitch_label.setText(_pitch_label(value))
        self._debounce.start()
        self._settings_debounce.start()

    def _on_vocal_changed(self, value: int) -> None:
        self._vocal_reduce = value
        self._vocal_label.setText(_vocal_label(value))
        self._debounce.start()
        self._settings_debounce.start()

    def _on_save(self) -> None:
        self.save_requested.emit(self._pitch, self._vocal_reduce)

    def _emit_filter(self) -> None:
        self.filter_changed.emit(build_mpv_filter_chain(self._pitch, self._vocal_reduce))

    def _toggle_fullscreen(self) -> None:
        self._set_fullscreen(not self._fullscreen)

    def _set_fullscreen(self, on: bool) -> None:
        if on == self._fullscreen:
            return
        self._fullscreen = on
        self._fullscreen_btn.setText("⛶  Exit full screen" if on else "⛶  Full screen")
        self.fullscreen_toggled.emit(on)
