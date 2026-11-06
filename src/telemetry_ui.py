from __future__ import annotations

import csv
import json
import math
import os
import socket
import threading
import webbrowser
from dataclasses import dataclass
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
REPOS_DATA = os.path.join(BASE_DIR, "repos", "rtk", "data")
SRC_DIR = os.path.join(BASE_DIR, "src")

SNAPSHOT_FILE = os.path.join(DATA_DIR, "global_stations_snapshot.json")
NORDIC_CSV = os.path.join(DATA_DIR, "nordic_geodnet_stations.csv")
NORWAY_CSV = os.path.join(DATA_DIR, "norway_only_stations.csv")
BOUNDARY_FILE = os.path.join(DATA_DIR, "nordic_boundaries_10m.geojson")
STATS_FILE = os.path.join(REPOS_DATA, "station_stats.json")
DAILY_FILE = os.path.join(REPOS_DATA, "daily_summary.json")
EVENTS_FILE = os.path.join(REPOS_DATA, "station_events.json")
DASHBOARD_FILE = os.path.join(SRC_DIR, "dashboard.html")

PORT_RANGE = range(8085, 8096)
MAP_ISOS = ("NOR", "SWE", "FIN", "DNK", "ISL")
STATUS_ORDER = ("ACTIVE", "ONLINE", "OFFLINE")
HASH = chr(35)
COLORS = {
    "ACTIVE": HASH + "66C2A5",
    "ONLINE": HASH + "E5A93B",
    "OFFLINE": HASH + "D95F5F",
}
FLAP_BIN_LABELS = ("0", "1-5", "6-20", "21-50", ">50")
FLAP_BIN_LIMITS = (0, 5, 20, 50)
BAND_WIDTH = 3.0
BAND_MIN = 54.0
BAND_MAX = 81.0
NORTH_LAT = 65.0


@dataclass(frozen=True, slots=True)
class Observatory:
    name: str
    lat: float
    lng: float


OBSERVATORIES = (
    Observatory("OSLS", 59.7366, 10.3683),
    Observatory("TROM", 69.6627, 18.9396),
    Observatory("NYA2", 78.9296, 11.8653),
)


def clamp(value: float, low: float, high: float) -> float:
    if not math.isfinite(value):
        return low
    return max(low, min(high, value))


def safe_float(value) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return float("nan")
    if not math.isfinite(result):
        return float("nan")
    return result


def round_or_none(value: float, digits: int):
    if not math.isfinite(value):
        return None
    return round(value, digits)


def load_json(path: str):
    if not (os.path.isfile(path) and os.path.getsize(path) > 0):
        return None
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def read_stations(path: str) -> list:
    stations = []
    if not (os.path.isfile(path) and os.path.getsize(path) > 0):
        return stations
    with open(path, "r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            lat = safe_float(row.get("lat"))
            lng = safe_float(row.get("lng"))
            if not (math.isfinite(lat) and math.isfinite(lng)):
                continue
            raw_id = row.get("station_id", "")
            try:
                station_id = int(raw_id)
            except (TypeError, ValueError):
                station_id = -1
            stations.append(
                {
                    "name": str(row.get("name", "")),
                    "station_id": station_id,
                    "status": str(row.get("status", "")).upper(),
                    "lat": round(lat, 5),
                    "lng": round(lng, 5),
                    "country_iso": str(row.get("country_iso", "")),
                    "station_class": str(row.get("station_class", "")),
                    "zone": str(row.get("zone", "")),
                    "dist_osls_km": round_or_none(safe_float(row.get("dist_to_osls_km")), 2),
                    "dist_trom_km": round_or_none(safe_float(row.get("dist_to_trom_km")), 2),
                    "dist_nya2_km": round_or_none(safe_float(row.get("dist_to_nya2_km")), 2),
                }
            )
    return stations


def load_boundaries() -> dict:
    raw = load_json(BOUNDARY_FILE)
    result = {}
    if not isinstance(raw, dict):
        return result
    for feature in raw.get("features", []):
        if not isinstance(feature, dict):
            continue
        iso = (feature.get("properties") or {}).get("iso")
        if iso not in MAP_ISOS:
            continue
        geometry = feature.get("geometry") or {}
        gtype = geometry.get("type")
        coords = geometry.get("coordinates") or []
        polygons = [coords] if gtype == "Polygon" else coords
        rings_out = []
        for polygon in polygons:
            if not polygon:
                continue
            simplified = []
            for point in polygon[0]:
                if not (isinstance(point, (list, tuple)) and len(point) >= 2):
                    continue
                lng = round(safe_float(point[0]), 4)
                lat = round(safe_float(point[1]), 4)
                if math.isfinite(lng) and math.isfinite(lat):
                    simplified.append([lng, lat])
            if len(simplified) >= 3:
                rings_out.append(simplified)
        result[str(iso)] = rings_out
    return result


def build_timelines(events) -> tuple:
    timeline = {}
    if isinstance(events, list):
        for event in events:
            if not isinstance(event, dict):
                continue
            name = event.get("name")
            timestamp = event.get("timestamp")
            to_status = str(event.get("toStatus", "")).upper()
            if not isinstance(name, str) or not isinstance(timestamp, (int, float)):
                continue
            timeline.setdefault(name, []).append((float(timestamp), to_status))
    epoch_end = 0.0
    for name in timeline:
        timeline[name].sort(key=lambda item: item[0])
        epoch_end = max(epoch_end, timeline[name][-1][0])
    return timeline, epoch_end


def compute_metrics(timeline: dict, epoch_end: float) -> dict:
    metrics = {}
    for name, points in timeline.items():
        if len(points) < 2 or epoch_end <= points[0][0]:
            continue
        durations = {"ACTIVE": 0.0, "ONLINE": 0.0, "OFFLINE": 0.0}
        for index in range(len(points) - 1):
            state = points[index][1]
            if state in durations:
                durations[state] += points[index + 1][0] - points[index][0]
        tail = points[-1][1]
        if tail in durations:
            durations[tail] += epoch_end - points[-1][0]
        total = durations["ACTIVE"] + durations["ONLINE"] + durations["OFFLINE"]
        if total <= 0.0:
            continue
        uptime = 100.0 * (durations["ACTIVE"] + durations["ONLINE"]) / total
        active_pct = 100.0 * durations["ACTIVE"] / total
        online_pct = 100.0 * durations["ONLINE"] / total
        offline_pct = 100.0 * durations["OFFLINE"] / total
        if not all(math.isfinite(value) for value in (uptime, active_pct, online_pct, offline_pct)):
            continue
        metrics[name] = {
            "first_seen_ms": points[0][0],
            "last_seen_ms": points[-1][0],
            "transitions": len(points) - 1,
            "uptime_pct": round(clamp(uptime, 0.0, 100.0), 2),
            "active_pct": round(clamp(active_pct, 0.0, 100.0), 2),
            "online_pct": round(clamp(online_pct, 0.0, 100.0), 2),
            "offline_pct": round(clamp(offline_pct, 0.0, 100.0), 2),
        }
    return metrics


def build_daily(daily) -> list:
    series = []
    if not isinstance(daily, dict):
        return series
    for key in sorted(daily.keys()):
        record = daily.get(key) or {}
        series.append(
            {
                "date": str(key),
                "active": int(record.get("totalActive", 0) or 0),
                "online": int(record.get("totalOnline", 0) or 0),
                "offline": int(record.get("totalOffline", 0) or 0),
                "total": int(record.get("totalStations", 0) or 0),
                "newActive": int(record.get("newActive", 0) or 0),
                "newOnline": int(record.get("newOnline", 0) or 0),
            }
        )
    return series


def build_cohort(daily_series: list) -> dict:
    bars = []
    cumulative = 0
    for entry in daily_series:
        new = entry["newActive"] + entry["newOnline"]
        cumulative += new
        bars.append({"date": entry["date"], "value": new, "cumulative": cumulative})
    return {"bars": bars, "total": cumulative}


def flap_bin_index(value: float) -> int:
    if value <= 0.0:
        return 0
    if value <= 5.0:
        return 1
    if value <= 20.0:
        return 2
    if value <= 50.0:
        return 3
    return 4


def build_flap_histogram(stats, nordic_names: set) -> dict:
    global_bins = [0, 0, 0, 0, 0]
    nordic_bins = [0, 0, 0, 0, 0]
    if isinstance(stats, dict):
        for name, entry in stats.items():
            if not isinstance(entry, dict):
                continue
            total = entry.get("totalFlips")
            if not isinstance(total, (int, float)) or not math.isfinite(float(total)):
                continue
            index = flap_bin_index(float(total))
            global_bins[index] += 1
            if name in nordic_names:
                nordic_bins[index] += 1
    return {"labels": list(FLAP_BIN_LABELS), "global": global_bins, "nordic": nordic_bins}


def build_bands(nordic_stations: list, stats) -> list:
    edges = []
    edge = BAND_MIN
    while edge < BAND_MAX:
        edges.append((edge, edge + BAND_WIDTH))
        edge += BAND_WIDTH
    stats_map = stats if isinstance(stats, dict) else {}
    bands = []
    for low, high in edges:
        counts = {"ACTIVE": 0, "ONLINE": 0, "OFFLINE": 0}
        flaps = []
        for station in nordic_stations:
            lat = station["lat"]
            if not (low <= lat < high):
                continue
            if station["status"] in counts:
                counts[station["status"]] += 1
            entry = stats_map.get(station["name"])
            if isinstance(entry, dict):
                total = entry.get("totalFlips")
                if isinstance(total, (int, float)) and math.isfinite(float(total)):
                    flaps.append(float(total))
        mean_flaps = round(sum(flaps) / len(flaps), 2) if flaps else 0.0
        if not math.isfinite(mean_flaps):
            mean_flaps = 0.0
        bands.append(
            {
                "label": str(int(low)) + "-" + str(int(high)),
                "low": low,
                "active": counts["ACTIVE"],
                "online": counts["ONLINE"],
                "offline": counts["OFFLINE"],
                "total": counts["ACTIVE"] + counts["ONLINE"] + counts["OFFLINE"],
                "meanFlaps": mean_flaps,
            }
        )
    return bands


def build_payload() -> dict:
    snapshot = load_json(SNAPSHOT_FILE)
    status_counts = {"ACTIVE": 0, "ONLINE": 0, "OFFLINE": 0}
    total_global = 0
    data = snapshot.get("data", []) if isinstance(snapshot, dict) else []
    if isinstance(data, list):
        total_global = len(data)
        for item in data:
            if not isinstance(item, dict):
                continue
            status = str(item.get("status", "")).upper()
            if status in status_counts:
                status_counts[status] += 1
    nordic = read_stations(NORDIC_CSV)
    norway = read_stations(NORWAY_CSV)
    stats = load_json(STATS_FILE)
    daily = load_json(DAILY_FILE)
    events = load_json(EVENTS_FILE)
    timeline, epoch_end = build_timelines(events)
    metrics = compute_metrics(timeline, epoch_end)
    nordic_names = {station["name"] for station in nordic}
    stats_map = stats if isinstance(stats, dict) else {}
    enriched = []
    for station in nordic:
        metric = metrics.get(station["name"], {})
        entry = stats_map.get(station["name"])
        flaps = entry.get("totalFlips") if isinstance(entry, dict) else None
        record = dict(station)
        record["flaps"] = int(flaps) if isinstance(flaps, (int, float)) else None
        record["first_seen_ms"] = metric.get("first_seen_ms")
        record["uptime_pct"] = metric.get("uptime_pct")
        record["active_pct"] = metric.get("active_pct")
        record["online_pct"] = metric.get("online_pct")
        record["offline_pct"] = metric.get("offline_pct")
        record["transitions"] = metric.get("transitions")
        enriched.append(record)
    daily_series = build_daily(daily)
    return {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "colors": COLORS,
        "totals": {
            "global": total_global,
            "active": status_counts["ACTIVE"],
            "online": status_counts["ONLINE"],
            "offline": status_counts["OFFLINE"],
            "norway": len(norway),
            "nordic": len(nordic),
            "auroral": sum(1 for station in nordic if station["lat"] >= NORTH_LAT),
        },
        "observatories": [
            {"name": observatory.name, "lat": observatory.lat, "lng": observatory.lng}
            for observatory in OBSERVATORIES
        ],
        "daily": daily_series,
        "cohort": build_cohort(daily_series),
        "bands": build_bands(nordic, stats),
        "flaps": build_flap_histogram(stats, nordic_names),
        "boundaries": load_boundaries(),
        "stations": enriched,
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args) -> None:
        return

    def _send(self, status: int, content_type: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _serve_dashboard(self) -> None:
        if not os.path.isfile(DASHBOARD_FILE):
            self._send(500, "text/plain; charset=utf-8", b"dashboard.html missing")
            return
        with open(DASHBOARD_FILE, "rb") as handle:
            body = handle.read()
        self._send(200, "text/html; charset=utf-8", body)

    def _serve_api(self) -> None:
        try:
            body = json.dumps(build_payload(), allow_nan=False).encode("utf-8")
        except Exception as exc:
            message = json.dumps({"error": str(exc)}).encode("utf-8")
            self._send(500, "application/json; charset=utf-8", message)
            return
        self._send(200, "application/json; charset=utf-8", body)

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html", "/dashboard.html"):
            self._serve_dashboard()
            return
        if path == "/api/telemetry":
            self._serve_api()
            return
        self._send(404, "text/plain; charset=utf-8", b"not found")


def find_free_port() -> int:
    for port in PORT_RANGE:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                probe.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    raise RuntimeError("no free port available in range")


def main() -> int:
    port = find_free_port()
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = "http://127.0.0.1:" + str(port) + "/"
    print("telemetry dashboard : " + url)
    print("telemetry api       : " + url + "api/telemetry")
    threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())