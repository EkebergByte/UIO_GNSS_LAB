# High-Latitude GNSS Infrastructure & Quality-Control Telemetry

[![CI](https://github.com/EkebergByte/UIO_GNSS_LAB/actions/workflows/ci.yml/badge.svg)](https://github.com/EkebergByte/UIO_GNSS_LAB/actions/workflows/ci.yml)
[![Rust 1.80+](https://img.shields.io/badge/Rust-1.80%2B-orange?logo=rust)](https://www.rust-lang.org/)
[![UiO Data Science](https://img.shields.io/badge/UiO-Mathematics%20%26%20Data-0B4F6C)](https://www.uio.no/)
[![Standard RINEX 3.04](https://img.shields.io/badge/Standard-RINEX%203.04-blue)](https://igs.org/)
[![Datum ITRF2020](https://img.shields.io/badge/Datum-ITRF2020%20%2F%20ETRS89-10b981)](https://www.epncb.oma.be/)
[![Engine 60 FPS](https://img.shields.io/badge/Engine-60%20FPS%20Canvas-00F0FF)](#)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

An independent GNSS data-science project at the **University of Oslo** (Mathematics: Data,
Modelling and Computations). It classifies GEODNET reference stations across the Nordic region and
monitors their quality-control behaviour at high latitudes. The engine is written in **Rust** and
runs entirely from local data — no external services are required at runtime.

**Screenshots** *(click any image to view full resolution)*

<table>
  <tr>
    <td align="center" width="33%">
      <a href="assets/01_multi_panel_telemetry.png"><img src="assets/01_multi_panel_telemetry.png" width="360" alt="Multi-Panel Daily Telemetry"/></a>
      <br/><sub>Tab 1 — Multi-Panel Daily Telemetry (3-track ACTIVE / ONLINE / OFFLINE).</sub>
    </td>
    <td align="center" width="33%">
      <a href="assets/02_cumulative_onboarding.png"><img src="assets/02_cumulative_onboarding.png" width="360" alt="Cumulative Station Onboarding"/></a>
      <br/><sub>Tab 1 — Cumulative Station Onboarding.</sub>
    </td>
    <td align="center" width="33%">
      <a href="assets/03_geodetic_map_3d.png"><img src="assets/03_geodetic_map_3d.png" width="360" alt="Interactive 3D-styled geodetic map"/></a>
      <br/><sub>Tab 2 — Interactive 3D-styled geodetic map with RTK rings and IGS baselines.</sub>
    </td>
  </tr>
</table>

---

## What GEODNET Is

GEODNET (Global Earth Observation Decentralized Network) is a global reference-station network that
distributes RTK corrections and post-processed GNSS data. Its stations serve surveying,
machine-control, autonomous-platform and geodetic applications, and the operational status of each
station determines the corrections available within its coverage area.

Station data is subject to two quality thresholds — **epoch completeness ≥ 90 %** and **multipath
MP12 ≤ 0.7 m** — and stations that fail the gate are held out of the RTK-ready set. This work
reports the station classification, status transitions and geometric coverage of the Nordic
sub-network, derived from the public coverage feed.

## What This Project Does

1. **Topology classification** (`--classify`). Every station in the cached snapshot is tested
   against Natural Earth 1:10m national boundaries (point-in-multipolygon, with a 20 km coastal
   fallback for fjords), assigned to a sovereign state, split into Norwegian research zones,
   separated into hardware classes, and written to two versioned CSV datasets.
2. **Local dashboard** (`--serve`). A dependency-free HTTP server exposes an interactive three-tab
   dashboard and a JSON endpoint (`/api/telemetry`) assembled purely from local files.

Classification is **cache-first**: the engine reads `data/global_stations_snapshot.json` from disk
and performs **no network request** at runtime.

---

## Network Telemetry Snapshot (Observation Epoch: 2026-11-09 UTC)

| Scope | Metric | Value |
| :--- | :--- | ---: |
| Global coverage feed | stations reported | 19 548 |
| Global coverage feed | ACTIVE / ONLINE / OFFLINE | 17 163 / 1 716 / 669 |
| Nordic (5 states) | classified stations | 300 |
| Nordic | ACTIVE / ONLINE / OFFLINE | 265 / 32 / 3 |
| Nordic | GEODNET_MINER / PUBLIC_IGS_EUREF | 291 / 9 |
| Norway | stations | 89 |
| Norway | Svalbard (above 74° N) | 2 |

Nordic distribution by state: **NOR 89 · SWE 146 · FIN 23 · DNK 34 · ISL 8**.

Norwegian research zones: **South-Oslo-Østlandet 43 · South-West-Vestlandet 19 ·
North-Auroral 15 · Central-Trøndelag 10 · Svalbard-Arctic 2**.

---

## Data Sources

Station inventory, status and coordinates come from the GEODNET coverage feed
(`rtk.geodnet.com/api/v2/coverage_stations`); country classification uses Natural Earth 1:10m
Admin-0 (v5.1.2); baselines reference the IGS/EUREF stations OSLS (Oslo), TROM (Tromsø) and
NYA2 (Ny-Ålesund). Provenance and the full snapshot/CSV schema are in
[`DATA_SOURCES.md`](DATA_SOURCES.md).

---

## How to Run

Requirements: **Rust 1.80+**. No external services are needed at runtime.

```bash
git clone https://github.com/EkebergByte/UIO_GNSS_LAB.git
cd UIO_GNSS_LAB
cargo run -- --classify
cargo run -- --serve
```

`--classify` recomputes the Nordic classification from the local snapshot cache and rewrites
`data/nordic_geodnet_stations.csv` and `data/norway_only_stations.csv` (atomic write). `--serve`
starts the dashboard on a free port between 8085 and 8095 and opens it in the browser.

---

## Repository Structure

```
UIO_GNSS_LAB/
├── Cargo.toml · README.md · DATA_SOURCES.md · LICENSE
├── src/                     Rust engine
│   ├── main.rs              CLI entry point
│   ├── types.rs             constants, status enum, data records
│   ├── geo.rs               Haversine, point-in-polygon, coastal buffer, zones
│   ├── classify_engine.rs   classification pipeline and CSV writer
│   ├── payload.rs           cached dashboard JSON payload builder
│   ├── server.rs            local HTTP server
│   └── dashboard.html       three-tab interactive dashboard
├── data/                    boundaries and generated CSV datasets
├── docs/                    report and README templates
├── repos/                   vendored upstream API references
└── assets/                  dashboard screenshots
```

---

## Roadmap

- **Phase R3 — Dual-frequency signal engine.** A RINEX 3.04 / RTCM 3.2 parser (L1/L2/E5a) that
  computes Slant TEC from the geometry-free combination and the ROTI index (Welford online
  standard deviation, ionospheric pierce point at 350 km).
- **Phase R4 — Error separation.** Statistical separation of regional space weather (auroral
  scintillation) from local antenna-installation errors (multipath MP12, QC error code 310).

---

## Acknowledgements

Thanks to the **GEODNET Foundation** and its station operators for the open reference network; the
**IGS** and **EUREF** permanent networks for the reference stations used as benchmarks; and
**Kartverket** for the Norwegian geodetic reference framework. Boundary data come from **Natural
Earth** (public domain).

---

## License

Released under the **MIT License** — see [`LICENSE`](LICENSE).
Copyright (c) 2026 University of Oslo GNSS Data Science Research Project.