from __future__ import annotations

import csv
import json
import math
import os
from dataclasses import dataclass

import matplotlib

matplotlib.use("Agg")

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from datetime import datetime
from matplotlib.gridspec import GridSpecFromSubplotSpec

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
REPOS_DATA = os.path.join(BASE_DIR, "repos", "rtk", "data")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")

SNAPSHOT_FILE = os.path.join(DATA_DIR, "global_stations_snapshot.json")
NORDIC_CSV = os.path.join(DATA_DIR, "nordic_geodnet_stations.csv")
NORWAY_CSV = os.path.join(DATA_DIR, "norway_only_stations.csv")
STATS_FILE = os.path.join(REPOS_DATA, "station_stats.json")
DAILY_FILE = os.path.join(REPOS_DATA, "daily_summary.json")
EVENTS_FILE = os.path.join(REPOS_DATA, "station_events.json")

OUT_PNG = os.path.join(ASSETS_DIR, "geodnet_telemetry_overview.png")
OUT_SVG = os.path.join(ASSETS_DIR, "geodnet_telemetry_overview.svg")

HASH = chr(35)
BG_COLOR = HASH + "0D1117"
AX_COLOR = HASH + "141A23"
SPINE_COLOR = HASH + "2D3748"
GRID_COLOR = HASH + "222B38"
TEXT_COLOR = HASH + "E2E8F0"
MUTED_COLOR = HASH + "94A3B8"
ACTIVE_COLOR = HASH + "34D399"
ONLINE_COLOR = HASH + "F59E0B"
OFFLINE_COLOR = HASH + "EF4444"
ACCENT_COLOR = HASH + "2AB7CA"

STATUS_ORDER = ("ACTIVE", "ONLINE", "OFFLINE")
STATUS_COLORS = {
    "ACTIVE": ACTIVE_COLOR,
    "ONLINE": ONLINE_COLOR,
    "OFFLINE": OFFLINE_COLOR,
}

AURORAL_LAT = 65.0
ARCTIC_LAT = 74.0
OSLS_LAT = 59.7366
TROM_LAT = 69.6627
NYA2_LAT = 78.9296
QC_COMPLETENESS = 90.0

COUNTRY_ORDER = ("SWE", "NOR", "DNK", "FIN", "ISL")
ZONE_ORDER = (
    "NO-South-Oslo-Ostlandet",
    "NO-South-West-Vestlandet",
    "NO-North-Auroral",
    "NO-Central-Trondelag",
    "NO-Svalbard-Arctic",
)


@dataclass(frozen=True, slots=True)
class NordicStation:
    name: str
    status: str
    lat: float
    lng: float
    country_iso: str
    station_class: str
    zone: str
    dist_osls_km: float
    dist_trom_km: float
    dist_nya2_km: float


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
            stations.append(
                NordicStation(
                    name=str(row.get("name", "")),
                    status=str(row.get("status", "")).upper(),
                    lat=lat,
                    lng=lng,
                    country_iso=str(row.get("country_iso", "")),
                    station_class=str(row.get("station_class", "")),
                    zone=str(row.get("zone", "")),
                    dist_osls_km=safe_float(row.get("dist_to_osls_km")),
                    dist_trom_km=safe_float(row.get("dist_to_trom_km")),
                    dist_nya2_km=safe_float(row.get("dist_to_nya2_km")),
                )
            )
    return stations


def style_figure() -> None:
    plt.rcParams.update(
        {
            "figure.facecolor": BG_COLOR,
            "savefig.facecolor": BG_COLOR,
            "axes.facecolor": AX_COLOR,
            "axes.edgecolor": SPINE_COLOR,
            "axes.labelcolor": MUTED_COLOR,
            "axes.titlecolor": TEXT_COLOR,
            "text.color": TEXT_COLOR,
            "xtick.color": MUTED_COLOR,
            "ytick.color": MUTED_COLOR,
            "grid.color": GRID_COLOR,
            "font.family": "DejaVu Sans",
            "font.size": 10,
        }
    )


def style_axes(ax) -> None:
    ax.set_facecolor(AX_COLOR)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    for side in ("bottom", "left"):
        ax.spines[side].set_color(SPINE_COLOR)
        ax.spines[side].set_linewidth(0.8)
    ax.grid(True, color=GRID_COLOR, alpha=0.7, linewidth=0.6, linestyle=":")
    ax.set_axisbelow(True)
    ax.tick_params(colors=MUTED_COLOR, labelsize=9)
    for label in ax.get_xticklabels() + ax.get_yticklabels():
        label.set_color(MUTED_COLOR)


def panel_accumulation(ax, daily, status_counts: dict, total_stations: int) -> None:
    style_axes(ax)
    ax.set_title(
        "Panel A  |  Network Accumulation & Status Composition",
        color=TEXT_COLOR,
        fontsize=11,
        loc="left",
        pad=8,
    )
    if not daily:
        ax.text(
            0.5,
            0.5,
            "daily_summary.json not available",
            ha="center",
            va="center",
            color=MUTED_COLOR,
            transform=ax.transAxes,
        )
        return
    field_for = {"ACTIVE": "totalActive", "ONLINE": "totalOnline", "OFFLINE": "totalOffline"}
    dates = []
    series = {"ACTIVE": [], "ONLINE": [], "OFFLINE": []}
    totals = []
    new_stations = 0
    for key in sorted(daily.keys()):
        record = daily.get(key) or {}
        try:
            moment = datetime.strptime(str(key), "%Y-%m-%d")
        except (TypeError, ValueError):
            continue
        dates.append(moment)
        for status in STATUS_ORDER:
            value = record.get(field_for[status], 0)
            series[status].append(float(value) if isinstance(value, (int, float)) else 0.0)
        totals.append(float(record.get("totalStations", 0) or 0))
        new_stations += int(record.get("newActive", 0) or 0) + int(record.get("newOnline", 0) or 0)
    if not dates:
        return
    ax.stackplot(
        dates,
        series["ACTIVE"],
        series["ONLINE"],
        series["OFFLINE"],
        colors=[STATUS_COLORS[status] for status in STATUS_ORDER],
        labels=list(STATUS_ORDER),
        alpha=0.85,
    )
    ax.plot(dates, totals, color=TEXT_COLOR, linewidth=1.1, label="Total monitored")
    ax.set_ylabel("Monitored stations", color=MUTED_COLOR, fontsize=9)
    locator = mdates.AutoDateLocator()
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))
    legend = ax.legend(loc="upper left", frameon=False, fontsize=8)
    for text in legend.get_texts():
        text.set_color(TEXT_COLOR)
    active = int(status_counts.get("ACTIVE", 0))
    online = int(status_counts.get("ONLINE", 0))
    offline = int(status_counts.get("OFFLINE", 0))
    note = (
        f"Observation epoch composition (n = {total_stations})\n"
        f"ACTIVE   {active}  ({100.0 * active / total_stations:.1f}%)\n"
        f"ONLINE   {online}  ({100.0 * online / total_stations:.1f}%)\n"
        f"OFFLINE  {offline}  ({100.0 * offline / total_stations:.1f}%)\n"
        f"New stations over series: {new_stations}"
    )
    ax.text(
        0.985,
        0.05,
        note,
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=8,
        color=TEXT_COLOR,
        bbox={"facecolor": BG_COLOR, "edgecolor": SPINE_COLOR, "boxstyle": "round,pad=0.5", "alpha": 0.85},
    )


def panel_nordic(ax, nordic_rows: list, norway_rows: list) -> None:
    style_axes(ax)
    ax.set_title(
        "Panel B  |  Nordic Countries & Norwegian Latitude Zones",
        color=TEXT_COLOR,
        fontsize=11,
        loc="left",
        pad=8,
    )
    labels = []
    counts = []
    for iso in COUNTRY_ORDER:
        row_counts = {status: 0 for status in STATUS_ORDER}
        for station in nordic_rows:
            if station.country_iso == iso and station.status in row_counts:
                row_counts[station.status] += 1
        labels.append(iso)
        counts.append(row_counts)
    for zone in ZONE_ORDER:
        row_counts = {status: 0 for status in STATUS_ORDER}
        for station in norway_rows:
            if station.zone == zone and station.status in row_counts:
                row_counts[station.status] += 1
        labels.append(zone)
        counts.append(row_counts)
    positions = list(range(len(labels)))[::-1]
    left = [0.0] * len(labels)
    for status in STATUS_ORDER:
        widths = [float(entry[status]) for entry in counts]
        ax.barh(
            positions,
            widths,
            left=left,
            color=STATUS_COLORS[status],
            height=0.62,
            label=status,
            alpha=0.9,
        )
        left = [left[index] + widths[index] for index in range(len(widths))]
    totals = [int(sum(entry.values())) for entry in counts]
    span = float(max(totals)) if totals else 1.0
    for index, position in enumerate(positions):
        ax.text(
            totals[index] + span * 0.015,
            position,
            str(totals[index]),
            va="center",
            ha="left",
            color=TEXT_COLOR,
            fontsize=8,
        )
    ax.set_yticks(positions)
    ax.set_yticklabels(labels, fontsize=8)
    ax.set_xlim(0.0, span * 1.16)
    ax.set_xlabel("Stations", color=MUTED_COLOR, fontsize=9)
    ax.axhline(len(COUNTRY_ORDER) - 0.5, color=SPINE_COLOR, linewidth=0.8, linestyle=":")
    legend = ax.legend(loc="lower right", frameon=False, fontsize=8)
    for text in legend.get_texts():
        text.set_color(TEXT_COLOR)


def median(values: list) -> float:
    if not values:
        return float("nan")
    ordered = sorted(values)
    count = len(ordered)
    middle = count // 2
    if count % 2 == 1:
        return ordered[middle]
    return 0.5 * (ordered[middle - 1] + ordered[middle])


def build_uptime_by_name(events) -> dict:
    if not isinstance(events, list):
        return {}
    timeline = {}
    for event in events:
        if not isinstance(event, dict):
            continue
        name = event.get("name")
        timestamp = event.get("timestamp")
        to_status = str(event.get("toStatus", "")).upper()
        if not isinstance(name, str) or not isinstance(timestamp, (int, float)):
            continue
        timeline.setdefault(name, []).append((float(timestamp), to_status))
    result = {}
    for name, points in timeline.items():
        if len(points) < 2:
            continue
        points.sort(key=lambda item: item[0])
        window = points[-1][0] - points[0][0]
        if window <= 0.0:
            continue
        serviceable = 0.0
        for index in range(len(points) - 1):
            if points[index][1] in ("ACTIVE", "ONLINE"):
                serviceable += points[index + 1][0] - points[index][0]
        fraction = 100.0 * serviceable / window
        if not math.isfinite(fraction):
            continue
        result[name] = clamp(fraction, 0.0, 100.0)
    return result


def draw_boxplot(ax, dataset: list, positions: list, colors: list, labels: list) -> None:
    plotted = [values if values else [0.0] for values in dataset]
    box = ax.boxplot(
        plotted,
        positions=positions,
        widths=0.5,
        patch_artist=True,
        showfliers=False,
        medianprops={"color": BG_COLOR, "linewidth": 1.4},
        whiskerprops={"color": MUTED_COLOR, "linewidth": 0.8},
        capprops={"color": MUTED_COLOR, "linewidth": 0.8},
    )
    for patch, color in zip(box["boxes"], colors):
        patch.set_facecolor(color)
        patch.set_edgecolor(color)
        patch.set_alpha(0.85)
    ax.set_xticks(positions)
    ax.set_xticklabels(labels, fontsize=8)
    for index, values in enumerate(dataset):
        if not values:
            continue
        ax.text(
            positions[index],
            median(values),
            f"md {median(values):.1f}",
            ha="center",
            va="bottom",
            fontsize=8,
            color=TEXT_COLOR,
        )


def panel_reliability(ax_uptime, ax_flaps, stats, uptime_by_name: dict) -> None:
    style_axes(ax_uptime)
    style_axes(ax_flaps)
    ax_uptime.set_title(
        "Panel C  |  Empirical Reliability: Uptime (%) vs QC Gate",
        color=TEXT_COLOR,
        fontsize=11,
        loc="left",
        pad=8,
    )
    ax_flaps.set_title(
        "Panel C  |  Status Flap Frequency (transitions)",
        color=TEXT_COLOR,
        fontsize=10,
        loc="left",
        pad=8,
    )
    uptime_groups = {"ACTIVE": [], "ONLINE": []}
    flap_groups = {"ACTIVE": [], "ONLINE": []}
    if isinstance(stats, dict):
        for entry in stats.values():
            if not isinstance(entry, dict):
                continue
            status = str(entry.get("status", "")).upper()
            if status not in uptime_groups:
                continue
            total = entry.get("totalFlips", 0)
            if isinstance(total, (int, float)) and math.isfinite(float(total)):
                flap_groups[status].append(float(total))
            name = entry.get("name")
            if isinstance(name, str) and name in uptime_by_name:
                uptime_groups[status].append(uptime_by_name[name])
    positions = [1, 2]
    labels = ["ACTIVE", "ONLINE"]
    colors = [ACTIVE_COLOR, ONLINE_COLOR]
    draw_boxplot(
        ax_uptime,
        [uptime_groups["ACTIVE"], uptime_groups["ONLINE"]],
        positions,
        colors,
        labels,
    )
    ax_uptime.axhline(
        QC_COMPLETENESS,
        color=ACCENT_COLOR,
        linewidth=1.0,
        linestyle="--",
        alpha=0.9,
    )
    ax_uptime.text(
        0.985,
        QC_COMPLETENESS,
        " QC gate 90.0%",
        transform=ax_uptime.get_yaxis_transform(),
        ha="right",
        va="bottom",
        fontsize=8,
        color=ACCENT_COLOR,
    )
    ax_uptime.set_ylim(0.0, 104.0)
    ax_uptime.set_ylabel("Uptime proxy (%)", color=MUTED_COLOR, fontsize=9)
    draw_boxplot(
        ax_flaps,
        [flap_groups["ACTIVE"], flap_groups["ONLINE"]],
        positions,
        colors,
        labels,
    )
    ax_flaps.set_ylabel("Status transitions", color=MUTED_COLOR, fontsize=9)


def min_distance_to_igs(station: NordicStation) -> float:
    values = [station.dist_osls_km, station.dist_trom_km, station.dist_nya2_km]
    finite = [value for value in values if math.isfinite(value)]
    if not finite:
        return float("nan")
    return min(finite)


def panel_latitude(ax, nordic_rows: list) -> None:
    style_axes(ax)
    ax.set_title(
        "Panel D  |  High-Latitude Profile & IGS/EUREF Baselines",
        color=TEXT_COLOR,
        fontsize=11,
        loc="left",
        pad=8,
    )
    by_status = {"ACTIVE": [], "ONLINE": [], "OFFLINE": []}
    igs_points = []
    for station in nordic_rows:
        nearest = min_distance_to_igs(station)
        if not math.isfinite(nearest):
            continue
        if station.station_class == "PUBLIC_IGS_EUREF":
            igs_points.append((station.lat, nearest, station.name))
            continue
        if station.status in by_status:
            by_status[station.status].append((station.lat, nearest))
    for status in STATUS_ORDER:
        points = by_status[status]
        if not points:
            continue
        ax.scatter(
            [point[0] for point in points],
            [point[1] for point in points],
            s=18,
            color=STATUS_COLORS[status],
            alpha=0.75,
            label=status,
            edgecolors="none",
        )
    if igs_points:
        ax.scatter(
            [point[0] for point in igs_points],
            [point[1] for point in igs_points],
            s=95,
            marker="*",
            color=ACCENT_COLOR,
            edgecolors=TEXT_COLOR,
            linewidths=0.6,
            label="PUBLIC_IGS_EUREF",
            zorder=5,
        )
        for lat, nearest, name in igs_points:
            ax.annotate(
                name,
                (lat, nearest),
                textcoords="offset points",
                xytext=(6, 6),
                fontsize=7,
                color=TEXT_COLOR,
            )
    ax.set_ylim(bottom=0.0)
    top = ax.get_ylim()[1] * 0.98
    ax.axvline(AURORAL_LAT, color=ONLINE_COLOR, linewidth=1.0, linestyle="--", alpha=0.9)
    ax.axvline(ARCTIC_LAT, color=OFFLINE_COLOR, linewidth=1.0, linestyle="--", alpha=0.9)
    ax.text(AURORAL_LAT, top, " Auroral Oval 65 N", rotation=90, va="top", ha="left", fontsize=7, color=ONLINE_COLOR)
    ax.text(ARCTIC_LAT, top, " Svalbard High-Arctic 74 N", rotation=90, va="top", ha="left", fontsize=7, color=OFFLINE_COLOR)
    for lat, name in ((OSLS_LAT, "OSLS 59.74"), (TROM_LAT, "TROM 69.66"), (NYA2_LAT, "NYA2 78.93")):
        ax.axvline(lat, color=MUTED_COLOR, linewidth=0.8, linestyle=":", alpha=0.7)
        ax.text(lat, 0.0, " " + name, rotation=90, va="bottom", ha="left", fontsize=7, color=MUTED_COLOR)
    ax.set_xlabel("Latitude (deg N)", color=MUTED_COLOR, fontsize=9)
    ax.set_ylabel("Distance to nearest IGS/EUREF (km)", color=MUTED_COLOR, fontsize=9)
    legend = ax.legend(loc="upper left", frameon=False, fontsize=8)
    for text in legend.get_texts():
        text.set_color(TEXT_COLOR)


def load_dataset() -> dict:
    snapshot = load_json(SNAPSHOT_FILE)
    status_counts = {}
    total_stations = 0
    data = snapshot.get("data", []) if isinstance(snapshot, dict) else []
    if isinstance(data, list):
        for item in data:
            if not isinstance(item, dict):
                continue
            status = str(item.get("status", "UNKNOWN")).upper()
            status_counts[status] = status_counts.get(status, 0) + 1
        total_stations = len(data)
    return {
        "status_counts": status_counts,
        "total_stations": total_stations,
        "nordic": read_stations(NORDIC_CSV),
        "norway": read_stations(NORWAY_CSV),
        "daily": load_json(DAILY_FILE),
        "stats": load_json(STATS_FILE),
        "events": load_json(EVENTS_FILE),
    }


def main() -> int:
    style_figure()
    os.makedirs(ASSETS_DIR, exist_ok=True)
    dataset = load_dataset()
    uptime_by_name = build_uptime_by_name(dataset["events"])
    figure = plt.figure(figsize=(16.0, 10.0), facecolor=BG_COLOR, constrained_layout=True)
    grid = figure.add_gridspec(2, 2)
    ax_a = figure.add_subplot(grid[0, 0])
    ax_b = figure.add_subplot(grid[0, 1])
    sub_c = GridSpecFromSubplotSpec(1, 2, subplot_spec=grid[1, 0], wspace=0.35)
    ax_c1 = figure.add_subplot(sub_c[0, 0])
    ax_c2 = figure.add_subplot(sub_c[0, 1])
    ax_d = figure.add_subplot(grid[1, 1])
    panel_accumulation(ax_a, dataset["daily"], dataset["status_counts"], dataset["total_stations"])
    panel_nordic(ax_b, dataset["nordic"], dataset["norway"])
    panel_reliability(ax_c1, ax_c2, dataset["stats"], uptime_by_name)
    panel_latitude(ax_d, dataset["nordic"])
    figure.suptitle(
        "GEODNET High-Latitude Telemetry Overview",
        color=TEXT_COLOR,
        fontsize=15,
        fontweight="bold",
    )
    figure.savefig(OUT_PNG, dpi=300, facecolor=BG_COLOR)
    figure.savefig(OUT_SVG, facecolor=BG_COLOR)
    plt.close(figure)
    print(f"nordic stations : {len(dataset['nordic'])}")
    print(f"norway stations : {len(dataset['norway'])}")
    print(f"total stations  : {dataset['total_stations']}")
    print(f"uptime proxy    : {len(uptime_by_name)} stations")
    print(f"png written     : {os.path.relpath(OUT_PNG, BASE_DIR)}")
    print(f"svg written     : {os.path.relpath(OUT_SVG, BASE_DIR)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
