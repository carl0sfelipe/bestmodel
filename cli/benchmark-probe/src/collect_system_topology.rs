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
    } else if cfg!(target_os = "linux") {
        std::fs::read_to_string("/etc/os-release")
            .ok()
            .and_then(|raw| parse_os_release_pretty(&raw))
            .unwrap_or_default()
    } else {
        String::new()
    }
}

fn detect_cpu_model() -> String {
    if cfg!(target_os = "macos") {
        run_output(&["sysctl", "-n", "machdep.cpu.brand_string"])
            .or_else(|| run_output(&["sysctl", "-n", "hw.model"]))
            .unwrap_or_default()
    } else if cfg!(target_os = "linux") {
        std::fs::read_to_string("/proc/cpuinfo")
            .ok()
            .and_then(|raw| parse_cpuinfo_model(&raw))
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
    } else if cfg!(target_os = "linux") {
        // NVIDIA first: it is what cloud VMs and the measured fleet run.
        // Anything else (AMD/Intel discrete, hybrid laptops) is simply not
        // detected — an empty list, never an invented GPU.
        let raw = run_with_timeout(
            &[
                "nvidia-smi",
                "--query-gpu=name,memory.total",
                "--format=csv,noheader",
            ],
            SYSTEM_PROFILER_TIMEOUT,
        );
        parse_nvidia_smi_gpus(raw.as_deref())
    } else {
        Vec::new()
    }
}

/// `PRETTY_NAME="Omarchy"` → `Omarchy`
fn parse_os_release_pretty(raw: &str) -> Option<String> {
    for line in raw.lines() {
        if let Some(value) = line.trim().strip_prefix("PRETTY_NAME=") {
            let cleaned = value.trim().trim_matches('"').trim();
            if !cleaned.is_empty() {
                return Some(cleaned.to_string());
            }
        }
    }
    None
}

/// First `model name	: Intel(R) Xeon(...)` from /proc/cpuinfo (x86).
/// ARM kernels have no `model name` — returns None, the field stays empty
/// rather than guessing.
fn parse_cpuinfo_model(raw: &str) -> Option<String> {
    for line in raw.lines() {
        if let Some((key, value)) = line.split_once(':') {
            if key.trim() == "model name" {
                let cleaned = value.trim();
                if !cleaned.is_empty() {
                    return Some(cleaned.to_string());
                }
            }
        }
    }
    None
}

/// nvidia-smi CSV lines like `NVIDIA GeForce RTX 3090, 24576 MiB`
/// (one per GPU). VRAM without a MiB unit is left as None — never guessed.
fn parse_nvidia_smi_gpus(raw: Option<&str>) -> Vec<GpuInfo> {
    let Some(raw) = raw else {
        return Vec::new();
    };
    raw.lines()
        .filter_map(|line| {
            let (name, vram) = line.split_once(',')?;
            let name = name.trim();
            if name.is_empty() {
                return None;
            }
            let vram_mib = vram.trim().split_whitespace().next().and_then(|number| {
                if vram.trim().ends_with("MiB") {
                    number.parse::<u64>().ok()
                } else {
                    None
                }
            });
            Some(GpuInfo {
                name: name.to_string(),
                vram_mib,
            })
        })
        .collect()
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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn os_release_pretty_name() {
        let raw = "NAME=\"Ubuntu\"\nVERSION=\"24.04.1 LTS (Noble Numbat)\"\nPRETTY_NAME=\"Ubuntu 24.04.1 LTS\"\n";
        assert_eq!(parse_os_release_pretty(raw).as_deref(), Some("Ubuntu 24.04.1 LTS"));
        assert_eq!(parse_os_release_pretty("NAME=x\n"), None);
    }

    #[test]
    fn cpuinfo_model_name() {
        let raw = "processor\t: 0\nvendor_id\t: GenuineIntel\nmodel name\t: Intel(R) Xeon(R) CPU E5-2680 v4 @ 2.40GHz\nflags\t: avx2\n";
        assert_eq!(
            parse_cpuinfo_model(raw).as_deref(),
            Some("Intel(R) Xeon(R) CPU E5-2680 v4 @ 2.40GHz")
        );
        // ARM cpuinfo has no model name: honest None
        assert_eq!(parse_cpuinfo_model("processor: 0\nBogoMIPS: 38.40\n"), None);
    }

    #[test]
    fn nvidia_smi_csv_single_and_multi_gpu() {
        let raw = Some("NVIDIA GeForce RTX 3090, 24576 MiB\n");
        let gpus = parse_nvidia_smi_gpus(raw);
        assert_eq!(gpus.len(), 1);
        assert_eq!(gpus[0].name, "NVIDIA GeForce RTX 3090");
        assert_eq!(gpus[0].vram_mib, Some(24576));

        let raw = Some("NVIDIA A10G, 23028 MiB\nNVIDIA A10G, 23028 MiB\n");
        let gpus = parse_nvidia_smi_gpus(raw);
        assert_eq!(gpus.len(), 2);

        // unknown unit or missing vram: name kept, vram None (never guessed)
        let gpus = parse_nvidia_smi_gpus(Some("NVIDIA GPU, 24 GB\n"));
        assert_eq!(gpus[0].vram_mib, None);
        assert_eq!(parse_nvidia_smi_gpus(None).len(), 0);
    }
}
