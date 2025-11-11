# Azoula Smart Integration for Home Assistant

[![GitHub Release](https://img.shields.io/github/release/maginawin/ha-azoula-smart.svg?style=flat-square)](https://github.com/maginawin/ha-azoula-smart/releases)
[![hacs](https://img.shields.io/badge/HACS-Custom-orange.svg?style=flat-square)](https://github.com/hacs/integration)

Home Assistant custom integration for Azoula Smart Hub devices via local MQTT.

## Requirements

- Home Assistant 2024.1.0+
- Azoula Smart Hub

## Supported Devices

This integration currently supports the following device types:

### Light

- On/Off control
- Brightness adjustment
- Color temperature (Kelvin)
- RGB/HS/XY color control

### Sensor

- Illuminance sensor

### Binary Sensor

- Occupancy detection
- Motion sensor

Device support is automatically detected based on TSL (Thing Specification Language) capabilities reported by your Azoula gateway.

## Installation

### HACS (Recommended)

1. Open HACS → Integrations
2. Three dots menu → Custom repositories
3. Add: `https://github.com/maginawin/ha-azoula-smart`
4. Category: Integration
5. Download and restart Home Assistant

### Manual

1. Download [latest release](https://github.com/maginawin/ha-azoula-smart/releases)
2. Copy `custom_components/sunricher_azoula` to your `custom_components` directory
3. Restart Home Assistant

## Configuration

1. Settings → Devices & Services → Add Integration
2. Search "Azoula Smart"
3. Enter gateway details:
   - Gateway ID
   - MQTT Broker Host (gateway IP)
   - MQTT Port (default: 1883)
   - Username/Password (if required)

## Debug Logging

```yaml
logger:
  logs:
    custom_components.sunricher_azoula: debug
```

## Support

- [Report Issues](https://github.com/maginawin/ha-azoula-smart/issues)
- [Development Guide](CLAUDE.md)
