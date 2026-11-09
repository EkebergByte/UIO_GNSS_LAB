use std::collections::HashMap;

use serde_json::Value;

use crate::error::{AppError, AppResult};
use crate::types::{EPSILON, EARTH_RADIUS_KM, KM_PER_DEG_LAT, KM_PER_DEG_LNG};

const EXACT_ORDER: [&str; 10] = ["NOR", "SWE", "FIN", "DNK", "ISL", "RUS", "EST", "LVA", "GBR", "DEU"];
const BUFFER_ORDER: [&str; 6] = ["NOR", "SWE", "FIN", "DNK", "ISL", "RUS"];
const NORDIC_KEEP: [&str; 5] = ["NOR", "SWE", "FIN", "DNK", "ISL"];
const COASTAL_BUFFER_KM: f64 = 20.0;
const COASTAL_MARGIN_FACTOR: f64 = 1.5;
const MISSING_DISTANCE: f64 = 1.0e9;
const CANDIDATE_MIN_LAT: f64 = 53.0;
const CANDIDATE_MAX_LAT: f64 = 82.0;
const CANDIDATE_MIN_LNG: f64 = -30.0;
const CANDIDATE_MAX_LNG: f64 = 35.0;
const SVALBARD_MIN_LAT: f64 = 74.0;
const NORTH_LAT_THRESHOLD: f64 = 65.0;
const CENTRAL_LAT_THRESHOLD: f64 = 62.0;
const OSLO_LNG_THRESHOLD: f64 = 9.0;

#[derive(Debug, Clone)]
pub struct Ring {
    pub points: Vec<[f64; 2]>,
    pub bbox: [f64; 4],
}

#[derive(Debug, Clone)]
pub struct Polygon {
    pub outer: Ring,
    pub holes: Vec<Ring>,
}

#[derive(Debug, Clone, Default)]
pub struct Country {
    pub polygons: Vec<Polygon>,
    pub rings: Vec<Ring>,
}

pub fn clamp(value: f64, low: f64, high: f64) -> f64 {
    if !value.is_finite() {
        return low;
    }
    value.max(low).min(high)
}

pub fn safe_round(value: f64, digits: usize) -> f64 {
    if !value.is_finite() {
        return 0.0;
    }
    let text = format!("{:.*}", digits, value);
    match text.parse::<f64>() {
        Ok(parsed) => parsed,
        Err(_) => value,
    }
}

pub fn ring_bbox(points: &[[f64; 2]]) -> [f64; 4] {
    if points.is_empty() {
        return [0.0, 0.0, 0.0, 0.0];
    }
    let mut min_x = points[0][0];
    let mut max_x = min_x;
    let mut min_y = points[0][1];
    let mut max_y = min_y;
    for point in points {
        let x = point[0];
        let y = point[1];
        if x < min_x {
            min_x = x;
        } else if x > max_x {
            max_x = x;
        }
        if y < min_y {
            min_y = y;
        } else if y > max_y {
            max_y = y;
        }
    }
    [min_x, min_y, max_x, max_y]
}

pub fn point_in_ring(lng: f64, lat: f64, ring: &[[f64; 2]]) -> bool {
    let count = ring.len();
    if count < 3 {
        return false;
    }
    let mut inside = false;
    let x = lng;
    let y = lat;
    let mut j = count - 1;
    for i in 0..count {
        let xi = ring[i][0];
        let yi = ring[i][1];
        let xj = ring[j][0];
        let yj = ring[j][1];
        if (yi > y) != (yj > y) {
            let denominator = yj - yi;
            if denominator.abs() > EPSILON {
                let intersect = (xj - xi) * (y - yi) / denominator + xi;
                if x < intersect {
                    inside = !inside;
                }
            }
        }
        j = i;
    }
    inside
}

pub fn point_in_polygon(lng: f64, lat: f64, polygon: &Polygon) -> bool {
    let bbox = polygon.outer.bbox;
    if !(bbox[0] <= lng && lng <= bbox[2] && bbox[1] <= lat && lat <= bbox[3]) {
        return false;
    }
    if !point_in_ring(lng, lat, &polygon.outer.points) {
        return false;
    }
    for hole in &polygon.holes {
        let hb = hole.bbox;
        if hb[0] <= lng && lng <= hb[2] && hb[1] <= lat && lat <= hb[3] {
            if point_in_ring(lng, lat, &hole.points) {
                return false;
            }
        }
    }
    true
}

fn point_segment_km(lng: f64, lat: f64, x1: f64, y1: f64, x2: f64, y2: f64) -> f64 {
    let lat_ref = clamp(lat, -90.0, 90.0).to_radians();
    let kx = KM_PER_DEG_LNG * lat_ref.cos();
    let ky = KM_PER_DEG_LAT;
    let ax = (x1 - lng) * kx;
    let ay = (y1 - lat) * ky;
    let bx = (x2 - lng) * kx;
    let by = (y2 - lat) * ky;
    let abx = bx - ax;
    let aby = by - ay;
    let denominator = abx * abx + aby * aby;
    let distance = if denominator <= EPSILON {
        ax.hypot(ay)
    } else {
        let mut t = -(ax * abx + ay * aby) / denominator;
        t = clamp(t, 0.0, 1.0);
        let cx = ax + t * abx;
        let cy = ay + t * aby;
        cx.hypot(cy)
    };
    if !distance.is_finite() {
        MISSING_DISTANCE
    } else {
        distance
    }
}

pub fn ring_min_distance(lng: f64, lat: f64, points: &[[f64; 2]]) -> f64 {
    let count = points.len();
    if count < 2 {
        return MISSING_DISTANCE;
    }
    let mut best = MISSING_DISTANCE;
    for i in 0..count {
        let p1 = points[i];
        let p2 = points[(i + 1) % count];
        let distance = point_segment_km(lng, lat, p1[0], p1[1], p2[0], p2[1]);
        if distance < best {
            best = distance;
        }
    }
    best
}

fn box_within_km(bbox: [f64; 4], lng: f64, lat: f64, km: f64) -> bool {
    let lat_margin = km / KM_PER_DEG_LAT;
    let cos_lat = clamp(lat, -89.5, 89.5).to_radians().cos();
    let lng_margin = if cos_lat.abs() > EPSILON {
        km / (KM_PER_DEG_LNG * cos_lat)
    } else {
        180.0
    };
    let min_x = bbox[0];
    let min_y = bbox[1];
    let max_x = bbox[2];
    let max_y = bbox[3];
    (min_x - lng_margin <= lng && lng <= max_x + lng_margin)
        && (min_y - lat_margin <= lat && lat <= max_y + lat_margin)
}

pub fn nearest_coast(
    lng: f64,
    lat: f64,
    countries: &HashMap<String, Country>,
) -> (Option<String>, f64) {
    let mut best_iso: Option<String> = None;
    let mut best_km = MISSING_DISTANCE;
    let margin = COASTAL_BUFFER_KM * COASTAL_MARGIN_FACTOR;
    for iso in BUFFER_ORDER {
        if let Some(entry) = countries.get(iso) {
            for ring in &entry.rings {
                if !box_within_km(ring.bbox, lng, lat, margin) {
                    continue;
                }
                let distance = ring_min_distance(lng, lat, &ring.points);
                if distance < best_km {
                    best_km = distance;
                    best_iso = Some(iso.to_string());
                    if best_km <= 0.0 {
                        return (best_iso, 0.0);
                    }
                }
            }
        }
    }
    (best_iso, best_km)
}

pub fn classify(
    lng: f64,
    lat: f64,
    countries: &HashMap<String, Country>,
) -> (Option<String>, Option<String>) {
    for iso in EXACT_ORDER {
        if let Some(entry) = countries.get(iso) {
            for polygon in &entry.polygons {
                if point_in_polygon(lng, lat, polygon) {
                    return (Some(iso.to_string()), Some("EXACT_POLYGON".to_string()));
                }
            }
        }
    }
    let (iso_opt, distance) = nearest_coast(lng, lat, countries);
    if let Some(code) = iso_opt {
        if distance <= COASTAL_BUFFER_KM {
            return (Some(code), Some("COASTAL_BUFFER".to_string()));
        }
    }
    (None, None)
}

pub fn haversine_km(lat1: f64, lon1: f64, lat2: f64, lon2: f64) -> f64 {
    let rlat1 = clamp(lat1, -90.0, 90.0).to_radians();
    let rlat2 = clamp(lat2, -90.0, 90.0).to_radians();
    let dlat = rlat2 - rlat1;
    let dlon = (clamp(lon2, -180.0, 180.0) - clamp(lon1, -180.0, 180.0)).to_radians();
    let sin_lat = (dlat / 2.0).sin();
    let sin_lon = (dlon / 2.0).sin();
    let mut a = sin_lat * sin_lat + rlat1.cos() * rlat2.cos() * sin_lon * sin_lon;
    a = clamp(a, 0.0, 1.0);
    let root = a.max(0.0).sqrt();
    let distance = 2.0 * EARTH_RADIUS_KM * clamp(root, 0.0, 1.0).asin();
    if !distance.is_finite() {
        0.0
    } else {
        distance
    }
}

pub fn station_class(name: &str) -> &'static str {
    if name.starts_with("****") {
        "GEODNET_MINER"
    } else {
        "PUBLIC_IGS_EUREF"
    }
}

pub fn assign_zone(iso: &str, lat: f64, lng: f64) -> String {
    if iso == "NOR" {
        if lat >= SVALBARD_MIN_LAT {
            return "NO-Svalbard-Arctic".to_string();
        }
        if lat >= NORTH_LAT_THRESHOLD {
            return "NO-North-Auroral".to_string();
        }
        if lat >= CENTRAL_LAT_THRESHOLD {
            return "NO-Central-Trondelag".to_string();
        }
        if lng >= OSLO_LNG_THRESHOLD {
            return "NO-South-Oslo-Ostlandet".to_string();
        }
        return "NO-South-West-Vestlandet".to_string();
    }
    match iso {
        "SWE" => "SE-Sweden".to_string(),
        "FIN" => "FI-Finland".to_string(),
        "DNK" => "DK-Denmark".to_string(),
        "ISL" => "IS-Iceland".to_string(),
        other => other.to_string(),
    }
}

pub fn in_candidate_region(lat: f64, lng: f64) -> bool {
    (CANDIDATE_MIN_LAT <= lat && lat <= CANDIDATE_MAX_LAT)
        && (CANDIDATE_MIN_LNG <= lng && lng <= CANDIDATE_MAX_LNG)
}

pub fn is_nordic_kept(iso: &str) -> bool {
    NORDIC_KEEP.contains(&iso)
}

fn parse_ring(value: &Value) -> Vec<[f64; 2]> {
    let mut points = Vec::new();
    if let Some(array) = value.as_array() {
        for point in array {
            if let Some(pair) = point.as_array() {
                if pair.len() >= 2 {
                    let x = pair[0].as_f64();
                    let y = pair[1].as_f64();
                    if let (Some(x), Some(y)) = (x, y) {
                        if x.is_finite() && y.is_finite() {
                            points.push([x, y]);
                        }
                    }
                }
            }
        }
    }
    points
}

fn parse_polygon(raw: &Value) -> Option<Polygon> {
    let rings = raw.as_array()?;
    let outer_value = rings.first()?;
    let outer_points = parse_ring(outer_value);
    if outer_points.is_empty() {
        return None;
    }
    let outer = Ring {
        bbox: ring_bbox(&outer_points),
        points: outer_points,
    };
    let mut holes = Vec::new();
    for hole_value in rings.iter().skip(1) {
        let hole_points = parse_ring(hole_value);
        if hole_points.is_empty() {
            continue;
        }
        holes.push(Ring {
            bbox: ring_bbox(&hole_points),
            points: hole_points,
        });
    }
    Some(Polygon { outer, holes })
}

fn parse_polygons(gtype: &str, coords: Option<&Value>) -> Vec<Polygon> {
    let mut out = Vec::new();
    let coords = match coords {
        Some(value) => value,
        None => return out,
    };
    if gtype == "Polygon" {
        if let Some(polygon) = parse_polygon(coords) {
            out.push(polygon);
        }
    } else if let Some(array) = coords.as_array() {
        for item in array {
            if let Some(polygon) = parse_polygon(item) {
                out.push(polygon);
            }
        }
    }
    out
}

pub fn load_countries(path: &str) -> AppResult<HashMap<String, Country>> {
    let text = std::fs::read_to_string(path)
        .map_err(|error| AppError::MissingData(format!("{path}: {error}")))?;
    let root: Value = serde_json::from_str(&text)?;
    let features = root
        .get("features")
        .and_then(|value| value.as_array())
        .ok_or_else(|| AppError::InvalidData("features missing".to_string()))?;
    let mut map: HashMap<String, Country> = HashMap::new();
    for feature in features {
        let iso = match feature
            .get("properties")
            .and_then(|props| props.get("iso"))
            .and_then(|value| value.as_str())
        {
            Some(code) => code.to_string(),
            None => continue,
        };
        let geometry = match feature.get("geometry") {
            Some(value) => value,
            None => continue,
        };
        let gtype = geometry
            .get("type")
            .and_then(|value| value.as_str())
            .unwrap_or("");
        let coords = geometry.get("coordinates");
        let polygons = parse_polygons(gtype, coords);
        let entry = map.entry(iso).or_insert_with(Country::default);
        for polygon in &polygons {
            entry.rings.push(Ring {
                points: polygon.outer.points.clone(),
                bbox: polygon.outer.bbox,
            });
            for hole in &polygon.holes {
                entry.rings.push(Ring {
                    points: hole.points.clone(),
                    bbox: hole.bbox,
                });
            }
        }
        entry.polygons.extend(polygons);
    }
    Ok(map)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn square_ring() -> Vec<[f64; 2]> {
        vec![[0.0, 0.0], [20.0, 0.0], [20.0, 20.0], [0.0, 20.0]]
    }

    #[test]
    fn haversine_zero() {
        assert_eq!(haversine_km(59.7, 10.3, 59.7, 10.3), 0.0);
    }

    #[test]
    fn haversine_oslo_tromso() {
        let distance = haversine_km(59.7366, 10.3683, 69.6627, 18.9396);
        assert!(distance > 1000.0 && distance < 1200.0);
    }

    #[test]
    fn ring_bbox_square() {
        assert_eq!(ring_bbox(&square_ring()), [0.0, 0.0, 20.0, 20.0]);
    }

    #[test]
    fn point_in_ring_inside_outside() {
        let ring = square_ring();
        assert!(point_in_ring(10.0, 10.0, &ring));
        assert!(!point_in_ring(30.0, 10.0, &ring));
    }

    #[test]
    fn point_in_polygon_hole() {
        let outer = square_ring();
        let hole = vec![[8.0, 8.0], [12.0, 8.0], [12.0, 12.0], [8.0, 12.0]];
        let polygon = Polygon {
            outer: Ring {
                bbox: ring_bbox(&outer),
                points: outer,
            },
            holes: vec![Ring {
                bbox: ring_bbox(&hole),
                points: hole,
            }],
        };
        assert!(point_in_polygon(2.0, 2.0, &polygon));
        assert!(!point_in_polygon(10.0, 10.0, &polygon));
    }

    #[test]
    fn zone_assignment() {
        assert_eq!(assign_zone("NOR", 75.0, 15.0), "NO-Svalbard-Arctic");
        assert_eq!(assign_zone("NOR", 66.0, 15.0), "NO-North-Auroral");
        assert_eq!(assign_zone("NOR", 63.0, 15.0), "NO-Central-Trondelag");
        assert_eq!(assign_zone("NOR", 60.0, 10.0), "NO-South-Oslo-Ostlandet");
        assert_eq!(assign_zone("NOR", 60.0, 5.0), "NO-South-West-Vestlandet");
        assert_eq!(assign_zone("SWE", 59.0, 18.0), "SE-Sweden");
    }

    #[test]
    fn hardware_class() {
        assert_eq!(station_class("****ABC"), "GEODNET_MINER");
        assert_eq!(station_class("OSLS"), "PUBLIC_IGS_EUREF");
    }

    #[test]
    fn safe_round_non_finite() {
        assert_eq!(safe_round(f64::NAN, 4), 0.0);
        assert_eq!(safe_round(f64::INFINITY, 4), 0.0);
        assert_eq!(safe_round(59.123456, 4), 59.1235);
    }
}
