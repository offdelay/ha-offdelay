"""Constants for offdelay."""

from logging import Logger, getLogger

from homeassistant.const import Platform

LOGGER: Logger = getLogger(__package__)

DOMAIN = "offdelay"
# Attribution text shown in Home Assistant UI for this integration
ATTRIBUTION = "Data provided by http://offdelay.be/"

# Proximity configuration
CONF_PERSONS = "persons"
HOME_NAME = "home"
HOME_ZONE = "zone.home"
PROXIMITY_TOLERANCE = 20

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
]

# New configuration keys for presence switches
CONF_OCCUPANCY_SENSORS = "occupancy_sensors"
CONF_GUEST_TURN_ON_DELAY = "guest_turn_on_delay"
CONF_GUEST_TURN_OFF_DELAY = "guest_turn_off_delay"

# Day mode configuration
CONF_WINTER_DAY_MAX_TEMP = "winter_day_max_temp"
CONF_SUMMER_DAY_MIN_TEMP = "summer_day_min_temp"
CONF_CLIMATE_DAY_START_HOUR = "climate_day_start_hour"
CONF_CLIMATE_NIGHT_START_HOUR = "climate_night_start_hour"
CONF_CLIMATES_BOOST = "climates_boost"  # Climates boost (list of climate entity ids)
CONF_BOOST_SUMMER_TEMP = "boost_summer_temp"
CONF_BOOST_WINTER_TEMP = "boost_winter_temp"

# Night mode temperature sensor configuration
CONF_SUMMER_NIGHT_TEMP_SENSOR = "summer_night_temp_sensor"
CONF_SUMMER_NIGHT_MAX_TEMP = "summer_night_max_temp"
CONF_SUMMER_NIGHT_MIN_TEMP = "summer_night_min_temp"
CONF_WINTER_NIGHT_TEMP_SENSOR = "winter_night_temp_sensor"
CONF_WINTER_NIGHT_MAX_TEMP = "winter_night_max_temp"
CONF_WINTER_NIGHT_MIN_TEMP = "winter_night_min_temp"

# Climate mode internal data keys
DATA_CLIMATE_MODE = "climate_mode"
CLIMATE_MODE_WINTER = "winter"
CLIMATE_MODE_SUMMER = "summer"
CLIMATE_MODE_OFF = "off"

# Energy source entity IDs (auto-detected, not configured)
EVCC_GRID_POWER_ENTITY = "sensor.evcc_grid_power"
EVCC_PV_POWER_ENTITY = "sensor.evcc_pv_power"
