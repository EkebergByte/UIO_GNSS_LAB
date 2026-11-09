use std::collections::HashMap;
use std::path::{Path, PathBuf};

use serde_json::Value;

use crate::error::{AppError, AppResult};
use crate::geo;
use crate::types::{Station, StationRow, Status, CSV_HEADER, NYA2_LAT, NYA2_LNG, OSLS_LAT, OSLS_LNG, TROM_LAT, TROM_LNG};

fn base_dir() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
}

fn value_to_f64(value: Option<&Value>) -> Option<f64> {
    match value {
        Some(Value::Number(number)) => number.as_f64(),
        Some(Value::String(text)) => text.trim().parse::<f64>().ok(),
        _ => None,
    }
}

fn parse_id(value: Option<&Value>) -> i64 {
    match value {
        Some(Value::Bool(_)) => 0,
        Some(Value::Number(number)) => number.as_i64().unwrap_or(0),
        Some(Value::String(text)) => text.trim().parse::<i64>().unwrap_or(0),
        _ => 0,
    }
}

fn parse_station(item: &Value) -> Option<Station> {
    let lat = value_to_f64(item.get("lat"))?;
    let lng = value_to_f64(item.get("lng"))?;
    if !(lat.is_finite() && lng.is_finite()) {
        return None;
    }
    let station_id = parse_id(item.get("stationId"));
    let name = item
        .get("name")
        .and_then(|value| value.as_str())
        .unwrap_or("")
        .to_string();
    let status = item
        .get("status")
        .and_then(|value| value.as_str())
        .unwrap_or("")
        .to_uppercase();
    Some(Station {
        station_id,
        name,
        status,
        lat,
        lng,
    })
}

pub fn build_row(station: &Station, iso: &str, method: &str) -> StationRow {
    StationRow {
        station_id: station.station_id,
        name: station.name.clone(),
        status: station.status.clone(),
        lat: geo::safe_round(station.lat, 5),
        lng: geo::safe_round(station.lng, 5),
        country_iso: iso.to_string(),
        match_method: method.to_string(),
        station_class: geo::station_class(&station.name).to_string(),
        zone: geo::assign_zone(iso, station.lat, station.lng),
        dist_to_osls_km: geo::safe_round(
            geo::haversine_km(station.lat, station.lng, OSLS_LAT, OSLS_LNG),
            4,
        ),
        dist_to_trom_km: geo::safe_round(
            geo::haversine_km(station.lat, station.lng, TROM_LAT, TROM_LNG),
            4,
        ),
        dist_to_nya2_km: geo::safe_round(
            geo::haversine_km(station.lat, station.lng, NYA2_LAT, NYA2_LNG),
            4,
        ),
    }
}

fn atomic_write_text(path: &Path, content: &str) -> AppResult<()> {
    let tmp = PathBuf::from(format!("{}.tmp", path.display()));
    std::fs::write(&tmp, content.as_bytes())?;
    std::fs::rename(&tmp, path)?;
    Ok(())
}

pub fn build_csv(rows: &[StationRow]) -> String {
    let mut out = String::new();
    out.push_str(CSV_HEADER);
    out.push('\n');
    for row in rows {
        out.push_str(&row.station_id.to_string());
        out.push(',');
        out.push_str(&row.name);
        out.push(',');
        out.push_str(&row.status);
        out.push(',');
        out.push_str(&format!("{:.5}", row.lat));
        out.push(',');
        out.push_str(&format!("{:.5}", row.lng));
        out.push(',');
        out.push_str(&row.country_iso);
        out.push(',');
        out.push_str(&row.match_method);
        out.push(',');
        out.push_str(&row.station_class);
        out.push(',');
        out.push_str(&row.zone);
        out.push(',');
        out.push_str(&format!("{:.4}", row.dist_to_osls_km));
        out.push(',');
        out.push_str(&format!("{:.4}", row.dist_to_trom_km));
        out.push(',');
        out.push_str(&format!("{:.4}", row.dist_to_nya2_km));
        out.push('\n');
    }
    out
}

pub fn run() -> AppResult<()> {
    let base = base_dir();
    let data_dir = base.join("data");
    let snapshot_path = data_dir.join("global_stations_snapshot.json");
    let boundary_path = data_dir.join("nordic_boundaries_10m.geojson");
    if !snapshot_path.is_file() {
        return Err(AppError::MissingData(snapshot_path.display().to_string()));
    }
    let snapshot_text = std::fs::read_to_string(&snapshot_path)?;
    let snapshot: Value = serde_json::from_str(&snapshot_text)?;
    let mut stations: Vec<Station> = Vec::new();
    if let Some(array) = snapshot.get("data").and_then(|value| value.as_array()) {
        for item in array {
            if let Some(station) = parse_station(item) {
                stations.push(station);
            }
        }
    }
    let countries = geo::load_countries(&boundary_path.to_string_lossy())?;
    let mut status_counts: HashMap<String, u64> = HashMap::new();
    for station in &stations {
        let key = Status::from_raw(&station.status).label().to_string();
        let counter = status_counts.entry(key).or_insert(0);
        *counter += 1;
    }
    let total = stations.len();
    let mut rows: Vec<StationRow> = Vec::new();
    for station in &stations {
        if !geo::in_candidate_region(station.lat, station.lng) {
            continue;
        }
        let (iso_opt, method_opt) = geo::classify(station.lng, station.lat, &countries);
        let (iso, method) = match (iso_opt, method_opt) {
            (Some(iso), Some(method)) => (iso, method),
            _ => continue,
        };
        if !geo::is_nordic_kept(&iso) {
            continue;
        }
        rows.push(build_row(station, &iso, &method));
    }
    rows.sort_by(|left, right| {
        left.country_iso
            .cmp(&right.country_iso)
            .then_with(|| left.dist_to_osls_km.total_cmp(&right.dist_to_osls_km))
    });
    let mut norway_rows: Vec<StationRow> = rows
        .iter()
        .filter(|row| row.country_iso == "NOR")
        .cloned()
        .collect();
    norway_rows.sort_by(|left, right| left.dist_to_osls_km.total_cmp(&right.dist_to_osls_km));
    let nordic_csv = build_csv(&rows);
    let norway_csv = build_csv(&norway_rows);
    atomic_write_text(&data_dir.join("nordic_geodnet_stations.csv"), &nordic_csv)?;
    atomic_write_text(&data_dir.join("norway_only_stations.csv"), &norway_csv)?;
    let mut status_keys: Vec<&String> = status_counts.keys().collect();
    status_keys.sort();
    println!("total stations   : {total}");
    for key in status_keys {
        if let Some(count) = status_counts.get(key) {
            println!("   {key:<8}: {count}");
        }
    }
    println!("nordic total     : {}", rows.len());
    println!("norway total     : {}", norway_rows.len());
    println!("csv written      : data/nordic_geodnet_stations.csv");
    println!("norway csv       : data/norway_only_stations.csv");
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sample_row() -> StationRow {
        StationRow {
            station_id: 1,
            name: "****TEST".to_string(),
            status: "ACTIVE".to_string(),
            lat: 59.0,
            lng: 10.0,
            country_iso: "NOR".to_string(),
            match_method: "EXACT_POLYGON".to_string(),
            station_class: "GEODNET_MINER".to_string(),
            zone: "NO-South-Oslo-Ostlandet".to_string(),
            dist_to_osls_km: 1.5,
            dist_to_trom_km: 1110.25,
            dist_to_nya2_km: 2000.0,
        }
    }

    #[test]
    fn csv_header_and_row() {
        let csv = build_csv(&[sample_row()]);
        let mut lines = csv.split('\n');
        assert_eq!(lines.next().unwrap_or(""), CSV_HEADER);
        let row = lines.next().unwrap_or("");
        assert!(row.contains("****TEST"));
        assert!(row.contains("59.00000"));
        assert!(csv.ends_with('\n'));
    }

    #[test]
    fn csv_has_trailing_newline_even_when_empty() {
        let csv = build_csv(&[]);
        assert_eq!(csv, format!("{CSV_HEADER}\n"));
    }
}
