"""Photo sources, behind an interface that is two calls wide.

A photo provider answers two questions and nothing else::

    people()                       -> the identities this source knows about
    photo_for(person_id, start, end) -> one photo of that person in that window

Everything source-specific -- credentials, face clustering, whichever endpoint
carries a trustworthy date -- lives inside the adapter and never leaks past it.
That seam is the reason this package exists as a package: written straight
against one photo server, the app absorbs that server's identifiers into its
core and getting them back out is a rewrite rather than a refactor.

**The face box is optional, and that is load-bearing.** A cropped face is what
makes a matched-age row read as a comparison instead of four unrelated
snapshots -- but a plain folder of photos has no faces at all. If the renderer
*required* a box, the plugin model would be theatre: one real provider and a
shape nobody else could fill. So ``FaceBox`` may be ``None`` and the renderer
falls back to a centre crop.

Writing a provider
------------------
Subclass :class:`PhotoProvider`, then advertise it::

    [project.entry-points."kiddo_growth_chart.providers"]
    myserver = "my_package.provider:MyProvider"

``configure(**options)`` receives whatever the user put in their config, so a
provider may take a URL or a token without this package knowing such things
exist.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FaceBox:
    """Face rectangle in *fractions* of the image (0-1), not pixels.

    Fractions so a provider can hand back a box measured against a thumbnail and
    have it stay correct against the full-size original.
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
    """An identity as the *source* understands it. Bound to a kid by the user."""

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

    Video mode needs this. Scaling a *face crop* by stature is nonsense -- head
    size barely changes proportionally after early childhood, so an eight-year
    -old ends up with a toddler's proportions and the animation looks broken.
    A provider that cannot tell says ``False`` and the renderer keeps the face
    at constant size beside an abstract figure.
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

        **Returning ``None`` is a first-class answer, not a failure.** Coverage
        is always thinnest in the earliest years, which is exactly where the
        matched-age view is most interesting. The caller renders the datapoint
        with no portrait. A provider must never widen the window on its own to
        find something: in a graphic whose whole premise is matched age, an
        off-by-four-years portrait is a lie that reads as data.
        """
        raise NotImplementedError

    def image_bytes(self, photo_id: str) -> tuple[bytes, str]:
        """Return ``(data, content_type)``. Bytes, so credentials stay server-side.

        The app proxies images rather than handing the browser a URL, because a
        provider's credential must never reach a page that a wall display or a
        guest's phone can render.
        """
        raise NotImplementedError


class NullProvider(PhotoProvider):
    """No photos. The default, so the chart works before anything is configured."""

    name = "none"

    def people(self) -> list[Person]:
        return []

    def photo_for(self, person_id, start, end, prefer_full_body=False):
        return None
