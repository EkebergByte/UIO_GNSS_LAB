# High-Latitude GNSS Infrastructure & Quality Control Telemetry (GEODNET / IGS)

An independent research project in **GNSS data science and signal physics**, carried out within
**University of Oslo — Mathematics: Data, Modelling and Computations**.

The project characterises the behaviour of dense, crowd-sourced GNSS reference infrastructure
(the GEODNET network) at high northern latitudes, and relates its raw, signal-level quality
metrics to the ionospheric state above the auroral oval and the Svalbard archipelago. It is a
data-science study built on open geodetic standards: WGS84/ITRF2020 coordinates, RTCM 3.x
observations, NTRIP transport, and Natural Earth 1:10m national boundaries.

---

## 1. Introduction

Above roughly 59° N and reaching to Ny-Ålesund (78.9° N) on Svalbard, GNSS signals traverse the
**ionospheric trough and the auroral oval**, where electron-density gradients, plasma
irregularities and scintillation are frequent and intense. In this domain a GNSS receiver
simultaneously experiences (i) large-scale, regionally coherent ionospheric disturbances driven
by space weather, and (ii) local, station-specific errors introduced by the physical installation
of the antenna (multipath, obstruction, poor sky view). The scientific interest of this project
is the **statistical separation** of these two error classes using only the observables that a
reference network exposes.

---

## 2. Research Objectives

### 2.1 Quantifying ionospheric disturbance — STEC and ROTI

Derive the **Slant Total Electron Content (STEC)** from the dual-frequency, **geometry-free
carrier-phase combination** (L1/L2/E5a), which isolates the dispersive ionospheric delay from the
non-dispersive geometric range, satellite clock and tropospheric terms. From STEC we form the
**Rate of TEC (ROT)** as the epoch-to-epoch derivative, and the **Rate of TEC Index (ROTI)** as the
standard deviation of ROT over a sliding window (1 TECU = 10¹⁶ electrons·m⁻²). The reference
implementation accumulates ROTI online using **Welford's algorithm** and geolocates every sample at
its **ionospheric pierce point (IPP)** on a thin shell at ~350 km altitude.

### 2.2 Separating space weather from local multipath

Distinguish two physically distinct failure modes:

- **Regional auroral scintillation (space weather).** Coherent, simultaneous phase degradation —
  elevated ROTI, frequent **cycle slips**, and degraded ambiguity resolution — observed at *many
  stations at once* along the auroral oval.
- **Local installation error (station-specific).** Incoherent multipath and signal-quality
  deficits confined to a single site: **MP12 > 0.7 m**, **effective-satellite SNR < 32 dB-Hz**,
  and reduced data availability, which trigger the GEODNET QC rejection path (business
  **status code 310**, epoch completeness < 90 %).

### 2.3 Benchmarking against IGS/EUREF reference stations

Anchor the network statistics to authoritative, high-grade reference stations — **OSLS** (Oslo,
59.7366° N 10.3683° E), **TROM** (Tromsø, 69.6627° N 18.9396° E) and **NYA2** (Ny-Ålesund,
Svalbard) — and to the University of Oslo Blindern campus (59.9400° N 10.7200° E), using
geodesic (Haversine) baselines as the common spatial reference.

---

## 3. Repository Dataset (as of 2026-11-06)

The classifier resolves station membership by **point-in-multipolygon** testing against the
Natural Earth 1:10m Admin-0 boundaries, with a **20 km coastal-closure buffer** that re-attributes
fjord and skjaergaard stations whose rounded coordinates fall just outside the land polygon.

**Nordic region — verified stations: 302** (26 attributed via the coastal buffer).

| Sovereign state | ISO | Stations |
| :--- | :--- | ---: |
| Norway | NOR | 92 |
| Sweden | SWE | 145 |
| Finland | FIN | 23 |
| Denmark | DNK | 34 |
| Iceland | ISL | 8 |

**Kingdom of Norway — research zones (92 stations):**

| Zone | Stations | Character |
| :--- | ---: | :--- |
| NO-South-Oslo-Ostlandet | 45 | lat < 62° N, lng ≥ 9° E |
| NO-South-West-Vestlandet | 20 | lat < 62° N, lng < 9° E |
| NO-North-Auroral | 15 | 65° N ≤ lat < 74° N (auroral oval) |
| NO-Central-Trondelag | 10 | 62° N ≤ lat < 65° N |
| NO-Svalbard-Arctic | 2 | lat ≥ 74° N |

**Hardware class (Nordic region):** `GEODNET_MINER` 293 · `PUBLIC_IGS_EUREF` 9.
The nine public scientific mountpoints are **METG** (FIN), **G025 / HOFN / REYK** (ISL),
**G022 / NYA2** (NOR) and **KIR8 / MAR7 / ONS1** (SWE).

---

## 4. Repository Structure

```
UIO_GNSS_LAB/
├── README.md                          This document
├── LICENSE                            MIT license
├── .gitignore                         Ignore rules (raw caches, tooling, IDE)
├── src/
│   └── nordic_station_classifier.py   Classifier + report generator
├── data/
│   ├── nordic_boundaries_10m.geojson  Natural Earth 1:10m polygons (10 states)
│   ├── nordic_geodnet_stations.csv    All 302 Nordic stations
│   └── norway_only_stations.csv       The 92 Norwegian stations (sorted by distance to UiO)
└── docs/
    ├── report_template.md             Report source template
    └── NORDIC_NETWORK_REPORT.md       Generated analytical report
```

The classifier is dependency-free (Python standard library only). Two large inputs —
`data/ne_10m_admin_0_countries.geojson` and `data/global_stations_snapshot.json` — are
**not** tracked and are regenerated on first use (see below).

---

## 5. Getting Started

Requirements: **Python 3.11+** (no third-party packages).

```bash
python src/nordic_station_classifier.py
```

The pipeline is **cache-first**. It reads the telemetry snapshot and the boundary working set
from disk when present and performs **no network request**; only on a cold start (missing
files) does it issue a single `urllib` GET to the public coverage endpoint and to Natural Earth,
each written atomically. Running the script regenerates:

- `data/nordic_geodnet_stations.csv`
- `data/norway_only_stations.csv`
- `docs/NORDIC_NETWORK_REPORT.md`

---

## 6. Methodology Notes

- **Topology.** Country identity is resolved through the property chain
  `ADM0_A3 → ISO_A3_EH → SOV_A3 → ISO3166-1-Alpha-3 → ISO_A3 → ADMIN/NAME`, which bypasses the
  known Natural Earth `ISO_A3 = "-99"` defect for Norway. Containment uses ray-casting parity
  with axis-aligned bounding-box pre-filtering and hole (enclave) subtraction.
- **Coastal closure.** Unmatched coastal points are attributed to the nearest national coastline
  within 20 km using a local-tangent-plane metric
  (`dx = Δlng·111.320·cos φ`, `dy = Δlat·110.574`).
- **Geodesy and stability.** Great-circle distances use the Haversine formula (mean Earth radius
  6371.0088 km). Every trigonometric argument is domain-clamped, every division is guarded by
  `abs(denominator) > 1e-12`, and every published metric passes a finite-value check before
  deterministic rounding.

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
