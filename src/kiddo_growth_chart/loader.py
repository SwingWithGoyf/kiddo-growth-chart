"""Read and validate a dataset file.

Every problem raises, naming the kid and index that caused it: a dropped
measurement is invisible on a chart, the line just goes somewhere else.
"""

from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path

from .model import Dataset, Kid, Measurement, Method, Unit

ENV_VAR = "KIDDO_DATASET"


class DatasetError(ValueError):
    """The dataset file is unusable. Message names the offending record."""


def _date(value: str, where: str) -> dt.date:
    try:
        return dt.date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise DatasetError(f"{where}: bad date {value!r}, expected YYYY-MM-DD") from exc


def parse(raw: dict) -> Dataset:
    if not isinstance(raw, dict) or "kids" not in raw:
        raise DatasetError("dataset must be an object with a 'kids' list")

    kids: list[Kid] = []
    seen: set[str] = set()
    for i, k in enumerate(raw["kids"]):
        where = f"kids[{i}]"
        for required in ("key", "name", "dob"):
            if required not in k:
                raise DatasetError(f"{where}: missing {required!r}")
        key = k["key"]
        if key in seen:
            raise DatasetError(f"{where}: duplicate key {key!r}")
        seen.add(key)
        dob = _date(k["dob"], f"{where}.dob")

        measurements: list[Measurement] = []
        for j, m in enumerate(k.get("measurements", [])):
            mwhere = f"{where}.measurements[{j}]"
            if "date" not in m:
                raise DatasetError(f"{mwhere}: missing 'date'")
            when = _date(m["date"], f"{mwhere}.date")
            if when < dob:
                raise DatasetError(
                    f"{mwhere}: measured {when} before date of birth {dob}"
                )
            if "value" in m:
                try:
                    unit = Unit(m.get("unit", "cm"))
                except ValueError as exc:
                    raise DatasetError(f"{mwhere}: unknown unit {m.get('unit')!r}") from exc
                value = float(m["value"])
            elif "cm" in m:                      # shorthand
                unit, value = Unit.CM, float(m["cm"])
            else:
                raise DatasetError(f"{mwhere}: needs 'value' (+'unit') or 'cm'")
            if value <= 0:
                raise DatasetError(f"{mwhere}: non-positive height {value!r}")
            try:
                method = Method(m.get("method", "unknown"))
            except ValueError as exc:
                known = ", ".join(x.value for x in Method)
                raise DatasetError(
                    f"{mwhere}: unknown method {m.get('method')!r} (known: {known})"
                ) from exc
            measurements.append(
                Measurement.from_source(when, value, unit, method, m.get("note", ""))
            )

        dupes = {d for d in (x.date for x in measurements)
                 if [x.date for x in measurements].count(d) > 1}
        if dupes:
            raise DatasetError(
                f"{where}: two measurements on {sorted(dupes)[0]}; "
                "the chart cannot draw two heights on one date"
            )

        kids.append(
            Kid(
                key=key,
                name=k["name"],
                dob=dob,
                sex=k.get("sex"),
                photo_person_id=k.get("photo_person_id"),
                measurements=tuple(sorted(measurements, key=lambda m: m.date)),
            )
        )

    if not kids:
        raise DatasetError("dataset contains no kids")
    return Dataset(kids=tuple(kids))


def load(path: str | os.PathLike | None = None) -> Dataset:
    """Load the dataset at ``path``, else ``$KIDDO_DATASET``, else the sample.

    Falling back to the sample is what lets a fresh clone render before anyone
    has written a config.
    """
    if path is None:
        path = os.environ.get(ENV_VAR) or sample_path()
    p = Path(path)
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise DatasetError(f"no dataset at {p} (set ${ENV_VAR})") from exc
    except json.JSONDecodeError as exc:
        raise DatasetError(f"{p}: invalid JSON at line {exc.lineno}: {exc.msg}") from exc
    return parse(raw)


def sample_path() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "sample" / "dataset.json"
