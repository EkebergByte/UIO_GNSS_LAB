use std::collections::{BTreeMap, HashMap};
use std::path::{Path, PathBuf};
use std::sync::{Mutex, OnceLock};

use serde::Serialize;
use serde_json::Value;

use crate::error::AppResult;
use crate::geo;
use crate::types::{NYA2_LAT, NYA2_LNG, OSLS_LAT, OSLS_LNG, TROM_LAT, TROM_LNG};

const COLOR_ACTIVE: &str = "#66C2A5";
const COLOR_ONLINE: &str = "#E5A93B";
const COLOR_OFFLINE: &str = "#D95F5F";
const NORTH_LAT: f64 = 65.0;
const MAP_ISOS: [&str; 5] = ["NOR", "SWE", "FIN", "DNK", "ISL"];
const MIN_MAP_LAT: f64 = 53.0;

#[derive(Debug, Serialize)]
pub struct Colors {
    #[serde(rename = "ACTIVE")]
    pub active: String,
    #[serde(rename = "ONLINE")]
    pub online: String,
    #[serde(rename = "OFFLINE")]
    pub offline: String,
}

#[derive(Debug, Serialize)]
pub struct Totals {
    pub global: usize,
    pub active: usize,
    pub online: usize,
    pub offline: usize,
    pub norway: usize,
    pub nordic: usize,
    pub auroral: usize,
}

#[derive(Debug, Serialize)]
pub struct ObservatoryOut {
    pub name: String,
    pub lat: f64,
    pub lng: f64,
}

#[derive(Debug, Serialize)]
pub struct DailyOut {
    pub date: String,
    pub active: i64,
    pub online: i64,
    pub offline: i64,
    pub total: i64,
    #[serde(rename = "newActive")]
    pub new_active: i64,
    #[serde(rename = "newOnline")]
    pub new_online: i64,
}

#[derive(Debug, Serialize)]
pub struct CohortBar {
    pub date: String,
    pub value: i64,
    pub cumulative: i64,
}

#[derive(Debug, Serialize)]
pub struct CohortOut {
    pub bars: Vec<CohortBar>,
    pub total: i64,
}

#[derive(Debug, Clone)]
pub struct StationBasic {
    pub name: String,
    pub station_id: i64,
    pub status: String,
    pub lat: f64,
    pub lng: f64,
    pub country_iso: String,
    pub station_class: String,
    pub zone: String,
    pub dist_osls_km: Option<f64>,
    pub dist_trom_km: Option<f64>,
    pub dist_nya2_km: Option<f64>,
}

#[derive(Debug, Serialize)]
pub struct StationRecord {
    pub name: String,
    pub station_id: i64,
    pub status: String,
    pub lat: f64,
    pub lng: f64,
    pub country_iso: String,
    pub station_class: String,
    pub zone: String,
    pub dist_osls_km: Option<f64>,
    pub dist_trom_km: Option<f64>,
    pub dist_nya2_km: Option<f64>,
    pub flaps: Option<i64>,
    pub first_seen_ms: Option<f64>,
    pub uptime_pct: Option<f64>,
}

#[derive(Debug, Clone)]
pub struct Metric {
    pub first_seen_ms: f64,
    pub uptime_pct: f64,
}

#[derive(Debug, Serialize)]
pub struct Payload {
    pub generated_at: String,
    pub colors: Colors,
    pub totals: Totals,
    pub observatories: Vec<ObservatoryOut>,
    pub daily: Vec<DailyOut>,
    pub cohort: CohortOut,
    pub boundaries: BTreeMap<String, Vec<Vec<[f64; 2]>>>,
    pub stations: Vec<StationRecord>,
}

fn manifest_dir() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
}

pub fn data_dir() -> PathBuf {
    manifest_dir().join("data")
}

pub fn repos_data_dir() -> PathBuf {
    manifest_dir().join("repos").join("rtk").join("data")
}

fn load_json(path: &Path) -> Option<Value> {
    if !path.is_file() {
        return None;
    }
    match std::fs::metadata(path) {
        Ok(metadata) => {
            if metadata.len() == 0 {
                return None;
            }
        }
        Err(_) => return None,
    }
    let text = std::fs::read_to_string(path).ok()?;
    serde_json::from_str(&text).ok()
}

fn parse_float(text: &str) -> f64 {
    match text.trim().parse::<f64>() {
        Ok(value) => {
            if value.is_finite() {
                value
            } else {
                f64::NAN
            }
        }
        Err(_) => f64::NAN,
    }
}

fn round_or_none(value: f64, digits: usize) -> Option<f64> {
    if !value.is_finite() {
        return None;
    }
    Some(geo::safe_round(value, digits))
}

fn get_int(record: Option<&Value>, key: &str) -> i64 {
    let value = record.and_then(|inner| inner.get(key));
    match value {
        Some(Value::Number(number)) => match number.as_i64() {
            Some(integer) => integer,
            None => match number.as_f64() {
                Some(float) => float as i64,
                None => 0,
            },
        },
        _ => 0,
    }
}

pub fn read_stations(path: &Path) -> Vec<StationBasic> {
    let mut stations = Vec::new();
    let text = match std::fs::read_to_string(path) {
        Ok(content) => content,
        Err(_) => return stations,
    };
    let mut lines = text.lines();
    let _header = lines.next();
    for line in lines {
        if line.is_empty() {
            continue;
        }
        let fields: Vec<&str> = line.split(',').collect();
        if fields.len() < 12 {
            continue;
        }
        let lat = parse_float(fields[3]);
        let lng = parse_float(fields[4]);
        if !(lat.is_finite() && lng.is_finite()) {
            continue;
        }
        let station_id = match fields[0].trim().parse::<i64>() {
            Ok(value) => value,
            Err(_) => -1,
        };
        stations.push(StationBasic {
            name: fields[1].to_string(),
            station_id,
            status: fields[2].to_uppercase(),
            lat: geo::safe_round(lat, 5),
            lng: geo::safe_round(lng, 5),
            country_iso: fields[5].to_string(),
            station_class: fields[7].to_string(),
            zone: fields[8].to_string(),
            dist_osls_km: round_or_none(parse_float(fields[9]), 2),
            dist_trom_km: round_or_none(parse_float(fields[10]), 2),
            dist_nya2_km: round_or_none(parse_float(fields[11]), 2),
        });
    }
    stations
}

pub fn count_stations(path: &Path) -> usize {
    let text = match std::fs::read_to_string(path) {
        Ok(content) => content,
        Err(_) => return 0,
    };
    let mut total = 0usize;
    let mut lines = text.lines();
    let _header = lines.next();
    for line in lines {
        if line.is_empty() {
            continue;
        }
        let fields: Vec<&str> = line.split(',').collect();
        if fields.len() < 5 {
            continue;
        }
        let lat = parse_float(fields[3]);
        let lng = parse_float(fields[4]);
        if lat.is_finite() && lng.is_finite() {
            total += 1;
        }
    }
    total
}

pub fn load_boundaries(path: &Path) -> BTreeMap<String, Vec<Vec<[f64; 2]>>> {
    let mut result: BTreeMap<String, Vec<Vec<[f64; 2]>>> = BTreeMap::new();
    let raw = match load_json(path) {
        Some(value) => value,
        None => return result,
    };
    let features = match raw.get("features").and_then(|value| value.as_array()) {
        Some(array) => array,
        None => return result,
    };
    for feature in features {
        let iso = match feature
            .get("properties")
            .and_then(|props| props.get("iso"))
            .and_then(|value| value.as_str())
        {
            Some(code) => code,
            None => continue,
        };
        if !MAP_ISOS.contains(&iso) {
            continue;
        }
        let geometry = match feature.get("geometry") {
            Some(value) => value,
            None => continue,
        };
        let gtype = geometry.get("type").and_then(|value| value.as_str()).unwrap_or("");
        let coords_value = match geometry.get("coordinates") {
            Some(value) => value,
            None => continue,
        };
        let polygons: Vec<&Value> = if gtype == "Polygon" {
            vec![coords_value]
        } else {
            match coords_value.as_array() {
                Some(array) => array.iter().collect(),
                None => continue,
            }
        };
        let mut rings_out: Vec<Vec<[f64; 2]>> = Vec::new();
        for polygon in polygons {
            let polygon_array = match polygon.as_array() {
                Some(array) => array,
                None => continue,
            };
            let outer = match polygon_array.first().and_then(|value| value.as_array()) {
                Some(array) => array,
                None => continue,
            };
            let mut simplified: Vec<[f64; 2]> = Vec::new();
            for point in outer {
                let pair = match point.as_array() {
                    Some(array) => array,
                    None => continue,
                };
                if pair.len() < 2 {
                    continue;
                }
                let lng = round_or_none(parse_float_value(&pair[0]), 4);
                let lat = round_or_none(parse_float_value(&pair[1]), 4);
                if let (Some(lng), Some(lat)) = (lng, lat) {
                    simplified.push([lng, lat]);
                }
            }
            if simplified.len() >= 3 {
                let mut max_lat = simplified[0][1];
                for point in &simplified {
                    if point[1] > max_lat {
                        max_lat = point[1];
                    }
                }
                if max_lat >= MIN_MAP_LAT {
                    rings_out.push(simplified);
                }
            }
        }
        result.insert(iso.to_string(), rings_out);
    }
    result
}

fn parse_float_value(value: &Value) -> f64 {
    match value.as_f64() {
        Some(number) => number,
        None => f64::NAN,
    }
}

pub fn build_timelines(events: Option<&Value>) -> (HashMap<String, Vec<(f64, String)>>, f64) {
    let mut timeline: HashMap<String, Vec<(f64, String)>> = HashMap::new();
    if let Some(array) = events.and_then(|value| value.as_array()) {
        for event in array {
            if !event.is_object() {
                continue;
            }
            let name = event.get("name").and_then(|value| value.as_str());
            let timestamp = event.get("timestamp").and_then(|value| value.as_f64());
            let to_status = event
                .get("toStatus")
                .and_then(|value| value.as_str())
                .unwrap_or("")
                .to_uppercase();
            if let (Some(name), Some(timestamp)) = (name, timestamp) {
                timeline
                    .entry(name.to_string())
                    .or_default()
                    .push((timestamp, to_status));
            }
        }
    }
    let mut epoch_end = 0.0f64;
    for points in timeline.values_mut() {
        points.sort_by(|left, right| left.0.total_cmp(&right.0));
        if let Some(last) = points.last() {
            if last.0 > epoch_end {
                epoch_end = last.0;
            }
        }
    }
    (timeline, epoch_end)
}

pub fn compute_metrics(
    timeline: &HashMap<String, Vec<(f64, String)>>,
    epoch_end: f64,
) -> HashMap<String, Metric> {
    let mut metrics: HashMap<String, Metric> = HashMap::new();
    for (name, points) in timeline {
        if points.len() < 2 {
            continue;
        }
        if epoch_end <= points[0].0 {
            continue;
        }
        let mut active = 0.0f64;
        let mut online = 0.0f64;
        let mut offline = 0.0f64;
        for index in 0..points.len() - 1 {
            let state = points[index].1.as_str();
            let delta = points[index + 1].0 - points[index].0;
            match state {
                "ACTIVE" => active += delta,
                "ONLINE" => online += delta,
                "OFFLINE" => offline += delta,
                _ => {}
            }
        }
        let last_index = points.len() - 1;
        let tail = points[last_index].1.as_str();
        let tail_delta = epoch_end - points[last_index].0;
        match tail {
            "ACTIVE" => active += tail_delta,
            "ONLINE" => online += tail_delta,
            "OFFLINE" => offline += tail_delta,
            _ => {}
        }
        let total = active + online + offline;
        if total <= 0.0 {
            continue;
        }
        let uptime = 100.0 * (active + online) / total;
        if !uptime.is_finite() {
            continue;
        }
        metrics.insert(
            name.clone(),
            Metric {
                first_seen_ms: points[0].0,
                uptime_pct: geo::safe_round(geo::clamp(uptime, 0.0, 100.0), 2),
            },
        );
    }
    metrics
}

pub fn build_daily(daily: Option<&Value>) -> Vec<DailyOut> {
    let mut series = Vec::new();
    let object = match daily.and_then(|value| value.as_object()) {
        Some(map) => map,
        None => return series,
    };
    let mut keys: Vec<&String> = object.keys().collect();
    keys.sort();
    for key in keys {
        let record = object.get(key);
        series.push(DailyOut {
            date: key.clone(),
            active: get_int(record, "totalActive"),
            online: get_int(record, "totalOnline"),
            offline: get_int(record, "totalOffline"),
            total: get_int(record, "totalStations"),
            new_active: get_int(record, "newActive"),
            new_online: get_int(record, "newOnline"),
        });
    }
    series
}

pub fn build_cohort(series: &[DailyOut]) -> CohortOut {
    let mut bars = Vec::new();
    let mut cumulative = 0i64;
    for entry in series {
        let new = entry.new_active + entry.new_online;
        cumulative += new;
        bars.push(CohortBar {
            date: entry.date.clone(),
            value: new,
            cumulative,
        });
    }
    CohortOut {
        bars,
        total: cumulative,
    }
}

fn collect_stats_flaps(stats: Option<&Value>) -> HashMap<String, f64> {
    let mut map: HashMap<String, f64> = HashMap::new();
    if let Some(object) = stats.and_then(|value| value.as_object()) {
        for (name, entry) in object {
            if let Some(entry_object) = entry.as_object() {
                if let Some(value) = entry_object.get("totalFlips").and_then(|item| item.as_f64()) {
                    if value.is_finite() {
                        map.insert(name.clone(), value);
                    }
                }
            }
        }
    }
    map
}

pub fn build_payload() -> Payload {
    let data = data_dir();
    let repos = repos_data_dir();
    let snapshot = load_json(&data.join("global_stations_snapshot.json"));
    let mut status_active = 0usize;
    let mut status_online = 0usize;
    let mut status_offline = 0usize;
    let mut total_global = 0usize;
    if let Some(snap) = &snapshot {
        if let Some(array) = snap.get("data").and_then(|value| value.as_array()) {
            total_global = array.len();
            for item in array {
                if !item.is_object() {
                    continue;
                }
                let status = item
                    .get("status")
                    .and_then(|value| value.as_str())
                    .unwrap_or("")
                    .to_uppercase();
                match status.as_str() {
                    "ACTIVE" => status_active += 1,
                    "ONLINE" => status_online += 1,
                    "OFFLINE" => status_offline += 1,
                    _ => {}
                }
            }
        }
    }
    let nordic = read_stations(&data.join("nordic_geodnet_stations.csv"));
    let norway_total = count_stations(&data.join("norway_only_stations.csv"));
    let stats = load_json(&repos.join("station_stats.json"));
    let daily = load_json(&repos.join("daily_summary.json"));
    let events = load_json(&repos.join("station_events.json"));
    let stats_flaps = collect_stats_flaps(stats.as_ref());
    let (timeline, epoch_end) = build_timelines(events.as_ref());
    let metrics = compute_metrics(&timeline, epoch_end);
    let mut records: Vec<StationRecord> = Vec::with_capacity(nordic.len());
    for station in &nordic {
        let metric = metrics.get(&station.name);
        let flaps = stats_flaps.get(&station.name).map(|value| *value as i64);
        records.push(StationRecord {
            name: station.name.clone(),
            station_id: station.station_id,
            status: station.status.clone(),
            lat: station.lat,
            lng: station.lng,
            country_iso: station.country_iso.clone(),
            station_class: station.station_class.clone(),
            zone: station.zone.clone(),
            dist_osls_km: station.dist_osls_km,
            dist_trom_km: station.dist_trom_km,
            dist_nya2_km: station.dist_nya2_km,
            flaps,
            first_seen_ms: metric.map(|item| item.first_seen_ms),
            uptime_pct: metric.map(|item| item.uptime_pct),
        });
    }
    let daily_series = build_daily(daily.as_ref());
    let cohort = build_cohort(&daily_series);
    let boundaries = load_boundaries(&data.join("nordic_boundaries_10m.geojson"));
    let auroral = nordic.iter().filter(|item| item.lat >= NORTH_LAT).count();
    let observatories = vec![
        ObservatoryOut {
            name: "OSLS".to_string(),
            lat: OSLS_LAT,
            lng: OSLS_LNG,
        },
        ObservatoryOut {
            name: "TROM".to_string(),
            lat: TROM_LAT,
            lng: TROM_LNG,
        },
        ObservatoryOut {
            name: "NYA2".to_string(),
            lat: NYA2_LAT,
            lng: NYA2_LNG,
        },
    ];
    let generated_at = chrono::Utc::now()
        .format("%Y-%m-%d %H:%M:%S UTC")
        .to_string();
    Payload {
        generated_at,
        colors: Colors {
            active: COLOR_ACTIVE.to_string(),
            online: COLOR_ONLINE.to_string(),
            offline: COLOR_OFFLINE.to_string(),
        },
        totals: Totals {
            global: total_global,
            active: status_active,
            online: status_online,
            offline: status_offline,
            norway: norway_total,
            nordic: nordic.len(),
            auroral,
        },
        observatories,
        daily: daily_series,
        cohort,
        boundaries,
        stations: records,
    }
}

fn payload_sources() -> Vec<PathBuf> {
    let data = data_dir();
    let repos = repos_data_dir();
    vec![
        data.join("global_stations_snapshot.json"),
        data.join("nordic_geodnet_stations.csv"),
        data.join("norway_only_stations.csv"),
        data.join("nordic_boundaries_10m.geojson"),
        repos.join("station_stats.json"),
        repos.join("daily_summary.json"),
        repos.join("station_events.json"),
    ]
}

fn source_signature() -> Vec<(String, u128, u64)> {
    payload_sources()
        .iter()
        .map(|path| match std::fs::metadata(path) {
            Ok(metadata) => {
                let modified = metadata
                    .modified()
                    .ok()
                    .and_then(|time| time.duration_since(std::time::UNIX_EPOCH).ok())
                    .map(|duration| duration.as_nanos())
                    .unwrap_or(0);
                (path.to_string_lossy().to_string(), modified, metadata.len())
            }
            Err(_) => (path.to_string_lossy().to_string(), 0, 0),
        })
        .collect()
}

static CACHE: OnceLock<Mutex<Option<(Vec<(String, u128, u64)>, Vec<u8>)>>> = OnceLock::new();

pub fn build_body_cached() -> AppResult<Vec<u8>> {
    let signature = source_signature();
    let cell = CACHE.get_or_init(|| Mutex::new(None));
    if let Ok(guard) = cell.lock() {
        if let Some((cached_signature, cached_body)) = guard.as_ref() {
            if *cached_signature == signature {
                return Ok(cached_body.clone());
            }
        }
    }
    let payload = build_payload();
    let body = serde_json::to_vec(&payload)?;
    if let Ok(mut guard) = cell.lock() {
        *guard = Some((signature, body.clone()));
    }
    Ok(body)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn payload_value() -> Value {
        let payload = build_payload();
        match serde_json::to_value(&payload) {
            Ok(value) => value,
            Err(_) => Value::Null,
        }
    }

    #[test]
    fn payload_has_dashboard_keys() {
        let value = payload_value();
        assert!(value.is_object());
        for key in [
            "generated_at",
            "colors",
            "totals",
            "observatories",
            "daily",
            "cohort",
            "boundaries",
            "stations",
        ] {
            assert!(value.get(key).is_some(), "missing top-level key {key}");
        }
        let totals = value.get("totals");
        for key in [
            "global", "active", "online", "offline", "norway", "nordic", "auroral",
        ] {
            assert!(
                totals.and_then(|item| item.get(key)).is_some(),
                "missing totals field {key}"
            );
        }
        let colors = value.get("colors");
        for key in ["ACTIVE", "ONLINE", "OFFLINE"] {
            assert!(
                colors.and_then(|item| item.get(key)).is_some(),
                "missing color key {key}"
            );
        }
    }

    #[test]
    fn station_records_have_schema_fields() {
        let value = payload_value();
        if let Some(stations) = value.get("stations").and_then(|item| item.as_array()) {
            if let Some(first) = stations.first() {
                for key in [
                    "name",
                    "station_id",
                    "status",
                    "lat",
                    "lng",
                    "country_iso",
                    "station_class",
                    "zone",
                    "dist_osls_km",
                    "dist_trom_km",
                    "dist_nya2_km",
                    "flaps",
                    "first_seen_ms",
                    "uptime_pct",
                ] {
                    assert!(first.get(key).is_some(), "missing station field {key}");
                }
                assert!(first.get("active_pct").is_none());
                assert!(first.get("online_pct").is_none());
                assert!(first.get("offline_pct").is_none());
                assert!(first.get("transitions").is_none());
            }
        }
    }

    #[test]
    fn cohort_shape_and_no_removed_keys() {
        let value = payload_value();
        let cohort = value.get("cohort");
        assert!(cohort.and_then(|item| item.get("bars")).is_some());
        assert!(cohort.and_then(|item| item.get("total")).is_some());
        assert!(value.get("bands").is_none());
        assert!(value.get("flaps").is_none());
    }
}
