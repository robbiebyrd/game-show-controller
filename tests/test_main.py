import os
from main import resolve_show_path, SHOWS_DIR


def test_bare_name_resolves_under_shows():
    assert resolve_show_path("jeopardy.yml") == os.path.join(SHOWS_DIR, "jeopardy.yml")


def test_absolute_path_passes_through():
    assert resolve_show_path("/tmp/some-show.yml") == "/tmp/some-show.yml"


def test_existing_literal_path_passes_through(tmp_path):
    path = tmp_path / "here.yml"
    path.write_text("x")
    assert resolve_show_path(str(path)) == str(path)
