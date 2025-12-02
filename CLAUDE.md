# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Home Assistant custom integration for Azoula Smart Hub devices. It provides MQTT-based communication to control smart home devices through the Azoula/Meribee ecosystem. The integration is designed for Azoula Smart gateways.

**Key Architecture Points:**

- **Domain**: `sunricher_azoula`
- **Communication**: Local MQTT broker on Azoula gateway (default port 1883)
- **IoT Class**: `local_push` (local network communication)
- **Current Status**: Bronze quality scale - foundational MQTT layer complete, device platforms not yet implemented

## Architecture Overview

### MQTT Communication Layer (`custom_components/sunricher_azoula/sdk/`)

The integration communicates with Azoula gateways via MQTT using a specific protocol:

**Topic Structure:**

- Subscribe: `meribee/platform-app/{gateway_id}`
- Publish: `meribee/gateway/{gateway_id}`
- Additional: `meribee/platform`, `meribee/weather/notify/{gateway_id}`

**Message Format:**

- JSON-based with `cmd` field for command identification
- Key methods: `thing.device.online/offline`, `thing.device.propPost/propSet`, `thing.device.serviceCall`, `thing.subdev.getall`

**SDK Components:**

- `hub.py` - Main `AzoulaGateway` class with async MQTT handling
- `const.py` - Protocol constants, MQTT topics, device type mappings
- `exceptions.py` - Custom exception classes

### paho-mqtt Compatibility Handling

The codebase handles both paho-mqtt < 2.0.0 and >= 2.0.0 API differences with dynamic callback detection in `hub.py`. This is critical when working with MQTT functionality.

### Home Assistant Integration Structure

- `config_flow.py` - User configuration flow for gateway setup
- `__init__.py` - Integration initialization and hub management
- `strings.json` - Configuration UI localization
- `manifest.json` - Integration metadata and HA version requirements

**Device Platform Support:**
Currently defined constants for 5 device types (switch, light, sensor, cover, climate) but no platform implementations exist yet. This is the main area for future development.

## Development Setup

### Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
pip install -e ".[dev]"
```

All development commands must run within activated virtual environment.

### Development Commands

```bash
# Format and lint
ruff format
ruff check --fix

# Type check
mypy --show-error-codes --pretty {project_path}
```

## Code Quality Guidelines

Follow Home Assistant's [Style Guidelines](https://developers.home-assistant.io/docs/development_guidelines/). Use Context7 MCP to query detailed documentation when needed.

### Key Rules

- **Logging**: Use percentage formatting, not f-strings (`"Gateway %s connected"` not `f"Gateway {gw} connected"`)
- **Comments**: Full sentences with periods. Comment non-obvious decisions, not obvious code
- **Entity Attributes**: Use `_attr_*` pattern in `__init__`, avoid `@property` decorators
- **Type Hints**: Required for all new code
- **Error Handling**: Proper exception handling with appropriate logging

### Resources

- [Home Assistant Development Guidelines](https://developers.home-assistant.io/docs/development_guidelines/)
- [Home Assistant Entity Architecture](https://developers.home-assistant.io/docs/core/entity/)
- Use Context7 to query Home Assistant documentation for specific patterns

## Development Principles

- **Code Language**: Use English in code, comments, and documentation files
- **Communication Language**: When communicating with the user/developer, use **Chinese (中文)** as the primary language
- **Incremental Development**: Propose each code change and get user approval before implementing. Present plan first, then modify one section at a time.
- Code readability first: prefer self-documenting code over comments
- Document design decisions and rationale for significant changes
