//! Component discovery for the platform's unified installation layout.
use std::path::{Path, PathBuf};

/// Desktop and the CLI PATH entry must refer to the same runtime files. A
/// partially installed directory is deliberately returned for normal runtime
/// verification to reject, rather than falling back to another installation.
pub fn installed_desktop_runtime_directory(executable: &Path) -> Option<PathBuf> {
    #[cfg(target_os = "macos")]
    if executable.starts_with("/Applications/WorkGPT Desktop.app/Contents/MacOS") {
        let directory = PathBuf::from("/Library/Application Support/WorkGPT/runtime");
        if directory.is_dir() {
            return Some(directory);
        }
    }
    let adjacent = executable.parent()?.join("workgpt-runtime");
    adjacent.is_dir().then_some(adjacent)
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn installed_desktop_uses_the_cli_runtime_directory_and_never_path_search() {
        let root = tempfile::tempdir().unwrap();
        let desktop = root.path().join("WorkGPT");
        assert!(installed_desktop_runtime_directory(&desktop).is_none());
        let runtime = root.path().join("workgpt-runtime");
        std::fs::create_dir(&runtime).unwrap();
        assert_eq!(installed_desktop_runtime_directory(&desktop), Some(runtime));
    }
}
