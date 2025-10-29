# Azoula Smart Integration for Home Assistant

[![GitHub Release](https://img.shields.io/github/release/maginawin/ha-azoula-smart.svg?style=flat-square)](https://github.com/maginawin/ha-azoula-smart/releases)
[![hacs](https://img.shields.io/badge/HACS-Custom-orange.svg?style=flat-square)](https://github.com/hacs/integration)

Home Assistant custom integration for Azoula Smart Hub devices via local MQTT.

## Requirements

- Home Assistant 2024.1.0+
- Azoula Smart Hub/Gateway
- MQTT integration enabled in Home Assistant

⚠️ **Note**: This integration is in early development. MQTT communication layer is complete, device platforms are work in progress.

## Installation

### HACS (Recommended)

1. Open HACS → Integrations
2. Three dots menu → Custom repositories
3. Add: `https://github.com/maginawin/ha-azoula-smart`
4. Category: Integration
5. Download and restart Home Assistant

### Manual

1. Download [latest release](https://github.com/maginawin/ha-azoula-smart/releases)
2. Copy `custom_components/azoula_smart` to your `custom_components` directory
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
    custom_components.azoula_smart: debug
```

## Support

- [Report Issues](https://github.com/maginawin/ha-azoula-smart/issues)
- [Development Guide](CLAUDE.md)
