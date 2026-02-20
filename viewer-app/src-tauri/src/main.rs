// Keep console visible for now so we can see errors
// TODO: re-enable once stable: #![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::path::PathBuf;
use std::io::Write;
#[tauri::command]
fn read_company_data(repo_path: String) -> Result<serde_json::Value, String> {
    let base = PathBuf::from(&repo_path);
    let company_dir = base.join("_company");

    if !company_dir.exists() {
        return Err(format!("No _company directory found at {}", repo_path));
    }

    let mut result = serde_json::Map::new();

    // Read each data file, returning null for missing optional files
    let files = vec![
        ("org_chart", "org_chart.json"),
        ("company_config", "company_config.json"),
        ("engagement_registry", "engagement_registry.json"),
        ("engagement_map", "engagement_map.json"),
        ("file_index", "file_index.json"),
    ];

    for (key, filename) in files {
        let path = company_dir.join(filename);
        if path.exists() {
            let content = std::fs::read_to_string(&path)
                .map_err(|e| format!("Failed to read {}: {}", filename, e))?;
            let value: serde_json::Value = serde_json::from_str(&content)
                .map_err(|e| format!("Failed to parse {}: {}", filename, e))?;
            result.insert(key.to_string(), value);
        } else {
            result.insert(key.to_string(), serde_json::Value::Null);
        }
    }

    // Scan for KNOWLEDGE_LOG.md files in engagement dirs
    let mut knowledge_entries: Vec<serde_json::Value> = Vec::new();
    if let Ok(entries) = std::fs::read_dir(&base) {
        for entry in entries.flatten() {
            let path = entry.path();
            if path.is_dir() && path.join("engagement_config.json").exists() {
                scan_knowledge_logs(&path, &mut knowledge_entries);
            }
        }
    }
    result.insert("knowledge".to_string(), serde_json::Value::Array(knowledge_entries));

    Ok(serde_json::Value::Object(result))
}

fn scan_knowledge_logs(engagement_dir: &PathBuf, entries: &mut Vec<serde_json::Value>) {
    let eng_name = engagement_dir
        .file_name()
        .unwrap_or_default()
        .to_string_lossy()
        .to_string();

    if let Ok(dir_entries) = std::fs::read_dir(engagement_dir) {
        for entry in dir_entries.flatten() {
            let path = entry.path();
            if path.is_dir() {
                let log_path = path.join("KNOWLEDGE_LOG.md");
                if log_path.exists() {
                    let workstream = path
                        .file_name()
                        .unwrap_or_default()
                        .to_string_lossy()
                        .to_string();
                    if let Ok(content) = std::fs::read_to_string(&log_path) {
                        parse_knowledge_log(&content, &eng_name, &workstream, entries);
                    }
                }
            }
        }
    }
}

fn parse_knowledge_log(
    content: &str,
    engagement: &str,
    workstream: &str,
    entries: &mut Vec<serde_json::Value>,
) {
    let mut current_date = String::new();
    let mut current_type = String::new();
    let mut current_summary = String::new();
    let mut current_detail = String::new();
    let mut current_source = String::new();
    let mut in_entry = false;

    for line in content.lines() {
        if line.starts_with("## ") && !line.starts_with("### ") {
            // Date header
            if in_entry {
                push_entry(
                    entries, engagement, workstream, &current_date,
                    &current_type, &current_summary, &current_detail, &current_source,
                );
            }
            current_date = line.trim_start_matches("## ").trim().to_string();
            in_entry = false;
        } else if line.starts_with("### ") {
            if in_entry {
                push_entry(
                    entries, engagement, workstream, &current_date,
                    &current_type, &current_summary, &current_detail, &current_source,
                );
            }
            let header = line.trim_start_matches("### ").trim();
            if let Some(rest) = header.strip_prefix('[') {
                if let Some(bracket_end) = rest.find(']') {
                    current_type = rest[..bracket_end].to_uppercase();
                    current_summary = rest[bracket_end + 1..].trim().to_string();
                } else {
                    current_type = String::new();
                    current_summary = header.to_string();
                }
            } else {
                current_type = String::new();
                current_summary = header.to_string();
            }
            current_detail.clear();
            current_source.clear();
            in_entry = true;
        } else if in_entry {
            let trimmed = line.trim_start_matches("- ");
            if let Some(rest) = trimmed.strip_prefix("**Detail**:") {
                current_detail = rest.trim().to_string();
            } else if let Some(rest) = trimmed.strip_prefix("**Source**:") {
                current_source = rest.trim().to_string();
            }
        }
    }
    if in_entry {
        push_entry(
            entries, engagement, workstream, &current_date,
            &current_type, &current_summary, &current_detail, &current_source,
        );
    }
}

fn push_entry(
    entries: &mut Vec<serde_json::Value>,
    engagement: &str,
    workstream: &str,
    date: &str,
    entry_type: &str,
    summary: &str,
    detail: &str,
    source: &str,
) {
    entries.push(serde_json::json!({
        "engagement": engagement,
        "workstream": workstream,
        "date": date,
        "type": entry_type,
        "summary": summary,
        "detail": detail,
        "source": source,
    }));
}

#[tauri::command]
fn get_repo_from_args() -> Option<String> {
    std::env::args().nth(1)
}

fn main() {
    // Log to file next to the exe for debugging
    let log_path = std::env::current_exe()
        .unwrap_or_default()
        .parent()
        .unwrap_or(std::path::Path::new("."))
        .join("sl-ot-viewer.log");

    let log = |msg: &str| {
        if let Ok(mut f) = std::fs::OpenOptions::new()
            .create(true)
            .append(true)
            .open(&log_path)
        {
            let _ = writeln!(f, "{}", msg);
        }
        eprintln!("{}", msg);
    };

    log("Starting sl-ot-viewer...");

    let result = tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_shell::init())
        .invoke_handler(tauri::generate_handler![read_company_data, get_repo_from_args])
        .run(tauri::generate_context!());

    match result {
        Ok(()) => log("Application exited normally."),
        Err(e) => {
            let msg = format!("Application error: {}", e);
            log(&msg);
            // Keep console open so user can read the error
            eprintln!("\nPress Enter to exit...");
            let _ = std::io::stdin().read_line(&mut String::new());
        }
    }
}
