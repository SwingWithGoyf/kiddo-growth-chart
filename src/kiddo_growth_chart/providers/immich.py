"""Photos from an Immich server.

Immich clusters faces into people, which is the identity this provider hands
back: a kid's ``photo_person_id`` is an Immich person UUID, bound once by the
user. It also stores a bounding box per detected face, so unlike ``folder``
this provider can fill in :class:`FaceBox` and let the renderer crop to the
child rather than to the middle of the frame.

Configure it with a server URL and an API key (Account Settings -> API Keys)::

    {
      "provider": "immich",
      "provider_options": {"url": "https://immich.example.com",
                           "api_key_env": "IMMICH_API_KEY"}
    }

The key is read from the environment by default so it stays out of the config
file. ``api_key`` may be given inline instead.

A bad key raises rather than returning ``None``. Returning nothing would render
as "no photo of this kid that year", which is exactly the failure that hides a
misconfiguration behind a plausible-looking chart. Timeouts and server errors do
return ``None``, since those are transient and a missing portrait is a state the
renderer already draws.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

from . import FaceBox, Person, Photo, PhotoProvider

UUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
                  r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
SEARCH_PAGE = 1000          # Immich's documented maximum for one search page
CACHE_TTL = 300.0
CACHE_MAX = 512


class ImmichError(RuntimeError):
    """The server rejected us. Loud, because a silent None reads as 'no photo'."""


_cache: dict[tuple, tuple[float, object]] = {}


def _cached(key, produce):
    now = time.monotonic()
    hit = _cache.get(key)
    if hit and hit[0] > now:
        return hit[1]
    value = produce()
    if len(_cache) >= CACHE_MAX:
        _cache.clear()
    _cache[key] = (now + CACHE_TTL, value)
    return value


class ImmichProvider(PhotoProvider):
    name = "immich"

    def __init__(self, url: str | None = None, api_key: str | None = None,
                 api_key_env: str = "IMMICH_API_KEY", timeout: float = 10.0):
        self.configure(url=url, api_key=api_key, api_key_env=api_key_env,
                       timeout=timeout)

    def configure(self, url=None, api_key=None, api_key_env="IMMICH_API_KEY",
                  timeout=10.0, **_ignored) -> None:
        self.base = _base_url(url) if url else None
        self.api_key = api_key or os.environ.get(api_key_env or "") or None
        self.timeout = float(timeout)

    # -- discovery ---------------------------------------------------------
    def people(self) -> list[Person]:
        """Named people only.

        An Immich library holds far more unnamed face clusters than named ones,
        and an unnamed cluster is not something a human can bind a kid to.

        ``photo_count`` is None: Immich reports it per person on a separate
        endpoint, and one request per cluster is not worth it here.
        """
        if not self.base or not self.api_key:
            return []
        body = self._get("/people", {"withHidden": "false", "size": "1000"})
        return [
            Person(id=p["id"], name=p["name"], photo_count=None)
            for p in body.get("people", [])
            if p.get("name") and not p.get("isHidden")
        ]

    def photo_for(self, person_id, start, end, prefer_full_body=False) -> Photo | None:
        if not self.base or not self.api_key or not UUID.match(person_id or ""):
            return None
        return _cached(
            (self.base, person_id, start, end),
            lambda: self._search(person_id, start, end),
        )

    def _search(self, person_id, start, end) -> Photo | None:
        try:
            body = self._post("/search/metadata", {
                # These flat fields are deprecated in favour of `filter` from
                # Immich 3.2, but still accepted, and they are the only form
                # older servers understand.
                "personIds": [person_id],
                "takenAfter": f"{start.isoformat()}T00:00:00.000Z",
                "takenBefore": f"{end.isoformat()}T23:59:59.999Z",
                "type": "IMAGE",
                "size": SEARCH_PAGE,
                "withExif": False,
            })
        except ImmichError:
            raise
        except OSError:
            return None      # transient; the renderer draws no portrait

        candidates = []
        for asset in body.get("assets", {}).get("items", []):
            taken = _taken_on(asset)
            # Re-check the window ourselves: the server filters on UTC, which
            # can drag an edge photo a day out of the year we asked for. Never
            # widen -- see PhotoProvider.photo_for.
            if taken and start <= taken <= end:
                candidates.append((taken, asset["id"]))
        if not candidates:
            return None

        target = start + (end - start) / 2
        taken, asset_id = min(candidates, key=lambda c: abs(c[0] - target))
        return Photo(
            id=asset_id,
            person_id=person_id,
            taken=taken,
            face=self._face(asset_id, person_id),
            full_body=False,   # Immich exposes no such signal; see below
        )

    def _face(self, asset_id: str, person_id: str) -> FaceBox | None:
        """This person's face in this asset, as fractions of the image.

        Immich gives pixel coordinates against the full-size original, so they
        are divided down here. An asset may carry several faces; only this
        person's is wanted.
        """
        try:
            faces = self._get("/faces", {"id": asset_id})
        except (ImmichError, OSError):
            return None
        for f in faces or []:
            if (f.get("person") or {}).get("id") != person_id:
                continue
            w, h = f.get("imageWidth") or 0, f.get("imageHeight") or 0
            if not w or not h:
                return None
            return FaceBox(
                x=f["boundingBoxX1"] / w,
                y=f["boundingBoxY1"] / h,
                w=(f["boundingBoxX2"] - f["boundingBoxX1"]) / w,
                h=(f["boundingBoxY2"] - f["boundingBoxY1"]) / h,
            ).clamped()
        return None

    def image_bytes(self, photo_id: str) -> tuple[bytes, str]:
        """The preview rendition, not the original.

        A phone original is several megabytes for a portrait drawn 120px wide,
        and the preview is already downscaled server-side.
        """
        if not self.base or not self.api_key or not UUID.match(photo_id or ""):
            raise FileNotFoundError(photo_id)
        req = self._request(f"/assets/{photo_id}/thumbnail?size=preview")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                return r.read(), r.headers.get("Content-Type", "image/jpeg")
        except (urllib.error.URLError, OSError) as exc:
            raise FileNotFoundError(photo_id) from exc

    # -- transport ---------------------------------------------------------
    def _request(self, path: str, data: bytes | None = None) -> urllib.request.Request:
        return urllib.request.Request(
            f"{self.base}{path}",
            data=data,
            headers={
                "x-api-key": self.api_key,
                "Accept": "application/json",
                **({"Content-Type": "application/json"} if data else {}),
            },
            method="POST" if data else "GET",
        )

    def _open(self, req):
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                return json.loads(r.read() or b"null")
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                raise ImmichError(
                    f"Immich rejected the API key ({exc.code}) for {self.base}"
                ) from exc
            raise OSError(f"Immich {exc.code} for {req.full_url}") from exc

    def _get(self, path: str, params: dict | None = None):
        query = "&".join(f"{k}={urllib.parse.quote(str(v))}"
                         for k, v in (params or {}).items())
        return self._open(self._request(f"{path}?{query}" if query else path))

    def _post(self, path: str, body: dict):
        return self._open(self._request(path, json.dumps(body).encode("utf-8")))


def _base_url(url: str) -> str:
    """Accept what a user pastes: with or without the /api suffix or a slash."""
    url = url.rstrip("/")
    return url if url.endswith("/api") else url + "/api"


def _taken_on(asset: dict) -> dt.date | None:
    """The calendar date the photo was taken.

    ``localDateTime`` is the photographer's wall clock from EXIF, which is the
    date a human would put on the photo. The string is sliced rather than parsed
    into an aware datetime on purpose: converting to UTC first can move a
    late-evening photo onto the next day, and the year is what we key on.
    """
    stamp = asset.get("localDateTime") or asset.get("fileCreatedAt")
    try:
        return dt.date.fromisoformat(stamp[:10])
    except (TypeError, ValueError):
        return None
