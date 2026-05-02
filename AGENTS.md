# PROJECT KNOWLEDGE BASE

**Generated:** 2026-04-19
**Commit:** 1b7bd0b
**Branch:** main

## OVERVIEW
This project is a Home Assistant custom integration for `offdelay` logic. It provides sensors, binary sensors, and switches to improve the ease of installation for a new Home Assistant instance.

## STRUCTURE
```
./
├── custom_components/    # Main integration code
├── scripts/              # Development and debugging scripts
├── tests/                # Pytest tests
├── config/               # Blueprint configurations
└── pyproject.toml        # Project configuration
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| Main integration logic | `custom_components/offdelay/` | Contains the core Python code for the integration. |
| Blueprints | `custom_components/offdelay/blueprints/` | Contains the blueprints for automations and scripts. |
| Tests | `tests/` | Contains the pytest tests for the integration. |
| Development scripts | `scripts/` | Contains scripts for development and debugging. |
| Project configuration | `pyproject.toml` | Contains project metadata, dependencies, and tool configurations. |

## CONVENTIONS
- This project uses `ruff` for Python linting. The configuration is in `pyproject.toml`.
- `pytest` is used for testing. The configuration is in `pyproject.toml`.
- The project follows the standard structure for a Home Assistant custom component.

## ANTI-PATTERNS (THIS PROJECT)
- The codebase contains comments with "DO NOT" and "NEVER", for example in `custom_components/offdelay/config_flow.py`.

## COMMANDS
```bash
# Run tests
pytest

# Run tests with coverage
pytest --cov=custom_components

# Run coverage report
coverage report
```

## NOTES
- This integration relies on the `Meteorologisk institutt (Met.no)` integration for weather data.
- Two zones, `zone.home` and `zone.near_home`, must be created in Home Assistant.

## POST-CHANGE HOOKS
After every file modification, the following skills must be executed in order:
- `lint`
- `unittest`
