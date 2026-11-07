from __future__ import annotations

import math
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from nordic_station_classifier import (
    CSV_HEADER,
    Polygon,
    Ring,
    StationRow,
    assign_zone,
    build_csv,
    classify,
    haversine_km,
    percent,
    point_in_polygon,
    point_in_ring,
    ring_bbox,
    safe_round,
    station_class,
)


def square_ring():
    return [[0.0, 0.0], [20.0, 0.0], [20.0, 20.0], [0.0, 20.0]]


def north_countries():
    outer = square_ring()
    box = ring_bbox(outer)
    polygon = Polygon(outer=outer, bbox=box, holes=[])
    ring = Ring(points=outer, bbox=box)
    return {"NOR": {"polygons": [polygon], "rings": [ring]}}


def sample_row():
    return StationRow(
        station_id=1,
        name="****TEST",
        status="ACTIVE",
        lat=59.0,
        lng=10.0,
        country_iso="NOR",
        match_method="EXACT_POLYGON",
        station_class="GEODNET_MINER",
        zone="NO-South-Oslo-Ostlandet",
        dist_to_osls_km=1.5,
        dist_to_trom_km=1110.25,
        dist_to_nya2_km=2000.0,
    )


class GeometryTests(unittest.TestCase):
    def test_ring_bbox(self) -> None:
        self.assertEqual(ring_bbox(square_ring()), (0.0, 0.0, 20.0, 20.0))

    def test_point_in_ring(self) -> None:
        ring = square_ring()
        self.assertTrue(point_in_ring(10.0, 10.0, ring))
        self.assertFalse(point_in_ring(30.0, 10.0, ring))

    def test_point_in_polygon_with_hole(self) -> None:
        outer = square_ring()
        hole = [[8.0, 8.0], [12.0, 8.0], [12.0, 12.0], [8.0, 12.0]]
        polygon = Polygon(outer=outer, bbox=ring_bbox(outer), holes=[(hole, ring_bbox(hole))])
        self.assertTrue(point_in_polygon(2.0, 2.0, polygon))
        self.assertFalse(point_in_polygon(10.0, 10.0, polygon))


class HaversineTests(unittest.TestCase):
    def test_zero_distance(self) -> None:
        self.assertEqual(haversine_km(59.7, 10.3, 59.7, 10.3), 0.0)

    def test_symmetry(self) -> None:
        forward = haversine_km(59.7366, 10.3683, 69.6627, 18.9396)
        backward = haversine_km(69.6627, 18.9396, 59.7366, 10.3683)
        self.assertAlmostEqual(forward, backward, places=6)

    def test_oslo_tromso_distance(self) -> None:
        distance = haversine_km(59.7366, 10.3683, 69.6627, 18.9396)
        self.assertTrue(1000.0 < distance < 1200.0)

    def test_antipodal_is_finite(self) -> None:
        distance = haversine_km(0.0, 0.0, 0.0, 180.0)
        self.assertTrue(math.isfinite(distance))
        self.assertLessEqual(distance, math.pi * 6371.0088 + 1.0)


class ClassificationTests(unittest.TestCase):
    def test_exact_polygon(self) -> None:
        iso, method = classify(10.0, 10.0, north_countries())
        self.assertEqual(iso, "NOR")
        self.assertEqual(method, "EXACT_POLYGON")

    def test_outside_all_polygons(self) -> None:
        iso, method = classify(60.0, 60.0, north_countries())
        self.assertIsNone(iso)
        self.assertIsNone(method)

    def test_coastal_buffer(self) -> None:
        iso, method = classify(10.0, -0.05, north_countries())
        self.assertEqual(iso, "NOR")
        self.assertEqual(method, "COASTAL_BUFFER")


class ZoneTests(unittest.TestCase):
    def test_norway_zones(self) -> None:
        cases = (
            (75.0, 15.0, "NO-Svalbard-Arctic"),
            (66.0, 15.0, "NO-North-Auroral"),
            (63.0, 15.0, "NO-Central-Trondelag"),
            (60.0, 10.0, "NO-South-Oslo-Ostlandet"),
            (60.0, 5.0, "NO-South-West-Vestlandet"),
        )
        for lat, lng, expected in cases:
            with self.subTest(lat=lat, lng=lng):
                self.assertEqual(assign_zone("NOR", lat, lng), expected)

    def test_neighbour_zone(self) -> None:
        self.assertEqual(assign_zone("SWE", 59.0, 18.0), "SE-Sweden")


class FormatTests(unittest.TestCase):
    def test_station_class(self) -> None:
        self.assertEqual(station_class("****ABC"), "GEODNET_MINER")
        self.assertEqual(station_class("OSLS"), "PUBLIC_IGS_EUREF")

    def test_safe_round(self) -> None:
        self.assertEqual(safe_round(float("nan")), 0.0)
        self.assertEqual(safe_round(float("inf")), 0.0)
        self.assertEqual(safe_round(59.123456, 4), 59.1235)

    def test_percent(self) -> None:
        self.assertEqual(percent(1, 4), "25.0%")
        self.assertEqual(percent(0, 0), "0.0%")
        self.assertEqual(percent(5, 0), "0.0%")


class CsvTests(unittest.TestCase):
    def test_header_and_row(self) -> None:
        lines = build_csv([sample_row()]).split("\n")
        self.assertEqual(lines[0], ",".join(CSV_HEADER))
        self.assertIn("****TEST", lines[1])
        self.assertIn("59.00000", lines[1])
        self.assertEqual(lines[-1], "")


if __name__ == "__main__":
    unittest.main()
