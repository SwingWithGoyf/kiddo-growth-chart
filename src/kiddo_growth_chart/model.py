"""The dataset: kids, and heights measured on dates.

Two invariants live here, and both exist because getting them wrong produces a
chart that looks fine and lies.

**Canonical centimetres, with the source preserved.** Practices export inches
with fractions, or centimetres, and a bare ``4`` is unrecoverable once the unit
is gone. Every measurement stores what the source actually said alongside the
converted value.

**Age is measured, never assumed.** Well-child visits cluster near a birthday
without landing on it, so age is always ``visit_date - dob`` in whole days. A
chart that assumes the birthday misaligns the matched-age view by up to a couple
of months, which at ages 0-2 is real height.
"""

from __future__ import annotations

import datetime as dt
import enum
from dataclasses import dataclass, field

CM_PER_INCH = 2.54
DAYS_PER_YEAR = 365.2425  # mean Gregorian year


class Method(enum.Enum):
    """How a measurement was taken. Kept per point, and rendered.

    The spread between these is not noise you can average away: shoes are ~2 cm
    and a spine compresses ~1 cm between morning and night -- both larger than a
    real quarter of growth in a school-age kid. A series that mixes methods
    without saying so shows spurts and *shrinkage* that never happened.
    """

    CLINICAL = "clinical"           # measured at a practice, barefoot, by staff
    HOME_BAREFOOT = "home_barefoot"
    HOME_SHOES = "home_shoes"
    DOORFRAME = "doorframe"         # transcribed pencil marks
    UNKNOWN = "unknown"

    @property
    def is_clinical(self) -> bool:
        return self is Method.CLINICAL


class Unit(enum.Enum):
    CM = "cm"
    IN = "in"

    def to_cm(self, value: float) -> float:
        return value if self is Unit.CM else value * CM_PER_INCH


@dataclass(frozen=True, slots=True)
class Measurement:
    date: dt.date
    cm: float
    method: Method = Method.UNKNOWN
    source_value: float | None = None
    source_unit: Unit | None = None
    note: str = ""

    @classmethod
    def from_source(
        cls,
        date: dt.date,
        value: float,
        unit: Unit | str,
        method: Method | str = Method.UNKNOWN,
        note: str = "",
    ) -> "Measurement":
        unit = Unit(unit) if not isinstance(unit, Unit) else unit
        method = Method(method) if not isinstance(method, Method) else method
        return cls(
            date=date,
            cm=round(unit.to_cm(value), 3),
            method=method,
            source_value=value,
            source_unit=unit,
            note=note,
        )

    def inches(self) -> float:
        return self.cm / CM_PER_INCH

    def feet_inches(self) -> tuple[int, float]:
        """Feet and inches, rounded *before* the split.

        Rounding the remainder instead produces 4'12.0" -- the inches round up
        to a whole foot and the feet never hear about it.
        """
        tenths = round(self.inches() * 10)
        return tenths // 120, (tenths % 120) / 10


@dataclass(frozen=True, slots=True)
class Kid:
    key: str                      # stable id used in URLs, photo folders, config
    name: str
    dob: dt.date
    sex: str | None = None        # "f" | "m" | None -- only used to pick a growth table
    photo_person_id: str | None = None   # provider-side identity, bound by the user
    measurements: tuple[Measurement, ...] = field(default_factory=tuple)

    def sorted_measurements(self) -> list[Measurement]:
        return sorted(self.measurements, key=lambda m: m.date)

    def age_days_at(self, when: dt.date) -> int:
        """Exact age in whole days. The one number the matched-age view turns on."""
        return (when - self.dob).days

    def age_years_at(self, when: dt.date) -> float:
        return self.age_days_at(when) / DAYS_PER_YEAR

    @property
    def mixed_methods(self) -> bool:
        return len({m.method for m in self.measurements}) > 1


@dataclass(frozen=True, slots=True)
class Dataset:
    kids: tuple[Kid, ...]

    def __iter__(self):
        return iter(self.kids)

    def __len__(self) -> int:
        return len(self.kids)

    def by_key(self, key: str) -> Kid:
        for kid in self.kids:
            if kid.key == key:
                return kid
        raise KeyError(key)
