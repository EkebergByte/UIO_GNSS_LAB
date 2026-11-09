use thiserror::Error;

#[derive(Debug, Error)]
pub enum AppError {
    #[error("io error: {0}")]
    Io(#[from] std::io::Error),
    #[error("json error: {0}")]
    Json(#[from] serde_json::Error),
    #[error("missing data file: {0}")]
    MissingData(String),
    #[error("invalid data: {0}")]
    InvalidData(String),
    #[error("not implemented: {0}")]
    NotImplemented(String),
}

pub type AppResult<T> = Result<T, AppError>;
