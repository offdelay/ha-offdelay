# Offdelay for Home Assistant

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/custom-components/hacs)
[![GitHub Release](https://img.shields.io/github/v/release/offdelay/offdelay-integration)](https://github.com/offdelay/offdelay-integration/releases)
[![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/offdelay/offdelay-integration/lint.yml)](https://github.com/offdelay/offdelay-integration/actions)

This custom integration for Home Assistant provides tools to improve the ease of installation for a new Home Assistant instance with the offdelay logic. Instead of manually creating automations and helper sensors, this integration provides a more manageable way to create and update these Home Assistant tools.

## Prerequisites

This integration auto-configures the dependencies it needs on first setup. You don't need to provision them manually, but they are listed here for transparency:

1.  **Meteorologisk institutt (Met.no) Integration**: Used as the weather provider for forecast data. If a [Met.no integration](https://www.home-assistant.io/integrations/met/) entry isn't already configured, this integration will automatically create one on first setup, using your Home Assistant home location and `track_home=true`. You will still need a weather entity named `weather.forecast_home` or `weather.home` (Met.no creates this automatically).
2.  **`zone.home`**: Your primary home [zone](https://www.home-assistant.io/integrations/zone/). If `zone.home` does not yet exist, this integration will automatically create it on first setup using your Home Assistant home coordinates (with `51.057122734917584, 3.720729617352293` as fallback when Home Assistant's home location is unset). The auto-created zone uses a 50&nbsp;m radius and the `mdi:home` icon — you can edit it later from **Settings &rarr; Areas &amp; Zones**.

## Installation

Because this is not part of the default HACS repository, you must add it as a custom repository.

[![Open your Home Assistant instance and open a repository with the HACS logo.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=offdelay&repository=offdelay-integration&category=integration)

1.  Go to HACS &rarr; Integrations &rarr; Click the three dots in the top right.
2.  Select "Custom repositories".
3.  Add the URL to this repository (`https://github.com/offdelay/offdelay-integration`) in the "Repository" field.
4.  Select "Integration" as the category.
5.  Click "ADD".
6.  The "Offdelay" will now show up. Click "INSTALL".
7.  Restart Home Assistant.

## Configuration

After installation, the integration can be configured through the Home Assistant UI. The setup wizard guides you through climate thresholds, presence settings, and energy configuration. You can reconfigure these groups at any time through the integration's options.

[![Add Integration](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=offdelay)

1.  Navigate to **Settings** &rarr; **Devices & Services**.
2.  Click **+ Add Integration**.
3.  Search for "Offdelay" and select it.
4.  Follow the on-screen instructions to complete the setup.

## Entities Provided

This integration creates the following entities:

### Sensors

- **Max Temp Today** (`sensor.weather_max_temp_today`): The forecasted maximum temperature for the current day.
  - **Unit**: `°C`

- **Min Temp Today** (`sensor.weather_min_temp_today`): The forecasted minimum temperature for the current day.
  - **Unit**: `°C`

- **Summer Night Temp Reading** (`sensor.summer_night_temp_reading`): Mirrors the configured summer night temperature sensor.
  - **Unit**: `°C`
  - **Category**: Diagnostic

- **Winter Night Temp Reading** (`sensor.winter_night_temp_reading`): Mirrors the configured winter night temperature sensor.
  - **Unit**: `°C`
  - **Category**: Diagnostic

### Binary Sensors

- **Is Home** (`binary_sensor.is_home`): Indicates if anyone is home.
  - **State**: `on` when at least one person is in the `home` zone, `off` otherwise.

- **Guest Mode** (`binary_sensor.guest_mode`): Mirrors the Guest Mode switch as a binary sensor for use in templates, blueprints, and automations that prefer binary sensors.
  - **State**: matches `switch.guest_mode` exactly (no extra logic, no delay).

- **Climate Mode Winter** (`binary_sensor.climate_mode_winter`): Indicates if the current climate mode is winter.

- **Climate Mode Summer** (`binary_sensor.climate_mode_summer`): Indicates if the current climate mode is summer.

- **Climate Mode Winter/Summer** (`binary_sensor.climate_mode_winter_summer`): Indicates if the current climate mode is either winter or summer (i.e., not in transition).

- **Boost Binary Sensors** (per configured climate): For each climate entity configured for boost, a summer and winter boost binary sensor is created (e.g., `binary_sensor.living_room_boost_summer`).

### Switches

- **Vacation Mode** (`switch.vacation_mode`): Manually control vacation mode. Auto-turns off after arriving home (minimum 4 hours).

- **Guest Mode** (`switch.guest_mode`): Auto-activates when nobody is home but occupancy is detected. Configurable turn-on and turn-off delays. When 2 or more occupancy sensors are ON at the same time, guest mode activates immediately and bypasses the turn-on delay. Auto-logic is only active when at least one occupancy sensor is configured; otherwise the switch behaves as a manual toggle. State is restored across Home Assistant restarts.

- **Boost Switches** (per configured climate): For each climate entity configured for boost, a switch is created to toggle boost mode (e.g., `switch.living_room_boost`).

## Blueprints

This integration comes with pre-made blueprints to help you get started with automations and scripts. Once the integration is installed, these blueprints will be available in your Home Assistant instance.

### Automations

- **Advanced Heating Control** (`climate_heatpump_V1`): Room-based heating and cooling control based on people presence, climate mode, and temperature thresholds.
- **Sensor Light** (`light_sensor_V1`): Customizable lighting control triggered by motion or other sensors.
- **EnOcean PTM215Z Switch** (`light_enocean_switch_V2`): Zigbee2MQTT EnOcean Friends of Hue switch support with dimming.

### Scripts

- **Entity Auto Turn Off** (`entity_auto_turn_off_v1`): Turns a switch on, waits a configured duration, then turns it off.
- **Notifications** (`notification_v1`): Configurable notification delivery.

### How to Find the Blueprints

1.  Navigate to **Settings** &rarr; **Automations & Scenes**.
2.  Select the **Blueprints** tab.
3.  You will find the blueprints provided by this integration listed here.

You can then use these blueprints to create new automations or scripts without needing to write any YAML code.

## Testing

This project uses `pytest` for testing. You can run the tests with the following command:

```bash
pytest
```

## Troubleshooting

If you encounter any issues with this integration, here are a few common troubleshooting steps:

1.  **Check the Logs**: Go to **Settings** &rarr; **System** &rarr; **Logs** to see if there are any error messages related to the "Offdelay" integration.
2.  **Restart Home Assistant**: Sometimes, a simple restart can resolve issues.
3.  **Re-add the Integration**: If the problems persist, you can try removing the integration and adding it again.
4.  **Create an Issue**: If you're still having trouble, please [create an issue](https://github.com/offdelay/offdelay-integration/issues) on our GitHub repository. Be sure to include any relevant logs and a detailed description of the problem.

## Contributing

Contributions are welcome! If you'd like to contribute to this project, please see our [contributing guidelines](CONTRIBUTING.md).

## License
This project is licensed under the [Apache 2.0 License](LICENSE).
