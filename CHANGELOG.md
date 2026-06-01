# Changelog

## Beta 1.38.4 (2025-06-01)

### Added
- CLI flags: `--version`, `--about`, `--doctor`, `--stats`, `--history`, `--clear-cache`, `--check-update`, `--config`, `--debug`, `--verbose`, `--no-cache`, `--player`, `--quiet`
- `hindi-cli --doctor` — system diagnostics (checks deps, paths, network, config health)
- `hindi-cli --stats` — usage statistics from local database
- `hindi-cli --history` — display watch history in terminal
- `hindi-cli --clear-cache` — clear all cached data
- `hindi-cli --config` — show config file path and contents
- `hindi-cli --check-update` — check GitHub for new releases
- Professional startup banner with version info
- Centralized version management via `version.py`
- `pyproject.toml` for modern Python packaging

### Changed
- Converted all hardcoded XDG paths to use `utils.platform` helpers (`get_app_dir()`, `get_cache_dir()`) — fixes paths on macOS and Windows
- Replaced `subprocess.run()` in download function with `Status` progress animation
- Download format changed from DASH to progressive for faster single-stream downloads
- Updated README with CLI docs, badges, screenshots section, FAQ, roadmap

### Fixed
- Preloader stall detection removed — now waits full 90s for more data, giving mpv a larger buffer
- `play_video()` now correctly waits for the cached file before passing to mpv
- Shemaroo channel URL typo fixed (space in handle)

### Infrastructure
- GitHub issue templates (bug report, feature request)
- Pull request template
- `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`
- `LICENSE` (MIT)
- `.gitignore` improvements

## Beta 1.37.0

### Added
- Preloader system for caching partial video data while streaming
- `Status` class with animated spinners and progress bars
- Platform-aware path resolution (`utils/platform.py`)

### Changed
- fzf UI theme improvements
- Faster search results with caching

## Beta 1.0.0

### Added
- Initial release
- YouTube search and playback
- Anime search from official channels
- Movie search from official channels
- fzf-powered terminal UI
- mpv integration with hardware acceleration
