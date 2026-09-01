"""A bring-your-own-data height chart for kids.

The only network traffic is whatever a photo provider you configured makes on
your behalf. No CDN, no telemetry, no reference data fetched at runtime.
"""

from .config import Config
from .loader import load, parse
from .model import Dataset, Kid, Measurement, Method, Unit
from .projections import Clock, frames, project

__version__ = "0.1.0"
__all__ = [
    "Config", "Dataset", "Kid", "Measurement", "Method", "Unit",
    "Clock", "frames", "load", "parse", "project",
]
