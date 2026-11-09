use std::net::SocketAddr;
use std::path::PathBuf;
use std::process::Command;

use tokio::io::{AsyncReadExt, AsyncWriteExt};
use tokio::net::{TcpListener, TcpStream};

use crate::error::{AppError, AppResult};
use crate::payload;

const PORT_RANGE_START: u16 = 8085;
const PORT_RANGE_END: u16 = 8095;

pub async fn run() -> AppResult<()> {
    let (listener, port) = bind_listener().await?;
    let url = format!("http://127.0.0.1:{port}/");
    println!("telemetry dashboard : {url}");
    println!("telemetry api       : {url}api/telemetry");
    if std::env::var("UIO_GNSS_NO_BROWSER").is_err() {
        let open_url = url.clone();
        tokio::spawn(async move {
            tokio::time::sleep(std::time::Duration::from_millis(600)).await;
            open_browser(&open_url);
        });
    }
    loop {
        match listener.accept().await {
            Ok((stream, _peer)) => {
                tokio::spawn(async move {
                    if let Err(error) = handle_connection(stream).await {
                        eprintln!("connection error: {error}");
                    }
                });
            }
            Err(error) => {
                eprintln!("accept error: {error}");
            }
        }
    }
}

async fn bind_listener() -> AppResult<(TcpListener, u16)> {
    for port in PORT_RANGE_START..=PORT_RANGE_END {
        let address = SocketAddr::from(([127, 0, 0, 1], port));
        match TcpListener::bind(address).await {
            Ok(listener) => return Ok((listener, port)),
            Err(_) => continue,
        }
    }
    Err(AppError::InvalidData(
        "no free port available in range".to_string(),
    ))
}

async fn handle_connection(mut stream: TcpStream) -> AppResult<()> {
    let mut buffer = [0u8; 4096];
    let read = stream.read(&mut buffer).await?;
    if read == 0 {
        return Ok(());
    }
    let request = String::from_utf8_lossy(&buffer[..read]);
    let first_line = request.lines().next().unwrap_or("");
    let mut parts = first_line.split_whitespace();
    let method = parts.next().unwrap_or("");
    let raw_path = parts.next().unwrap_or("/");
    let path = raw_path.split('?').next().unwrap_or("/");
    if method != "GET" {
        return write_response(
            &mut stream,
            405,
            "text/plain; charset=utf-8",
            b"method not allowed",
        )
        .await;
    }
    match path {
        "/" | "/index.html" | "/dashboard.html" => serve_dashboard(&mut stream).await,
        "/api/telemetry" => serve_api(&mut stream).await,
        _ => write_response(&mut stream, 404, "text/plain; charset=utf-8", b"not found").await,
    }
}

async fn serve_dashboard(stream: &mut TcpStream) -> AppResult<()> {
    let path = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("src")
        .join("dashboard.html");
    match tokio::fs::read(&path).await {
        Ok(body) => {
            write_response(stream, 200, "text/html; charset=utf-8", &body).await
        }
        Err(_) => {
            write_response(
                stream,
                500,
                "text/plain; charset=utf-8",
                b"dashboard.html missing",
            )
            .await
        }
    }
}

async fn serve_api(stream: &mut TcpStream) -> AppResult<()> {
    let result = tokio::task::spawn_blocking(payload::build_body_cached).await;
    match result {
        Ok(Ok(body)) => {
            write_response(stream, 200, "application/json; charset=utf-8", &body).await
        }
        Ok(Err(error)) => {
            let message = serde_json::json!({ "error": error.to_string() }).to_string();
            write_response(
                stream,
                500,
                "application/json; charset=utf-8",
                message.as_bytes(),
            )
            .await
        }
        Err(_) => {
            write_response(
                stream,
                500,
                "application/json; charset=utf-8",
                b"{\"error\":\"join failure\"}",
            )
            .await
        }
    }
}

async fn write_response(
    stream: &mut TcpStream,
    status: u16,
    content_type: &str,
    body: &[u8],
) -> AppResult<()> {
    let reason = status_text(status);
    let header = format!(
        "HTTP/1.1 {status} {reason}\r\nContent-Type: {content_type}\r\nContent-Length: {}\r\nCache-Control: no-store\r\nConnection: close\r\n\r\n",
        body.len()
    );
    stream.write_all(header.as_bytes()).await?;
    stream.write_all(body).await?;
    stream.flush().await?;
    Ok(())
}

fn status_text(status: u16) -> &'static str {
    match status {
        200 => "OK",
        404 => "Not Found",
        405 => "Method Not Allowed",
        500 => "Internal Server Error",
        _ => "OK",
    }
}

fn open_browser(url: &str) {
    let result = if cfg!(target_os = "windows") {
        Command::new("cmd").args(["/c", "start", "", url]).spawn()
    } else if cfg!(target_os = "macos") {
        Command::new("open").arg(url).spawn()
    } else {
        Command::new("xdg-open").arg(url).spawn()
    };
    if result.is_err() {
        eprintln!("could not open browser automatically");
    }
}
