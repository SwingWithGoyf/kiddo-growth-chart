import json

import pytest
from kiddo_growth_chart.config import Config
from kiddo_growth_chart.loader import sample_path
from kiddo_growth_chart.web import create_app


@pytest.fixture
def client():
    photos = sample_path().parent / "photos"
    cfg = Config(provider="folder", provider_options={"root": str(photos)})
    app = create_app(cfg)
    app.config.update(TESTING=True)
    return app.test_client()


def test_index_renders(client):
    r = client.get("/")
    assert r.status_code == 200 and b"Growth chart" in r.data


def test_both_clocks_serve_the_same_number_of_points(client):
    a = json.loads(client.get("/data.json?clock=date").data)
    b = json.loads(client.get("/data.json?clock=age").data)
    count = lambda d: sum(len(s["points"]) for s in d["series"])
    assert count(a) == count(b) > 0
    assert a["clock"] == "date" and b["clock"] == "age"


def test_a_year_with_no_photo_is_a_404_not_a_substitute(client):
    assert client.get("/photo/ada/1990").status_code == 404


def test_a_year_with_a_photo_is_served_as_bytes_with_its_true_date(client):
    r = client.get("/photo/ada/2019")
    assert r.status_code == 200
    assert r.headers["X-Photo-Taken"].startswith("2019")
    assert r.data[:8] == b"\x89PNG\r\n\x1a\n"


def test_a_broken_dataset_says_so_instead_of_drawing_an_empty_chart(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text('{"kids": [{"name": "no key"}]}')
    app = create_app(Config(dataset=str(bad)))
    app.config.update(TESTING=True)
    r = app.test_client().get("/")
    assert r.status_code == 500 and b"missing" in r.data


def test_a_date_asks_for_a_window_around_it_not_the_whole_year(client):
    """The sample photo is 15 June, so a tight window on it hits and one on
    April misses -- which is the whole difference from asking for the year."""
    assert client.get("/photo/ada/2019-06-15?window=20").status_code == 200
    assert client.get("/photo/ada/2019-02-01?window=20").status_code == 404


def test_a_narrow_window_that_misses_every_photo_is_a_404(client):
    """Narrower is allowed to find nothing. The renderer draws no portrait."""
    assert client.get("/photo/ada/2019-01-02?window=5").status_code == 404


def test_a_bare_year_still_means_the_whole_year(client):
    r = client.get("/photo/ada/2019")
    assert r.status_code == 200 and r.headers["X-Photo-Taken"].startswith("2019")


def test_an_unparseable_date_is_a_404_not_a_500(client):
    for bad in ("not-a-date", "2019-13-45", "june"):
        assert client.get(f"/photo/ada/{bad}").status_code == 404


def test_the_window_is_bounded_so_a_caller_cannot_ask_for_everything(client):
    """A huge window would quietly become 'any photo ever', which is the lie."""
    from kiddo_growth_chart.web.app import MAX_WINDOW_DAYS, _window
    start, end = _window("2019-06-15", "99999")
    assert (end - start).days == 2 * MAX_WINDOW_DAYS


def test_providers_endpoint_lists_installed_sources(client):
    body = json.loads(client.get("/providers.json").data)
    assert "folder" in body["installed"] and "none" in body["installed"]
    assert {p["id"] for p in body["people"]} >= {"ada", "dov"}
