"""PlayingView — video surface + pitch/vocal sliders + save button."""

import logging
from typing import Optional

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from karaoke_buddy.core.filter_chain import build_filter_chain
from karaoke_buddy.core.library import LibraryEntry

log = logging.getLogger(__name__)

_DEBOUNCE_MS = 120


def _pitch_label(semitones: int) -> str:
    if semitones == 0:
        return "Normal key"
    direction = "Higher" if semitones > 0 else "Lower"
    abs_s = abs(semitones)
    word = "key" if abs_s == 1 else "keys"
    return f"{direction} by {abs_s} {word}"


def _format_time(seconds: float) -> str:
    s = int(seconds)
    return f"{s // 60}:{s % 60:02d}"


class PlayingView(QWidget):
    filter_changed = Signal(str)
    seek_requested = Signal(float)
    play_pause_toggled = Signal()
    save_requested = Signal(int, int)
    back_to_library = Signal()
    settings_changed = Signal(int, int)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._pitch = 0
        self._vocal_reduce = 0
        self._duration = 0.0

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.video_widget = QWidget()
        self.video_widget.setMinimumHeight(300)
        self.video_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.video_widget.setStyleSheet("background: black;")
        root.addWidget(self.video_widget, stretch=1)

        controls = QWidget()
        controls.setStyleSheet("background: #1e1e1e;")
        ctrl_layout = QVBoxLayout(controls)
        ctrl_layout.setContentsMargins(16, 12, 16, 12)
        ctrl_layout.setSpacing(10)

        # Timeline
        timeline_row = QHBoxLayout()
        self._time_label = QLabel("0:00")
        self._time_label.setFixedWidth(40)
        timeline_row.addWidget(self._time_label)

        self._timeline = QSlider(Qt.Orientation.Horizontal)
        self._timeline.setRange(0, 1000)
        self._timeline.sliderMoved.connect(self._on_seek)
        timeline_row.addWidget(self._timeline, stretch=1)

        self._duration_label = QLabel("0:00")
        self._duration_label.setFixedWidth(40)
        self._duration_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        timeline_row.addWidget(self._duration_label)
        ctrl_layout.addLayout(timeline_row)

        # Play/pause
        play_row = QHBoxLayout()
        self._play_btn = QPushButton("\u25b6  Play")
        self._play_btn.setFixedWidth(100)
        self._play_btn.clicked.connect(self.play_pause_toggled)
        play_row.addWidget(self._play_btn)
        play_row.addStretch()
        ctrl_layout.addLayout(play_row)

        # Pitch slider
        pitch_section = QLabel("Song key")
        pitch_section.setStyleSheet("font-weight: bold; color: #ddd;")
        ctrl_layout.addWidget(pitch_section)

        pitch_row = QHBoxLayout()
        pitch_row.addWidget(QLabel("Lower"))
        self._pitch_slider = QSlider(Qt.Orientation.Horizontal)
        self._pitch_slider.setRange(-12, 12)
        self._pitch_slider.setValue(0)
        self._pitch_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._pitch_slider.setTickInterval(1)
        self._pitch_slider.setSingleStep(1)
        self._pitch_slider.valueChanged.connect(self._on_pitch_changed)
        pitch_row.addWidget(self._pitch_slider, stretch=1)
        pitch_row.addWidget(QLabel("Higher"))
        ctrl_layout.addLayout(pitch_row)

        self._pitch_label = QLabel("Normal key")
        self._pitch_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._pitch_label.setStyleSheet("color: #aaa;")
        ctrl_layout.addWidget(self._pitch_label)

        # Vocal reduce slider
        vocal_section = QLabel("Silence the singer")
        vocal_section.setStyleSheet("font-weight: bold; color: #ddd;")
        ctrl_layout.addWidget(vocal_section)

        vocal_row = QHBoxLayout()
        vocal_row.addWidget(QLabel("Off"))
        self._vocal_slider = QSlider(Qt.Orientation.Horizontal)
        self._vocal_slider.setRange(0, 100)
        self._vocal_slider.setValue(0)
        self._vocal_slider.valueChanged.connect(self._on_vocal_changed)
        vocal_row.addWidget(self._vocal_slider, stretch=1)
        vocal_row.addWidget(QLabel("Full"))
        ctrl_layout.addLayout(vocal_row)

        self._vocal_label = QLabel("Guide vocals: on")
        self._vocal_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._vocal_label.setStyleSheet("color: #aaa;")
        ctrl_layout.addWidget(self._vocal_label)

        # Bottom row
        bottom_row = QHBoxLayout()
        self._save_btn = QPushButton("\U0001f4be  Save this version")
        self._save_btn.setFixedHeight(44)
        self._save_btn.setStyleSheet("font-size: 13px;")
        self._save_btn.clicked.connect(self._on_save)
        bottom_row.addWidget(self._save_btn)
        bottom_row.addStretch()
        back_btn = QPushButton("\u2190 Back to library")
        back_btn.setFlat(True)
        back_btn.setStyleSheet("color: #888;")
        back_btn.clicked.connect(self.back_to_library)
        bottom_row.addWidget(back_btn)
        ctrl_layout.addLayout(bottom_row)

        root.addWidget(controls)

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

    def load_entry(self, entry: LibraryEntry) -> None:
        self._pitch_slider.setValue(entry.last_pitch)
        self._vocal_slider.setValue(entry.last_vocal_reduce)

    def update_time(self, seconds: float) -> None:
        self._time_label.setText(_format_time(seconds))
        if self._duration > 0:
            pos = int(seconds / self._duration * 1000)
            self._timeline.blockSignals(True)
            self._timeline.setValue(pos)
            self._timeline.blockSignals(False)

    def update_duration(self, seconds: float) -> None:
        self._duration = seconds
        self._duration_label.setText(_format_time(seconds))

    def update_paused(self, paused: bool) -> None:
        self._play_btn.setText("\u25b6  Play" if paused else "\u23f8  Pause")

    def current_filter(self) -> str:
        return build_filter_chain(self._pitch, self._vocal_reduce)

    def _on_pitch_changed(self, value: int) -> None:
        self._pitch = value
        self._pitch_label.setText(_pitch_label(value))
        self._debounce.start()
        self._settings_debounce.start()

    def _on_vocal_changed(self, value: int) -> None:
        self._vocal_reduce = value
        if value == 0:
            self._vocal_label.setText("Guide vocals: on")
        elif value == 100:
            self._vocal_label.setText("Guide vocals: fully removed")
        else:
            self._vocal_label.setText(f"Guide vocals: {100 - value}% audible")
        self._debounce.start()
        self._settings_debounce.start()

    def _on_seek(self, position: int) -> None:
        if self._duration > 0:
            self.seek_requested.emit(position / 1000 * self._duration)

    def _on_save(self) -> None:
        self.save_requested.emit(self._pitch, self._vocal_reduce)

    def _emit_filter(self) -> None:
        self.filter_changed.emit(build_filter_chain(self._pitch, self._vocal_reduce))
