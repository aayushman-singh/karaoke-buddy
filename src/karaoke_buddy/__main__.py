"""KaraokeBuddy — entry point."""

import logging
import logging.handlers
import os
import sys
import tempfile
import traceback
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


def _setup_smoke_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    logging.getLogger().addHandler(handler)
    logging.getLogger().setLevel(logging.INFO)


def _log_unhandled_exception(
    exc_type: type[BaseException], exc: BaseException, traceback: object
) -> None:
    logging.getLogger(__name__).critical(
        "Unhandled exception during launch", exc_info=(exc_type, exc, traceback)
    )


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


def _missing_bundled_dependency_message(
    ffmpeg_exe: Path | None, ffprobe_exe: Path | None
) -> str | None:
    if not getattr(sys, "frozen", False):
        return None

    missing = []
    if ffmpeg_exe is None:
        missing.append("ffmpeg.exe")
    if ffprobe_exe is None:
        missing.append("ffprobe.exe")

    if not missing:
        return None

    return (
        "Installation is incomplete. Please re-download KaraokeBuddy. "
        f"Missing bundled dependencies: {', '.join(missing)}."
    )


def _runtime_binary_dirs() -> list[Path]:
    """Directories that may contain runtime binaries in packaged builds."""
    if not getattr(sys, "frozen", False):
        return []

    dirs: list[Path] = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        dirs.append(Path(meipass))
    dirs.append(Path(sys.executable).parent)
    return dirs


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
    binary_dirs = [d for d in _runtime_binary_dirs() if d.exists()]
    if not binary_dirs:
        return

    if hasattr(os, "add_dll_directory"):
        for directory in binary_dirs:
            os.add_dll_directory(str(directory))

    current_path = os.environ.get("PATH", "")
    existing = current_path.split(os.pathsep) if current_path else []
    additions = [str(d) for d in binary_dirs if str(d) not in existing]
    if additions:
        os.environ["PATH"] = os.pathsep.join([*additions, *existing])


def _run_smoke_check(
    base_dir: Path,
    ffmpeg_exe: Path | None,
    ffprobe_exe: Path | None,
    duration_ms: int = 250,
) -> int:
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
    uncaught_exceptions: list[str] = []
    previous_excepthook = sys.excepthook

    def smoke_excepthook(exc_type, exc_value, exc_tb) -> None:
        formatted = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        uncaught_exceptions.append(formatted)
        log.critical("Uncaught exception during launch smoke check:\n%s", formatted)
        previous_excepthook(exc_type, exc_value, exc_tb)

    sys.excepthook = smoke_excepthook
    try:
        window = MainWindow(
            library=Library(base_dir / "library.json"),
            base_dir=base_dir,
            ffmpeg_exe=ffmpeg_exe,
            ffprobe_exe=ffprobe_exe,
        )
        window.show()
        if os.environ.get("KARAOKE_BUDDY_SMOKE_RAISE_UNCAUGHT"):
            QTimer.singleShot(
                0,
                lambda: (_ for _ in ()).throw(
                    RuntimeError("Injected launch smoke exception")
                ),
            )
        QTimer.singleShot(duration_ms, app.quit)
        exit_code = int(app.exec())
        if uncaught_exceptions:
            raise RuntimeError(
                "Launch smoke check hit uncaught exception:\n"
                + "\n".join(uncaught_exceptions)
            )
        return exit_code
    finally:
        sys.excepthook = previous_excepthook


def main() -> None:
    if getattr(sys, "frozen", False):
        base_dir = Path(sys.executable).parent
    else:
        base_dir = Path(__file__).parent.parent.parent

    smoke_check = "--smoke-check" in sys.argv
    if smoke_check:
        _setup_smoke_logging()
    else:
        _setup_logging(base_dir / "logs")
        sys.excepthook = _log_unhandled_exception
    log = logging.getLogger(__name__)
    log.info("KaraokeBuddy starting \u2014 base_dir=%s", base_dir)

    # Must happen before any import that pulls in python-mpv.
    _setup_dll_search_path()
    log.info("Runtime binary path configured")

    ffmpeg_exe = _locate_bundled("ffmpeg.exe")
    ffprobe_exe = _locate_bundled("ffprobe.exe")
    log.info("Bundled ffmpeg=%s ffprobe=%s", ffmpeg_exe, ffprobe_exe)

    dependency_error = _missing_bundled_dependency_message(ffmpeg_exe, ffprobe_exe)
    if smoke_check and dependency_error:
        log.critical(dependency_error)
        sys.exit(1)

    if smoke_check:
        with tempfile.TemporaryDirectory(prefix="karaoke-buddy-smoke-") as tmp:
            sys.exit(_run_smoke_check(Path(tmp), ffmpeg_exe, ffprobe_exe))

    from PySide6.QtWidgets import QApplication, QMessageBox

    app = QApplication(sys.argv)
    app.setApplicationName("KaraokeBuddy")
    log.info("Qt application created")

    if dependency_error:
        QMessageBox.critical(
            None,
            "KaraokeBuddy",
            "Installation is incomplete. Please re-download KaraokeBuddy.",
        )
        sys.exit(1)

    from karaoke_buddy.core.library import Library
    from karaoke_buddy.ui.main_window import MainWindow

    log.info("Creating main window")
    library = Library(base_dir / "library.json")
    window = MainWindow(
        library=library,
        base_dir=base_dir,
        ffmpeg_exe=ffmpeg_exe,
        ffprobe_exe=ffprobe_exe,
    )
    window.show()
    log.info("Main window shown")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
