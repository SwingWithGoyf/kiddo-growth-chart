"""Photo sources, behind an interface two calls wide::

    people()                         -> identities this source knows about
    photo_for(person_id, start, end) -> one photo of them in that window

Credentials, face clustering and date handling stay inside the adapter.
``configure(**options)`` receives the user's config, so a provider may take a
URL or a token without this package knowing such things exist.

Subclass :class:`PhotoProvider`, then advertise it::

    [project.entry-points."kiddo_growth_chart.providers"]
    myserver = "my_package.provider:MyProvider"
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FaceBox:
    """Face rectangle in fractions of the image (0-1), not pixels.

    Fractions so a box measured against a thumbnail stays correct against the
    full-size original. May be ``None``: a folder of photos has no faces, and
    the renderer falls back to a centre crop.
    """

    x: float
    y: float
    w: float
    h: float

    def clamped(self) -> "FaceBox":
        x = min(max(self.x, 0.0), 1.0)
        y = min(max(self.y, 0.0), 1.0)
        return FaceBox(x, y, min(self.w, 1.0 - x), min(self.h, 1.0 - y))


@dataclass(frozen=True, slots=True)
class Person:
    """An identity as the source understands it. Bound to a kid by the user."""

    id: str
    name: str
    photo_count: int | None = None


@dataclass(frozen=True, slots=True)
class Photo:
    id: str
    person_id: str
    taken: dt.date
    face: FaceBox | None = None
    full_body: bool = False
    """True when the frame shows the whole child.

    Video mode scales the figure by stature, which is nonsense for a face crop:
    head size barely changes proportionally after early childhood. A provider
    that cannot tell says ``False`` and the renderer keeps the face at constant
    size beside an abstract figure.
    """


class PhotoProvider:
    """Base class. Subclasses override :meth:`people` and :meth:`photo_for`."""

    name = "abstract"

    def configure(self, **options) -> None:
        """Accept user config. Default: nothing to configure."""

    def people(self) -> list[Person]:
        raise NotImplementedError

    def photo_for(
        self,
        person_id: str,
        start: dt.date,
        end: dt.date,
        prefer_full_body: bool = False,
    ) -> Photo | None:
        """Best photo of ``person_id`` taken in ``[start, end]``, or ``None``.

        ``None`` is a real answer: the caller renders the datapoint with no
        portrait. Never widen the window to find something. In a graphic whose
        premise is matched age, an off-by-four-years portrait reads as data.
        """
        raise NotImplementedError

    def image_bytes(self, photo_id: str) -> tuple[bytes, str]:
        """Return ``(data, content_type)``.

        Bytes rather than a URL, so a provider's credential stays in this
        process and never reaches the page.
        """
        raise NotImplementedError


class NullProvider(PhotoProvider):
    """No photos. The default, so the chart works before anything is configured."""

    name = "none"

    def people(self) -> list[Person]:
        return []

    def photo_for(self, person_id, start, end, prefer_full_body=False):
        return None
