"""KaraokeBuddy — entry point."""

import logging
import logging.handlers
import os
import sys
import tempfile
import traceback
from pathlib import Path

from karaoke_buddy.core.runtime_paths import locate_bundled, runtime_binary_dirs

_DLL_DIRECTORY_HANDLES: list[object] = []


def _setup_logging(log_dir: Path) -> None:
    log_dir.mkdir(exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(
        log_dir / "app.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
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


def _missing_bundled_dependency_message(ffmpeg_exe: Path | None) -> str | None:
    if not getattr(sys, "frozen", False):
        return None

    missing: list[str] = []
    if ffmpeg_exe is None:
        missing.append("ffmpeg.exe")
    if locate_bundled("ffprobe.exe") is None:
        missing.append("ffprobe.exe")

    if not missing:
        return None

    return (
        "Installation is incomplete. Please re-download KaraokeBuddy. "
        f"Missing bundled dependencies: {', '.join(missing)}."
    )


def _setup_dll_search_path(base_dir: Path | None = None) -> None:
    """Prepend runtime binary dirs to PATH (and Windows DLL search on Windows).

    Packaged builds use the PyInstaller extraction directory. Development uses
    ``build/bin/`` when present so FFmpeg and libmpv do not need a global install.

    Must be called before any ``import mpv`` (i.e. before importing
    ``MainWindow``, which transitively imports ``player.py``).
    """
    binary_dirs = [d for d in runtime_binary_dirs(base_dir) if d.exists()]
    if not binary_dirs:
        return

    if sys.platform == "win32" and hasattr(os, "add_dll_directory"):
        for directory in binary_dirs:
            _DLL_DIRECTORY_HANDLES.append(os.add_dll_directory(str(directory)))

    current_path = os.environ.get("PATH", "")
    existing = current_path.split(os.pathsep) if current_path else []
    additions = [str(d) for d in binary_dirs if str(d) not in existing]
    if additions:
        os.environ["PATH"] = os.pathsep.join([*additions, *existing])


def _run_smoke_check(
    base_dir: Path,
    ffmpeg_exe: Path | None,
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

    from karaoke_buddy.ui import theme

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("KaraokeBuddy Smoke Check")
    theme.apply(app)
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
        )
        window.show()
        if os.environ.get("KARAOKE_BUDDY_SMOKE_RAISE_UNCAUGHT"):
            QTimer.singleShot(
                0,
                lambda: (_ for _ in ()).throw(RuntimeError("Injected launch smoke exception")),
            )
        QTimer.singleShot(duration_ms, app.quit)
        exit_code = int(app.exec())
        if uncaught_exceptions:
            raise RuntimeError(
                "Launch smoke check hit uncaught exception:\n" + "\n".join(uncaught_exceptions)
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
    _setup_dll_search_path(base_dir)
    log.info("Runtime binary path configured: %s", runtime_binary_dirs(base_dir))

    ffmpeg_exe = locate_bundled("ffmpeg.exe")
    ffprobe_exe = locate_bundled("ffprobe.exe")
    libmpv_dll = locate_bundled("libmpv-2.dll")
    deno_exe = locate_bundled("deno.exe")
    log.info(
        "Bundled ffmpeg=%s ffprobe=%s libmpv=%s deno=%s",
        ffmpeg_exe,
        ffprobe_exe,
        libmpv_dll,
        deno_exe,
    )

    if smoke_check:
        with tempfile.TemporaryDirectory(prefix="karaoke-buddy-smoke-") as tmp:
            sys.exit(_run_smoke_check(Path(tmp), ffmpeg_exe))

    from karaoke_buddy.core.dependency_preflight import (
        RuntimeDependencyError,
        preflight_runtime_dependencies,
    )

    try:
        preflight_runtime_dependencies(
            ffmpeg_exe=ffmpeg_exe,
            libmpv_dll=libmpv_dll,
            frozen=bool(getattr(sys, "frozen", False)),
        )
    except RuntimeDependencyError as exc:
        log.exception(
            "Dependency preflight failed: base_dir=%s frozen=%s ffmpeg=%s libmpv=%s",
            base_dir,
            bool(getattr(sys, "frozen", False)),
            ffmpeg_exe,
            libmpv_dll,
        )
        print(str(exc), file=sys.stderr)
        # QMessageBox from Git Bash / MSYS often segfaults; stderr is reliable.
        sys.exit(1)

    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    app.setApplicationName("KaraokeBuddy")

    from karaoke_buddy.ui import theme

    theme.apply(app)
    log.info("Qt application created")

    from karaoke_buddy.core.library import Library
    from karaoke_buddy.ui.main_window import MainWindow

    log.info("Creating main window")
    library = Library(base_dir / "library.json")
    window = MainWindow(
        library=library,
        base_dir=base_dir,
        ffmpeg_exe=ffmpeg_exe,
    )
    window.show()
    log.info("Main window shown")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
