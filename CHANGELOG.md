# Changelog

All notable changes to this fork of [soinkleined/sonos-analyzer](https://github.com/soinkleined/sonos-analyzer). The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/).

## [0.4.0-beta.1] - 2026-11-12

Pilot pre-release of the desktop app.

### Added

- Desktop app for Windows and macOS (Apple silicon and Intel), built by GitHub Actions and attached to each release. Opens the analyzer in the browser, with discovery working; unsigned for the pilot. The guide also shows how to run the identical app from inspectable source with Python. See [Desktop app for Windows and Mac](docs/desktop-app.md).
- `sonos-analyzer-app` / `python -m sonos_analyzer.app`: serves the UI on this computer, opens the browser, and stops on **Quit** or after 15 minutes with no page open.

### Changed

- Pre-release tags no longer update the `latest` Docker image.

## [0.3.0] - 2026-11-12

### Added

- Ready-built Docker image for Intel/AMD and ARM at `ghcr.io/grahamfairbank/sonos-analyzer`, built by GitHub Actions from each version tag.
- [Run on a laptop with Docker Desktop](docs/docker-desktop.md): a guide for Windows and Mac laptops, with an easy route (ready-built image, one command) and an inspect-the-code route (build from source).
- `docker-compose.desktop.yml`: bridge networking with the UI on `127.0.0.1:8400`, for Docker Desktop.
- README "Get started" table pointing laptop, server and Python users to the right instructions.
- This changelog.

### Changed

- Speaker discovery is sent on every network interface by default; `--interface` / `SONOS_ANALYZER_INTERFACE` limits it to one. Docker's own bridge interfaces are skipped.
- Unreachable speakers are ruled out together before fetching, so a failed scan takes seconds instead of about 8 seconds per speaker.
- Clearer messages when discovery finds nothing, or when the host has no address on the speakers' network.

### Fixed

- Replies from non-Sonos devices to the discovery search were treated as speakers.

## [0.2.0] - 2026-10-11

### Added

- Web UI (`sonos-analyzer-web`), Dockerfile and `docker-compose.yml` using host networking.
- Rooms: stereo pairs and home theater sets grouped with each speaker's role, and checked as a unit.
- Wi-Fi PHY error rate measured over a sample window, with household outliers flagged; noise floor per speaker.
- Radio channel map, speaker-to-speaker signal matrix and diagram, wired-link checks, and per-model firmware comparison.
- Findings grouped per issue, listing every affected speaker; an `info` severity.

### Changed

- The household review is fetched once instead of once per speaker, making scans about five times faster on large systems.

### Fixed

- Model name and version were never read from the device description.
- The Trueplay calibration state was interpreted the wrong way round.
- Home theater satellites were flagged for bridge packet drops they make by design.

## [0.1.0] - 2026-08-22

Original command-line analyzer by David Klein ([soinkleined/sonos-analyzer](https://github.com/soinkleined/sonos-analyzer)).

[0.4.0-beta.1]: https://github.com/grahamfairbank/sonos-analyzer/compare/v0.3.0...v0.4.0-beta.1
[0.3.0]: https://github.com/grahamfairbank/sonos-analyzer/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/grahamfairbank/sonos-analyzer/compare/56892df...4530d00
[0.1.0]: https://github.com/soinkleined/sonos-analyzer/commit/56892df
