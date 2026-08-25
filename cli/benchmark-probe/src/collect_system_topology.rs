use std::process::Command;
use std::time::Duration;

pub struct GpuInfo {
    pub name: String,
    pub vram_mib: Option<u64>,
}

pub struct SystemTopology {
    pub os_name: String,
    pub os_version: String,
    pub cpu_model: String,
    pub gpus: Vec<GpuInfo>,
}

const SYSTEM_PROFILER_TIMEOUT: Duration = Duration::from_secs(5);

pub fn collect_system_topology() -> SystemTopology {
    SystemTopology {
        os_name: std::env::consts::OS.to_string(),
        os_version: detect_os_version(),
        cpu_model: detect_cpu_model(),
        gpus: detect_gpus(),
    }
}

fn detect_os_version() -> String {
    if cfg!(target_os = "macos") {
        run_output(&["sysctl", "-n", "kern.osproductversion"]).unwrap_or_default()
    } else {
        String::new()
    }
}

fn detect_cpu_model() -> String {
    if cfg!(target_os = "macos") {
        run_output(&["sysctl", "-n", "machdep.cpu.brand_string"])
            .or_else(|| run_output(&["sysctl", "-n", "hw.model"]))
            .unwrap_or_default()
    } else {
        String::new()
    }
}

fn detect_gpus() -> Vec<GpuInfo> {
    if cfg!(target_os = "macos") {
        let raw = run_with_timeout(
            &["system_profiler", "SPDisplaysDataType"],
            SYSTEM_PROFILER_TIMEOUT,
        );
        parse_system_profiler_gpus(raw.as_deref())
    } else {
        Vec::new()
    }
}

fn run_output(args: &[&str]) -> Option<String> {
    let output = Command::new(args[0]).args(&args[1..]).output().ok()?;
    if !output.status.success() {
        return None;
    }
    Some(String::from_utf8_lossy(&output.stdout).trim().to_string())
}

fn run_with_timeout(args: &[&str], timeout: Duration) -> Option<String> {
    let (tx, rx) = std::sync::mpsc::channel();
    let owned: Vec<String> = args.iter().map(|value| value.to_string()).collect();
    std::thread::spawn(move || {
        let result = Command::new(&owned[0]).args(&owned[1..]).output().ok();
        let _ = tx.send(result);
    });
    rx.recv_timeout(timeout).ok().flatten().and_then(|output| {
        if output.status.success() {
            Some(String::from_utf8_lossy(&output.stdout).into_owned())
        } else {
            None
        }
    })
}

fn parse_system_profiler_gpus(raw: Option<&str>) -> Vec<GpuInfo> {
    let mut gpus = Vec::new();
    let Some(raw) = raw else {
        return gpus;
    };
    let mut current: Option<GpuInfo> = None;
    for line in raw.lines() {
        let trimmed = line.trim();
        if let Some(name) = trimmed.strip_prefix("Chipset Model:") {
            if let Some(gpu) = current.take() {
                gpus.push(gpu);
            }
            current = Some(GpuInfo {
                name: name.trim().to_string(),
                vram_mib: None,
            });
        } else if let Some(gpu) = current.as_mut() {
            if let Some(vram) = trimmed.strip_prefix("VRAM (") {
                if gpu.vram_mib.is_none() {
                    let value = vram.split(':').nth(1).unwrap_or_default().trim();
                    gpu.vram_mib = parse_vram_mib(value);
                }
            }
        }
    }
    if let Some(gpu) = current {
        gpus.push(gpu);
    }
    gpus
}

fn parse_vram_mib(value: &str) -> Option<u64> {
    let mut parts = value.split_whitespace();
    let number: f64 = parts.next()?.parse().ok()?;
    match parts.next()? {
        "GB" | "GiB" => Some((number * 1024.0) as u64),
        "MB" => Some(number as u64),
        _ => None,
    }
}
