# High-Latitude GNSS Infrastructure & Quality Control Telemetry in the Nordic Region (GEODNET / IGS)

**Programme:** UIO_GNSS_LAB — High-Latitude GNSS Infrastructure & Ionospheric Quality Control
**Affiliation:** University of Oslo — Mathematics: Data, Modelling and Computations
**Report generated:** 2026-11-07 21:32:15 UTC
**Telemetry snapshot source:** local-cache
**Reference sources:** GEODNET public API documentation; Natural Earth 1:10m Admin-0 boundaries; IGS/EUREF station registry

---

## 0. Executive summary

1. **Scope.** This report establishes an independent, reproducible baseline of GEODNET reference-station coverage and quality-control behaviour across the high-latitude Nordic domain, combining the public coverage API with authoritative cartographic boundaries (Natural Earth 1:10m) and the published quality-control contracts of the GEODNET network.
2. **QC contract.** GEODNET's data-quality gate is fully documented: a station's hourly data is only usable when **epoch completeness ≥ 90 %** and the **multipath metric MP12 ≤ 0.7 m**. The PPK download endpoint returns business **error code 310 = "Station QC quality is poor. Download failed."** when that gate is not met.
3. **Processing toolchain.** RTCM 3.x to RINEX conversion follows the documented **RTKLIB** (`convbin`) route distributed as `geodnet/rtklib_lte`, which enables standard post-processed kinematic (PPK) workflows on the retrieved observations.
4. **Live network.** On 2026-11-06 14:09:31 UTC the public coverage endpoint reported **19566** global stations. Precise point-in-multipolygon classification (Natural Earth 1:10m Admin-0, with a 20 km coastal-buffer fallback) resolved **302** stations across the five Nordic sovereign states, of which **92** lie in the Kingdom of Norway (including **2** in Svalbard above 74° N).

---

## 1. GEODNET API specification (source: `repos/GEODNET_API`)

### 1.1 Service map

| Service | Base host | Auth model | Primary use |
| :--- | :--- | :--- | :--- |
| RTK (real-time NTRIP corrections) | `rtk.geodnet.com` (port 2101) | NTRIP user/pass + reseller `appId`/`appKey` (MD5 sign) | Real-time centimetre RTK |
| PPK (post-processing archive) | `ppk.geodnet.com` | Token (JWT from `/api/user/signin`) | Historical RINEX/RTCM retrieval |
| RAWDATA (raw observations) | `rawdata.geodnet.com` | Account user/pass | Raw RTCM streaming + QC metrics |
| GGA (rover position stream) | `nmea.geodnet.com` (WebSocket `wss://`) | Bearer token from `/rover/v1/user/login` | Live rover telemetry |
| KB (knowledge centre) | documentation only | none | NTRIP/RTCM/RTK background |

### 1.2 Regional NTRIP casters (RTK API)

| Region | Domain | IPv4 | Port | Mountpoints |
| :--- | :--- | :--- | --- | :--- |
| USA / Global | `rtk.geodnet.com` | 13.56.117.10 | 2101 | AUTO, AUTO_ITRF2020, AUTO_WGS84, AUTO_NAD83 |
| Europe | `eu.geodnet.com` | 3.73.41.96 | 2101 | AUTO, AUTO_ETRS89, AUTO_ITRF2020 |
| South America | `sa.geodnet.com` | 18.230.73.64 | 2101 | AUTO, AUTO_SIRGAS2000, AUTO_ITRF2020 |
| Australia | `aus.geodnet.com` | 54.206.56.130 | 2101 | AUTO, AUTO_GDA2020, AUTO_NZGD2000 |
| India | `ind.geodnet.com` | 13.203.34.145 | 2101 | AUTO |

**Mountpoint semantics.** `AUTO` selects the regional geodetic frame (ETRS89/ETRF2000 2010.0 for Europe). `AUTO_ITRF2020`, `AUTO_ITRF2014`, `AUTO_WGS84` (WGS84 G2139 at mid-year epoch) pin a specific frame. `BRDC` broadcasts global ephemeris. GGA upload is mandatory: without it the AUTO mountpoint returns no corrections.

### 1.3 Reseller signature (RTK API)

`sign = md5_hex( concat(values of params sorted by key, excluding appKey and sign) + appKey )`, lowercase hex, `time` in Unix epoch milliseconds.

### 1.4 RTK API endpoints

| Endpoint | Method | Purpose |
| :--- | :--- | :--- |
| `/api/v3/user/create` | POST | Create RTK account |
| `/api/v3/user/info` | POST | Query one account |
| `/api/v3/user/list` | POST | Paginated account list |
| `/api/v3/user/set/expiration` | POST | Update expiry |
| `/api/v3/user/set/password` | POST | Update password |
| `/api/v3/user/set/status` | POST | Enable/disable |
| `/api/v3/user/set/connections` | POST | Max concurrent logins |
| `/api/v3/user/set/email` | POST | Update e-mail |
| `/api/v3/user/logs` | POST | Change logs |
| `/api/v3/user/rtk/logs` | POST | RTK session logs |
| `/api/v3/user/rand` | POST | Temporary random account (license-gated) |
| `/api/v3/user/subscription` | POST | Query subscription |
| `/api/v3/user/subscription/report` | POST | Report subscription |
| `/api/v3/coverage/list` | POST | Nearest stations to a point (radius ≤ 200 km, amount ≤ 50) |
| `/api/v3/coverage/quality` | POST | Station quality (radius ≤ 100 km, amount ≤ 20) |
| `/api/v3/station/list` | POST | Station list (optionally by ISO-3166 alpha-3 region) |
| `/api/v3/station/info` | POST | Station detail: 72 h uptime + per-constellation satInfo |
| `/api/v2/signin` | POST | Personal login (MD5 password) → JWT |
| `/api/v2/history` | POST | Personal RTK session history (fix/float counters) |

**RTK business status codes:** `1000` success, `1001` invalid appId, `1002` appId disabled, `1003` sign error, `1004` username exists, `1005` username missing, `1006` API not authorised, `1007` invalid expiry, `1008` station missing, `1009` startTime > 6 months, `1010` range > 7 days, `1011` start > end, `1012` invalid id, `1013` order missing, `1019` user not found, `1020` duplicate payment report, `1099` system error, `1100` deprecated API.

**Coverage quality scale:** `1 = do not recommend`, `2 = OK`, `3 = good`, `4 = excellent`.

### 1.5 PPK API endpoints (source: `GEODNET_PPK_API.md`)

| Endpoint | Method | Purpose |
| :--- | :--- | :--- |
| `/api/user/signin` | POST | Sign in → token |
| `/api/user/info` | POST | Account info |
| `/api/user/nearest/stations` | POST | Nearest base stations |
| `/api/user/download/order` | POST | Create RINEX/RTCM download order |
| `/api/user/download/nrcan/order` | POST | Create NRCan CSRS-PPP result order |
| `/api/user/download/order/status` | POST | Poll order status |
| `/api/user/download/file` | POST | Download the produced file |
| `/api/user/check/station/epoch-ratio` | POST | **QC gate**: epoch completeness + MP12 |
| `/api/user/station/list` | GET | All stations |
| `/api/user/station/info` | POST | Station coordinates (ITRF2020 / WGS84 / local) + NRCan sigma95 |

**PPK status codes:** `200` success, `201` parameter error, `202` user missing, `203` bad password, `204` invalid account, `205` token expired, `206` account expired, `301` incomplete date, `302` invalid date, `303` insufficient balance, `304` task not completed, `305` task failed, `306` period > 1 month, `307` invalid stations / no data, `308` RINEX single-station only, `309` no cross-day RINEX, **`310` Station QC quality is poor — download failed**, `321` end ≤ start, `322` start/end not same UTC day, `501` request exception.

### 1.6 QC gate (the "code 310" mechanism)

The `/api/user/check/station/epoch-ratio` endpoint returns:

| Field | Meaning | Limit |
| :--- | :--- | :--- |
| `ratio` | Epoch completeness (%) rounded to 2 dp | **≥ 90 % required** |
| `mp12` | Arithmetic mean of hourly `mp.MP12` values, 4 dp | **≤ 0.7 required** |
| `qualified` | Boolean overall verdict | `true` only if both pass and every QC record has a numeric MP12 |

A request for data from a station that fails this gate is rejected with business **code 310**. This is the exact algorithm GEODNET applies before releasing reference data — the arithmetic-mean-of-MP12 over the query window and the epoch-completeness ratio.

### 1.7 RAWDATA API endpoints (source: `GEODNET_RAWDATA_API.md`)

| Endpoint | Method | Purpose |
| :--- | :--- | :--- |
| mountpoints list / add / replace | POST | Manage stream mountpoints |
| base-station coordinates | POST | Precise coordinates |
| station list / info | POST | Metadata |
| `/api/rawdata/v1/qc/hourly` | POST | QC metrics by hour |
| `/api/rawdata/v1/qc/station` | POST | QC metrics by station |

**RAWDATA status codes:** `1000` success, `1001` no auth header, `1002` invalid auth, `1003` account missing, `1004` bad user/pass, `1005` disabled, `1006` expired, `1007` parameter error, `1008` invalid date, `1009` API not authorised, `1010` time parameter invalid, `1011` target = original station, `1012` original station not in list, `1013` target already in list, `1014` target missing, `1015` invalid station, `1016` only last 6 months queryable, `1017` end ≤ start, `1018` no group info, `1019` maximum limit reached.

**Hourly QC record fields:** `numObs` (complete observations), `expEpoch` (epochs with observations), `numEpoch` (possible epochs), `rate` (data availability %), `crcFailure`, `iodSlip` (IOD slips), `mpSlip` (MP slips), `oslps` (o/slips), and a multipath object with per-frequency-pair values **`mp12, mp21, mp15, mp51, mp16, mp61, mp17, mp71, mp18, mp81`** (metres).

### 1.8 GGA API (source: `GEODNET_GGA_API.md`)

`POST https://nmea.geodnet.com/rover/v1/user/login` → Bearer token; then WebSocket `wss://nmea.geodnet.com/rover/v1/subscribe/all` or `/subscribe/{id}`. Messages carry NMEA 0183 GGA strings per rover id. **Status codes:** `0` success, `10001` system error, `10002` invalid parameters, `10003` user missing, `10004` invalid JSON, `10005` invalid token, `10006` invalid subscription path, `10007` subscription id/all required.

---

## 2. Architectural Review of GEODNET Quality Control & ROTI Methodologies

This section reviews the quality-control (QC) and ionospheric-monitoring methodologies published by GEODNET, which jointly determine the admissibility of reference data and the derived space-weather products used in this study.

### 2.1 Quality-control admissibility criteria

GEODNET publishes an explicit, quantitative admissibility gate for reference-station data. An hourly observation record is admitted only if it satisfies **epoch completeness (ratio) ≥ 90 %** and a mean **multipath metric MP12 ≤ 0.7 m**; a request that violates either bound is refused with the business **status code 310** ("Station QC quality is poor — download failed"). These criteria, together with the per-hour metrics `numObs`, `expEpoch`, `numEpoch`, `crcFailure`, `iodSlip`, `mpSlip` and `oslps`, form the QC basis applied throughout this report.

### 2.2 Installation-level signal-quality criteria

The installation specification defines a semi-automated signal-quality procedure:

- **Station discovery** via `https://console.geodnet.com/map` using the last 5 digits of the serial number; an absent station means it is not online.
- **`databytes`** metric: current message bytes received; `0` indicates an internet/uplink problem.
- **Effective-satellite rule:** the *effective* satellite count is the number of tracked GNSS satellites with **SNR > 32**; a large share of satellites with **SNR < 32** indicates a poor installation.
- **Hourly online rate and token rate** should be **close to 100 %** for a good installation.
- **Wi-Fi signal** (full green bars) is a performance factor.
- **RTK service status semantics:** `ONLINE` = online but not ready for RTK; `ACTIVE` = ready for RTK; `OFFLINE` = offline. The backend decides, per station, whether to advertise it into the RTK service.

These thresholds (SNR > 32, availability ≈ 100 %) complement the API-side QC gate (epoch completeness ≥ 90 %, MP12 ≤ 0.7, error code 310) documented in Section 1.

### 2.3 RTCM3 to RINEX conversion (RTKLIB / convbin)

The PPK workflow instructs users to convert downloaded RTCM to RINEX with **RTKLIB** from the fork `geodnet/rtklib_lte` ("The Windows binary includes `convbin.exe`"). The documented invocation is:

```
convbin.exe -r rtcm3 -tr year/mon/day hour:min:sec unziped_rtcm_file
```

Interpretation: `-r rtcm3` forces the input format, `-tr` supplies the start time (year/month/day and hh:mm:ss), the last positional argument is the input RTCM file. No `gfzrnx` or `teqc` is referenced anywhere in the repositories.

### 2.4 ROTI computation: geometry-free STEC and online standard deviation

`roti/index.html` is regenerated by `publish_roti_map.py` from a `caster-vrs` NTRIP caster. The documented algorithm:

1. Dual-frequency carrier-phase observations → **geometry-free combination** isolating the dispersive ionospheric term → slant TEC.
2. **ROT(t) = (TEC(t) − TEC(t − dt)) / dt** in TECU/min, per (station, satellite), reset on cycle slip / new pass.
3. **ROTI** = standard deviation of ROT accumulated online via **Welford's algorithm** over a bounded sliding window; absence = "not enough data", never "quiet".
4. Each value is geo-located at the signal's **ionospheric pierce point (IPP)** at ~350 km altitude.
5. Values are binned onto a regular lat/lng grid and **averaged per cell (no IDW/Kriging)**.
6. Colour thresholds (TECU/min): green < 0.3, yellow 0.3–0.6, orange 0.6–1.2, red > 1.2. Station markers are rounded to 2 dp (≈ 1 km) to avoid disclosing exact positions.

### 2.5 Coverage-endpoint contract and baseline-quality semantics

`app.js` and `scripts/sync_stations.js` reveal the operational contract of the public endpoint used in Section 3:

- **`GET https://rtk.geodnet.com/api/v2/coverage_stations`** returns `{code, msg, data[]}` where each station is `{name (masked UID), status (ACTIVE|ONLINE|OFFLINE), stationId (12-bit RTCM id 0–4095), lat, lng}`.
- `sync_stations.js` guards against partial responses (`< 5000` stations → abort) and mass-flap spikes (`> 2500` transitions → skip logging); it keeps a 20 000-event rolling history.
- Baseline distance semantics for RTK quality: `< 15 km` optimal (< 1.0 cm), `15–30 km` survey-grade (1.0–2.0 cm), `30–50 km` extended (2.0–4.0 cm), `> 50 km` long baseline (PPP recommended). Delaunay edges > 250 km are discarded as cross-ocean.

---

## 3. Live GEODNET network statistics

**Snapshot:** 2026-11-06 14:09:31 UTC · **source:** local-cache · **boundaries:** local-cache

### 3.1 Global totals by status

**Total global stations: 19566**

| Status | Stations | Share |
| :--- | ---: | ---: |
| ACTIVE | 17223 | 88.0% |
| OFFLINE | 671 | 3.4% |
| ONLINE | 1672 | 8.5% |

### 3.2 Nordic classification by sovereign state (Natural Earth 1:10m, point-in-multipolygon)

Each station is tested against the full Admin-0 polygon set of its candidate region. Direct hits are `EXACT_POLYGON`; coastal fjord / skjaergaard stations within **20 km** of a national coastline are resolved to the nearest coastline and flagged `COASTAL_BUFFER`. Stations resolving to `RUS`, `EST`, `LVA`, `GBR` or `DEU` are excluded from the Nordic set.

| ISO | Country | Stations | Share |
| :--- | :--- | ---: | ---: |
| NOR | Norway | 92 | 30.5% |
| SWE | Sweden | 145 | 48.0% |
| FIN | Finland | 23 | 7.6% |
| DNK | Denmark | 34 | 11.3% |
| ISL | Iceland | 8 | 2.6% |

**Nordic total (NOR + SWE + FIN + DNK + ISL): 302** — of which **26** were resolved via the coastal buffer.

### 3.3 Kingdom of Norway — research zones

**Norway total: 92**

| Zone | Stations |
| :--- | ---: |
| NO-Central-Trondelag | 10 |
| NO-North-Auroral | 15 |
| NO-South-Oslo-Ostlandet | 45 |
| NO-South-West-Vestlandet | 20 |
| NO-Svalbard-Arctic | 2 |

### 3.4 Hardware class split (Nordic region)

| Station class | Stations | Share |
| :--- | ---: | ---: |
| GEODNET_MINER | 293 | 97.0% |
| PUBLIC_IGS_EUREF | 9 | 3.0% |

- Nordic `GEODNET_MINER`: **293**
- Nordic `PUBLIC_IGS_EUREF`: **9**

---

## 4. High-latitude station analysis

### 4.1 Public IGS/EUREF mountpoints in the Nordic region

Every station whose name is not a masked miner UID (`****…`) is surfaced as an explicit scientific / national mountpoint.

| ISO | Station ID | Name | Status | Zone | Lat | Lng |
| :--- | ---: | :--- | :--- | :--- | ---: | ---: |
| FIN | 847 | METG | ACTIVE | FI-Finland | 60.2420 | 24.3840 |
| ISL | 281 | G025 | ACTIVE | IS-Iceland | 65.9230 | -17.5720 |
| ISL | 658 | HOFN | ACTIVE | IS-Iceland | 64.2670 | -15.1980 |
| ISL | 657 | REYK | ACTIVE | IS-Iceland | 64.1390 | -21.9550 |
| NOR | 473 | G022 | ACTIVE | NO-North-Auroral | 68.7860 | 16.5380 |
| NOR | 3042 | NYA2 | ACTIVE | NO-Svalbard-Arctic | 78.9300 | 11.8590 |
| SWE | 845 | KIR8 | ACTIVE | SE-Sweden | 67.8780 | 21.0600 |
| SWE | 843 | MAR7 | ACTIVE | SE-Sweden | 60.5950 | 17.2580 |
| SWE | 3040 | ONS1 | ACTIVE | SE-Sweden | 57.3950 | 11.9250 |

### 4.2 Fifteen southern Norwegian stations nearest to the OSLS IGS/EUREF reference station (Oslo, 59.7366 N 10.3683 E)

Distances are geodesic (Haversine, mean Earth radius 6371.0088 km); the table is sorted by `dist_to_osls_km`.

| Rank | Station ID | Name | Status | Class | Zone | Lat | Lng | Dist OSLS km |
| ---: | ---: | :--- | :--- | :--- | :--- | ---: | ---: | ---: |
| 1 | 1922 | ****AE3D5 | ONLINE | GEODNET_MINER | NO-South-Oslo-Ostlandet | 59.8290 | 10.4440 | 11.11 |
| 2 | 3202 | ****3A786 | ONLINE | GEODNET_MINER | NO-South-Oslo-Ostlandet | 59.7510 | 10.0460 | 18.13 |
| 3 | 79 | ****895F9 | ACTIVE | GEODNET_MINER | NO-South-Oslo-Ostlandet | 59.7520 | 10.0310 | 18.98 |
| 4 | 3748 | ****F3E3D | ACTIVE | GEODNET_MINER | NO-South-Oslo-Ostlandet | 59.9400 | 10.5850 | 25.65 |
| 5 | 492 | ****B7DF4 | ACTIVE | GEODNET_MINER | NO-South-Oslo-Ostlandet | 59.4950 | 10.2510 | 27.66 |
| 6 | 70 | ****0C6D9 | ACTIVE | GEODNET_MINER | NO-South-Oslo-Ostlandet | 59.7690 | 9.8510 | 29.20 |
| 7 | 973 | ****380AD | ACTIVE | GEODNET_MINER | NO-South-Oslo-Ostlandet | 59.9490 | 10.6870 | 29.58 |
| 8 | 71 | ****33B71 | ACTIVE | GEODNET_MINER | NO-South-Oslo-Ostlandet | 59.9120 | 9.9500 | 30.45 |
| 9 | 69 | ****9ACD9 | ACTIVE | GEODNET_MINER | NO-South-Oslo-Ostlandet | 59.8920 | 9.9150 | 30.67 |
| 10 | 3010 | ****7369D | ONLINE | GEODNET_MINER | NO-South-Oslo-Ostlandet | 59.3970 | 10.4660 | 38.16 |
| 11 | 3567 | ****30824 | ONLINE | GEODNET_MINER | NO-South-Oslo-Ostlandet | 59.5550 | 11.0750 | 44.55 |
| 12 | 3634 | ****29E0D | ACTIVE | GEODNET_MINER | NO-South-Oslo-Ostlandet | 59.5550 | 11.0750 | 44.55 |
| 13 | 1260 | ****6E8CC | ACTIVE | GEODNET_MINER | NO-South-Oslo-Ostlandet | 59.9490 | 11.1170 | 48.03 |
| 14 | 109 | ****CE955 | ACTIVE | GEODNET_MINER | NO-South-Oslo-Ostlandet | 59.6410 | 11.2350 | 49.79 |
| 15 | 1439 | ****CBB75 | ACTIVE | GEODNET_MINER | NO-South-Oslo-Ostlandet | 59.8790 | 11.2490 | 51.73 |

### 4.3 Fifteen northernmost Norwegian stations (Auroral Oval / Svalbard)

Sorted by descending latitude; `Dist TROM` is the geodesic distance to the IGS/EUREF reference station TROM (69.6627 N 18.9396 E).

| Rank | Station ID | Name | Status | Class | Zone | Lat | Lng | Dist TROM km |
| ---: | ---: | :--- | :--- | :--- | :--- | ---: | ---: | ---: |
| 1 | 3042 | NYA2 | ACTIVE | PUBLIC_IGS_EUREF | NO-Svalbard-Arctic | 78.9300 | 11.8590 | 1050.42 |
| 2 | 2699 | ****1CC2E | ONLINE | GEODNET_MINER | NO-Svalbard-Arctic | 78.2510 | 15.4370 | 960.60 |
| 3 | 921 | ****8FA45 | ACTIVE | GEODNET_MINER | NO-North-Auroral | 70.6850 | 23.7060 | 212.60 |
| 4 | 658 | ****51365 | OFFLINE | GEODNET_MINER | NO-North-Auroral | 70.6100 | 26.0290 | 287.61 |
| 5 | 470 | ****A8239 | ACTIVE | GEODNET_MINER | NO-North-Auroral | 70.0210 | 23.5360 | 180.53 |
| 6 | 2595 | ****5C9E9 | ACTIVE | GEODNET_MINER | NO-North-Auroral | 70.0170 | 23.5420 | 180.68 |
| 7 | 680 | ****773B9 | ACTIVE | GEODNET_MINER | NO-North-Auroral | 69.9770 | 23.3020 | 170.91 |
| 8 | 1363 | ****14B6A | ACTIVE | GEODNET_MINER | NO-North-Auroral | 69.9160 | 22.0840 | 124.02 |
| 9 | 1878 | ****B09F5 | ACTIVE | GEODNET_MINER | NO-North-Auroral | 69.6450 | 18.9900 | 2.77 |
| 10 | 2554 | ****84C0D | ACTIVE | GEODNET_MINER | NO-North-Auroral | 69.3930 | 18.6030 | 32.72 |
| 11 | 699 | ****0B611 | ACTIVE | GEODNET_MINER | NO-North-Auroral | 69.1030 | 18.6130 | 63.54 |
| 12 | 388 | ****40451 | ACTIVE | GEODNET_MINER | NO-North-Auroral | 68.7880 | 16.5590 | 135.17 |
| 13 | 473 | G022 | ACTIVE | PUBLIC_IGS_EUREF | NO-North-Auroral | 68.7860 | 16.5380 | 135.91 |
| 14 | 222 | ****C7C69 | ACTIVE | GEODNET_MINER | NO-North-Auroral | 68.7810 | 16.5480 | 136.04 |
| 15 | 186 | ****46775 | ACTIVE | GEODNET_MINER | NO-North-Auroral | 68.3560 | 15.3900 | 202.68 |

---

## 5. Methodology, reproducibility and limitations

**Pipeline (`src/nordic_station_classifier.py`).**
1. **Cache-first telemetry.** By default the script reads `data/global_stations_snapshot.json` from disk and performs **no** network request. A single `urllib` GET to `https://rtk.geodnet.com/api/v2/coverage_stations` (20 s timeout, atomic write) is issued only on a cold start (no local snapshot) or when the operator explicitly passes `--refresh`.
2. **Cache-first boundaries.** `data/nordic_boundaries_10m.geojson` is the light working set. If absent, the script downloads Natural Earth 1:10m Admin-0 once (raw cache `data/ne_10m_admin_0_countries.geojson`, fallback `datasets/geo-countries`) and extracts the ten target sovereign states.
3. **Topology.** Country identity is resolved through the property chain `ADM0_A3 → ISO_A3_EH → SOV_A3 → ISO3166-1-Alpha-3 → ISO_A3 → ADMIN/NAME` (this bypasses the known Natural Earth `ISO_A3 = "-99"` defect for Norway). Containment uses ray-casting parity with AABB pre-filtering and hole (enclave) subtraction. Coastal stations unmatched by any polygon are assigned to the nearest national coastline within 20 km using a local-tangent-plane metric (`dx = Δlng·111.320·cos φ`, `dy = Δlat·110.574`).
4. **Geodesy and stability.** Haversine distances to the three IGS/EUREF reference stations OSLS, TROM and NYA2; all trigonometric arguments are clamped, every division is guarded by `abs(denominator) > 1e-12`, and every output metric passes a `math.isfinite` check before deterministic rounding.
5. **Outputs.** `data/global_stations_snapshot.json`, `data/nordic_boundaries_10m.geojson`, `data/nordic_geodnet_stations.csv`, `data/norway_only_stations.csv`, this report and the auto-generated `README.md`.

**Reference points (IGS/EUREF).**

| Point | Latitude | Longitude | Role |
| :--- | ---: | ---: | :--- |
| OSLS | 59.7366 | 10.3683 | IGS/EUREF reference station, Oslo |
| TROM | 69.6627 | 18.9396 | IGS/EUREF reference station, Tromsø |
| NYA2 | 78.9296 | 11.8653 | IGS/EUREF reference station, Ny-Ålesund (Svalbard) |

**Limitations.**
- Classification rests on Natural Earth 1:10m Admin-0 geometry; sub-kilometre coastal offsets can push a fjord / skjaergaard station into the 20 km coastal buffer — which is precisely why that fallback exists.
- Station coordinates are rounded by GEODNET and names are masked UIDs; `stationId` is a 12-bit RTCM id that is **not globally unique** and is reused across regions.
- Distances are spherical (Haversine) or local-tangent-plane approximations; ellipsoidal geodesics would differ by a few hundred metres at these baselines.
- The QC gate (epoch completeness ≥ 90 %, MP12 ≤ 0.7, code 310) applies to the authenticated PPK/RAWDATA services and cannot be re-evaluated from the public coverage feed alone.



