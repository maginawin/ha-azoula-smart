# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Home Assistant custom integration for Azoula Smart Hub devices. It provides MQTT-based communication to control smart home devices through the Azoula/Meribee ecosystem. The integration is designed for Azoula Smart gateways.

**Key Architecture Points:**

- **Domain**: `azoula_smart`
- **Communication**: Local MQTT broker on Azoula gateway (default port 1883)
- **IoT Class**: `local_push` (local network communication)
- **Current Status**: Bronze quality scale - foundational MQTT layer complete, device platforms not yet implemented

## Development Commands

```bash
# Install development dependencies
pip install -e .[dev]

# Linting and formatting
ruff check .
ruff format .

# Type checking
mypy .

# SDK connection testing
python script/test_all.py

# With environment variables (preferred)
cp .env.example .env  # Edit with your gateway details
python script/test_all.py

# With command line arguments
python script/test_all.py --host 192.168.1.100 --username admin --password secret --gateway-id HUB001
```

## Architecture Overview

### MQTT Communication Layer (`custom_components/azoula_smart/sdk/`)

The integration communicates with Azoula gateways via MQTT using a specific protocol:

**Topic Structure:**

- Subscribe: `meribee/platform-app/{gateway_id}`
- Publish: `meribee/gateway/{gateway_id}`
- Additional: `meribee/platform`, `meribee/weather/notify/{gateway_id}`

**Message Format:**

- JSON-based with `cmd` field for command identification
- Key methods: `thing.device.online/offline`, `thing.device.propPost/propSet`, `thing.device.serviceCall`, `thing.subdev.getall`

**SDK Components:**

- `hub.py` - Main `AzoulaSmartHub` class with async MQTT handling
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

## Development Environment Setup

1. Configure environment variables in `.env`:

   ```
   AZOULA_HOST=192.168.1.100
   AZOULA_USERNAME=admin
   AZOULA_PASSWORD=your_password
   AZOULA_GATEWAY_ID=your_gateway_id
   ```

2. The test script (`script/test_all.py`) validates SDK connection/disconnection functionality and is essential for testing MQTT communication without full HA setup.

## Code Quality Configuration

- **Ruff**: Comprehensive linting with Google docstring convention, special handling for constants files
- **MyPy**: Strict type checking targeting Python 3.13, special overrides for legacy components
- **Pre-commit**: Configured for automated code quality checks

## Current Development Status

**Implemented:** MQTT communication layer, config flow, connection management, development tooling

**Missing:** Device platform implementations, device discovery, entity creation, comprehensive testing

When adding new device platforms, follow the established pattern in `const.py` for device type mappings and ensure proper async/await patterns consistent with the hub implementation.

### Branch Naming Convention

- **Features**: `feature/description-of-feature`
- **Bug Fixes**: `fix/description-of-fix`
- **Documentation**: `docs/description-of-docs`
- **Refactoring**: `refactor/description-of-refactor`
- **Testing**: `test/description-of-test`

### Commit Message Format

Follow conventional commits format:

```text
type(scope): brief description

Detailed explanation of changes (if necessary)

- Bullet points for multiple changes
- Reference issue numbers (#123)
- Breaking changes noted with BREAKING CHANGE:
```

**Examples:**

- `feat(gateway): add support for Azoula device groups`
- `fix(sensor): correct energy sensor precision`
- `docs(readme): update installation instructions`
- `chore(release): bump version to 0.2.0`

**IMPORTANT**: Do not include Claude Code signatures, co-author attributions, or AI-generated markers in commit messages. Keep commits clean and focused on the technical changes.

### Pull Request Process

1. **Create feature branch** from main branch
2. **Create PR** with clear description and test plan
3. **Update documentation** (README.md) if needed
4. **Merge using squash and merge** strategy

### Release Process

1. **Update version** in `manifest.json`
2. **Update CHANGELOG.md** with release notes:
   - Use simplified structure: Added, Fixed, Technical
   - Include issue references (#123) for user-facing changes
   - Include commit hashes (abc1234) for technical changes without issues
   - Follow [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) format
   - Update version links at bottom of changelog
3. **Commit changes** to main branch using format: `chore(release): bump version to x.y.z`
4. **Create and push tag** to upstream: `git tag v{version} && git push upstream v{version}`
5. **Create GitHub release** using `gh release create v{version} --title "v{version}" --notes "..."`
   - Copy release notes from CHANGELOG.md with same structure (Added, Fixed, Technical sections)
6. **Follow semantic versioning**: MAJOR.MINOR.PATCH

#### Changelog Structure Template

```markdown
## [x.y.z] - YYYY-MM-DD

### Added
- New user-facing features

### Fixed  
- Important bug fixes (#issue)

### Technical
- Dependency updates, CI/CD improvements, code refactoring
```

### Code Quality Requirements

- **Type hints**: All new code must include proper type annotations
- **Error handling**: Use proper exception handling with logging
- **Documentation**: Add docstrings for all public methods and classes
- **Constants**: Define constants in separate constants file
- **Testing**: Write unit tests for all new functionality
- **Architecture Documentation**: Document significant design decisions and alternatives considered
