"""Percentile bands from LMS parameters. Computed locally, from vendored tables.

Reference growth data (CDC stature-for-age 2-20, WHO length/height-for-age under
2) is published as **LMS parameters** -- a skewness ``L``, median ``M`` and
coefficient of variation ``S`` per sex per age -- from which any percentile is
arithmetic::

    X = M (1 + L S Z)^(1/L)      for L != 0
    X = M exp(S Z)               for L == 0

So bands need no API, no key, and no network. **Tables are vendored into the
repo, never fetched at runtime**: a first-run download would break the
local-only promise on precisely the machine that chose this tool for it.

No table ships in this scaffold. ``tables/`` documents the expected CSV columns
and where to get the data; until a file is dropped in, band rendering is simply
off. That is deliberate -- inventing plausible-looking reference values would be
worse than having none, since a wrong percentile is a medical-sounding claim.

Bands default to **off** in the UI regardless. A family keepsake and a growth
percentile are different objects, and the second one turns a chart on the wall
into something a parent can worry at.
"""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path

TABLE_DIR = Path(__file__).resolve().parent / "tables"
REQUIRED_COLUMNS = {"sex", "age_days", "l", "m", "s"}


@dataclass(frozen=True, slots=True)
class LMSRow:
    sex: str
    age_days: float
    l: float
    m: float
    s: float


@dataclass(frozen=True, slots=True)
class LMSTable:
    name: str
    rows: tuple[LMSRow, ...]

    def for_sex(self, sex: str) -> list[LMSRow]:
        return sorted((r for r in self.rows if r.sex == sex), key=lambda r: r.age_days)

    def at(self, sex: str, age_days: float) -> LMSRow | None:
        """Nearest row by age. Tables are dense (monthly), so nearest is honest."""
        rows = self.for_sex(sex)
        if not rows:
            return None
        return min(rows, key=lambda r: abs(r.age_days - age_days))


def percentile_to_cm(row: LMSRow, percentile: float) -> float:
    """Height at a percentile (0 < p < 100) for this age/sex row."""
    if not 0 < percentile < 100:
        raise ValueError("percentile must be strictly between 0 and 100")
    return _from_z(row, _z_from_percentile(percentile / 100.0))


def cm_to_percentile(row: LMSRow, cm: float) -> float:
    if row.l == 0:
        z = math.log(cm / row.m) / row.s
    else:
        z = ((cm / row.m) ** row.l - 1) / (row.l * row.s)
    return _normal_cdf(z) * 100.0


def _from_z(row: LMSRow, z: float) -> float:
    if row.l == 0:
        return row.m * math.exp(row.s * z)
    return row.m * (1 + row.l * row.s * z) ** (1 / row.l)


def _normal_cdf(z: float) -> float:
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


def _z_from_percentile(p: float) -> float:
    """Inverse normal CDF by bisection -- exact enough, and keeps scipy out."""
    lo, hi = -6.0, 6.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if _normal_cdf(mid) < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def available_tables() -> list[str]:
    return sorted(p.stem for p in TABLE_DIR.glob("*.csv"))


def load_table(name: str) -> LMSTable:
    path = TABLE_DIR / f"{name}.csv"
    if not path.is_file():
        raise FileNotFoundError(
            f"no vendored growth table {name!r} in {TABLE_DIR} "
            f"(see {TABLE_DIR / 'README.md'}); bands stay off until one is added"
        )
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{path}: missing columns {sorted(missing)}")
        rows = tuple(
            LMSRow(
                sex=r["sex"].strip().lower()[:1],
                age_days=float(r["age_days"]),
                l=float(r["l"]),
                m=float(r["m"]),
                s=float(r["s"]),
            )
            for r in reader
        )
    return LMSTable(name=name, rows=rows)
