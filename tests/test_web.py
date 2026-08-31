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


def test_providers_endpoint_lists_installed_sources(client):
    body = json.loads(client.get("/providers.json").data)
    assert "folder" in body["installed"] and "none" in body["installed"]
    assert {p["id"] for p in body["people"]} >= {"ada", "dov"}
