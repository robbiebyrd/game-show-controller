from gameshow.shows import list_shows, ShowEntry


def _write(dir_path, name, text):
    p = dir_path / name
    p.write_text(text)
    return p


def test_reads_show_name_from_metadata(tmp_path):
    _write(tmp_path, "trivia.yml", "show:\n  name: Trivia Night\n")
    entries = list_shows(str(tmp_path))
    assert entries == [ShowEntry(filename="trivia.yml", name="Trivia Night")]


def test_falls_back_to_filename_stem_when_no_name(tmp_path):
    _write(tmp_path, "faceoff.yaml", "show:\n  scenes: []\n")
    entries = list_shows(str(tmp_path))
    assert entries == [ShowEntry(filename="faceoff.yaml", name="faceoff")]


def test_ignores_non_yaml_files(tmp_path):
    _write(tmp_path, "readme.txt", "not a show")
    _write(tmp_path, "a.yml", "show:\n  name: A\n")
    entries = list_shows(str(tmp_path))
    assert [e.filename for e in entries] == ["a.yml"]


def test_sorted_by_filename(tmp_path):
    _write(tmp_path, "b.yml", "show:\n  name: B\n")
    _write(tmp_path, "a.yml", "show:\n  name: A\n")
    assert [e.filename for e in list_shows(str(tmp_path))] == ["a.yml", "b.yml"]


def test_missing_directory_returns_empty():
    assert list_shows("does/not/exist") == []


def test_malformed_file_is_skipped_gracefully(tmp_path):
    _write(tmp_path, "broken.yml", "show: [this: is, : not valid yaml\n")
    entries = list_shows(str(tmp_path))
    # File still listed, name falls back to the stem; no exception raised.
    assert entries == [ShowEntry(filename="broken.yml", name="broken")]
