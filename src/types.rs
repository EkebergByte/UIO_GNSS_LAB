use serde::{Deserialize, Serialize};

pub const OSLS_LAT: f64 = 59.7366;
pub const OSLS_LNG: f64 = 10.3683;
pub const TROM_LAT: f64 = 69.6627;
pub const TROM_LNG: f64 = 18.9396;
pub const NYA2_LAT: f64 = 78.9296;
pub const NYA2_LNG: f64 = 11.8653;

pub const EARTH_RADIUS_KM: f64 = 6371.0088;
pub const KM_PER_DEG_LAT: f64 = 110.574;
pub const KM_PER_DEG_LNG: f64 = 111.320;
pub const EPSILON: f64 = 1e-12;

pub const CSV_HEADER: &str = "station_id,name,status,lat,lng,country_iso,match_method,station_class,zone,dist_to_osls_km,dist_to_trom_km,dist_to_nya2_km";

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum Status {
    Active,
    Online,
    Offline,
    Unknown,
}

impl Status {
    pub fn from_raw(raw: &str) -> Status {
        match raw.to_uppercase().as_str() {
            "ACTIVE" => Status::Active,
            "ONLINE" => Status::Online,
            "OFFLINE" => Status::Offline,
            _ => Status::Unknown,
        }
    }

    pub fn label(&self) -> &'static str {
        match self {
            Status::Active => "ACTIVE",
            Status::Online => "ONLINE",
            Status::Offline => "OFFLINE",
            Status::Unknown => "UNKNOWN",
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Station {
    pub station_id: i64,
    pub name: String,
    pub status: String,
    pub lat: f64,
    pub lng: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StationRow {
    pub station_id: i64,
    pub name: String,
    pub status: String,
    pub lat: f64,
    pub lng: f64,
    pub country_iso: String,
    pub match_method: String,
    pub station_class: String,
    pub zone: String,
    pub dist_to_osls_km: f64,
    pub dist_to_trom_km: f64,
    pub dist_to_nya2_km: f64,
}
