"""One dataset, two clocks: x is the date measured, or x is ``date - dob``.

Nothing here interpolates. Segments join consecutive measurements as straight
lines, since a spline through points a year apart invents the shape of a spurt
nobody measured, and a segment spanning two methods is flagged so the renderer
can draw it as the guess it is. Video mode is the same pair of projections with
time driving frames rather than the x-axis, so it lives here too.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from enum import Enum

from .model import DAYS_PER_YEAR, Dataset, Kid, Measurement


class Clock(Enum):
    DATE = "date"
    AGE = "age"


@dataclass(frozen=True, slots=True)
class Point:
    x: float                 # days since epoch (DATE) or days since birth (AGE)
    cm: float
    date: dt.date
    age_days: int
    method: str
    label_x: str             # what the axis calls this x

    @property
    def age_years(self) -> float:
        return self.age_days / DAYS_PER_YEAR


@dataclass(frozen=True, slots=True)
class Segment:
    a: Point
    b: Point
    mixed_method: bool       # endpoints measured differently; render as uncertain

    @property
    def cm_gained(self) -> float:
        return self.b.cm - self.a.cm


@dataclass(frozen=True, slots=True)
class Series:
    kid_key: str
    name: str
    points: tuple[Point, ...]
    segments: tuple[Segment, ...]

    @property
    def latest(self) -> Point | None:
        return self.points[-1] if self.points else None


@dataclass(frozen=True, slots=True)
class Projection:
    clock: Clock
    series: tuple[Series, ...]
    x_min: float
    x_max: float
    cm_min: float
    cm_max: float

    @property
    def empty(self) -> bool:
        return not any(s.points for s in self.series)


_EPOCH = dt.date(1970, 1, 1)


def _point(kid: Kid, m: Measurement, clock: Clock) -> Point:
    age_days = kid.age_days_at(m.date)
    if clock is Clock.DATE:
        x, label = (m.date - _EPOCH).days, m.date.isoformat()
    else:
        x, label = float(age_days), f"{age_days / DAYS_PER_YEAR:.1f}y"
    return Point(
        x=float(x),
        cm=m.cm,
        date=m.date,
        age_days=age_days,
        method=m.method.value,
        label_x=label,
    )


def project(dataset: Dataset, clock: Clock | str = Clock.DATE) -> Projection:
    clock = Clock(clock) if not isinstance(clock, Clock) else clock
    series: list[Series] = []
    xs: list[float] = []
    cms: list[float] = []

    for kid in dataset:
        pts = tuple(_point(kid, m, clock) for m in kid.sorted_measurements())
        segs = tuple(
            Segment(a, b, mixed_method=a.method != b.method)
            for a, b in zip(pts, pts[1:])
        )
        series.append(Series(kid.key, kid.name, pts, segs))
        xs.extend(p.x for p in pts)
        cms.extend(p.cm for p in pts)

    if not xs:                      # an empty dataset must still be drawable
        return Projection(clock, tuple(series), 0.0, 1.0, 0.0, 1.0)

    pad = max((max(cms) - min(cms)) * 0.08, 2.0)
    return Projection(
        clock=clock,
        series=tuple(series),
        x_min=min(xs),
        x_max=max(xs),
        cm_min=min(cms) - pad,
        cm_max=max(cms) + pad,
    )


@dataclass(frozen=True, slots=True)
class Frame:
    """One step of video mode: who is how tall now, and who just grew.

    ``grew`` holds the kids whose measurement lands on this frame, and is what
    springs, so the animation asserts growth only where a measurement exists.
    """

    index: int
    label: str
    x: float
    heights: dict[str, float]        # kid key -> cm currently shown (last known)
    grew: tuple[str, ...]            # kid keys whose value changes on this frame
    dates: dict[str, dt.date]        # kid key -> date of the value being shown


def frames(dataset: Dataset, clock: Clock | str = Clock.DATE) -> tuple[Frame, ...]:
    """Discrete frames for video mode, one per real measurement date.

    Visit dates differ, so a shared annual step would assert that four children
    grew at the same moment. Frames are cut at the dates that exist, each naming
    who changed. A kid with no measurement on a frame holds their last known
    height rather than vanishing or drifting.
    """
    clock = Clock(clock) if not isinstance(clock, Clock) else clock
    proj = project(dataset, clock)

    events: dict[float, dict[str, Point]] = {}
    for s in proj.series:
        for p in s.points:
            events.setdefault(p.x, {})[s.kid_key] = p

    out: list[Frame] = []
    heights: dict[str, float] = {}
    dates: dict[str, dt.date] = {}
    for i, x in enumerate(sorted(events)):
        changed = events[x]
        for key, p in changed.items():
            heights[key] = p.cm
            dates[key] = p.date
        label = next(iter(changed.values())).label_x
        out.append(
            Frame(
                index=i,
                label=label,
                x=x,
                heights=dict(heights),
                grew=tuple(sorted(changed)),
                dates=dict(dates),
            )
        )
    return tuple(out)
