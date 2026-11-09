mod classify_engine;
mod error;
mod geo;
mod types;

use std::path::PathBuf;
use std::process::ExitCode;

use error::AppError;

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();
    match run(&args) {
        Ok(()) => ExitCode::SUCCESS,
        Err(error) => {
            eprintln!("error: {error}");
            ExitCode::from(1)
        }
    }
}

fn run(args: &[String]) -> error::AppResult<()> {
    if args.is_empty() {
        print_usage();
        return Ok(());
    }
    for arg in args {
        match arg.as_str() {
            "--classify" => classify_engine::run()?,
            "--check-purity" => check_purity()?,
            "--serve" => {
                return Err(AppError::NotImplemented("--serve (Phase R2)".to_string()));
            }
            "--process-iono" => {
                return Err(AppError::NotImplemented(
                    "--process-iono (Phase R3-R4)".to_string(),
                ));
            }
            other => return Err(AppError::InvalidData(format!("unknown option: {other}"))),
        }
    }
    Ok(())
}

fn print_usage() {
    println!("usage: uio-gnss-lab <command>");
    println!("  --classify       classify Nordic stations and refresh CSV files");
    println!("  --check-purity   scan Rust sources for forbidden comment tokens");
    println!("  --serve          start the local dashboard server (Phase R2)");
    println!("  --process-iono   process RINEX and compute STEC/ROTI (Phase R3-R4)");
}

fn check_purity() -> error::AppResult<()> {
    let base = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let src_dir = base.join("src");
    let slash = '/';
    let star = '*';
    let double_slash = format!("{slash}{slash}");
    let block_open = format!("{slash}{star}");
    let block_close = format!("{star}{slash}");
    let mut paths: Vec<PathBuf> = Vec::new();
    for entry in std::fs::read_dir(&src_dir)? {
        let entry = entry?;
        let path = entry.path();
        if path.extension().and_then(|ext| ext.to_str()) == Some("rs") {
            paths.push(path);
        }
    }
    paths.sort();
    let mut checked = 0usize;
    let mut bad = 0usize;
    for path in &paths {
        checked += 1;
        let text = std::fs::read_to_string(path)?;
        for (index, line) in text.lines().enumerate() {
            if line.contains(&block_open) || line.contains(&block_close) {
                println!("BAD {}:{}", path.display(), index + 1);
                bad += 1;
                continue;
            }
            if let Some(position) = line.find(&double_slash) {
                let before = &line[..position];
                if !before.ends_with(':') {
                    println!("BAD {}:{}", path.display(), index + 1);
                    bad += 1;
                }
            }
        }
    }
    if bad > 0 {
        println!("PURITY_FAIL {bad} in {checked} files");
        return Err(AppError::InvalidData(format!(
            "purity failed with {bad} findings"
        )));
    }
    println!("PURITY_OK {checked} files");
    Ok(())
}
