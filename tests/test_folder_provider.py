import datetime as dt

import pytest
from kiddo_growth_chart.providers.folder import FolderProvider


@pytest.fixture
def root(tmp_path):
    (tmp_path / "ada" / "2019").mkdir(parents=True)
    (tmp_path / "ada" / "2019" / "ada-2019-04-11.png").write_bytes(b"x")
    (tmp_path / "ada" / "2019" / "no-date-here.png").write_bytes(b"x")
    (tmp_path / "ada" / "2021").mkdir()
    (tmp_path / "ada" / "2021" / "whatever.png").write_bytes(b"x")
    return tmp_path


def test_people_are_the_top_level_directories(root):
    people = FolderProvider(root).people()
    assert [p.id for p in people] == ["ada"]
    assert people[0].photo_count == 3


def test_filename_date_beats_the_year_directory(root):
    p = FolderProvider(root).photo_for("ada", dt.date(2019, 1, 1), dt.date(2019, 12, 31))
    assert p.taken == dt.date(2019, 4, 11)


def test_year_directory_is_used_when_the_filename_has_no_date(root):
    p = FolderProvider(root).photo_for("ada", dt.date(2021, 1, 1), dt.date(2021, 12, 31))
    assert p.taken.year == 2021


def test_a_window_with_no_photo_returns_none_and_never_widens(root):
    assert FolderProvider(root).photo_for("ada", dt.date(2016, 1, 1), dt.date(2016, 12, 31)) is None


def test_this_provider_reports_no_faces(root):
    p = FolderProvider(root).photo_for("ada", dt.date(2019, 1, 1), dt.date(2019, 12, 31))
    assert p.face is None and p.full_body is False


def test_photo_id_cannot_escape_the_root(root, tmp_path):
    secret = tmp_path.parent / "secret.png"
    secret.write_bytes(b"nope")
    with pytest.raises(FileNotFoundError):
        FolderProvider(root).image_bytes("../secret.png")


def test_unknown_person_is_none_not_an_error(root):
    assert FolderProvider(root).photo_for("nobody", dt.date(2019, 1, 1), dt.date(2019, 12, 31)) is None


def test_a_guessed_year_date_never_outranks_a_real_filename_date(root):
    """A year-dir date is pinned to mid-year, so nearness alone would hand the
    window to the file whose date is least known."""
    p = FolderProvider(root)
    assert p._date_of(root / "ada" / "2019" / "ada-2019-04-11.png")[1] == 2
    assert p._date_of(root / "ada" / "2019" / "no-date-here.png")[1] == 1
    chosen = p.photo_for("ada", dt.date(2019, 1, 1), dt.date(2019, 12, 31))
    assert chosen.id.endswith("ada-2019-04-11.png")
