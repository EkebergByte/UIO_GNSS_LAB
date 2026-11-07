from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from telemetry_ui import (
    PAYLOAD_SOURCES,
    build_body_cached,
    build_cohort,
    build_daily,
    compute_metrics,
    count_stations,
    flap_bin_index,
    source_signature,
)


class DailyTests(unittest.TestCase):
    def test_series_sorted_and_typed(self) -> None:
        daily = {
            "2026-01-02": {"totalActive": 7, "totalOnline": 1, "newActive": 1, "newOnline": 1},
            "2026-01-01": {"totalActive": 5, "totalOnline": 2, "newActive": 2, "newOnline": 1},
        }
        series = build_daily(daily)
        self.assertEqual([item["date"] for item in series], ["2026-01-01", "2026-01-02"])
        self.assertEqual(series[0]["active"], 5)
        self.assertEqual(series[1]["newActive"], 1)

    def test_missing_fields_default_to_zero(self) -> None:
        series = build_daily({"2026-01-01": {}})
        self.assertEqual(series[0]["active"], 0)


class CohortTests(unittest.TestCase):
    def test_cumulative_sum(self) -> None:
        series = [
            {"date": "d1", "newActive": 2, "newOnline": 1},
            {"date": "d2", "newActive": 1, "newOnline": 1},
        ]
        cohort = build_cohort(series)
        self.assertEqual(cohort["total"], 5)
        self.assertEqual([bar["cumulative"] for bar in cohort["bars"]], [3, 5])


class FlapTests(unittest.TestCase):
    def test_bin_boundaries(self) -> None:
        cases = ((0.0, 0), (3.0, 1), (10.0, 2), (30.0, 3), (100.0, 4))
        for value, expected in cases:
            with self.subTest(value=value):
                self.assertEqual(flap_bin_index(value), expected)


class MetricsTests(unittest.TestCase):
    def test_uptime_split(self) -> None:
        timeline = {"X": [(0.0, "ACTIVE"), (10.0, "OFFLINE")]}
        metrics = compute_metrics(timeline, 20.0)
        self.assertEqual(metrics["X"]["uptime_pct"], 50.0)
        self.assertEqual(metrics["X"]["offline_pct"], 50.0)
        self.assertEqual(metrics["X"]["transitions"], 1)

    def test_short_series_is_ignored(self) -> None:
        timeline = {"Y": [(0.0, "ACTIVE")]}
        self.assertEqual(compute_metrics(timeline, 20.0), {})


class CountTests(unittest.TestCase):
    def test_counts_valid_rows(self) -> None:
        handle = tempfile.NamedTemporaryFile(
            "w", suffix=".csv", delete=False, encoding="utf-8", newline=""
        )
        handle.write("station_id,name,status,lat,lng\n")
        handle.write("1,AAA,ACTIVE,59.0,10.0\n")
        handle.write("2,BBB,ONLINE,bad,10.0\n")
        handle.close()
        try:
            self.assertEqual(count_stations(handle.name), 1)
        finally:
            os.remove(handle.name)

    def test_missing_file_returns_zero(self) -> None:
        self.assertEqual(count_stations(os.path.join(ROOT, "does_not_exist.csv")), 0)


class CacheTests(unittest.TestCase):
    def test_signature_shape(self) -> None:
        self.assertEqual(len(source_signature()), len(PAYLOAD_SOURCES))

    def test_body_is_stable_and_valid(self) -> None:
        first = build_body_cached()
        second = build_body_cached()
        self.assertEqual(first, second)
        payload = json.loads(first.decode("utf-8"))
        self.assertIn("totals", payload)
        self.assertIn("stations", payload)


if __name__ == "__main__":
    unittest.main()
