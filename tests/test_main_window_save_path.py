"""Save-path tests: a non-zero vocal reduction must flow end-to-end from the
PlayingView save signal through ``build_filter_chain``, the Exporter thread, and
into the Library — never silently dropped to 0.

These mirror the established mocking style: patch the format-chooser modal, the
OS save dialog, the progress dialog, and the ExportThread at the
``main_window`` module level so no real ffmpeg/mpv/Qt-native dialog runs.
"""

from pathlib import Path

import pytest

from karaoke_buddy.core.library import Library, LibraryEntry
from karaoke_buddy.ui import main_window as mw
from karaoke_buddy.ui.main_window import MainWindow


class _FakeThread:
    """Stand-in for ExportThread that records construction args and never runs."""

    instances: list["_FakeThread"] = []

    def __init__(self, input_path, filter_chain, output_path, ffmpeg_exe=None, parent=None):
        self.input_path = input_path
        self.filter_chain = filter_chain
        self.output_path = output_path
        self.progress = _FakeSignal()
        self.finished = _FakeSignal()
        self.error = _FakeSignal()
        _FakeThread.instances.append(self)

    def start(self):
        # Do not spawn a real thread; the test drives _on_export_done directly.
        pass

    def cancel(self):
        pass


class _FakeSignal:
    def connect(self, *_args, **_kwargs):
        pass


@pytest.fixture
def window(tmp_path, qtbot, monkeypatch):
    library = Library(tmp_path / "library.json")
    entry = LibraryEntry(
        title="Test Song",
        source_type="local",
        source=str(tmp_path / "song.mp4"),
        cached_path=str(tmp_path / "song.mp4"),
    )
    library.upsert(entry)

    win = MainWindow(library, base_dir=tmp_path)
    qtbot.addWidget(win)
    win._current_entry = entry

    # Format chooser -> always ".mp4"; save dialog -> a fixed path; no real dialogs.
    monkeypatch.setattr(mw, "_ask_export_format", lambda *_: ".mp4")
    monkeypatch.setattr(
        mw.QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *a, **k: (str(tmp_path / "out.mp4"), "")),
    )
    monkeypatch.setattr(mw, "QProgressDialog", _FakeProgress)
    monkeypatch.setattr(mw, "ExportThread", _FakeThread)
    _FakeThread.instances.clear()

    return win, library, entry


class _FakeProgress:
    def __init__(self, *a, **k):
        self.canceled = _FakeSignal()

    def setWindowModality(self, *_):
        pass

    def setMinimumDuration(self, *_):
        pass

    def setValue(self, *_):
        pass

    def close(self):
        pass


def test_nonzero_vocal_reduce_reaches_filter_chain_and_thread(window, monkeypatch):
    win, _library, _entry = window

    captured = {}
    real_build = mw.build_filter_chain

    def spy_build(pitch, vocal_reduce):
        captured["args"] = (pitch, vocal_reduce)
        return real_build(pitch, vocal_reduce)

    monkeypatch.setattr(mw, "build_filter_chain", spy_build)

    win._on_save(pitch=2, vocal_reduce=60)

    # build_filter_chain saw the REAL vocal reduction, not 0.
    assert captured["args"] == (2, 60)

    # The chain handed to the exporter contains the centre-subtraction pan
    # with mix = (60/100)*0.5 = 0.30.
    assert len(_FakeThread.instances) == 1
    chain = _FakeThread.instances[0].filter_chain
    assert "c0=c0-0.3000*c1" in chain
    assert "c1=c1-0.3000*c0" in chain


def test_save_dialog_default_name_flags_reduced_vocals(window, monkeypatch):
    win, _library, _entry = window
    captured = {}

    def fake_save(*args, **kwargs):
        captured["default_path"] = args[2]
        return (str(Path(args[2])), "")

    monkeypatch.setattr(mw.QFileDialog, "getSaveFileName", staticmethod(fake_save))

    win._on_save(pitch=0, vocal_reduce=60)
    assert "(vocals reduced)" in captured["default_path"]


def test_export_done_persists_real_vocal_reduce_to_library(window, monkeypatch):
    win, library, entry = window

    # The "Saved" confirmation is a modal QMessageBox; stub it so the test
    # never blocks on a dialog.
    monkeypatch.setattr(mw.QMessageBox, "information", staticmethod(lambda *a, **k: None))

    win._on_export_done(str(Path("out.mp4")), pitch=2, vocal_reduce=60, progress=_FakeProgress())

    saved = library.get(entry.id).saved_outputs
    assert len(saved) == 1
    assert saved[0].vocal_reduce == 60
    assert saved[0].pitch == 2


def test_persist_settings_touches_library_with_vocal_reduce(window):
    win, library, entry = window

    win._persist_settings(pitch=3, vocal_reduce=45)

    stored = library.get(entry.id)
    assert stored.last_pitch == 3
    assert stored.last_vocal_reduce == 45
