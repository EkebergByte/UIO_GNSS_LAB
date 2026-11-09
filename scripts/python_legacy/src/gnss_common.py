from __future__ import annotations

import math
from dataclasses import dataclass


def clamp(value: float, low: float, high: float) -> float:
    if not math.isfinite(value):
        return low
    return max(low, min(high, value))


OSLS_LAT = 59.7366
OSLS_LNG = 10.3683
TROM_LAT = 69.6627
TROM_LNG = 18.9396
NYA2_LAT = 78.9296
NYA2_LNG = 11.8653

EARTH_RADIUS_KM = 6371.0088
KM_PER_DEG_LAT = 110.574
KM_PER_DEG_LNG = 111.320
EPSILON = 1e-12


@dataclass(frozen=True, slots=True)
class Observatory:
    name: str
    lat: float
    lng: float


OBSERVATORIES = (
    Observatory("OSLS", OSLS_LAT, OSLS_LNG),
    Observatory("TROM", TROM_LAT, TROM_LNG),
    Observatory("NYA2", NYA2_LAT, NYA2_LNG),
)
