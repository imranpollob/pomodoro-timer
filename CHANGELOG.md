# Changelog

All notable changes are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Fixed
- CI: `compact_size_from_pref` is compiled only on Linux (and in tests), fixing the dead-code lint failure on Windows and macOS.

## [1.0.0]

### Changed
- Promoted the Tauri 2 / Rust / Svelte app to the repository root and removed the legacy Python app. See [MIGRATION.md](MIGRATION.md).
