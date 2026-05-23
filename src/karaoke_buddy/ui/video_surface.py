"""Minimal video surface — owns the native HWND that mpv attaches to.

Windows note: mpv embeds via ``--wid`` and draws into a native HWND that lives
above any Qt-painted sibling. Putting Qt overlay widgets on top of it does not
work reliably — they either disappear behind the mpv HWND, or (when promoted to
a native translucent window) paint as a black layer that hides the video.

The architecture intentionally keeps all transport controls *outside* the video
widget. This module exposes only the embeddable surface; ``PlayingView`` owns
buttons, sliders, and the back arrow.
"""

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QSlider, QVBoxLayout, QWidget


class ClickJumpSlider(QSlider):
    """Slider that jumps to the clicked position instead of paging by chunks."""

    def mousePressEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton and self.maximum() > self.minimum():
            if self.orientation() == Qt.Orientation.Horizontal:
                ratio = event.position().x() / max(1, self.width())
            else:
                ratio = 1.0 - event.position().y() / max(1, self.height())
            ratio = max(0.0, min(1.0, ratio))
            value = self.minimum() + round((self.maximum() - self.minimum()) * ratio)
            self.setValue(value)
            self.sliderMoved.emit(value)
            event.accept()
            return
        super().mousePressEvent(event)


PLAYBACK_SPEEDS: list[tuple[str, float]] = [
    ("0.5x", 0.5),
    ("0.75x", 0.75),
    ("Normal", 1.0),
    ("1.25x", 1.25),
    ("1.5x", 1.5),
    ("1.75x", 1.75),
    ("2x", 2.0),
]


def format_time(seconds: float) -> str:
    s = int(seconds)
    return f"{s // 60}:{s % 60:02d}"


class VideoSurface(QWidget):
    """Black widget that exposes a native HWND child for mpv to render into."""

    clicked = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.video_widget = QWidget(self)
        self.video_widget.setStyleSheet("background: black;")
        # mpv attaches via HWND; force a real native window up front so winId()
        # returns a realized handle even before the widget is shown.
        self.video_widget.setAttribute(Qt.WidgetAttribute.WA_NativeWindow, True)
        self.video_widget.setAttribute(Qt.WidgetAttribute.WA_DontCreateNativeAncestors, True)
        self.video_widget.winId()
        layout.addWidget(self.video_widget)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
            event.accept()
            return
        super().mousePressEvent(event)
