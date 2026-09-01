"""Photos from a directory tree. The reference provider.

Layout::

    <root>/<person>/<anything>-2019-04-11.jpg
    <root>/<person>/2019/whatever.jpg

Dates come from the filename, else the enclosing year directory, else mtime.
An mtime is weakest: a copy or a sync rewrites it, redating a 2009 photo to
whenever the drive was last touched.

Confidence outranks closeness when picking between candidates. A year-directory
date is pinned to mid-year, landing dead centre of a calendar-year window, so
ranking by nearness alone would hand every contest to the weakest provenance.
"""

from __future__ import annotations

import datetime as dt
import mimetypes
import re
from pathlib import Path

from . import Person, Photo, PhotoProvider

SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".heic", ".avif"}
_DATE_IN_NAME = re.compile(r"(19|20)\d{2}[-_]?(0[1-9]|1[0-2])[-_]?(0[1-9]|[12]\d|3[01])")
_YEAR_DIR = re.compile(r"^(19|20)\d{2}$")


class FolderProvider(PhotoProvider):
    name = "folder"

    def __init__(self, root: str | Path | None = None):
        self.root = Path(root).expanduser() if root else None

    def configure(self, root: str | Path | None = None, **_ignored) -> None:
        if root:
            self.root = Path(root).expanduser()

    # -- discovery ---------------------------------------------------------
    def people(self) -> list[Person]:
        if not self.root or not self.root.is_dir():
            return []
        out = []
        for child in sorted(self.root.iterdir()):
            if child.is_dir() and not child.name.startswith("."):
                out.append(
                    Person(id=child.name, name=child.name, photo_count=len(self._files(child)))
                )
        return out

    def photo_for(self, person_id, start, end, prefer_full_body=False) -> Photo | None:
        if not self.root:
            return None
        person_dir = (self.root / person_id).resolve()
        if not self._inside_root(person_dir) or not person_dir.is_dir():
            return None

        candidates = []
        for f in self._files(person_dir):
            dated = self._date_of(f)
            if dated and start <= dated[0] <= end:
                candidates.append((*dated, f))
        if not candidates:
            return None      # never widen the window; see PhotoProvider.photo_for

        # Middle of the window, so "age 8" gets a photo from the middle of being
        # eight rather than the day after the birthday.
        target = start + (end - start) / 2
        taken, _confidence, path = min(
            candidates, key=lambda c: (-c[1], abs(c[0] - target))
        )
        return Photo(
            id=str(path.relative_to(self.root)),
            person_id=person_id,
            taken=taken,
            face=None,              # a folder knows nothing about faces
            full_body=False,
        )

    def image_bytes(self, photo_id: str) -> tuple[bytes, str]:
        if not self.root:
            raise FileNotFoundError(photo_id)
        path = (self.root / photo_id).resolve()
        if not self._inside_root(path) or not path.is_file():
            raise FileNotFoundError(photo_id)   # blocks ../ traversal via photo id
        ctype, _ = mimetypes.guess_type(path.name)
        return path.read_bytes(), ctype or "application/octet-stream"

    # -- internals ---------------------------------------------------------
    def _inside_root(self, path: Path) -> bool:
        try:
            path.relative_to(self.root.resolve())
        except (ValueError, AttributeError):
            return False
        return True

    @staticmethod
    def _files(directory: Path) -> list[Path]:
        return sorted(
            p for p in directory.rglob("*")
            if p.is_file() and p.suffix.lower() in SUFFIXES and not p.name.startswith(".")
        )

    @staticmethod
    def _date_of(path: Path) -> tuple[dt.date, int] | None:
        """Return ``(date, confidence)``; higher confidence is a better-known date.

        2 = stated in the filename, 1 = a year directory (day unknown, pinned to
        mid-year), 0 = mtime, a fact about the filesystem rather than the photo.
        """
        if m := _DATE_IN_NAME.search(path.stem):
            digits = re.sub(r"[-_]", "", m.group(0))
            try:
                return dt.date(int(digits[:4]), int(digits[4:6]), int(digits[6:8])), 2
            except ValueError:
                pass
        for parent in path.parents:
            if _YEAR_DIR.match(parent.name):
                return dt.date(int(parent.name), 7, 1), 1
        try:
            return dt.date.fromtimestamp(path.stat().st_mtime), 0
        except OSError:
            return None
