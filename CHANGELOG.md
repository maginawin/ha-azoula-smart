# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.1] - 2025-11-17

### Fixed

- Add missing `zip_release: true` in hacs.json for HACS compatibility

## [0.1.0] - 2025-01-13

### Added

- Button platform with device identify functionality (#8)
- Device identify button for locating physical devices
- Sensor platform with TSL-based capability detection (#7)
- Gateway device registration in Home Assistant device registry (#6)
- Light platform with full MQTT callback support (#6)
- Device service calls for device control (#4)
- Dynamic device discovery from gateway (#2)
- Configuration flow for gateway setup

### Technical

- CI/CD workflows for release, CodeQL, and validation (#3)
- Refactor domain from `sunricher_azoula_smart` to `sunricher_azoula` (6fd13c1)
- Complete project restructure with improved architecture (#5)
- TSL (Thing Specification Language) support for device capabilities
- Multi-listener callback system for MQTT events
- Comprehensive type hints and documentation

[0.1.1]: https://github.com/maginawin/ha-azoula-smart/releases/tag/v0.1.1
[0.1.0]: https://github.com/maginawin/ha-azoula-smart/releases/tag/v0.1.0
