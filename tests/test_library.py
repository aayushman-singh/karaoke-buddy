"""Tests for Library - JSON persistence, round trips, and explicit load failures."""

from pathlib import Path

import pytest

from karaoke_buddy.core.library import Library, LibraryEntry, SavedOutput


@pytest.fixture
def lib_path(tmp_path: Path) -> Path:
    return tmp_path / "library.json"


@pytest.fixture
def lib(lib_path: Path) -> Library:
    return Library(lib_path)


def make_entry(**kwargs) -> LibraryEntry:
    defaults = dict(title="Test Song", source_type="local", source="/path/to/file.mp4")
    defaults.update(kwargs)
    return LibraryEntry(**defaults)


def test_empty_library_list_is_empty(lib):
    assert lib.list() == []


def test_upsert_and_get(lib):
    e = make_entry(title="Hotel California")
    lib.upsert(e)
    fetched = lib.get(e.id)
    assert fetched is not None
    assert fetched.title == "Hotel California"


def test_get_unknown_id_returns_none(lib):
    assert lib.get("nonexistent-id") is None


def test_upsert_updates_existing_entry(lib):
    e = make_entry(title="Original")
    lib.upsert(e)
    e.title = "Updated"
    lib.upsert(e)
    assert lib.get(e.id).title == "Updated"
    assert len(lib.list()) == 1


def test_remove_deletes_entry(lib):
    e = make_entry()
    lib.upsert(e)
    lib.remove(e.id)
    assert lib.get(e.id) is None
    assert lib.list() == []


def test_remove_unknown_id_raises(lib):
    with pytest.raises(KeyError, match="ghost-id"):
        lib.remove("ghost-id")


def test_upsert_writes_to_disk(lib_path, lib):
    lib.upsert(make_entry(title="Persisted"))
    assert lib_path.exists()


def test_round_trip_survives_reload(tmp_path):
    path = tmp_path / "library.json"
    lib1 = Library(path)
    e = make_entry(title="Round-trip Song")
    lib1.upsert(e)

    lib2 = Library(path)
    assert len(lib2.list()) == 1
    assert lib2.list()[0].title == "Round-trip Song"
    assert lib2.list()[0].id == e.id


def test_saved_outputs_survive_round_trip(tmp_path):
    path = tmp_path / "library.json"
    lib1 = Library(path)
    e = make_entry()
    e.saved_outputs.append(
        SavedOutput(
            path="/out/file.mp4",
            pitch=-3,
            vocal_reduce=40,
            saved_at="2026-01-01T00:00:00Z",
        )
    )
    lib1.upsert(e)

    lib2 = Library(path)
    reloaded = lib2.get(e.id)
    assert len(reloaded.saved_outputs) == 1
    assert reloaded.saved_outputs[0].pitch == -3


def test_find_by_source_matches_original_source(lib):
    entry = make_entry(source="C:/Videos/song.mp4")
    lib.upsert(entry)

    assert lib.find_by_source("C:/Videos/song.mp4") == entry


def test_find_by_source_matches_cached_path(lib):
    entry = make_entry(cached_path="cache/youtube-id/video.mp4")
    lib.upsert(entry)

    assert lib.find_by_source("cache/youtube-id/video.mp4") == entry


def test_touch_updates_last_opened_and_settings(lib):
    entry = make_entry(last_opened="2026-01-01T00:00:00+00:00")
    lib.upsert(entry)

    lib.touch(entry.id, pitch=-2, vocal_reduce=35)
    updated = lib.get(entry.id)

    assert updated.last_pitch == -2
    assert updated.last_vocal_reduce == 35
    assert updated.last_opened != "2026-01-01T00:00:00+00:00"


def test_touch_unknown_id_raises(lib):
    with pytest.raises(KeyError, match="ghost-id"):
        lib.touch("ghost-id", pitch=1, vocal_reduce=10)


def test_add_saved_output_appends_record(lib):
    entry = make_entry()
    lib.upsert(entry)

    lib.add_saved_output(entry.id, "C:/Videos/KaraokeBuddy/song.mp4", -1, 20)
    updated = lib.get(entry.id)

    assert len(updated.saved_outputs) == 1
    assert updated.saved_outputs[0].path == "C:/Videos/KaraokeBuddy/song.mp4"
    assert updated.saved_outputs[0].pitch == -1
    assert updated.saved_outputs[0].vocal_reduce == 20


def test_add_saved_output_unknown_id_raises(lib):
    with pytest.raises(KeyError, match="ghost-id"):
        lib.add_saved_output("ghost-id", "C:/Videos/song.mp4", -1, 20)


def test_atomic_write_uses_tmp_file(tmp_path, monkeypatch):
    path = tmp_path / "library.json"
    lib = Library(path)
    tmp_file = path.with_suffix(".tmp")

    written_paths = []
    real_replace = __import__("os").replace

    def spy_replace(src, dst):
        written_paths.append((str(src), str(dst)))
        real_replace(src, dst)

    monkeypatch.setattr("karaoke_buddy.core.library.os.replace", spy_replace)
    lib.upsert(make_entry())

    assert any(str(tmp_file) in p[0] for p in written_paths)
    assert any(str(path) in p[1] for p in written_paths)


def test_corrupted_json_raises_and_preserves_file(tmp_path):
    path = tmp_path / "library.json"
    path.write_text("{ not valid json !!!", encoding="utf-8")

    with pytest.raises(RuntimeError, match="Could not load library"):
        Library(path)

    assert path.exists()
    assert path.read_text(encoding="utf-8") == "{ not valid json !!!"
    assert not list(tmp_path.glob("library.json.corrupted-*"))


def test_list_is_sorted_most_recently_opened_first(lib):
    e1 = make_entry(title="Old", last_opened="2026-01-01T00:00:00Z")
    e2 = make_entry(title="New", last_opened="2026-06-01T00:00:00Z")
    lib.upsert(e1)
    lib.upsert(e2)
    titles = [e.title for e in lib.list()]
    assert titles == ["New", "Old"]
