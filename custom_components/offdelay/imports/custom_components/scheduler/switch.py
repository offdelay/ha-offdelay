"""Initialization of Scheduler switch platform."""

import copy
import datetime
import logging

from homeassistant.components.alarm_control_panel import AlarmControlPanelState
from homeassistant.components.switch import DOMAIN as PLATFORM
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_NAME,
    ATTR_SERVICE_DATA,
    ATTR_TIME,
    CONF_CONDITIONS,
    CONF_SERVICE,
    CONF_SERVICE_DATA,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import EntityCategory, ToggleEntity
from homeassistant.helpers.event import async_call_later
from homeassistant.util import slugify
import homeassistant.util.dt as dt_util
import voluptuous as vol

from . import const
from .actions import ActionHandler
from .store import ScheduleEntry, async_get_registry
from .timer import TimerHandler

_LOGGER = logging.getLogger(__name__)


SERVICE_RUN_ACTION = "run_action"
RUN_ACTION_SCHEMA = cv.make_entity_service_schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
        vol.Optional(ATTR_TIME): cv.time,
        vol.Optional(const.ATTR_SKIP_CONDITIONS): cv.boolean,
    }
)


def entity_exists_in_hass(hass, entity_id):
    """Check that an entity exists."""
    return hass.states.get(entity_id) is not None


def date_in_future(date_string: str):
    now = dt_util.as_local(dt_util.utcnow())
    date = dt_util.parse_date(date_string)
    diff = date - now.date()
    return diff.days > 0


async def async_setup(hass, config):
    """Track states and offer events for binary sensors."""
    return True


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the platform from config."""
    return True


async def async_setup_entry(hass, _config_entry, async_add_entities):
    """Set up the Scheduler switch devices."""
    coordinator = hass.data[const.DOMAIN]["coordinator"]

    @callback
    def async_add_entity(schedule: ScheduleEntry):
        """Add switch for Scheduler."""
        schedule_id = schedule.schedule_id
        name = schedule.name

        if name and len(slugify(name)):
            entity_id = f"{PLATFORM}.schedule_{slugify(name)}"
        else:
            entity_id = f"{PLATFORM}.schedule_{schedule_id}"

        entity = ScheduleEntity(coordinator, hass, schedule_id, entity_id)
        hass.data[const.DOMAIN]["schedules"][schedule_id] = entity
        async_add_entities([entity])

    for entry in coordinator.store.schedules.values():
        async_add_entity(entry)

    async_dispatcher_connect(hass, const.EVENT_ITEM_CREATED, async_add_entity)

    platform = entity_platform.current_platform.get()

    platform.async_register_entity_service(
        SERVICE_RUN_ACTION, RUN_ACTION_SCHEMA, "async_service_run_action"
    )


class ScheduleEntity(ToggleEntity):
    """Defines a base schedule entity."""

    def __init__(self, coordinator, hass, schedule_id: str, entity_id: str) -> None:
        """Initialize the schedule entity."""
        self.coordinator = coordinator
        self.hass = hass
        self.schedule_id = schedule_id
        self.entity_id = entity_id
        self.schedule = None

        self._state = None
        self._timer = None
        self._timestamps = []
        self._next_entries = []
        self._current_slot = None
        self._init = True
        self._tags = []

        self._listeners = [
            async_dispatcher_connect(
                self.hass, const.EVENT_ITEM_UPDATED, self.async_item_updated
            ),
            async_dispatcher_connect(
                self.hass, const.EVENT_TIMER_UPDATED, self.async_timer_updated
            ),
            async_dispatcher_connect(
                self.hass, const.EVENT_TIMER_FINISHED, self.async_timer_finished
            ),
        ]

    @callback
    async def async_item_updated(self, id: str):
        """Update internal properties when schedule config was changed."""
        if id != self.schedule_id:
            return

        store = await async_get_registry(self.hass)
        self.schedule = store.async_get_schedule(self.schedule_id)
        self._tags = self.coordinator.async_get_tags_for_schedule(self.schedule_id)

        if self.schedule[const.ATTR_ENABLED] and self._state in [
            STATE_OFF,
            const.STATE_COMPLETED,
        ]:
            self._state = STATE_ON
        elif not self.schedule[const.ATTR_ENABLED] and self._state not in [
            STATE_OFF,
            const.STATE_COMPLETED,
        ]:
            self._state = STATE_OFF

        self._init = True  # trigger actions of starting timeslot

        if self.hass is None:
            return

        self.async_write_ha_state()
        self.hass.bus.async_fire(const.EVENT)

    @callback
    async def async_timer_updated(self, id: str):
        """Update internal properties when schedule timer was changed."""
        if id != self.schedule_id:
            return

        self._next_entries = self._timer_handler.slot_queue
        self._timestamps = list(
            map(
                datetime.datetime.isoformat, self._timer_handler.timestamps
            )
        )
        if self._current_slot is not None and self._timer_handler.current_slot is None:
            # we are leaving a timeslot, stop execution of actions
            if (
                len(self.schedule[const.ATTR_TIMESLOTS]) == 1
                and self.schedule[const.ATTR_REPEAT_TYPE] == const.REPEAT_TYPE_REPEAT
            ):
                # allow unavailable entities to restore within 9 mins (+1 minute of triggered duration)
                await self._action_handler.async_empty_queue(restore_time=9)
            else:
                await self._action_handler.async_empty_queue()

            if self._current_slot == (
                len(self.schedule[const.ATTR_TIMESLOTS]) - 1
            ) and (
                not self.schedule[const.ATTR_END_DATE]
                or not date_in_future(self.schedule[const.ATTR_END_DATE])
            ):
                # last timeslot has ended
                # in case period is assigned, the end date must have been reached as well

                if self.schedule[const.ATTR_REPEAT_TYPE] == const.REPEAT_TYPE_PAUSE:
                    _LOGGER.debug(
                        f"Scheduler {self.schedule_id} has finished the last timeslot, turning off"
                    )
                    await self.async_turn_off()
                    self._state = const.STATE_COMPLETED

                elif self.schedule[const.ATTR_REPEAT_TYPE] == const.REPEAT_TYPE_SINGLE:
                    _LOGGER.debug(
                        f"Scheduler {self.schedule_id} has finished the last timeslot, removing"
                    )
                    self.coordinator.async_delete_schedule(self.schedule_id)

        self._current_slot = self._timer_handler.current_slot

        if self._state not in [STATE_OFF, AlarmControlPanelState.TRIGGERED]:
            if len(self._next_entries) < 1:
                self._state = STATE_UNAVAILABLE
            else:
                now = dt_util.as_local(dt_util.utcnow())
                if (self._timer_handler._next_trigger - now).total_seconds() < 0:
                    self._state = const.STATE_COMPLETED
                else:
                    self._state = (
                        STATE_ON if self.schedule[const.ATTR_ENABLED] else STATE_OFF
                    )

        if self._init:
            # initial startpoint for timer calculated, fire actions if currently overlapping with timeslot
            if self._current_slot is not None and self._state != STATE_OFF:
                skip_initial_execution = False
                if (
                    self.coordinator.state == const.STATE_INIT
                    and self.coordinator.time_shutdown
                ):
                    # if the date+time of prior shutdown is known, determine which timeslots are already triggered before
                    # calculate the next start of timeslot since the time of shutdown, execute only if this is in the past
                    ts_shutdown = self.coordinator.time_shutdown
                    now = dt_util.as_local(dt_util.utcnow())
                    start_time = self.schedule[const.ATTR_TIMESLOTS][
                        self._current_slot
                    ][const.ATTR_START]
                    start_of_timeslot = self._timer_handler.calculate_timestamp(
                        start_time, ts_shutdown
                    )
                    if start_of_timeslot > now:
                        skip_initial_execution = True

                if skip_initial_execution:
                    _LOGGER.debug(
                        f"Schedule {self.schedule_id} was already executed before shutdown, initial timeslot is skipped."
                    )
                else:
                    _LOGGER.debug(
                        f"Schedule {self.schedule_id} is starting in a timeslot, proceed with actions"
                    )
                await self._action_handler.async_queue_actions(
                    self.schedule[const.ATTR_TIMESLOTS][self._current_slot],
                    skip_initial_execution,
                )
            self._init = False

        if self.hass is None:
            return

        self.async_write_ha_state()
        self.hass.bus.async_fire(const.EVENT)

    @callback
    async def async_timer_finished(self, id: str):
        """Fire actions when timer is finished."""
        if id != self.schedule_id:
            return

        if self._state not in [STATE_OFF, const.STATE_COMPLETED]:
            self._current_slot = self._timer_handler.current_slot
            if self._current_slot is not None:
                _LOGGER.debug(
                    f"Schedule {self.schedule_id} is triggered, proceed with actions"
                )
                await self._action_handler.async_queue_actions(
                    self.schedule[const.ATTR_TIMESLOTS][self._current_slot]
                )

        @callback
        async def async_trigger_finished(_now):
            """Internal timer is finished, reset the schedule."""
            if self._state == AlarmControlPanelState.TRIGGERED:
                self._state = STATE_ON
            await self._timer_handler.async_start_timer()

        # keep the entity in triggered state for 1 minute, then restart the timer
        self._timer = async_call_later(self.hass, 60, async_trigger_finished)
        if self._state == STATE_ON:
            self._state = AlarmControlPanelState.TRIGGERED

        self.async_write_ha_state()
        self.hass.bus.async_fire(const.EVENT)

    async def async_cancel_timer(self):
        """Cancel timer."""
        if self._timer:
            self._timer()
            self._timer = None

    @property
    def device_info(self) -> dict:
        """Return info for device registry."""
        device = self.coordinator.id
        return {
            "identifiers": {(const.DOMAIN, device)},
            "name": "Scheduler",
            "model": "Scheduler",
            "sw_version": const.VERSION,
            "manufacturer": "@nielsfaber",
        }

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        if self.schedule and self.schedule[ATTR_NAME]:
            return self.schedule[ATTR_NAME]
        return f"Schedule #{self.schedule_id}"

    @property
    def should_poll(self) -> bool:
        """Return the polling requirement of the entity."""
        return False

    @property
    def state(self):
        """Return the state of the entity."""
        return self._state

    @property
    def icon(self):
        """Return icon."""
        return "mdi:calendar-clock"

    @property
    def entity_category(self):
        """Return EntityCategory."""
        return EntityCategory.CONFIG

    @property
    def weekdays(self):
        return self.schedule[const.ATTR_WEEKDAYS] if self.schedule else None

    @property
    def entities(self):
        entities = []
        if not self.schedule:
            return None
        for timeslot in self.schedule[const.ATTR_TIMESLOTS]:
            for action in timeslot[const.ATTR_ACTIONS]:
                if action[ATTR_ENTITY_ID] and action[ATTR_ENTITY_ID] not in entities:
                    entities.append(action[ATTR_ENTITY_ID])

        return entities

    @property
    def actions(self):
        if not self.schedule:
            return None
        return [
            {
                CONF_SERVICE: timeslot["actions"][0][CONF_SERVICE],
            }
            if not timeslot["actions"][0][ATTR_SERVICE_DATA]
            else {
                CONF_SERVICE: timeslot["actions"][0][CONF_SERVICE],
                CONF_SERVICE_DATA: timeslot["actions"][0][ATTR_SERVICE_DATA],
            }
            for timeslot in self.schedule[const.ATTR_TIMESLOTS]
        ]

    @property
    def timeslots(self):
        timeslots = []
        if not self.schedule:
            return None
        for timeslot in self.schedule[const.ATTR_TIMESLOTS]:
            if timeslot[const.ATTR_STOP]:
                timeslots.append(
                    f"{timeslot[const.ATTR_START]} - {timeslot[const.ATTR_STOP]}"
                )
            else:
                timeslots.append(timeslot[const.ATTR_START])
        return timeslots

    @property
    def tags(self):
        return self._tags

    @property
    def state_attributes(self):
        """Return the data of the entity."""
        return {
            "weekdays": self.weekdays,
            "timeslots": self.timeslots,
            "entities": self.entities,
            "actions": self.actions,
            "current_slot": self._current_slot,
            "next_slot": self._next_entries[0] if len(self._next_entries) else None,
            "next_trigger": self._timestamps[self._next_entries[0]]
            if len(self._next_entries)
            else None,
            "tags": self.tags,
        }


    @property
    def available(self):
        """Return True if entity is available."""
        return True

    @property
    def unique_id(self):
        """Return a unique ID to use for this entity."""
        return f"{self.schedule_id}"

    @property
    def is_on(self):
        """Return true if entity is on."""
        return self._state not in [STATE_OFF, const.STATE_COMPLETED]

    @callback
    def async_get_entity_state(self):
        """Fetch schedule data for websocket API."""
        data = copy.copy(self.schedule)
        if not data:
            data = {}
        data.update(
            {
                "next_entries": self._next_entries,
                "timestamps": self._timestamps,
                "name": self.schedule[ATTR_NAME] if self.schedule else "",
                "entity_id": self.entity_id,
                "tags": self.tags,
            }
        )
        return data

    async def async_added_to_hass(self):
        """Connect to dispatcher listening for entity data notifications."""
        store = await async_get_registry(self.hass)
        self.schedule = store.async_get_schedule(self.schedule_id)
        self._tags = self.coordinator.async_get_tags_for_schedule(self.schedule_id)

        self._timer_handler = TimerHandler(self.hass, self.schedule_id)
        self._action_handler = ActionHandler(self.hass, self.schedule_id)

    async def async_turn_off(self):
        """Turn off a schedule."""
        if self.schedule[const.ATTR_ENABLED]:
            await self._action_handler.async_empty_queue()
            self.coordinator.async_edit_schedule(
                self.schedule_id, {const.ATTR_ENABLED: False}
            )

    async def async_turn_on(self):
        """Turn on a schedule."""
        if not self.schedule[const.ATTR_ENABLED]:
            self.coordinator.async_edit_schedule(
                self.schedule_id, {const.ATTR_ENABLED: True}
            )

    async def async_will_remove_from_hass(self):
        """Remove entity from hass."""
        _LOGGER.debug(f"Schedule {self.schedule_id} is removed from hass")

        await self.async_cancel_timer()
        await self._action_handler.async_empty_queue()
        await self._timer_handler.async_unload()

        while len(self._listeners):
            self._listeners.pop()()

        await super().async_will_remove_from_hass()

    async def async_service_remove(self):
        """Remove a schedule."""
        self._state = STATE_OFF

        await self.async_remove()

    async def async_service_edit(
        self, entries, actions, conditions=None, options=None, name=None
    ):
        """Edit a schedule."""
        if self._timer:
            old_state = self._state
            self._state = STATE_OFF
            self._timer()
            self._timer = None
            self._state = old_state

        await self.async_cancel_timer()
        await self._action_handler.async_empty_queue()
        await self._timer_handler.async_unload()

        self.async_write_ha_state()

    async def async_service_run_action(self, time=None, skip_conditions=False):
        """Manually trigger the execution of the actions of a timeslot."""
        now = dt_util.as_local(dt_util.utcnow())
        if time is not None:
            now = now.replace(hour=time.hour, minute=time.minute, second=time.second)

        (slot, ts) = self._timer_handler.current_timeslot(now)

        if (
            slot is None
            and time is None
            and len(self.schedule[const.ATTR_TIMESLOTS]) == 1
        ):
            slot = 0

        if slot is None:
            _LOGGER.info(
                "Schedule {} has no active timeslot at {}".format(
                    self.entity_id, now.strftime("%H:%M:%S")
                )
            )
            return

        schedule = dict(self.schedule[const.ATTR_TIMESLOTS][slot])
        if skip_conditions:
            schedule[CONF_CONDITIONS] = []

        _LOGGER.debug(
            f"Executing actions for {self.entity_id}, timeslot {slot}, skip_conditions {skip_conditions}"
        )

        await self._action_handler.async_queue_actions(schedule)
