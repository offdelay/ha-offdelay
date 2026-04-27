"""Constants for offdelay."""

from logging import Logger, getLogger

from homeassistant.const import Platform

LOGGER: Logger = getLogger(__package__)

DOMAIN = "offdelay"  # TEST COMMENT: Agent workflow test - please run tests and review
# Attribution text shown in Home Assistant UI for this integration
ATTRIBUTION = "Data provided by http://offdelay.be/"

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
]

# New configuration keys for presence switches
CONF_OCCUPANCY_SENSORS = "occupancy_sensors"
CONF_GUEST_TURN_ON_DELAY = "guest_turn_on_delay"
CONF_GUEST_TURN_OFF_DELAY = "guest_turn_off_delay"

# Climate mode configuration
CONF_WINTER_MAX_TEMP = "winter_max_temp"
CONF_SUMMER_MIN_TEMP = "summer_min_temp"
CONF_CLIMATES = "climates"
CONF_CLIMATE_DELTA_TOLERANCE = "climate_delta_tolerance"
CONF_CLIMATE_DAY_START_HOUR = "climate_day_start_hour"
CONF_CLIMATE_NIGHT_START_HOUR = "climate_night_start_hour"
CONF_CLIMATES_BOOST = "climates_boost"  # Climates boost (list of climate entity ids)

# Climate mode internal data keys
DATA_CLIMATE_MODE = "climate_mode"
DATA_CLIMATE_DELTA_TO_TARGET = "climate_delta_to_target"
CLIMATE_MODE_WINTER = "winter"
CLIMATE_MODE_SUMMER = "summer"
CLIMATE_MODE_OFF = "off"
