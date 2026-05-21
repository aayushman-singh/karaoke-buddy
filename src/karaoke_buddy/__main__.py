"""KaraokeBuddy — entry point."""

import logging
import logging.handlers
import os
import sys
import tempfile
from pathlib import Path


def _setup_logging(log_dir: Path) -> None:
    log_dir.mkdir(exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(
        log_dir / "app.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    logging.getLogger().addHandler(handler)
    logging.getLogger().setLevel(logging.INFO)


def _locate_bundled(name: str) -> Path | None:
    """Find a binary bundled by PyInstaller.

    Checks ``sys._MEIPASS`` first (populated in ``--onefile`` mode when the
    archive is extracted to a temp directory), then falls back to the directory
    that contains the executable (correct for ``--onedir`` mode).

    Returns ``None`` in development (non-frozen) mode, or if the file does not
    exist in any candidate location.
    """
    if not getattr(sys, "frozen", False):
        return None
    search_dirs: list[Path] = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        search_dirs.append(Path(meipass))
    search_dirs.append(Path(sys.executable).parent)
    for d in search_dirs:
        candidate = d / name
        if candidate.exists():
            return candidate
    return None


def _setup_dll_search_path() -> None:
    """In frozen mode, add the PyInstaller extraction directory to the Windows
    DLL search path so that ``ctypes`` (used by python-mpv) can find
    ``libmpv-2.dll`` without it being on the system ``PATH``.

    Must be called before any ``import mpv`` (i.e. before importing
    ``MainWindow``, which transitively imports ``player.py``).

    No-op in development mode and on non-Windows platforms.
    """
    if not getattr(sys, "frozen", False):
        return
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass and hasattr(os, "add_dll_directory"):
        os.add_dll_directory(meipass)


def _run_smoke_check(base_dir: Path, duration_ms: int = 250) -> int:
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    from karaoke_buddy.core.library import Library
    from karaoke_buddy.ui.home_view import HomeView
    from karaoke_buddy.ui.library_view import LibraryView
    from karaoke_buddy.ui.main_window import MainWindow
    from karaoke_buddy.ui.playing_view import PlayingView

    ui_modules = (HomeView, LibraryView, MainWindow, PlayingView)
    log = logging.getLogger(__name__)
    log.info("Launch smoke check imported UI modules: %s", ui_modules)

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("KaraokeBuddy Smoke Check")

    with tempfile.TemporaryDirectory(prefix="karaoke-buddy-smoke-") as tmp:
        window = MainWindow(
            library=Library(Path(tmp) / "library.json"),
            base_dir=base_dir,
        )
        window.show()
        QTimer.singleShot(duration_ms, app.quit)
        return int(app.exec())


def main() -> None:
    if getattr(sys, "frozen", False):
        base_dir = Path(sys.executable).parent
    else:
        base_dir = Path(__file__).parent.parent.parent

    _setup_logging(base_dir / "logs")
    log = logging.getLogger(__name__)
    log.info("KaraokeBuddy starting \u2014 base_dir=%s", base_dir)

    # Must happen before any import that pulls in python-mpv.
    _setup_dll_search_path()

    if "--smoke-check" in sys.argv:
        sys.exit(_run_smoke_check(base_dir))

    from PySide6.QtWidgets import QApplication, QMessageBox

    app = QApplication(sys.argv)
    app.setApplicationName("KaraokeBuddy")

    ffmpeg_exe = _locate_bundled("ffmpeg.exe")
    ffprobe_exe = _locate_bundled("ffprobe.exe")

    if getattr(sys, "frozen", False) and (ffmpeg_exe is None or ffprobe_exe is None):
        QMessageBox.critical(
            None,
            "KaraokeBuddy",
            "Installation is incomplete. Please re-download KaraokeBuddy.",
        )
        sys.exit(1)

    from karaoke_buddy.core.library import Library
    from karaoke_buddy.ui.main_window import MainWindow

    library = Library(base_dir / "library.json")
    window = MainWindow(
        library=library,
        base_dir=base_dir,
        ffmpeg_exe=ffmpeg_exe,
        ffprobe_exe=ffprobe_exe,
    )
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
