use std::fs;
use std::path::Path;
use std::process::Command;

pub struct RuntimeInstall {
    pub binary_path: String,
    pub version: Option<String>,
}

pub struct RuntimeInstallations {
    pub llama_cpp: Option<RuntimeInstall>,
    pub ollama: Option<RuntimeInstall>,
}

pub fn detect_runtime_installations() -> RuntimeInstallations {
    RuntimeInstallations {
        llama_cpp: detect_install("llama-cli"),
        ollama: detect_install("ollama"),
    }
}

fn detect_install(binary_name: &str) -> Option<RuntimeInstall> {
    let binary_path = find_executable_in_path(binary_name)?;
    Some(RuntimeInstall {
        version: detect_version(&binary_path),
        binary_path,
    })
}

fn find_executable_in_path(binary_name: &str) -> Option<String> {
    let path_var = std::env::var_os("PATH")?;
    for dir in std::env::split_paths(&path_var) {
        let candidate = dir.join(binary_name);
        if is_executable_file(&candidate) {
            return Some(candidate.to_string_lossy().into_owned());
        }
    }
    None
}

fn is_executable_file(path: &Path) -> bool {
    let Ok(metadata) = fs::metadata(path) else {
        return false;
    };
    if !metadata.is_file() {
        return false;
    }
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        metadata.permissions().mode() & 0o111 != 0
    }
    #[cfg(not(unix))]
    {
        true
    }
}

fn detect_version(binary_path: &str) -> Option<String> {
    let output = Command::new(binary_path).arg("--version").output().ok()?;
    let combined = format!(
        "{}{}",
        String::from_utf8_lossy(&output.stdout),
        String::from_utf8_lossy(&output.stderr)
    );
    combined.lines().next().map(|line| line.trim().to_string())
}
