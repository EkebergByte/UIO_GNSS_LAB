from __future__ import annotations

import csv
import io
import json
import math
import os
import sys
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from gnss_common import (
    EARTH_RADIUS_KM,
    EPSILON,
    KM_PER_DEG_LAT,
    KM_PER_DEG_LNG,
    NYA2_LAT,
    NYA2_LNG,
    OSLS_LAT,
    OSLS_LNG,
    TROM_LAT,
    TROM_LNG,
    clamp,
)

API_URL = "https://rtk.geodnet.com/api/v2/coverage_stations"
NE_URL = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/v5.1.2/geojson/ne_10m_admin_0_countries.geojson"
NE_FALLBACK_URL = "https://raw.githubusercontent.com/datasets/geo-countries/main/data/countries.geojson"
HTTP_TIMEOUT = 20
NE_TIMEOUT = 90

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
SNAPSHOT_FILE = os.path.join(DATA_DIR, "global_stations_snapshot.json")
NE_RAW_FILE = os.path.join(DATA_DIR, "ne_10m_admin_0_countries.geojson")
BOUNDARY_FILE = os.path.join(DATA_DIR, "nordic_boundaries_10m.geojson")
CSV_FILE = os.path.join(DATA_DIR, "nordic_geodnet_stations.csv")
NORWAY_CSV_FILE = os.path.join(DATA_DIR, "norway_only_stations.csv")
REPORT_TEMPLATE = os.path.join(BASE_DIR, "docs", "report_template.md")
REPORT_FILE = os.path.join(BASE_DIR, "docs", "NORDIC_NETWORK_REPORT.md")
README_TEMPLATE = os.path.join(BASE_DIR, "docs", "readme_template.md")
README_FILE = os.path.join(BASE_DIR, "README.md")

CANDIDATE_MIN_LAT = 53.0
CANDIDATE_MAX_LAT = 82.0
CANDIDATE_MIN_LNG = -30.0
CANDIDATE_MAX_LNG = 35.0

SVALBARD_MIN_LAT = 74.0
NORTH_LAT_THRESHOLD = 65.0
CENTRAL_LAT_THRESHOLD = 62.0
OSLO_LNG_THRESHOLD = 9.0

COASTAL_BUFFER_KM = 20.0
COASTAL_MARGIN_FACTOR = 1.5
MISSING_DISTANCE = 1.0e9

PROPERTY_FIELDS = ("ADM0_A3", "ISO_A3_EH", "SOV_A3", "ISO3166-1-Alpha-3", "ISO_A3")
EXACT_ORDER = ("NOR", "SWE", "FIN", "DNK", "ISL", "RUS", "EST", "LVA", "GBR", "DEU")
BUFFER_ORDER = ("NOR", "SWE", "FIN", "DNK", "ISL", "RUS")
NORDIC_KEEP = ("NOR", "SWE", "FIN", "DNK", "ISL")
NAME_TO_ISO = {
    "Norway": "NOR",
    "Sweden": "SWE",
    "Finland": "FIN",
    "Denmark": "DNK",
    "Iceland": "ISL",
    "Russia": "RUS",
    "Estonia": "EST",
    "Latvia": "LVA",
    "United Kingdom": "GBR",
    "Germany": "DEU",
}
TARGET_SET = frozenset(NAME_TO_ISO.values())
ZONE_BY_ISO = {
    "SWE": "SE-Sweden",
    "FIN": "FI-Finland",
    "DNK": "DK-Denmark",
    "ISL": "IS-Iceland",
}

CSV_HEADER = [
    "station_id",
    "name",
    "status",
    "lat",
    "lng",
    "country_iso",
    "match_method",
    "station_class",
    "zone",
    "dist_to_osls_km",
    "dist_to_trom_km",
    "dist_to_nya2_km",
]


@dataclass(frozen=True, slots=True)
class Station:
    station_id: int
    name: str
    status: str
    lat: float
    lng: float


@dataclass(frozen=True, slots=True)
class StationRow:
    station_id: int
    name: str
    status: str
    lat: float
    lng: float
    country_iso: str
    match_method: str
    station_class: str
    zone: str
    dist_to_osls_km: float
    dist_to_trom_km: float
    dist_to_nya2_km: float


@dataclass(frozen=True, slots=True)
class Ring:
    points: list
    bbox: tuple


@dataclass(frozen=True, slots=True)
class Polygon:
    outer: list
    bbox: tuple
    holes: list


def safe_round(value: float, digits: int = 4) -> float:
    if not math.isfinite(value):
        return 0.0
    return round(value, digits)


def ring_bbox(ring: list) -> tuple:
    min_x = ring[0][0]
    max_x = min_x
    min_y = ring[0][1]
    max_y = min_y
    for point in ring:
        x = point[0]
        y = point[1]
        if x < min_x:
            min_x = x
        elif x > max_x:
            max_x = x
        if y < min_y:
            min_y = y
        elif y > max_y:
            max_y = y
    return (min_x, min_y, max_x, max_y)


def point_in_bbox(lng: float, lat: float, bbox: tuple) -> bool:
    min_x, min_y, max_x, max_y = bbox
    return (min_x <= lng <= max_x) and (min_y <= lat <= max_y)


def point_in_ring(lng: float, lat: float, ring: list) -> bool:
    count = len(ring)
    if count < 3:
        return False
    inside = False
    x = lng
    y = lat
    j = count - 1
    for i in range(count):
        xi = ring[i][0]
        yi = ring[i][1]
        xj = ring[j][0]
        yj = ring[j][1]
        if (yi > y) != (yj > y):
            denominator = yj - yi
            if abs(denominator) > EPSILON:
                intersect = (xj - xi) * (y - yi) / denominator + xi
                if x < intersect:
                    inside = not inside
        j = i
    return inside


def point_in_polygon(lng: float, lat: float, polygon: Polygon) -> bool:
    if not point_in_bbox(lng, lat, polygon.bbox):
        return False
    if not point_in_ring(lng, lat, polygon.outer):
        return False
    for hole, hole_box in polygon.holes:
        if point_in_bbox(lng, lat, hole_box) and point_in_ring(lng, lat, hole):
            return False
    return True


def point_segment_km(lng: float, lat: float, x1: float, y1: float, x2: float, y2: float) -> float:
    lat_ref = math.radians(clamp(lat, -90.0, 90.0))
    kx = KM_PER_DEG_LNG * math.cos(lat_ref)
    ky = KM_PER_DEG_LAT
    ax = (x1 - lng) * kx
    ay = (y1 - lat) * ky
    bx = (x2 - lng) * kx
    by = (y2 - lat) * ky
    abx = bx - ax
    aby = by - ay
    denominator = abx * abx + aby * aby
    if denominator <= EPSILON:
        distance = math.hypot(ax, ay)
    else:
        t = -(ax * abx + ay * aby) / denominator
        t = clamp(t, 0.0, 1.0)
        cx = ax + t * abx
        cy = ay + t * aby
        distance = math.hypot(cx, cy)
    if not math.isfinite(distance):
        return MISSING_DISTANCE
    return distance


def ring_min_distance(lng: float, lat: float, ring: list) -> float:
    count = len(ring)
    if count < 2:
        return MISSING_DISTANCE
    best = MISSING_DISTANCE
    for i in range(count):
        x1 = ring[i][0]
        y1 = ring[i][1]
        x2 = ring[(i + 1) % count][0]
        y2 = ring[(i + 1) % count][1]
        distance = point_segment_km(lng, lat, x1, y1, x2, y2)
        if distance < best:
            best = distance
    return best


def box_within_km(bbox: tuple, lng: float, lat: float, km: float) -> bool:
    lat_margin = km / KM_PER_DEG_LAT
    cos_lat = math.cos(math.radians(clamp(lat, -89.5, 89.5)))
    if abs(cos_lat) > EPSILON:
        lng_margin = km / (KM_PER_DEG_LNG * cos_lat)
    else:
        lng_margin = 180.0
    min_x, min_y, max_x, max_y = bbox
    return (min_x - lng_margin <= lng <= max_x + lng_margin) and (
        min_y - lat_margin <= lat <= max_y + lat_margin
    )


def nearest_coast(lng: float, lat: float, countries: dict) -> tuple:
    best_iso = None
    best_km = MISSING_DISTANCE
    margin = COASTAL_BUFFER_KM * COASTAL_MARGIN_FACTOR
    for iso in BUFFER_ORDER:
        entry = countries.get(iso)
        if not entry:
            continue
        for ring in entry["rings"]:
            if not box_within_km(ring.bbox, lng, lat, margin):
                continue
            distance = ring_min_distance(lng, lat, ring.points)
            if distance < best_km:
                best_km = distance
                best_iso = iso
                if best_km <= 0.0:
                    return best_iso, 0.0
    return best_iso, best_km


def build_country(geometry: dict) -> tuple:
    gtype = geometry.get("type")
    coords = geometry.get("coordinates") or []
    raw_polygons = [coords] if gtype == "Polygon" else coords
    polygons = []
    rings = []
    for raw in raw_polygons:
        if not raw:
            continue
        outer = raw[0]
        outer_box = ring_bbox(outer)
        holes = []
        for hole in raw[1:]:
            holes.append((hole, ring_bbox(hole)))
        polygons.append(Polygon(outer=outer, bbox=outer_box, holes=holes))
        rings.append(Ring(points=outer, bbox=outer_box))
        for hole, hole_box in holes:
            rings.append(Ring(points=hole, bbox=hole_box))
    return polygons, rings


def resolve_iso(props: dict) -> Optional[str]:
    for field in PROPERTY_FIELDS:
        value = props.get(field)
        if isinstance(value, str):
            code = value.strip().upper()
            if code in TARGET_SET:
                return code
    admin = props.get("ADMIN")
    if not isinstance(admin, str):
        admin = props.get("NAME")
    if isinstance(admin, str):
        return NAME_TO_ISO.get(admin.strip())
    return None


def download_bytes(url: str, timeout: int) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "UIO-GNSS-Lab/1.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def atomic_write_bytes(path: str, data: bytes) -> None:
    tmp_path = path + ".tmp"
    with open(tmp_path, "wb") as handle:
        handle.write(data)
    os.replace(tmp_path, path)


def atomic_write_text(path: str, content: str) -> None:
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8", newline="") as handle:
        handle.write(content)
    os.replace(tmp_path, path)


def fetch_json(url: str, timeout: int) -> dict:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "UIO-GNSS-Lab/1.0", "Accept": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = response.read()
    return json.loads(payload.decode("utf-8"))


def load_or_fetch_snapshot(refresh: bool) -> tuple:
    if not refresh and os.path.isfile(SNAPSHOT_FILE) and os.path.getsize(SNAPSHOT_FILE) > 0:
        with open(SNAPSHOT_FILE, "r", encoding="utf-8") as handle:
            snapshot = json.load(handle)
        return snapshot.get("data", []), "local-cache"
    payload = fetch_json(API_URL, HTTP_TIMEOUT)
    stations = payload.get("data", [])
    snapshot = {
        "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": API_URL,
        "api_code": payload.get("code"),
        "api_msg": payload.get("msg"),
        "station_count": len(stations),
        "data": stations,
    }
    atomic_write_text(SNAPSHOT_FILE, json.dumps(snapshot, indent=2))
    return stations, "live-fetch"


def snapshot_fetched_at() -> str:
    if not (os.path.isfile(SNAPSHOT_FILE) and os.path.getsize(SNAPSHOT_FILE) > 0):
        return "not-available"
    with open(SNAPSHOT_FILE, "r", encoding="utf-8") as handle:
        snapshot = json.load(handle)
    raw = snapshot.get("fetched_at_utc")
    if not isinstance(raw, str) or not raw:
        return "unknown"
    try:
        stamp = datetime.fromisoformat(raw)
    except ValueError:
        return raw
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def load_or_fetch_ne_raw() -> tuple:
    if os.path.isfile(NE_RAW_FILE) and os.path.getsize(NE_RAW_FILE) > 0:
        with open(NE_RAW_FILE, "rb") as handle:
            raw = handle.read()
        return json.loads(raw.decode("utf-8")), "local-cache"
    try:
        raw = download_bytes(NE_URL, NE_TIMEOUT)
        source = NE_URL
    except Exception:
        raw = download_bytes(NE_FALLBACK_URL, NE_TIMEOUT)
        source = NE_FALLBACK_URL
    atomic_write_bytes(NE_RAW_FILE, raw)
    return json.loads(raw.decode("utf-8")), source


def extract_boundaries(raw: dict, source: str) -> dict:
    features = raw.get("features") or []
    selected = []
    for feature in features:
        props = feature.get("properties") or {}
        iso = resolve_iso(props)
        if iso is None:
            continue
        geometry = feature.get("geometry")
        if not geometry:
            continue
        name = props.get("ADMIN") or props.get("NAME") or iso
        selected.append(
            {"type": "Feature", "properties": {"iso": iso, "name": name}, "geometry": geometry}
        )
    codes = sorted({feature["properties"]["iso"] for feature in selected})
    boundary = {
        "type": "FeatureCollection",
        "source": source,
        "iso_codes": codes,
        "features": selected,
    }
    atomic_write_text(BOUNDARY_FILE, json.dumps(boundary))
    return boundary


def load_or_extract_boundaries() -> tuple:
    if os.path.isfile(BOUNDARY_FILE) and os.path.getsize(BOUNDARY_FILE) > 0:
        with open(BOUNDARY_FILE, "r", encoding="utf-8") as handle:
            boundary = json.load(handle)
        return boundary, "local-cache"
    raw, source = load_or_fetch_ne_raw()
    boundary = extract_boundaries(raw, source)
    return boundary, source


def build_structures(boundary: dict) -> dict:
    countries: dict = {}
    for feature in boundary.get("features") or []:
        iso = (feature.get("properties") or {}).get("iso")
        if not iso:
            continue
        polygons, rings = build_country(feature.get("geometry") or {})
        entry = countries.setdefault(iso, {"polygons": [], "rings": []})
        entry["polygons"].extend(polygons)
        entry["rings"].extend(rings)
    return countries


def parse_station(raw: dict) -> Optional[Station]:
    try:
        lat = float(raw["lat"])
        lng = float(raw["lng"])
    except (KeyError, TypeError, ValueError):
        return None
    if not (math.isfinite(lat) and math.isfinite(lng)):
        return None
    raw_id = raw.get("stationId", 0)
    if isinstance(raw_id, bool):
        station_id = 0
    elif isinstance(raw_id, int):
        station_id = raw_id
    else:
        try:
            station_id = int(raw_id)
        except (TypeError, ValueError):
            station_id = 0
    return Station(
        station_id=station_id,
        name=str(raw.get("name", "")),
        status=str(raw.get("status", "")).upper(),
        lat=lat,
        lng=lng,
    )


def in_candidate_region(lat: float, lng: float) -> bool:
    return (CANDIDATE_MIN_LAT <= lat <= CANDIDATE_MAX_LAT) and (
        CANDIDATE_MIN_LNG <= lng <= CANDIDATE_MAX_LNG
    )


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    rlat1 = math.radians(clamp(lat1, -90.0, 90.0))
    rlat2 = math.radians(clamp(lat2, -90.0, 90.0))
    dlat = rlat2 - rlat1
    dlon = math.radians(clamp(lon2, -180.0, 180.0) - clamp(lon1, -180.0, 180.0))
    sin_lat = math.sin(dlat / 2.0)
    sin_lon = math.sin(dlon / 2.0)
    a = sin_lat * sin_lat + math.cos(rlat1) * math.cos(rlat2) * sin_lon * sin_lon
    a = clamp(a, 0.0, 1.0)
    root = math.sqrt(max(0.0, a))
    distance = 2.0 * EARTH_RADIUS_KM * math.asin(clamp(root, 0.0, 1.0))
    if not math.isfinite(distance):
        return 0.0
    return distance


def classify(lng: float, lat: float, countries: dict) -> tuple:
    for iso in EXACT_ORDER:
        entry = countries.get(iso)
        if not entry:
            continue
        for polygon in entry["polygons"]:
            if point_in_polygon(lng, lat, polygon):
                return iso, "EXACT_POLYGON"
    iso, distance = nearest_coast(lng, lat, countries)
    if iso is not None and distance <= COASTAL_BUFFER_KM:
        return iso, "COASTAL_BUFFER"
    return None, None


def station_class(name: str) -> str:
    if name.startswith("****"):
        return "GEODNET_MINER"
    return "PUBLIC_IGS_EUREF"


def assign_zone(iso: str, lat: float, lng: float) -> str:
    if iso == "NOR":
        if lat >= SVALBARD_MIN_LAT:
            return "NO-Svalbard-Arctic"
        if lat >= NORTH_LAT_THRESHOLD:
            return "NO-North-Auroral"
        if lat >= CENTRAL_LAT_THRESHOLD:
            return "NO-Central-Trondelag"
        if lng >= OSLO_LNG_THRESHOLD:
            return "NO-South-Oslo-Ostlandet"
        return "NO-South-West-Vestlandet"
    return ZONE_BY_ISO.get(iso, iso)


def build_row(station: Station, iso: str, method: str) -> StationRow:
    zone = assign_zone(iso, station.lat, station.lng)
    return StationRow(
        station_id=station.station_id,
        name=station.name,
        status=station.status,
        lat=safe_round(station.lat, 5),
        lng=safe_round(station.lng, 5),
        country_iso=iso,
        match_method=method,
        station_class=station_class(station.name),
        zone=zone,
        dist_to_osls_km=safe_round(haversine_km(station.lat, station.lng, OSLS_LAT, OSLS_LNG), 4),
        dist_to_trom_km=safe_round(haversine_km(station.lat, station.lng, TROM_LAT, TROM_LNG), 4),
        dist_to_nya2_km=safe_round(haversine_km(station.lat, station.lng, NYA2_LAT, NYA2_LNG), 4),
    )


def build_csv(rows: list) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(CSV_HEADER)
    for row in rows:
        writer.writerow(
            [
                row.station_id,
                row.name,
                row.status,
                f"{row.lat:.5f}",
                f"{row.lng:.5f}",
                row.country_iso,
                row.match_method,
                row.station_class,
                row.zone,
                f"{row.dist_to_osls_km:.4f}",
                f"{row.dist_to_trom_km:.4f}",
                f"{row.dist_to_nya2_km:.4f}",
            ]
        )
    return buffer.getvalue()


def percent(part: int, whole: int) -> str:
    if abs(float(whole)) > EPSILON:
        value = 100.0 * float(part) / float(whole)
        if not math.isfinite(value):
            return "0.0%"
        return f"{value:.1f}%"
    return "0.0%"


def status_markdown(counts: dict, total: int) -> str:
    lines = ["| Status | Stations | Share |", "| :--- | ---: | ---: |"]
    for status in sorted(counts):
        lines.append(f"| {status} | {counts[status]} | {percent(counts[status], total)} |")
    return "\n".join(lines)


def country_markdown(counts: dict, total: int) -> str:
    labels = {
        "NOR": "Norway",
        "SWE": "Sweden",
        "FIN": "Finland",
        "DNK": "Denmark",
        "ISL": "Iceland",
    }
    lines = ["| ISO | Country | Stations | Share |", "| :--- | :--- | ---: | ---: |"]
    for iso in NORDIC_KEEP:
        value = counts.get(iso, 0)
        lines.append(f"| {iso} | {labels.get(iso, iso)} | {value} | {percent(value, total)} |")
    return "\n".join(lines)


def zone_markdown(counts: dict) -> str:
    lines = ["| Zone | Stations |", "| :--- | ---: |"]
    for zone in sorted(counts):
        lines.append(f"| {zone} | {counts[zone]} |")
    return "\n".join(lines)


def class_markdown(counts: dict, total: int) -> str:
    lines = ["| Station class | Stations | Share |", "| :--- | ---: | ---: |"]
    for label in ("GEODNET_MINER", "PUBLIC_IGS_EUREF"):
        value = counts.get(label, 0)
        lines.append(f"| {label} | {value} | {percent(value, total)} |")
    return "\n".join(lines)


def public_list_markdown(rows: list) -> str:
    lines = [
        "| ISO | Station ID | Name | Status | Zone | Lat | Lng |",
        "| :--- | ---: | :--- | :--- | :--- | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            f"| {row.country_iso} | {row.station_id} | {row.name} | {row.status} | "
            f"{row.zone} | {row.lat:.4f} | {row.lng:.4f} |"
        )
    if not rows:
        lines.append("| — | — | — | — | — | — | — |")
    return "\n".join(lines)


def southern_markdown(rows: list, limit: int) -> str:
    ordered = sorted(rows, key=lambda r: r.dist_to_osls_km)[:limit]
    lines = [
        "| Rank | Station ID | Name | Status | Class | Zone | Lat | Lng | Dist OSLS km |",
        "| ---: | ---: | :--- | :--- | :--- | :--- | ---: | ---: | ---: |",
    ]
    for index, row in enumerate(ordered, start=1):
        lines.append(
            f"| {index} | {row.station_id} | {row.name} | {row.status} | {row.station_class} | "
            f"{row.zone} | {row.lat:.4f} | {row.lng:.4f} | {row.dist_to_osls_km:.2f} |"
        )
    return "\n".join(lines)


def northern_markdown(rows: list, limit: int) -> str:
    ordered = sorted(rows, key=lambda r: r.lat, reverse=True)[:limit]
    lines = [
        "| Rank | Station ID | Name | Status | Class | Zone | Lat | Lng | Dist TROM km |",
        "| ---: | ---: | :--- | :--- | :--- | :--- | ---: | ---: | ---: |",
    ]
    for index, row in enumerate(ordered, start=1):
        lines.append(
            f"| {index} | {row.station_id} | {row.name} | {row.status} | {row.station_class} | "
            f"{row.zone} | {row.lat:.4f} | {row.lng:.4f} | {row.dist_to_trom_km:.2f} |"
        )
    return "\n".join(lines)


def render_template(context: dict, template_path: str) -> str:
    if not os.path.isfile(template_path):
        return ""
    with open(template_path, "r", encoding="utf-8") as handle:
        template = handle.read()
    output = template
    for key in context:
        output = output.replace("{{" + key + "}}", context[key])
    return output


def main() -> int:
    refresh = "--refresh" in sys.argv
    os.makedirs(DATA_DIR, exist_ok=True)
    print(f"pre-run snapshot fetched_at_utc: {snapshot_fetched_at()}")
    raw_stations, snap_source = load_or_fetch_snapshot(refresh)
    if not isinstance(raw_stations, list):
        print("unexpected snapshot structure", file=sys.stderr)
        return 1
    boundary, boundary_source = load_or_extract_boundaries()
    countries = build_structures(boundary)

    stations = [
        parsed
        for parsed in (parse_station(item) for item in raw_stations if isinstance(item, dict))
        if parsed is not None
    ]
    total = len(stations)

    status_counts: dict = {}
    for station in stations:
        status_counts[station.status] = status_counts.get(station.status, 0) + 1

    rows: list = []
    candidate_count = 0
    for station in stations:
        if not in_candidate_region(station.lat, station.lng):
            continue
        candidate_count += 1
        iso, method = classify(station.lng, station.lat, countries)
        if iso is None or iso not in NORDIC_KEEP:
            continue
        rows.append(build_row(station, iso, method))

    rows.sort(key=lambda item: (item.country_iso, item.dist_to_osls_km))
    atomic_write_text(CSV_FILE, build_csv(rows))

    norway_rows = sorted(
        [row for row in rows if row.country_iso == "NOR"], key=lambda row: row.dist_to_osls_km
    )
    atomic_write_text(NORWAY_CSV_FILE, build_csv(norway_rows))

    country_counts: dict = {}
    class_counts: dict = {}
    coastal_count = 0
    for row in rows:
        country_counts[row.country_iso] = country_counts.get(row.country_iso, 0) + 1
        class_counts[row.station_class] = class_counts.get(row.station_class, 0) + 1
        if row.match_method == "COASTAL_BUFFER":
            coastal_count += 1

    zone_counts: dict = {}
    for row in norway_rows:
        zone_counts[row.zone] = zone_counts.get(row.zone, 0) + 1

    public_rows = sorted(
        [row for row in rows if row.station_class == "PUBLIC_IGS_EUREF"],
        key=lambda row: (row.country_iso, row.name),
    )
    nordic_total = len(rows)
    norway_total = len(norway_rows)
    svalbard_total = zone_counts.get("NO-Svalbard-Arctic", 0)

    context = {
        "GENERATED_AT": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "SNAPSHOT_FETCHED_AT": snapshot_fetched_at(),
        "SNAPSHOT_SOURCE": snap_source,
        "BOUNDARY_SOURCE": boundary_source,
        "TOTAL_STATIONS": str(total),
        "STATUS_TABLE": status_markdown(status_counts, total),
        "COUNTRY_TABLE": country_markdown(country_counts, nordic_total),
        "NORDIC_TOTAL": str(nordic_total),
        "COASTAL_COUNT": str(coastal_count),
        "NORWAY_TOTAL": str(norway_total),
        "NORWAY_ZONE_TABLE": zone_markdown(zone_counts),
        "CLASS_TABLE": class_markdown(class_counts, nordic_total),
        "MINER_TOTAL": str(class_counts.get("GEODNET_MINER", 0)),
        "PUBLIC_TOTAL": str(class_counts.get("PUBLIC_IGS_EUREF", 0)),
        "SVALBARD_TOTAL": str(svalbard_total),
        "PUBLIC_LIST_TABLE": public_list_markdown(public_rows),
        "SOUTHERN_15_TABLE": southern_markdown(norway_rows, 15),
        "NORTHERN_15_TABLE": northern_markdown(norway_rows, 15),
    }
    report = render_template(context, REPORT_TEMPLATE)
    if report:
        atomic_write_text(REPORT_FILE, report)
    readme = render_template(context, README_TEMPLATE)
    if readme:
        atomic_write_text(README_FILE, readme)

    print("================= GEODNET NORDIC CLASSIFICATION =================")
    print(f"snapshot source  : {snap_source}")
    print(f"boundary source  : {boundary_source}")
    print(f"boundary isos    : {', '.join(boundary.get('iso_codes', []))}")
    print(f"total stations   : {total}")
    for status in sorted(status_counts):
        print(f"   {status:<8}: {status_counts[status]:>6}  ({percent(status_counts[status], total)})")
    print(f"candidate region : {candidate_count}")
    print("----------------- NORDIC BY COUNTRY -----------------")
    for iso in NORDIC_KEEP:
        print(f"   {iso}: {country_counts.get(iso, 0)}")
    print(f"nordic total     : {nordic_total}  (coastal buffer: {coastal_count})")
    print("----------------- NORWAY ZONES -----------------")
    for zone in sorted(zone_counts):
        print(f"   {zone:<26}: {zone_counts[zone]}")
    print("----------------- HARDWARE CLASS -----------------")
    for label in ("GEODNET_MINER", "PUBLIC_IGS_EUREF"):
        print(f"   {label:<18}: {class_counts.get(label, 0)}")
    print(f"refresh mode     : {refresh}")
    print(f"csv written      : {os.path.relpath(CSV_FILE)}")
    print(f"norway csv       : {os.path.relpath(NORWAY_CSV_FILE)}")
    if report:
        print(f"report written   : {os.path.relpath(REPORT_FILE)}")
    if readme:
        print(f"readme written   : {os.path.relpath(README_FILE)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
