"""Find providers: the in-tree ones, plus anything installed that advertises itself."""

from __future__ import annotations

from importlib.metadata import entry_points

from . import NullProvider, PhotoProvider
from .folder import FolderProvider

ENTRY_POINT_GROUP = "kiddo_growth_chart.providers"

_BUILTIN: dict[str, type[PhotoProvider]] = {
    NullProvider.name: NullProvider,
    FolderProvider.name: FolderProvider,
}


def available() -> dict[str, type[PhotoProvider]]:
    found = dict(_BUILTIN)
    for ep in entry_points(group=ENTRY_POINT_GROUP):
        if ep.name in found:
            continue          # in-tree wins; a plugin cannot silently shadow it
        try:
            found[ep.name] = ep.load()
        except Exception:      # noqa: BLE001 -- a broken plugin must not break the app
            continue
    return found


def get(name: str, **options) -> PhotoProvider:
    providers = available()
    if name not in providers:
        known = ", ".join(sorted(providers))
        raise KeyError(f"unknown photo provider {name!r} (available: {known})")
    provider = providers[name]()
    provider.configure(**options)
    return provider
