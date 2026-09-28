//! Shared immutable vocabulary for detecting secret-like command/process text.

/// Stable non-secret token prefixes shared by redaction consumers.
pub const WORKGPT_SECRET_PREFIXES: &[&str] = &[
    "wg_pat_",
    "wg_agent_",
    "wg_acct_",
    "wg_oat_",
    "wg_ort_",
    "wg_csec_",
    "wg_pair_",
    "wg_boot_",
];

/// Conservative detector used before emitting command/process previews.
pub fn secret_like_value(value: &str) -> bool {
    let lower = value.to_ascii_lowercase();
    lower.contains("-----begin")
        || lower.contains("bearer ")
        || lower.contains("api_key")
        || lower.contains("token=")
        || lower.contains("id_rsa")
        || lower.contains("id_ed25519")
        || WORKGPT_SECRET_PREFIXES
            .iter()
            .any(|prefix| lower.contains(prefix))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn preserves_shared_secret_detection_vocabulary() {
        for value in [
            "Bearer abc",
            "api_key=value",
            "token=value",
            "-----BEGIN PRIVATE KEY-----",
            "id_rsa",
            "id_ed25519",
            "wg_pat_demo",
            "wg_agent_demo",
            "wg_acct_demo",
            "wg_oat_demo",
            "wg_ort_demo",
            "wg_csec_demo",
            "wg_pair_demo",
            "wg_boot_demo",
        ] {
            assert!(secret_like_value(value), "{value}");
        }
        assert!(!secret_like_value("cargo check -p workgpt"));
    }
}
