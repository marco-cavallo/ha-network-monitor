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
"""The Network monitor integration.

Scans the local network on a schedule, flags devices that are not on the
trusted list, and notifies by email and/or mobile push.

Network monitor - By Marco Cavallo.
"""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_NAME, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.helpers.typing import ConfigType

from . import websocket_api as nm_ws
from .const import (
    CONF_EMAIL_RECIPIENT,
    CONF_ENABLE_TRACKERS,
    CONF_IP,
    CONF_MAC,
    CONF_NEW_DEVICE_HOLD,
    CONF_NOTIFY_SERVICES,
    CONF_SCAN_INTERVAL,
    CONF_SCAN_METHOD,
    CONF_SUBNET,
    CONF_WHITELIST,
    DEFAULT_ENABLE_TRACKERS,
    DEFAULT_NEW_DEVICE_HOLD,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SCAN_METHOD,
    DOMAIN,
    MIN_SCAN_INTERVAL,
    SCAN_METHODS,
    SERVICE_ADD_TO_WHITELIST,
    SERVICE_FORGET_DEVICE,
    SERVICE_REMOVE_FROM_WHITELIST,
    SERVICE_ADD_TO_WATCHLIST,
    SERVICE_REMOVE_FROM_WATCHLIST,
    SERVICE_SCAN_NOW,
    PANEL_COMPONENT,
    PANEL_ICON,
    PANEL_MODULE_URL,
    PANEL_TITLE,
    PANEL_URL_PATH,
)
from .coordinator import (
    NetworkMonitorConfigEntry,
    NetworkMonitorCoordinator,
    WhitelistEntry,
)
from .scanner import normalize_mac

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
    Platform.DEVICE_TRACKER,
]

WHITELIST_ENTRY_SCHEMA = vol.Schema(
    vol.All(
        {
            vol.Optional(CONF_MAC): cv.string,
            vol.Optional(CONF_IP): cv.string,
            vol.Optional(CONF_NAME): cv.string,
        },
        cv.has_at_least_one_key(CONF_MAC, CONF_IP),
    )
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_SUBNET): cv.string,
                vol.Optional(
                    CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                ): vol.All(cv.positive_int, vol.Range(min=MIN_SCAN_INTERVAL)),
                vol.Optional(CONF_SCAN_METHOD, default=DEFAULT_SCAN_METHOD): vol.In(
                    SCAN_METHODS
                ),
                vol.Optional(CONF_WHITELIST, default=list): vol.All(
                    cv.ensure_list, [WHITELIST_ENTRY_SCHEMA]
                ),
                vol.Optional(CONF_EMAIL_RECIPIENT): cv.string,
                vol.Optional(CONF_NOTIFY_SERVICES, default=list): vol.All(
                    cv.ensure_list, [cv.string]
                ),
                vol.Optional(
                    CONF_NEW_DEVICE_HOLD, default=DEFAULT_NEW_DEVICE_HOLD
                ): cv.positive_int,
                vol.Optional(
                    CONF_ENABLE_TRACKERS, default=DEFAULT_ENABLE_TRACKERS
                ): cv.boolean,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

# YAML whitelist entries are kept out of the config entry so that the file
# stays the source of truth for them; the UI list lives in the store.
_YAML_WHITELIST_KEY = f"{DOMAIN}_yaml_whitelist"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Import a configuration.yaml block into a config entry."""
    if (yaml_config := config.get(DOMAIN)) is None:
        return True

    hass.data[_YAML_WHITELIST_KEY] = [
        WhitelistEntry(
            mac=normalize_mac(item.get(CONF_MAC)),
            ip=item.get(CONF_IP),
            name=item.get(CONF_NAME),
            source="yaml",
        )
        for item in yaml_config.get(CONF_WHITELIST, [])
    ]

    entry_data = {
        key: value
        for key, value in yaml_config.items()
        if key != CONF_WHITELIST
    }

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=entry_data
        )
    )
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: NetworkMonitorConfigEntry
) -> bool:
    """Set up Network monitor from a config entry."""
    coordinator = NetworkMonitorCoordinator(
        hass, entry, yaml_whitelist=hass.data.get(_YAML_WHITELIST_KEY, [])
    )
    await coordinator.async_load_store()
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    _async_register_services(hass)
    nm_ws.async_register(hass)
    await _async_setup_panel(hass, coordinator.panel_enabled)
    return True


async def _async_setup_panel(hass: HomeAssistant, enabled: bool) -> None:
    """Register or remove the sidebar panel."""
    if not enabled:
        if PANEL_URL_PATH in hass.data.get("frontend_panels", {}):
            frontend.async_remove_panel(hass, PANEL_URL_PATH)
        return

    if PANEL_URL_PATH in hass.data.get("frontend_panels", {}):
        return

    if not hass.data.get(f"{DOMAIN}_static_registered"):
        await hass.http.async_register_static_paths(
            [
                StaticPathConfig(
                    PANEL_MODULE_URL,
                    hass.config.path(f"custom_components/{DOMAIN}/panel/panel.js"),
                    False,   # no long cache: the file changes with the integration
                )
            ]
        )
        hass.data[f"{DOMAIN}_static_registered"] = True

    await panel_custom.async_register_panel(
        hass,
        webcomponent_name=PANEL_COMPONENT,
        frontend_url_path=PANEL_URL_PATH,
        module_url=PANEL_MODULE_URL,
        sidebar_title=PANEL_TITLE,
        sidebar_icon=PANEL_ICON,
        require_admin=True,
        config={},
    )


async def async_unload_entry(
    hass: HomeAssistant, entry: NetworkMonitorConfigEntry
) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded and not hass.config_entries.async_loaded_entries(DOMAIN):
        if PANEL_URL_PATH in hass.data.get("frontend_panels", {}):
            frontend.async_remove_panel(hass, PANEL_URL_PATH)
        for service in (
            SERVICE_SCAN_NOW,
            SERVICE_ADD_TO_WHITELIST,
            SERVICE_REMOVE_FROM_WHITELIST,
            SERVICE_FORGET_DEVICE,
            SERVICE_ADD_TO_WATCHLIST,
            SERVICE_REMOVE_FROM_WATCHLIST,
        ):
            hass.services.async_remove(DOMAIN, service)
    return unloaded


async def async_reload_entry(
    hass: HomeAssistant, entry: NetworkMonitorConfigEntry
) -> None:
    """Reload the config entry."""
    await hass.config_entries.async_reload(entry.entry_id)


async def _async_update_listener(
    hass: HomeAssistant, entry: NetworkMonitorConfigEntry
) -> None:
    """Apply changed options without a full reload where possible."""
    coordinator = entry.runtime_data
    coordinator.async_apply_options()
    await _async_setup_panel(hass, coordinator.panel_enabled)
    await coordinator.async_request_refresh()


# ----------------------------------------------------------------------
# Services
# ----------------------------------------------------------------------
def _async_register_services(hass: HomeAssistant) -> None:
    """Register the integration services once."""
    if hass.services.has_service(DOMAIN, SERVICE_SCAN_NOW):
        return

    def _coordinators() -> list[NetworkMonitorCoordinator]:
        return [
            entry.runtime_data
            for entry in hass.config_entries.async_loaded_entries(DOMAIN)
            if hasattr(entry, "runtime_data")
        ]

    async def handle_scan_now(_call: ServiceCall) -> None:
        for coordinator in _coordinators():
            await coordinator.async_request_refresh()

    async def handle_add(call: ServiceCall) -> None:
        mac = call.data.get(CONF_MAC)
        ip = call.data.get(CONF_IP)
        name = call.data.get(CONF_NAME)
        added = False
        for coordinator in _coordinators():
            added |= await coordinator.async_add_to_whitelist(mac, ip, name)
        if not added:
            raise ServiceValidationError(
                "Provide a valid mac or ip to add to the whitelist"
            )

    async def handle_remove(call: ServiceCall) -> None:
        identifier = call.data["device"]
        removed = False
        for coordinator in _coordinators():
            removed |= await coordinator.async_remove_from_whitelist(identifier)
        if not removed:
            raise ServiceValidationError(f"{identifier} is not in the whitelist")

    async def handle_forget(call: ServiceCall) -> None:
        identifier = call.data["device"]
        forgotten = False
        for coordinator in _coordinators():
            forgotten |= await coordinator.async_forget_device(identifier)
        if not forgotten:
            raise ServiceValidationError(f"{identifier} is not a known device")

    async def handle_watch(call: ServiceCall) -> None:
        identifier = call.data["device"]
        watched = call.data.get("watched", True)
        done = False
        for coordinator in _coordinators():
            for key, record in coordinator.devices.items():
                if identifier in (key, record.mac, record.ip):
                    done |= await coordinator.async_set_watched(key, watched)
        if not done:
            raise ServiceValidationError(f"{identifier} is not a known device")

    async def handle_unwatch(call: ServiceCall) -> None:
        await handle_watch(
            ServiceCall(
                hass, DOMAIN, SERVICE_REMOVE_FROM_WATCHLIST,
                {"device": call.data["device"], "watched": False},
            )
        )

    hass.services.async_register(
        DOMAIN, SERVICE_ADD_TO_WATCHLIST, handle_watch,
        schema=vol.Schema({vol.Required("device"): cv.string,
                           vol.Optional("watched", default=True): cv.boolean}),
    )
    hass.services.async_register(
        DOMAIN, SERVICE_REMOVE_FROM_WATCHLIST, handle_unwatch,
        schema=vol.Schema({vol.Required("device"): cv.string}),
    )
    hass.services.async_register(DOMAIN, SERVICE_SCAN_NOW, handle_scan_now)
    hass.services.async_register(
        DOMAIN,
        SERVICE_ADD_TO_WHITELIST,
        handle_add,
        schema=vol.Schema(
            vol.All(
                {
                    vol.Optional(CONF_MAC): cv.string,
                    vol.Optional(CONF_IP): cv.string,
                    vol.Optional(CONF_NAME): cv.string,
                },
                cv.has_at_least_one_key(CONF_MAC, CONF_IP),
            )
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_REMOVE_FROM_WHITELIST,
        handle_remove,
        schema=vol.Schema({vol.Required("device"): cv.string}),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_FORGET_DEVICE,
        handle_forget,
        schema=vol.Schema({vol.Required("device"): cv.string}),
    )
