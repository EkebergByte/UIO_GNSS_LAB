# Data Sources and Schema

This document records the provenance, schema and quality-control semantics of every dataset used
by the project. It is the reference for reviewers who need to reproduce or audit the pipeline.

## Upstream sources

| Dataset | Provider | Reference | Used for |
| :--- | :--- | :--- | :--- |
| Coverage stations | GEODNET Foundation | `https://rtk.geodnet.com/api/v2/coverage_stations` | Station inventory, status and coordinates |
| National boundaries | Natural Earth | `ne_10m_admin_0_countries` (1:10m, v5.1.2) | Point-in-polygon country classification |
| Permanent reference stations | IGS / EUREF | OSLS (Oslo), TROM (Tromsø), NYA2 (Ny-Ålesund) | Haversine baselines |
| Geodetic framework | Kartverket | Norwegian reference network | Context for the Norwegian research zones |

Boundary fallback source: `https://raw.githubusercontent.com/datasets/geo-countries/main/data/countries.geojson`.

## Cached artefacts (data/)

| File | Description | Versioned |
| :--- | :--- | :--- |
| `global_stations_snapshot.json` | Raw coverage snapshot (timestamp, source, station list) | No (cache) |
| `nordic_boundaries_10m.geojson` | Extracted Nordic polygons (light working set) | Yes |
| `nordic_geodnet_stations.csv` | Classified Nordic stations | Yes |
| `norway_only_stations.csv` | Norwegian stations sorted by distance to OSLS | Yes |

## Snapshot schema

| Field | Type | Meaning |
| :--- | :--- | :--- |
| `fetched_at_utc` | ISO-8601 string | Retrieval timestamp |
| `source` | string | API endpoint used |
| `api_code` / `api_msg` | int / string | Upstream response envelope |
| `station_count` | int | Number of stations in `data` |
| `data` | array | Station objects (`stationId`, `name`, `status`, `lat`, `lng`) |

## CSV column dictionary

| Column | Meaning |
| :--- | :--- |
| `station_id` | GEODNET station identifier |
| `name` | Station name (masked for miners) |
| `status` | ACTIVE / ONLINE / OFFLINE at snapshot time |
| `lat`, `lng` | WGS84 decimal degrees |
| `country_iso` | Resolved sovereign state (ISO 3166-1 alpha-3) |
| `match_method` | EXACT_POLYGON or COASTAL_BUFFER |
| `station_class` | GEODNET_MINER or PUBLIC_IGS_EUREF |
| `zone` | Research zone (Norwegian zones or country) |
| `dist_to_osls_km`, `dist_to_trom_km`, `dist_to_nya2_km` | Haversine distance to the reference stations |

## Quality-control gate

A station is usable only when the GEODNET quality gate passes: epoch completeness >= 90 percent and
multipath MP12 <= 0.7 m. A failed download returns business error code 310 (station QC quality is poor).

## Caching policy

All network access is cache-first: the pipeline reads local files and performs no HTTP request when the
cache exists. A single request is issued only on a cold start or when the operator passes `--refresh`.
