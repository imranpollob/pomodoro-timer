fn main() {
    // Only public project identifiers are embedded. OAuth secrets stay in Supabase.
    println!("cargo:rerun-if-changed=../.env.local");
    let config = std::fs::read_to_string("../.env.local").unwrap_or_default();
    for name in ["SUPABASE_URL", "SUPABASE_PUBLISHABLE_KEY"] {
        println!("cargo:rerun-if-env-changed={name}");
        let value = std::env::var(name)
            .ok()
            .or_else(|| {
                config.lines().find_map(|line| {
                    let (key, value) = line.trim().split_once('=')?;
                    (key.trim() == name).then(|| value.trim().trim_matches(['\"', '\'']).to_owned())
                })
            })
            .unwrap_or_default();
        assert!(
            !value.contains(['\r', '\n']),
            "Invalid public Supabase configuration"
        );
        println!("cargo:rustc-env={name}={value}");
    }
    tauri_build::build()
}
