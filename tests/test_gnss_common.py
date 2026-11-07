from __future__ import annotations

import math
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from gnss_common import OBSERVATORIES, clamp


class ClampTests(unittest.TestCase):
    def test_finite_value_passes_through(self) -> None:
        self.assertEqual(clamp(5.0, 0.0, 10.0), 5.0)

    def test_below_low_returns_low(self) -> None:
        self.assertEqual(clamp(-3.0, 0.0, 10.0), 0.0)

    def test_above_high_returns_high(self) -> None:
        self.assertEqual(clamp(42.0, 0.0, 10.0), 10.0)

    def test_non_finite_returns_low(self) -> None:
        for bad in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=bad):
                self.assertEqual(clamp(bad, -1.0, 1.0), -1.0)


class ObservatoryTests(unittest.TestCase):
    def test_reference_station_names(self) -> None:
        self.assertEqual([item.name for item in OBSERVATORIES], ["OSLS", "TROM", "NYA2"])

    def test_coordinates_within_globe(self) -> None:
        for item in OBSERVATORIES:
            with self.subTest(name=item.name):
                self.assertTrue(math.isfinite(item.lat) and math.isfinite(item.lng))
                self.assertTrue(-90.0 <= item.lat <= 90.0)
                self.assertTrue(-180.0 <= item.lng <= 180.0)


if __name__ == "__main__":
    unittest.main()
