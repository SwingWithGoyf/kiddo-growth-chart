#!/usr/bin/env python3
"""Regenerate the sample dataset and its placeholder photos.

Everyone here is invented, so the repo ships something that renders on a fresh
clone without a real child's name, birthday or measurement entering git
history. PNGs are written by hand (zlib + struct) to keep this dependency-free.
"""

from __future__ import annotations

import datetime as dt
import json
import struct
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent

KIDS = [
    # key,     name,      dob,          sex, cm at age 1, cm/yr, spurt age
    ("ada",    "Ada",     "2011-03-14", "f", 75.0, 6.5, 11),
    ("bram",   "Bram",    "2013-08-02", "m", 78.5, 6.9, 12),
    ("cleo",   "Cleo",    "2016-11-27", "f", 72.0, 5.8, 10),
    ("dov",    "Dov",     "2019-05-09", "m", 76.0, 6.2, 12),
]
TINT = {"ada": (0xC8, 0xDC, 0xF0), "bram": (0xF4, 0xDF, 0xC4),
        "cleo": (0xC9, 0xE8, 0xDF), "dov": (0xE2, 0xD3, 0xEE)}
TODAY = dt.date(2026, 8, 30)

# Visit offsets from the birthday, in days. Non-zero on purpose: well-child
# visits cluster near a birthday without landing on it, and the sample should
# exercise the age arithmetic rather than flatter it.
OFFSETS = [11, -6, 23, 4, -18, 31, 9, -12, 27, 2, 17, -9, 21, 6, 14, -3, 19]


def height_cm(base: float, rate: float, spurt: int, age: float) -> float:
    """Plausible stature. Invented and only roughly shaped, not a reference."""
    cm = base + rate * (age - 1)
    if age > spurt:                       # a couple of fast years, then a taper
        cm += min(age - spurt, 3) * 2.6
    if age > spurt + 4:
        cm -= (age - spurt - 4) * 1.4
    return round(cm, 1)


def build() -> dict:
    kids = []
    for key, name, dob_s, sex, base, rate, spurt in KIDS:
        dob = dt.date.fromisoformat(dob_s)
        measurements = []
        for age in range(1, 30):
            when = dob.replace(year=dob.year + age) + dt.timedelta(
                days=OFFSETS[age % len(OFFSETS)]
            )
            if when > TODAY:
                break
            cm = height_cm(base, rate, spurt, age)
            # Two non-clinical points, so the dashed mixed-method segment and
            # the hollow marker show up in the sample and not only in a test.
            method = "clinical"
            if key == "ada" and age == 9:
                method, cm = "doorframe", cm + 1.8      # marks read high
            if key == "cleo" and age == 5:
                method, cm = "home_shoes", cm + 2.1     # shoes read high
            measurements.append(
                {"date": when.isoformat(), "value": round(cm / 2.54, 1),
                 "unit": "in", "method": method}
            )
        kids.append({
            "key": key, "name": name, "dob": dob_s, "sex": sex,
            "photo_person_id": key, "measurements": measurements,
        })
    return {
        "_comment": "Invented children. No real person's data belongs in this repo.",
        "kids": kids,
    }


def png(path: Path, rgb: tuple[int, int, int], w: int = 200, h: int = 200) -> None:
    """Minimal solid-colour PNG with a soft vertical ramp, no dependencies."""
    rows = bytearray()
    for y in range(h):
        k = 0.82 + 0.18 * (y / h)
        rows.append(0)                                   # filter type: none
        rows.extend(bytes([int(c * k) for c in rgb]) * w)

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(bytes(rows), 9))
        + chunk(b"IEND", b"")
    )


def main() -> None:
    data = build()
    (HERE / "dataset.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    photos = HERE / "photos"
    for kid in data["kids"]:
        # Not every year gets a photo, so the sample exercises the
        # missing-portrait path.
        years = sorted({m["date"][:4] for m in kid["measurements"]})
        for i, year in enumerate(years):
            if i % 3 == 2:
                continue
            d = photos / kid["key"] / year
            d.mkdir(parents=True, exist_ok=True)
            png(d / f"{kid['key']}-{year}-06-15.png", TINT[kid["key"]])
    counts = {k["key"]: len(k["measurements"]) for k in data["kids"]}
    print("measurements:", counts)


if __name__ == "__main__":
    main()
