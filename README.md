# Offdelay for Home Assistant

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/custom-components/hacs)
[![GitHub Release](https://img.shields.io/github/v/release/offdelay/offdelay-integration)](https://github.com/offdelay/offdelay-integration/releases)
[![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/offdelay/offdelay-integration/lint.yml)](https://github.com/offdelay/offdelay-integration/actions)

This custom integration for Home Assistant provides tools to improve the ease of installation for a new Home Assistant instance with the offdelay logic. Instead of manually creating automations and helper sensors, this integration provides a more manageable way to create and update these Home Assistant tools.

## Prerequisites

Before installing, please ensure you have the following set up in your Home Assistant instance:

1.  **Meteorologisk institutt (Met.no) Integration**: This integration relies on a weather provider for forecast data. The [Met.no integration](https://www.home-assistant.io/integrations/met/) is the recommended provider. You will need a weather entity named `weather.forecast_home` or `weather.home`.
2.  **Zones**: You must create two [zones](https://www.home-assistant.io/integrations/zone/):
    *   `zone.home`: Your primary home location.
    *   `zone.near_home`: An area around your home to detect when you are close.

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

After installation, the integration can be configured through the Home Assistant UI.

[![Add Integration](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=offdelay)

1.  Navigate to **Settings** &rarr; **Devices & Services**.
2.  Click **+ Add Integration**.
3.  Search for "Offdelay" and select it.
4.  Follow the on-screen instructions to complete the setup.

## Entities Provided

This integration creates the following entities:

### Sensors

- **`sensor.home_status`**: Shows the current status of the home.
  - **State**: `Home`, `NearHome`, `Away`, or `Vacation`.
  - **Use**: Ideal for creating automations based on household presence.

- **`sensor.weather_max_temp_today`**: The forecasted maximum temperature for the current day.
  - **Unit**: `°C`

- **`sensor.weather_condition_rank_today`**: A numerical rank for today's forecasted weather.
  - **Details**: A higher number is better (e.g., sunny=4, rainy=1). This helps in creating automations based on "good" vs "bad" weather without dealing with multiple condition strings.

- **`sensor.weather_condition_rank_tomorrow`**: Same as above, but for tomorrow's forecast.

- **`sensor.weather_condition_today`**: The friendly name of the forecasted weather condition for today.
  - **Example States**: `sunny`, `cloudy`, `rainy`.

- **`sensor.weather_condition_tomorrow`**: The friendly name of the forecasted weather condition for tomorrow.

### Binary Sensors

- **`binary_sensor.is_home`**: A simple sensor indicating if anyone is home.
  - **State**: `on` when anyone is in the `home` zone, `off` otherwise.

### Switch

- **`switch.home_vacation`**: An input switch to manually control vacation mode.
  - **Action**: Turning this switch `on` will force the `sensor.home_status` to `Vacation`.

## Blueprints

This integration comes with pre-made blueprints to help you get started with automations and scripts. Once the integration is installed, these blueprints will be available in your Home Assistant instance.

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
This project is licensed under the [Apache 2.0 License](LICENSE.md).
