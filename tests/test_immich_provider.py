"""The Immich provider against a fake server. No socket is opened here."""

import datetime as dt
import io
import json
import urllib.error

import pytest
from kiddo_growth_chart.providers import immich
from kiddo_growth_chart.providers.immich import ImmichError, ImmichProvider

PERSON = "11111111-2222-4333-8444-555555555555"
ASSET = "99999999-8888-4777-8666-555555555555"
OTHER = "00000000-0000-4000-8000-000000000001"


class FakeResponse(io.BytesIO):
    def __init__(self, payload, ctype=None):
        raw = isinstance(payload, bytes)
        super().__init__(payload if raw else json.dumps(payload).encode())
        self.headers = {"Content-Type": ctype or
                        ("image/jpeg" if raw else "application/json")}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


@pytest.fixture
def server(monkeypatch):
    """Route urlopen to a dict of canned responses, recording every request."""
    calls = []
    routes = {}

    def fake_urlopen(req, timeout=None):
        calls.append((req.method, req.full_url,
                      json.loads(req.data) if req.data else None,
                      req.headers))
        for fragment, payload in routes.items():
            if fragment in req.full_url:
                if isinstance(payload, Exception):
                    raise payload
                return FakeResponse(payload)
        raise AssertionError(f"no route for {req.full_url}")

    monkeypatch.setattr(immich.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(immich, "_cache", {})
    return type("S", (), {"calls": calls, "routes": routes})()


@pytest.fixture
def provider():
    return ImmichProvider(url="https://immich.test", api_key="secret")


def _asset(local="2019-04-11T17:20:00.000Z", asset_id=ASSET):
    return {"id": asset_id, "localDateTime": local, "type": "IMAGE"}


def test_people_are_the_named_clusters_only(server, provider):
    server.routes["/people"] = {"people": [
        {"id": PERSON, "name": "Ada", "isHidden": False},
        {"id": OTHER, "name": "", "isHidden": False},          # unnamed cluster
        {"id": OTHER, "name": "Hidden", "isHidden": True},
    ]}
    people = provider.people()
    assert [(p.id, p.name) for p in people] == [(PERSON, "Ada")]


def test_the_api_key_travels_in_the_header(server, provider):
    server.routes["/people"] = {"people": []}
    provider.people()
    headers = server.calls[0][3]
    assert headers["X-api-key"] == "secret"


def test_the_window_is_sent_and_the_nearest_to_its_middle_wins(server, provider):
    server.routes["/search/metadata"] = {"assets": {"items": [
        _asset("2019-01-02T09:00:00.000Z", OTHER),
        _asset("2019-06-28T09:00:00.000Z", ASSET),     # nearest to 1 July
        _asset("2019-12-30T09:00:00.000Z", OTHER),
    ]}}
    server.routes["/faces"] = []
    p = provider.photo_for(PERSON, dt.date(2019, 1, 1), dt.date(2019, 12, 31))
    assert p.id == ASSET and p.taken == dt.date(2019, 6, 28)
    body = server.calls[0][2]
    assert body["personIds"] == [PERSON]
    assert body["takenAfter"].startswith("2019-01-01")
    assert body["takenBefore"].startswith("2019-12-31")


def test_an_asset_outside_the_window_is_dropped_not_stretched_to_fit(server, provider):
    """The server filters on UTC, so an edge photo can come back a day out."""
    server.routes["/search/metadata"] = {"assets": {"items": [
        _asset("2018-12-31T23:30:00.000Z")]}}
    assert provider.photo_for(PERSON, dt.date(2019, 1, 1), dt.date(2019, 12, 31)) is None


def test_no_photo_in_the_window_is_none(server, provider):
    server.routes["/search/metadata"] = {"assets": {"items": []}}
    assert provider.photo_for(PERSON, dt.date(2016, 1, 1), dt.date(2016, 12, 31)) is None


def test_the_face_box_is_converted_to_fractions(server, provider):
    server.routes["/search/metadata"] = {"assets": {"items": [_asset()]}}
    server.routes["/faces"] = [
        {"person": {"id": OTHER}, "imageWidth": 1000, "imageHeight": 2000,
         "boundingBoxX1": 0, "boundingBoxY1": 0,
         "boundingBoxX2": 100, "boundingBoxY2": 100},
        {"person": {"id": PERSON}, "imageWidth": 1000, "imageHeight": 2000,
         "boundingBoxX1": 200, "boundingBoxY1": 400,
         "boundingBoxX2": 400, "boundingBoxY2": 800},
    ]
    face = provider.photo_for(PERSON, dt.date(2019, 1, 1), dt.date(2019, 12, 31)).face
    assert (face.x, face.y, face.w, face.h) == (0.2, 0.2, 0.2, 0.2)


def test_a_face_belonging_to_someone_else_is_not_used(server, provider):
    server.routes["/search/metadata"] = {"assets": {"items": [_asset()]}}
    server.routes["/faces"] = [
        {"person": {"id": OTHER}, "imageWidth": 100, "imageHeight": 100,
         "boundingBoxX1": 0, "boundingBoxY1": 0,
         "boundingBoxX2": 50, "boundingBoxY2": 50}]
    assert provider.photo_for(PERSON, dt.date(2019, 1, 1), dt.date(2019, 12, 31)).face is None


def test_a_rejected_key_raises_instead_of_reading_as_no_photo(server, provider):
    server.routes["/search/metadata"] = urllib.error.HTTPError(
        "u", 401, "Unauthorized", {}, None)
    with pytest.raises(ImmichError, match="rejected the API key"):
        provider.photo_for(PERSON, dt.date(2019, 1, 1), dt.date(2019, 12, 31))


def test_a_server_error_is_a_missing_portrait_not_a_crash(server, provider):
    server.routes["/search/metadata"] = urllib.error.HTTPError(
        "u", 503, "Unavailable", {}, None)
    assert provider.photo_for(PERSON, dt.date(2019, 1, 1), dt.date(2019, 12, 31)) is None


def test_image_bytes_asks_for_the_preview_rendition(server, provider):
    server.routes[f"/assets/{ASSET}/thumbnail"] = b"\x89PNG\r\n\x1a\n"
    data, ctype = provider.image_bytes(ASSET)
    assert data == b"\x89PNG\r\n\x1a\n"
    assert ctype == "image/jpeg"
    assert "size=preview" in server.calls[0][1]


def test_bytes_are_returned_rather_than_a_url_so_the_key_stays_server_side(
        server, provider):
    server.routes[f"/assets/{ASSET}/thumbnail"] = b"jpegdata"
    data, _ = provider.image_bytes(ASSET)
    assert isinstance(data, bytes) and b"secret" not in data


def test_a_photo_id_that_is_not_a_uuid_never_reaches_the_server(server, provider):
    """The id lands in a URL path, so it is validated before it is interpolated."""
    with pytest.raises(FileNotFoundError):
        provider.image_bytes("../../etc/passwd")
    assert server.calls == []


def test_an_unconfigured_provider_is_empty_rather_than_an_error(server):
    bare = ImmichProvider()
    bare.configure(url=None, api_key=None, api_key_env="NOT_SET_ANYWHERE")
    assert bare.people() == []
    assert bare.photo_for(PERSON, dt.date(2019, 1, 1), dt.date(2019, 12, 31)) is None
    assert server.calls == []


def test_the_key_can_come_from_the_environment(server, monkeypatch):
    monkeypatch.setenv("IMMICH_API_KEY", "from-env")
    p = ImmichProvider(url="https://immich.test")
    server.routes["/people"] = {"people": []}
    p.people()
    assert server.calls[0][3]["X-api-key"] == "from-env"


def test_repeated_windows_are_served_from_cache(server, provider):
    server.routes["/search/metadata"] = {"assets": {"items": [_asset()]}}
    server.routes["/faces"] = []
    for _ in range(3):
        provider.photo_for(PERSON, dt.date(2019, 1, 1), dt.date(2019, 12, 31))
    searches = [c for c in server.calls if "search" in c[1]]
    assert len(searches) == 1
