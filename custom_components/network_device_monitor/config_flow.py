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
"""Config and options flow for the Network monitor integration.

Network monitor - By Marco Cavallo.
"""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from ipaddress import ip_interface

from homeassistant.components import network
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    AUTHOR,
    CONF_EMAIL_RECIPIENT,
    CONF_ENABLE_TRACKERS,
    CONF_IP,
    CONF_MAC,
    CONF_NEW_DEVICE_HOLD,
    CONF_NOTIFY_MESSAGE,
    CONF_NOTIFY_SERVICES,
    CONF_NOTIFY_TITLE,
    CONF_DEFAULT_OPEN_PORT,
    CONF_RECOVERY_MESSAGE,
    CONF_RECOVERY_TITLE,
    CONF_WATCH_MESSAGE,
    CONF_WATCH_TITLE,
    CONF_ENABLE_PANEL,
    CONF_PORT_LIST,
    CONF_PORT_SCAN,
    CONF_PORT_SCAN_INTERVAL,
    CONF_OFFLINE_AFTER,
    CONF_SCAN_INTERVAL,
    CONF_SCAN_METHOD,
    CONF_SUBNET,
    DEFAULT_ENABLE_TRACKERS,
    DEFAULT_NEW_DEVICE_HOLD,
    DEFAULT_ENABLE_PANEL,
    DEFAULT_OPEN_PORT,
    DEFAULT_PORT_LIST,
    DEFAULT_PORT_SCAN,
    DEFAULT_PORT_SCAN_INTERVAL,
    DEFAULT_OFFLINE_AFTER,
    default_templates,
    recovery_templates,
    watch_templates,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SCAN_METHOD,
    DOMAIN,
    INTEGRATION_NAME,
    VERSION,
    MIN_SCAN_INTERVAL,
    SCAN_METHODS,
)
from .coordinator import NetworkMonitorConfigEntry
from .device_types import GENERIC
from .scanner import NetworkScanner, normalize_mac

_LOGGER = logging.getLogger(__name__)

# Do not suggest anything bigger than a /20 (the scanner rejects it anyway).
MAX_SUGGEST_HOSTS = 4096

OPTION_KEYS = (
    CONF_SUBNET,
    CONF_SCAN_INTERVAL,
    CONF_SCAN_METHOD,
    CONF_EMAIL_RECIPIENT,
    CONF_NOTIFY_MESSAGE,
    CONF_NOTIFY_SERVICES,
    CONF_NOTIFY_TITLE,
    CONF_NEW_DEVICE_HOLD,
    CONF_ENABLE_TRACKERS,
    CONF_OFFLINE_AFTER,
    CONF_ENABLE_PANEL,
    CONF_PORT_SCAN,
    CONF_PORT_LIST,
    CONF_PORT_SCAN_INTERVAL,
    CONF_DEFAULT_OPEN_PORT,
    CONF_WATCH_TITLE,
    CONF_WATCH_MESSAGE,
    CONF_RECOVERY_TITLE,
    CONF_RECOVERY_MESSAGE,
)


def _device_label(record) -> str:
    """One line describing a device: name, IP, MAC, vendor, online state.

    Config-flow selectors render their labels as plain text -- the frontend
    strips markup -- so the name is upper-cased to stand out instead.
    """
    detail = [record.ip]
    if record.mac:
        detail.append(record.mac)
    if record.vendor and record.vendor not in record.display_name:
        detail.append(record.vendor)
    if record.online:
        detail.append("online")
    emoji = record.device_type.emoji
    return f"{emoji} {record.display_name.upper()}  —  {'  |  '.join(detail)}"


def _runtime(entry: NetworkMonitorConfigEntry):
    """Return the coordinator, or None when the entry failed to load."""
    return getattr(entry, "runtime_data", None)


def _notify_service_options(hass) -> list[str]:
    """Return the notify services currently registered, as 'notify.x'."""
    services = hass.services.async_services().get("notify", {})
    return sorted(f"notify.{name}" for name in services)


def _settings_schema(hass, defaults: dict[str, Any]) -> vol.Schema:
    """Build the shared settings form for both flows."""
    tpl_title, tpl_message = default_templates(hass.config.language)
    w_title, w_message = watch_templates(hass.config.language)
    r_title, r_message = recovery_templates(hass.config.language)
    return vol.Schema(
        {
            vol.Required(
                CONF_SUBNET, default=defaults.get(CONF_SUBNET, "")
            ): selector.TextSelector(),
            vol.Required(
                CONF_SCAN_INTERVAL,
                default=defaults.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=MIN_SCAN_INTERVAL,
                    max=86400,
                    step=10,
                    unit_of_measurement="s",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                CONF_SCAN_METHOD,
                default=defaults.get(CONF_SCAN_METHOD, DEFAULT_SCAN_METHOD),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=list(SCAN_METHODS),
                    translation_key="scan_method",
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Optional(
                CONF_EMAIL_RECIPIENT,
                description={
                    "suggested_value": defaults.get(CONF_EMAIL_RECIPIENT, "")
                },
            ): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.EMAIL)
            ),
            vol.Optional(
                CONF_NOTIFY_SERVICES,
                default=defaults.get(CONF_NOTIFY_SERVICES, []),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=_notify_service_options(hass),
                    multiple=True,
                    custom_value=True,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required(
                CONF_NEW_DEVICE_HOLD,
                default=defaults.get(CONF_NEW_DEVICE_HOLD, DEFAULT_NEW_DEVICE_HOLD),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=30,
                    max=3600,
                    step=10,
                    unit_of_measurement="s",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                CONF_OFFLINE_AFTER,
                default=defaults.get(CONF_OFFLINE_AFTER, DEFAULT_OFFLINE_AFTER),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1, max=10, step=1, mode=selector.NumberSelectorMode.BOX
                )
            ),
            vol.Required(
                CONF_ENABLE_PANEL,
                default=defaults.get(CONF_ENABLE_PANEL, DEFAULT_ENABLE_PANEL),
            ): selector.BooleanSelector(),
            vol.Required(
                CONF_ENABLE_TRACKERS,
                default=defaults.get(CONF_ENABLE_TRACKERS, DEFAULT_ENABLE_TRACKERS),
            ): selector.BooleanSelector(),
            # TemplateSelector gives syntax highlighting and a live preview.
            # The preview works because every placeholder in the shipped
            # templates carries a `default(...)`, so it renders sample values
            # instead of failing on variables that only exist at send time.
            vol.Required(
                CONF_PORT_SCAN,
                default=defaults.get(CONF_PORT_SCAN, DEFAULT_PORT_SCAN),
            ): selector.BooleanSelector(),
            vol.Optional(
                CONF_PORT_LIST,
                default=defaults.get(CONF_PORT_LIST, DEFAULT_PORT_LIST),
            ): selector.TextSelector(),
            vol.Required(
                CONF_PORT_SCAN_INTERVAL,
                default=defaults.get(
                    CONF_PORT_SCAN_INTERVAL, DEFAULT_PORT_SCAN_INTERVAL
                ),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=60, max=86400, step=60, unit_of_measurement="s",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                CONF_DEFAULT_OPEN_PORT,
                default=defaults.get(CONF_DEFAULT_OPEN_PORT, DEFAULT_OPEN_PORT),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, max=65535, step=1, mode=selector.NumberSelectorMode.BOX
                )
            ),
            vol.Optional(
                CONF_NOTIFY_TITLE,
                default=defaults.get(CONF_NOTIFY_TITLE, tpl_title),
            ): selector.TemplateSelector(),
            vol.Optional(
                CONF_NOTIFY_MESSAGE,
                default=defaults.get(CONF_NOTIFY_MESSAGE, tpl_message),
            ): selector.TemplateSelector(),
            vol.Optional(
                CONF_WATCH_TITLE,
                default=defaults.get(CONF_WATCH_TITLE, w_title),
            ): selector.TemplateSelector(),
            vol.Optional(
                CONF_WATCH_MESSAGE,
                default=defaults.get(CONF_WATCH_MESSAGE, w_message),
            ): selector.TemplateSelector(),
            vol.Optional(
                CONF_RECOVERY_TITLE,
                default=defaults.get(CONF_RECOVERY_TITLE, r_title),
            ): selector.TemplateSelector(),
            vol.Optional(
                CONF_RECOVERY_MESSAGE,
                default=defaults.get(CONF_RECOVERY_MESSAGE, r_message),
            ): selector.TemplateSelector(),
        }
    )


async def _async_validate(hass, user_input: dict[str, Any]) -> dict[str, str]:
    """Validate the settings form, returning a field -> error-key map."""
    errors: dict[str, str] = {}

    try:
        user_input[CONF_SUBNET] = NetworkScanner.validate_subnet(
            user_input[CONF_SUBNET]
        )
    except ValueError:
        errors[CONF_SUBNET] = "invalid_subnet"

    if user_input.get(CONF_SCAN_METHOD) == "nmap":
        if not await NetworkScanner.async_nmap_available():
            errors[CONF_SCAN_METHOD] = "nmap_missing"

    return errors


def _coerce(user_input: dict[str, Any]) -> dict[str, Any]:
    """Normalise numeric selector output to plain ints."""
    for key in (
        CONF_SCAN_INTERVAL,
        CONF_NEW_DEVICE_HOLD,
        CONF_OFFLINE_AFTER,
        CONF_PORT_SCAN_INTERVAL,
        CONF_DEFAULT_OPEN_PORT,
    ):
        if key in user_input:
            user_input[key] = int(user_input[key])
    return user_input


class NetworkMonitorConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the initial configuration of Network monitor."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect the settings from the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            user_input = _coerce(dict(user_input))
            errors = await _async_validate(self.hass, user_input)
            if not errors:
                return self.async_create_entry(
                    title=INTEGRATION_NAME, data={}, options=user_input
                )

        defaults = dict(user_input or {})
        if not defaults.get(CONF_SUBNET):
            defaults[CONF_SUBNET] = await _async_suggest_subnet(self.hass)

        return self.async_show_form(
            step_id="user",
            data_schema=_settings_schema(self.hass, defaults),
            errors=errors,
        )

    async def async_step_import(
        self, import_data: dict[str, Any]
    ) -> ConfigFlowResult:
        """Create the entry from a configuration.yaml block."""
        self._async_abort_entries_match()

        options = {
            key: import_data[key] for key in OPTION_KEYS if key in import_data
        }
        try:
            options[CONF_SUBNET] = NetworkScanner.validate_subnet(
                options.get(CONF_SUBNET, "")
            )
        except ValueError:
            _LOGGER.error(
                "Invalid subnet in configuration.yaml: %s", options.get(CONF_SUBNET)
            )
            return self.async_abort(reason="invalid_subnet")

        return self.async_create_entry(
            title=INTEGRATION_NAME, data={}, options=options
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the Reconfigure entry in the integration menu."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            user_input = _coerce(dict(user_input))
            errors = await _async_validate(self.hass, user_input)
            if not errors:
                return self.async_update_reload_and_abort(
                    entry, options={**entry.options, **user_input}
                )

        defaults = {**entry.options, **(user_input or {})}
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_settings_schema(self.hass, defaults),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: NetworkMonitorConfigEntry,
    ) -> NetworkMonitorOptionsFlow:
        """Return the options flow handler."""
        return NetworkMonitorOptionsFlow()


async def _async_suggest_subnet(hass) -> str:
    """Guess the local subnet from the Home Assistant host address.

    async_get_adapters is a coroutine: iterating it without awaiting raises
    TypeError, which is how this used to silently fall back to 192.168.1.0/24.
    """
    try:
        adapters = await network.async_get_adapters(hass)
    except Exception:  # noqa: BLE001 - suggestion only, never fatal
        _LOGGER.debug("Could not enumerate network adapters", exc_info=True)
        return ""

    # The adapter flagged "default" carries the route to the LAN; the docker
    # and hassio bridges must never win.
    for adapter in sorted(adapters, key=lambda a: not a.get("default")):
        if not adapter.get("enabled"):
            continue
        for ipv4 in adapter.get("ipv4", []):
            try:
                interface = ip_interface(
                    f"{ipv4['address']}/{ipv4['network_prefix']}"
                )
            except ValueError:
                continue
            if interface.ip.is_loopback or not interface.ip.is_private:
                continue
            if interface.network.num_addresses > MAX_SUGGEST_HOSTS:
                continue
            return str(interface.network)
    return ""


class NetworkMonitorOptionsFlow(OptionsFlow):
    """Edit settings and manage the whitelist from the UI."""

    config_entry: NetworkMonitorConfigEntry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the top-level menu."""
        return self.async_show_menu(
            step_id="init",
            menu_options=["settings", "add_whitelist", "remove_whitelist", "about"],
        )

    async def async_step_about(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show what the integration is and how it is currently running."""
        if user_input is not None:
            return await self.async_step_init()

        coordinator = _runtime(self.config_entry)
        if coordinator is None:
            stats = dict.fromkeys(
                ("total", "online", "anomalous", "whitelist", "method",
                 "last_scan", "watched", "watched_offline", "ports",
                 "panel", "named", "interval"),
                "-",
            )
        else:
            payload = coordinator.panel_payload()
            stats = {
                "total": payload["total"],
                "online": payload["online"],
                "anomalous": payload["anomalous"],
                "whitelist": len(coordinator.whitelist),
                "method": payload["scan_method"] or "-",
                "last_scan": payload["last_scan"] or "-",
                "watched": payload["watched"],
                "watched_offline": payload["watched_offline"],
                "ports": "on" if coordinator.port_scan_enabled else "off",
                "panel": "on" if coordinator.panel_enabled else "off",
                "named": sum(
                    1 for r in coordinator.devices.values() if r.web_name
                ),
                "interval": payload["scan_interval"],
            }

        return self.async_show_form(
            step_id="about",
            data_schema=vol.Schema({}),
            description_placeholders={
                "name": INTEGRATION_NAME,
                "version": VERSION,
                "author": AUTHOR,
                "subnet": coordinator.subnet if coordinator else "-",
                **{k: str(v) for k, v in stats.items()},
            },
        )

    async def async_step_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit scan and notification settings."""
        errors: dict[str, str] = {}

        if user_input is not None:
            user_input = _coerce(dict(user_input))
            errors = await _async_validate(self.hass, user_input)
            if not errors:
                return self.async_create_entry(data=user_input)

        defaults = {**self.config_entry.options, **(user_input or {})}
        return self.async_show_form(
            step_id="settings",
            data_schema=_settings_schema(self.hass, defaults),
            errors=errors,
        )

    async def async_step_add_whitelist(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Trust one or more currently-detected devices, or a manual MAC/IP."""
        if (coordinator := _runtime(self.config_entry)) is None:
            return self.async_abort(reason="not_loaded")

        candidates = {
            record.key: _device_label(record)
            for record in coordinator.devices.values()
            if not coordinator.is_whitelisted(record)
        }

        if user_input is not None:
            selected = (
                list(candidates)
                if user_input.get("select_all")
                else user_input.get("devices", [])
            )
            for key in selected:
                if (record := coordinator.devices.get(key)) is not None:
                    await coordinator.async_add_to_whitelist(
                        mac=record.mac,
                        ip=None if record.mac else record.ip,
                        name=record.display_name,
                    )

            manual = (user_input.get("manual") or "").strip()
            if manual:
                if (mac := normalize_mac(manual)) is not None:
                    await coordinator.async_add_to_whitelist(
                        mac=mac, name=user_input.get(CONF_NAME) or None
                    )
                else:
                    await coordinator.async_add_to_whitelist(
                        ip=manual, name=user_input.get(CONF_NAME) or None
                    )

            await coordinator.async_request_refresh()
            return self.async_create_entry(data=dict(self.config_entry.options))

        schema = vol.Schema(
            {
                vol.Optional("devices", default=[]): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(value=key, label=label)
                            for key, label in sorted(
                                candidates.items(), key=lambda item: item[1]
                            )
                        ],
                        multiple=True,
                        mode=selector.SelectSelectorMode.LIST,
                    )
                ),
                vol.Optional("select_all", default=False): (
                    selector.BooleanSelector()
                ),
                vol.Optional("manual", default=""): selector.TextSelector(),
                vol.Optional(CONF_NAME, default=""): selector.TextSelector(),
            }
        )
        return self.async_show_form(
            step_id="add_whitelist",
            data_schema=schema,
            description_placeholders={"count": str(len(candidates))},
        )

    async def async_step_remove_whitelist(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Remove entries from the UI-managed whitelist."""
        if (coordinator := _runtime(self.config_entry)) is None:
            return self.async_abort(reason="not_loaded")

        # Only UI entries are removable; YAML entries belong to the file.
        # Reuse the same label as the add step so both lists look alike:
        # look the rule back up against the inventory to recover vendor,
        # online state and the icon.
        by_mac = {r.mac: r for r in coordinator.devices.values() if r.mac}
        by_ip = {r.ip: r for r in coordinator.devices.values()}

        removable: dict[str, str] = {}
        for rule in coordinator.whitelist:
            if rule.source != "ui" or not rule.identifier:
                continue
            record = by_mac.get(rule.mac) or by_ip.get(rule.ip)
            if record is not None:
                removable[rule.identifier] = _device_label(record)
            else:
                # Whitelisted but no longer in the inventory.
                name = (rule.name or rule.identifier).upper()
                removable[rule.identifier] = (
                    f"{GENERIC.emoji} {name}  —  {rule.identifier}  |  non rilevato"
                )

        if not removable:
            return self.async_abort(reason="whitelist_empty")

        if user_input is not None:
            selected = (
                list(removable)
                if user_input.get("remove_all")
                else user_input.get("devices", [])
            )
            for identifier in selected:
                await coordinator.async_remove_from_whitelist(identifier)
            await coordinator.async_request_refresh()
            return self.async_create_entry(data=dict(self.config_entry.options))

        schema = vol.Schema(
            {
                vol.Optional("devices", default=[]): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(value=key, label=label)
                            for key, label in sorted(
                                removable.items(), key=lambda item: item[1]
                            )
                        ],
                        multiple=True,
                        mode=selector.SelectSelectorMode.LIST,
                    )
                ),
                vol.Optional("remove_all", default=False): (
                    selector.BooleanSelector()
                ),
            }
        )
        return self.async_show_form(
            step_id="remove_whitelist",
            data_schema=schema,
            description_placeholders={"count": str(len(removable))},
        )
