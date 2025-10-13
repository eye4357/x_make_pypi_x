# Changelog — Control Room Production Log

All notable changes to x_make_pypi_x are documented here. We hew to [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and Semantic Versioning so every PyPI drop has a clean trail.

## [0.20.1] - 2025-10-13
### Changed
- Centralized PyPI availability polling in `publish_flow.wait_for_pypi_release` so the orchestrator simply delegates.
- Refreshed documentation to steer every publisher to the Road to 0.20.1 control-room ledger before shipping a build.

## [0.20.0-prep] - 2025-10-12
### Added
- Codified the README to explain how the publisher isolates builds, generates typing artifacts, and drives Twine uploads.
- Logged the changelog scaffold so every future release captures metadata, credentials, and packaging shifts.

### Changed
- None.

### Fixed
- None.
