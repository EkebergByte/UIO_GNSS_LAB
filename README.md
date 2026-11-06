# High-Latitude GNSS Infrastructure & Quality Control Telemetry (GEODNET / IGS)

An **initiated, modular research project** in GNSS data science and signal physics, carried out
within **University of Oslo — Mathematics: Data, Modelling and Computations**.

This is the starting phase of an independent study of dense, crowd-sourced GNSS reference
infrastructure (the GEODNET network) at high northern latitudes. The project is being developed
**modularly in three phases** (see the roadmap in Section 2). At present the repository publishes
the completed **Phase 1** network baseline and the verified spatial datasets derived from it;
**Phase 2** (the dual-frequency ionospheric signal engine) is in progress, and **Phase 3** (error
separation) is planned. This repository therefore documents the current, verified state of the
network and the project roadmap honestly — the ionospheric STEC/ROTI processing code is **not yet
part of this repository**.

---

## 1. Research Objectives

### 1.1 Quantifying ionospheric disturbance — STEC and ROTI

Derive the **Slant Total Electron Content (STEC)** from the dual-frequency, **geometry-free
carrier-phase combination** (L1/L2/E5a), which isolates the dispersive ionospheric delay from the
non-dispersive geometric range, satellite clock and tropospheric terms. From STEC we form the
**Rate of TEC (ROT)** as the epoch-to-epoch derivative, and the **Rate of TEC Index (ROTI)** as the
standard deviation of ROT over a sliding window (1 TECU = 10¹⁶ electrons·m⁻²). The reference
implementation accumulates ROTI online using **Welford's algorithm** and geolocates every sample at
its **ionospheric pierce point (IPP)** on a thin shell at ~350 km altitude.

### 1.2 Separating space weather from local multipath

Distinguish two physically distinct failure modes:

- **Regional auroral scintillation (space weather).** Coherent, simultaneous phase degradation —
  elevated ROTI, frequent **cycle slips**, and degraded ambiguity resolution — observed at *many
  stations at once* along the auroral oval.
- **Local installation error (station-specific).** Incoherent multipath and signal-quality
  deficits confined to a single site: **MP12 > 0.7 m**, **effective-satellite SNR < 32 dB-Hz**,
  and reduced data availability, which trigger the GEODNET QC rejection path (business
  **status code 310**, epoch completeness < 90 %).

### 1.3 Benchmarking against IGS/EUREF reference stations

Anchor the network statistics to three authoritative **IGS/EUREF** reference stations —
**OSLS** (Oslo, 59.7366° N 10.3683° E), **TROM** (Tromsø, 69.6627° N 18.9396° E) and **NYA2**
(Ny-Ålesund, Svalbard, 78.9296° N 11.8653° E) — using geodesic (Haversine) baselines as the
common spatial reference. Each Nordic station therefore carries three reference distances:
`dist_to_osls_km`, `dist_to_trom_km` and `dist_to_nya2_km`.

---

## 2. Project Roadmap & Current Implementation Status

| Phase | Status | Module | Scope |
| :--- | :--- | :--- | :--- |
| **Phase 1 — Spatial Topology & Network Classification** | `COMPLETED` | `src/nordic_station_classifier.py` | Point-in-MultiPolygon classification, Norwegian research zones, hardware split, IGS/EUREF baselines |
| **Phase 2 — Dual-Frequency RINEX / RTCM Signal Parser & Ionospheric Engine** | `IN PROGRESS` | `src/` (planned) | L1/L2/E5a observation parsing, geometry-free STEC, Welford ROTI at 350 km IPP |
| **Phase 3 — Spatiotemporal Error Separation: Space Weather vs. Local Multipath** | `PLANNED` | `src/` (planned) | Statistical separation of auroral scintillation from local antenna-installation defects |

**Phase 1 — Spatial Topology & Network Classification (`COMPLETED`).** Implemented in
`src/nordic_station_classifier.py`: Point-in-MultiPolygon classification against the Natural Earth
1:10m Admin-0 boundary set with a **20 km coastal fjord closure** fallback; partitioning of the
Kingdom of Norway into research zones (including the auroral oval and Svalbard); hardware
separation `GEODNET_MINER` vs. `PUBLIC_IGS_EUREF`; and geodesic (Haversine) baselines to the
IGS/EUREF reference stations `OSLS`, `TROM` and `NYA2`.

**Phase 2 — Dual-Frequency RINEX / RTCM Signal Parser & Ionospheric Engine (`IN PROGRESS`).**
Extraction of L1/L2/E5a code and carrier-phase observations from **RINEX 3.04** files and
**NTRIP RTCM 3.2** streams; computation of **Slant TEC (STEC)** from the geometry-free linear
combination, and of the **ROTI** index (a 5-minute standard deviation of ROT using Welford's online
algorithm) evaluated at ionospheric pierce points (IPP) at 350 km altitude.

**Phase 3 — Spatiotemporal Error Separation: Space Weather vs. Local Multipath (`PLANNED`).**
A statistical model that distinguishes regional auroral scintillation (simultaneous ROTI spikes and
cycle slips across many stations) from local antenna-installation defects (multipath `MP12 > 0.7 m`,
low signal-to-noise ratio `SNR < 32 dB-Hz`, and data rejected with QC `code 310`).

---

## 3. Empirical Network Dataset (Observation Epoch: 2026-11-06 15:43:30 UTC)

The reference observation epoch comprises **19566** stations globally. Within the
Nordic domain the classifier resolves **302** verified stations across five sovereign
states, of which **92** lie in the Kingdom of Norway. Membership is established by
**point-in-multipolygon** testing against the Natural Earth 1:10m Admin-0 boundaries, with a
**20 km coastal-closure buffer** that re-attributes fjord and skjaergaard stations whose rounded
coordinates fall just outside the land polygon.

### 3.1 Interactive Telemetry Dashboard

A three-tab analytical dashboard is served locally by `src/telemetry_ui.py`:

- **Tab 1 — Network growth and historical series.** Daily status composition at full scale
  (0–20k), a zoomed view of daily dynamics, and the new-station cohort growth curve derived from
  the observed history.
- **Tab 2 — Nordic and Norway spatial map.** A cartographic projection of the Natural Earth 1:10m
  boundaries with the station population, the 65° N auroral-oval and 74° N Svalbard thresholds, and
  the `OSLS`, `TROM` and `NYA2` observatories; sovereign-state and Norwegian latitudinal-zone
  breakdowns.
- **Tab 3 — Station reliability and data explorer.** Status-transition frequency distributions, a
  latitude-band availability analysis, and a filterable, sortable station table.

### 3.2 Nordic stations by sovereign state

| ISO | Country | Stations | Share |
| :--- | :--- | ---: | ---: |
| NOR | Norway | 92 | 30.5% |
| SWE | Sweden | 145 | 48.0% |
| FIN | Finland | 23 | 7.6% |
| DNK | Denmark | 34 | 11.3% |
| ISL | Iceland | 8 | 2.6% |

### 3.3 Kingdom of Norway — research zones

| Zone | Stations |
| :--- | ---: |
| NO-Central-Trondelag | 10 |
| NO-North-Auroral | 15 |
| NO-South-Oslo-Ostlandet | 45 |
| NO-South-West-Vestlandet | 20 |
| NO-Svalbard-Arctic | 2 |

### 3.4 Hardware class split (Nordic region)

| Station class | Stations |
| :--- | ---: |
| `GEODNET_MINER` | 293 |
| `PUBLIC_IGS_EUREF` | 9 |

---

## 4. Repository Structure

```
UIO_GNSS_LAB/
├── README.md                          Auto-generated (from docs/readme_template.md)
├── LICENSE                            MIT license
├── .gitignore                         Ignore rules (raw caches, tooling, IDE)
├── src/
│   ├── nordic_station_classifier.py       Phase 1 classifier + report/README generator
│   ├── telemetry_ui.py                    Local analytical server (/api/telemetry)
│   └── dashboard.html                     Three-tab interactive dashboard
├── data/
│   ├── nordic_boundaries_10m.geojson      Natural Earth 1:10m polygons (10 states)
│   ├── nordic_geodnet_stations.csv        All Nordic stations
│   └── norway_only_stations.csv           Norwegian stations (sorted by dist_to_osls_km)
└── docs/
    ├── report_template.md                 Analytical report source template
    ├── NORDIC_NETWORK_REPORT.md           Generated analytical report
    └── readme_template.md                 README source template
```

The classifier is dependency-free (Python standard library only). Two large inputs —
`data/ne_10m_admin_0_countries.geojson` and `data/global_stations_snapshot.json` — are **not**
tracked and are regenerated on first use.

---

## 5. Getting Started

Requirements: **Python 3.11+**. Both tools use only the Python standard library.

**Default mode — deterministic regeneration from local artefacts (no network I/O):**

```bash
python src/nordic_station_classifier.py
```

Reads the existing `data/global_stations_snapshot.json` and `data/nordic_boundaries_10m.geojson`
from disk and rewrites the CSV datasets, `docs/NORDIC_NETWORK_REPORT.md` and `README.md`.

**Network re-observation (explicit opt-in):**

```bash
python src/nordic_station_classifier.py --refresh
```

Retrieves a single reference-epoch observation from `https://rtk.geodnet.com/api/v2/coverage_stations`,
overwrites `data/global_stations_snapshot.json` atomically, and recomputes every table — refreshing
the CSVs, the analytical report and this `README.md`.

**Interactive telemetry dashboard (local analytical server):**

```bash
python src/telemetry_ui.py
```

Starts a local `http.server` on the first free port in the 8085–8095 range, opens the browser, and
serves the three-tab dashboard together with a JSON endpoint `/api/telemetry` computed exclusively
from the local artefacts (no network access).

---

## 6. Methodology Notes

- **Topology.** Country identity is resolved through the property chain
  `ADM0_A3 → ISO_A3_EH → SOV_A3 → ISO3166-1-Alpha-3 → ISO_A3 → ADMIN/NAME`, which bypasses the
  known Natural Earth `ISO_A3 = "-99"` defect for Norway. Containment uses ray-casting parity
  with axis-aligned bounding-box pre-filtering and hole (enclave) subtraction.
- **Coastal closure.** Unmatched coastal points are attributed to the nearest national coastline
  within 20 km using a local-tangent-plane metric
  (`dx = Δlng·111.320·cos φ`, `dy = Δlat·110.574`).
- **Geodesy and stability.** Great-circle distances to the IGS/EUREF stations `OSLS`, `TROM` and
  `NYA2` use the Haversine formula (mean Earth radius 6371.0088 km). Every trigonometric argument
  is domain-clamped, every division is guarded by `abs(denominator) > 1e-12`, and every published
  metric passes a finite-value check before deterministic rounding.

---

## 7. Acknowledgement

This work gratefully acknowledges the **GEODNET Foundation** and its station operators for
providing open, crowd-sourced GNSS reference infrastructure; the **International GNSS Service
(IGS)** and **EUREF** permanent networks for the authoritative reference stations used as
benchmarks; and **Kartverket** (the Norwegian Mapping Authority) for the national geodetic
reference framework. Station boundary data are derived from **Natural Earth** (public domain).

---

## 8. License

Released under the **MIT License** — see [`LICENSE`](LICENSE).
Copyright (c) 2026 University of Oslo GNSS Data Science Research Project.
