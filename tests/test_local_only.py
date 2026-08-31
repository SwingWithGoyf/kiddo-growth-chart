"""The claim the whole project is chosen for, as a test rather than a promise.

Rendering a chart must make **no** outbound connection. Any socket that is not
loopback fails here, and the assets are scanned for third-party URLs, because a
single CDN font would quietly make an offline machine the one place this tool
does not work.
"""

from __future__ import annotations

import json
import re
import socket
from pathlib import Path

import pytest
from kiddo_growth_chart.config import Config
from kiddo_growth_chart.loader import sample_path
from kiddo_growth_chart.web import create_app

ASSETS = Path(__file__).resolve().parent.parent / "src" / "kiddo_growth_chart" / "web"
LOOPBACK = {"127.0.0.1", "::1", "localhost"}


@pytest.fixture
def no_outbound(monkeypatch):
    calls = []
    real = socket.socket.connect

    def guarded(self, address, *a, **kw):
        host = address[0] if isinstance(address, tuple) else str(address)
        if host not in LOOPBACK:
            calls.append(host)
            raise AssertionError(f"outbound connection attempted to {host}")
        return real(self, address, *a, **kw)

    monkeypatch.setattr(socket.socket, "connect", guarded)
    return calls


def test_rendering_makes_no_outbound_connection(no_outbound):
    photos = sample_path().parent / "photos"
    app = create_app(Config(provider="folder", provider_options={"root": str(photos)}))
    app.config.update(TESTING=True)
    c = app.test_client()
    assert c.get("/").status_code == 200
    assert json.loads(c.get("/data.json?clock=age").data)["series"]
    c.get("/photo/ada/2019")
    assert no_outbound == []


@pytest.mark.parametrize("path", sorted(
    [*ASSETS.glob("templates/*.html"), *ASSETS.glob("static/*")], key=str))
def test_no_asset_references_a_third_party_host(path):
    text = path.read_text(encoding="utf-8")
    urls = re.findall(r"""https?://[^\s"'<>)]+""", text)
    external = [u for u in urls
                if not re.match(r"https?://(127\.0\.0\.1|localhost|\[::1\])", u)
                and not u.startswith("http://www.w3.org/")]  # SVG namespace, not a fetch
    assert external == [], f"{path.name} would fetch from {external}"


def test_no_growth_table_is_fetched_at_runtime():
    """Reference data is vendored or absent -- never downloaded on first run."""
    src = (ASSETS.parent / "growth" / "lms.py").read_text(encoding="utf-8")
    assert "urllib" not in src and "requests" not in src and "http" not in src.split('"""')[2]
