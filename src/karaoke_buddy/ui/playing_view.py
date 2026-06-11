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
from karaoke_buddy.ui import theme
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


class PlayingView(QWidget):
    filter_changed = Signal(str)
    seek_requested = Signal(float)
    play_pause_toggled = Signal()
    volume_changed = Signal(int)
    speed_changed = Signal(float)
    save_requested = Signal(int)
    back_to_library = Signal()
    settings_changed = Signal(int)
    fullscreen_toggled = Signal(bool)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._pitch = 0
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
        self._settings_debounce.timeout.connect(lambda: self.settings_changed.emit(self._pitch))

    def _build_header(self) -> QWidget:
        header = QWidget()
        header.setObjectName("PlayHeader")
        header.setFixedHeight(52)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(6)

        back_btn = QPushButton("  Back to library")
        back_btn.setObjectName("HeaderButton")
        back_btn.setIcon(theme.icon("back", theme.INK, 20))
        back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        back_btn.clicked.connect(self.back_to_library.emit)
        layout.addWidget(back_btn)

        layout.addStretch()

        self._fullscreen_btn = QPushButton("  Full screen")
        self._fullscreen_btn.setObjectName("HeaderButton")
        self._fullscreen_btn.setIcon(theme.icon("maximize", theme.INK, 18))
        self._fullscreen_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._fullscreen_btn.setToolTip("Toggle full screen (Esc to exit)")
        self._fullscreen_btn.clicked.connect(self._toggle_fullscreen)
        layout.addWidget(self._fullscreen_btn)

        return header

    def _build_controls_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("ControlsPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(22, 16, 22, 18)
        layout.setSpacing(14)

        # ---- seek row ----
        timeline_row = QHBoxLayout()
        timeline_row.setSpacing(14)
        self._time_label = QLabel("0:00")
        self._time_label.setObjectName("TimeLabel")
        self._time_label.setFixedWidth(44)
        timeline_row.addWidget(self._time_label)
        self._timeline = ClickJumpSlider(Qt.Orientation.Horizontal)
        self._timeline.setRange(0, 1000)
        self._timeline.sliderMoved.connect(self._on_seek_slider)
        timeline_row.addWidget(self._timeline, stretch=1)
        self._duration_label = QLabel("0:00")
        self._duration_label.setObjectName("TimeLabel")
        self._duration_label.setFixedWidth(44)
        self._duration_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        timeline_row.addWidget(self._duration_label)
        layout.addLayout(timeline_row)

        # ---- transport row ----
        transport_row = QHBoxLayout()
        transport_row.setSpacing(12)
        self._play_btn = QPushButton()
        self._play_btn.setObjectName("PlayCircle")
        self._play_btn.setFixedSize(52, 52)
        self._play_btn.setIcon(theme.icon("play", "#FFFFFF", 24))
        self._play_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._play_btn.setToolTip("Play / pause (Space)")
        self._play_btn.setAccessibleName("Play / pause")
        self._play_btn.clicked.connect(self.play_pause_toggled.emit)
        transport_row.addWidget(self._play_btn)

        vol_icon = QLabel()
        vol_icon.setPixmap(theme.icon("volume", theme.INK_2, 22).pixmap(22, 22))
        vol_icon.setFixedWidth(26)
        transport_row.addWidget(vol_icon)
        self._volume = QSlider(Qt.Orientation.Horizontal)
        self._volume.setRange(0, 100)
        self._volume.setValue(100)
        self._volume.setFixedWidth(130)
        self._volume.valueChanged.connect(self.volume_changed.emit)
        transport_row.addWidget(self._volume)

        transport_row.addStretch()

        speed_lbl = QLabel("Speed")
        speed_lbl.setObjectName("SpeedLabel")
        transport_row.addWidget(speed_lbl)
        self._speed = QComboBox()
        for label, _ in PLAYBACK_SPEEDS:
            self._speed.addItem(label)
        self._speed.setCurrentIndex(2)
        self._speed.currentIndexChanged.connect(self._on_speed_index)
        transport_row.addWidget(self._speed)
        layout.addLayout(transport_row)

        # ---- pitch section ----
        section = QHBoxLayout()
        section.setSpacing(8)
        section_ic = QLabel()
        section_ic.setPixmap(theme.icon("music", theme.CORAL, 18, stroke=2.3).pixmap(18, 18))
        section.addWidget(section_ic)
        section_lbl = QLabel("Song key")
        section_lbl.setObjectName("SectionLabel")
        section.addWidget(section_lbl)
        section.addStretch()
        layout.addLayout(section)

        pitch_row = QHBoxLayout()
        pitch_row.setSpacing(14)
        lower_lbl = QLabel("Lower")
        lower_lbl.setObjectName("EndCap")
        pitch_row.addWidget(lower_lbl)
        self._pitch_slider = ClickJumpSlider(Qt.Orientation.Horizontal)
        self._pitch_slider.setRange(-12, 12)
        self._pitch_slider.setValue(0)
        self._pitch_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._pitch_slider.setTickInterval(1)
        self._pitch_slider.setSingleStep(1)
        self._pitch_slider.valueChanged.connect(self._on_pitch_changed)
        pitch_row.addWidget(self._pitch_slider, stretch=1)
        higher_lbl = QLabel("Higher")
        higher_lbl.setObjectName("EndCap")
        pitch_row.addWidget(higher_lbl)
        layout.addLayout(pitch_row)

        self._pitch_label = QLabel("Normal key")
        self._pitch_label.setObjectName("PitchReadout")
        self._pitch_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._pitch_label.setFont(theme.display_font(20))
        layout.addWidget(self._pitch_label)

        self._save_btn = QPushButton("  Save this version")
        self._save_btn.setObjectName("SaveButton")
        self._save_btn.setFixedHeight(52)
        self._save_btn.setIcon(theme.icon("save", "#FFFFFF", 22))
        self._save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
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
        self._play_btn.setIcon(theme.icon("play" if paused else "pause", "#FFFFFF", 24))

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
        return build_mpv_filter_chain(self._pitch)

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

    def _on_save(self) -> None:
        self.save_requested.emit(self._pitch)

    def _emit_filter(self) -> None:
        self.filter_changed.emit(build_mpv_filter_chain(self._pitch))

    def _toggle_fullscreen(self) -> None:
        self._set_fullscreen(not self._fullscreen)

    def _set_fullscreen(self, on: bool) -> None:
        if on == self._fullscreen:
            return
        self._fullscreen = on
        self._fullscreen_btn.setText("  Exit full screen" if on else "  Full screen")
        self.fullscreen_toggled.emit(on)
