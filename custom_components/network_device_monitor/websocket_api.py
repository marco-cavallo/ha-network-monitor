# Copyright 2026 Marco Cavallo
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""WebSocket commands backing the sidebar panel.

Network monitor - By Marco Cavallo.
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from .const import (
    AUTHOR,
    DOMAIN,
    INTEGRATION_NAME,
    VERSION,
    WS_DEVICES,
    WS_SCAN,
    WS_SCAN_PORTS,
    WS_SET_WATCH,
    WS_SET_WHITELIST,
    WS_UPDATE_DEVICE,
)


def _coordinators(hass: HomeAssistant) -> list[Any]:
    """Every loaded coordinator for this integration."""
    return [
        entry.runtime_data
        for entry in hass.config_entries.async_loaded_entries(DOMAIN)
        if getattr(entry, "runtime_data", None) is not None
    ]


def _first(hass: HomeAssistant) -> Any | None:
    """The single coordinator (the integration is single-instance)."""
    found = _coordinators(hass)
    return found[0] if found else None


@callback
def async_register(hass: HomeAssistant) -> None:
    """Register the panel's WebSocket commands once."""
    websocket_api.async_register_command(hass, ws_devices)
    websocket_api.async_register_command(hass, ws_update_device)
    websocket_api.async_register_command(hass, ws_set_whitelist)
    websocket_api.async_register_command(hass, ws_scan)
    websocket_api.async_register_command(hass, ws_scan_ports)
    websocket_api.async_register_command(hass, ws_set_watch)


@websocket_api.websocket_command({vol.Required("type"): WS_DEVICES})
@callback
def ws_devices(hass, connection, msg) -> None:
    """Return the full inventory plus scan metadata."""
    coordinator = _first(hass)
    if coordinator is None:
        connection.send_error(msg["id"], "not_loaded", "Integration not loaded")
        return
    payload = coordinator.panel_payload()
    payload["integration"] = {
        "name": INTEGRATION_NAME,
        "version": VERSION,
        "author": AUTHOR,
    }
    connection.send_result(msg["id"], payload)


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_UPDATE_DEVICE,
        vol.Required("key"): str,
        vol.Optional("name"): vol.Any(str, None),
        vol.Optional("note"): vol.Any(str, None),
    }
)
@websocket_api.async_response
async def ws_update_device(hass, connection, msg) -> None:
    """Set a custom name and/or note on one device."""
    coordinator = _first(hass)
    if coordinator is None:
        connection.send_error(msg["id"], "not_loaded", "Integration not loaded")
        return
    ok = await coordinator.async_update_device(
        msg["key"], name=msg.get("name"), note=msg.get("note")
    )
    if not ok:
        connection.send_error(msg["id"], "not_found", "Unknown device")
        return
    connection.send_result(msg["id"], {"ok": True})


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_SET_WHITELIST,
        vol.Required("key"): str,
        vol.Required("trusted"): bool,
    }
)
@websocket_api.async_response
async def ws_set_whitelist(hass, connection, msg) -> None:
    """Trust or untrust one device."""
    coordinator = _first(hass)
    if coordinator is None:
        connection.send_error(msg["id"], "not_loaded", "Integration not loaded")
        return

    record = coordinator.devices.get(msg["key"])
    if record is None:
        connection.send_error(msg["id"], "not_found", "Unknown device")
        return

    if msg["trusted"]:
        await coordinator.async_add_to_whitelist(
            mac=record.mac,
            ip=None if record.mac else record.ip,
            name=record.display_name,
        )
    else:
        await coordinator.async_remove_from_whitelist(record.mac or record.ip)

    connection.send_result(msg["id"], {"ok": True})


@websocket_api.websocket_command({vol.Required("type"): WS_SCAN})
@websocket_api.async_response
async def ws_scan(hass, connection, msg) -> None:
    """Force a scan right now."""
    for coordinator in _coordinators(hass):
        await coordinator.async_request_refresh()
    connection.send_result(msg["id"], {"ok": True})


@websocket_api.websocket_command(
    {vol.Required("type"): WS_SCAN_PORTS, vol.Optional("key"): vol.Any(str, None)}
)
@websocket_api.async_response
async def ws_scan_ports(hass, connection, msg) -> None:
    """Probe ports now, for one device or for every online device."""
    coordinator = _first(hass)
    if coordinator is None:
        connection.send_error(msg["id"], "not_loaded", "Integration not loaded")
        return
    result = await coordinator.async_scan_ports_now(msg.get("key"))
    if result == "no_ports":
        connection.send_error(msg["id"], "no_ports", "No ports configured")
        return
    if result == "busy":
        connection.send_error(
            msg["id"], "busy", "A network scan is running, try again shortly"
        )
        return
    connection.send_result(msg["id"], {"ok": True})


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_SET_WATCH,
        vol.Required("key"): str,
        vol.Required("watched"): bool,
    }
)
@websocket_api.async_response
async def ws_set_watch(hass, connection, msg) -> None:
    """Add or remove a device from the availability watchlist."""
    coordinator = _first(hass)
    if coordinator is None:
        connection.send_error(msg["id"], "not_loaded", "Integration not loaded")
        return
    if not await coordinator.async_set_watched(msg["key"], msg["watched"]):
        connection.send_error(msg["id"], "not_found", "Unknown device")
        return
    connection.send_result(msg["id"], {"ok": True})
