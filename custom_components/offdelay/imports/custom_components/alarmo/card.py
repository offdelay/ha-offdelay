"""WebSocket handler and registration for Alarmo card update events."""

from homeassistant.components.websocket_api import async_register_command, decorators
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
import voluptuous as vol


@decorators.websocket_command(
    {
        vol.Required("type"): "alarmo_updated",
    }
)
@decorators.async_response
async def handle_subscribe_updates(hass, connection, msg):
    """Handle subscribe updates."""

    @callback
    def handle_event(event: str, area_id: str, args: dict = None):
        """Forward events to websocket."""
        if args is None:
            args = {}
        data = dict(**args, **{"event": event, "area_id": area_id})
        connection.send_message(
            {"id": msg["id"], "type": "event", "event": {"data": data}}
        )

    connection.subscriptions[msg["id"]] = async_dispatcher_connect(
        hass, "alarmo_event", handle_event
    )
    connection.send_result(msg["id"])


async def async_register_card(hass):
    """Publish event to lovelace when alarm changes."""
    async_register_command(hass, handle_subscribe_updates)
