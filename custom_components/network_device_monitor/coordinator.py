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
"""Scan coordinator, persistence and notification logic.

Network monitor - By Marco Cavallo.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from dataclasses import fields as dataclass_fields
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.template import Template
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    ATTR_FIRST_SEEN,
    ATTR_EMOJI,
    ATTR_HA_DEVICE,
    ATTR_HOSTNAME,
    ATTR_ICON,
    ATTR_IP,
    ATTR_LAST_SEEN,
    ATTR_MAC,
    ATTR_NAME,
    ATTR_NOTE,
    ATTR_PORTS,
    ATTR_ONLINE,
    ATTR_VENDOR,
    CONF_EMAIL_RECIPIENT,
    CONF_ENABLE_TRACKERS,
    CONF_NEW_DEVICE_HOLD,
    CONF_NOTIFY_MESSAGE,
    CONF_NOTIFY_SERVICES,
    CONF_NOTIFY_TITLE,
    CONF_DEFAULT_OPEN_PORT,
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
    PORT_NAMES,
    WEB_PORTS,
    DEFAULT_OFFLINE_AFTER,
    STARTUP_GRACE_SECONDS,
    STORE_CHECKPOINT_SECONDS,
    default_templates,
    recovery_templates,
    watch_templates,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SCAN_METHOD,
    CONF_RECOVERY_MESSAGE,
    CONF_RECOVERY_TITLE,
    CONF_WATCH_MESSAGE,
    CONF_WATCH_TITLE,
    EVENT_ANOMALOUS_DEVICE,
    EVENT_WATCHED_DOWN,
    EVENT_WATCHED_UP,
    EVENT_NEW_DEVICE,
    INTEGRATION_NAME,
    SIGNAL_NEW_TRACKERS,
    STORAGE_KEY,
    STORAGE_VERSION,
)
from .device_types import DeviceType, classify
from .scanner import (
    DiscoveredDevice,
    NetworkScanner,
    ScannerError,
    async_identify_web,
    clean_label,
    async_scan_ports,
    normalize_mac,
    ALL_PORTS,
    FULL_PORT_CONCURRENCY,
    FULL_PORT_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)

type NetworkMonitorConfigEntry = ConfigEntry[NetworkMonitorCoordinator]


@dataclass(slots=True)
class DeviceRecord:
    """A host the integration has seen at least once."""

    key: str
    ip: str
    mac: str | None = None
    hostname: str | None = None
    vendor: str | None = None
    name: str | None = None
    ha_device: str | None = None
    note: str = ""
    ports: list[int] = field(default_factory=list)
    ports_scanned_at: str = ""
    web_name: str | None = None
    web_model: str | None = None
    web_server: str | None = None
    first_seen: str = ""
    last_seen: str = ""
    online: bool = False
    misses: int = 0   # consecutive scans this host failed to answer

    @property
    def display_name(self) -> str:
        """Best human-readable label available for this host.

        Preference order: the name the user gave it, the name of the
        matching Home Assistant device, what its own web interface calls
        itself, the reverse-DNS hostname, the hardware vendor, and finally
        the bare IP address.
        """
        return (
            self.name
            or self.ha_device
            or self.web_name
            or self.hostname
            or (f"{self.vendor} ({self.ip})" if self.vendor else self.ip)
        )

    @property
    def device_type(self) -> DeviceType:
        """Icon pair inferred from the device name or hardware vendor."""
        return classify(self.ha_device, self.vendor)

    def as_attributes(self) -> dict[str, Any]:
        """Render the record for entity attributes and notifications."""
        device_type = self.device_type
        return {
            ATTR_NAME: self.display_name,
            ATTR_NOTE: self.note,
            ATTR_PORTS: list(self.ports),
            ATTR_ICON: device_type.icon,
            ATTR_EMOJI: device_type.emoji,
            ATTR_HA_DEVICE: self.ha_device,
            ATTR_MAC: self.mac,
            ATTR_IP: self.ip,
            ATTR_HOSTNAME: self.hostname,
            ATTR_VENDOR: self.vendor,
            ATTR_FIRST_SEEN: self.first_seen,
            ATTR_LAST_SEEN: self.last_seen,
            ATTR_ONLINE: self.online,
        }


@dataclass(slots=True)
class WhitelistEntry:
    """A device the user has explicitly marked as trusted."""

    mac: str | None = None
    ip: str | None = None
    name: str | None = None
    source: str = "ui"  # "ui" or "yaml"

    def matches(self, record: DeviceRecord) -> bool:
        """Return True when this rule covers ``record``."""
        if self.mac and record.mac and self.mac == record.mac:
            return True
        return bool(self.ip and self.ip == record.ip)

    @property
    def identifier(self) -> str:
        """Stable key used by the options flow and the remove service."""
        return self.mac or self.ip or ""


class NetworkMonitorCoordinator(DataUpdateCoordinator[dict[str, DeviceRecord]]):
    """Own the scan cycle, the device inventory and the whitelist."""

    config_entry: NetworkMonitorConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: NetworkMonitorConfigEntry,
        yaml_whitelist: list[WhitelistEntry] | None = None,
    ) -> None:
        """Set up the coordinator for ``entry``."""
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, STORAGE_KEY, private=True
        )
        self._devices: dict[str, DeviceRecord] = {}
        self._whitelist: list[WhitelistEntry] = []
        self._watchlist: list[WhitelistEntry] = []
        self._yaml_whitelist = yaml_whitelist or []
        self._last_new_device_at: datetime | None = None
        self._last_scan_at: datetime | None = None
        self._last_saved_at: datetime | None = None
        self._last_port_scan_at: datetime | None = None
        self._port_scan_running = False
        # Chiave del dispositivo sotto scansione completa, per il pannello.
        self._port_scan_target: str | None = None
        self._discovery_running = False
        self._recovered: list[DeviceRecord] = []
        self._started_at = dt_util.utcnow()
        self._scanner: NetworkScanner | None = None
        self._known_tracker_keys: set[str] = set()

        super().__init__(
            hass,
            _LOGGER,
            name=INTEGRATION_NAME,
            config_entry=entry,
            update_interval=timedelta(seconds=self.scan_interval_from(entry)),
        )

    # ------------------------------------------------------------------
    # Configuration helpers
    # ------------------------------------------------------------------
    @staticmethod
    def scan_interval_from(entry: ConfigEntry) -> int:
        """Read the scan interval from options, falling back to data."""
        return int(
            entry.options.get(
                CONF_SCAN_INTERVAL,
                entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            )
        )

    def _option(self, key: str, default: Any) -> Any:
        """Read ``key`` from options, then data, then ``default``."""
        entry = self.config_entry
        return entry.options.get(key, entry.data.get(key, default))

    @property
    def subnet(self) -> str:
        """Subnet being scanned."""
        return str(self._option(CONF_SUBNET, ""))

    @property
    def scan_method(self) -> str:
        """Configured scan back-end."""
        return str(self._option(CONF_SCAN_METHOD, DEFAULT_SCAN_METHOD))

    @property
    def new_device_hold(self) -> int:
        """Seconds the 'new device' binary sensor stays on."""
        return int(self._option(CONF_NEW_DEVICE_HOLD, DEFAULT_NEW_DEVICE_HOLD))

    @property
    def offline_after(self) -> int:
        """Consecutive missed scans before a host is marked offline."""
        return max(1, int(self._option(CONF_OFFLINE_AFTER, DEFAULT_OFFLINE_AFTER)))

    @property
    def panel_enabled(self) -> bool:
        """Whether the sidebar panel is shown."""
        return bool(self._option(CONF_ENABLE_PANEL, DEFAULT_ENABLE_PANEL))

    @property
    def port_scan_enabled(self) -> bool:
        """Whether open ports are probed on discovered hosts."""
        return bool(self._option(CONF_PORT_SCAN, DEFAULT_PORT_SCAN))

    @property
    def port_list(self) -> list[int]:
        """Ports to probe, parsed from the comma-separated option."""
        raw = str(self._option(CONF_PORT_LIST, DEFAULT_PORT_LIST))
        ports: list[int] = []
        for chunk in raw.replace(";", ",").split(","):
            chunk = chunk.strip()
            if not chunk.isdigit():
                continue
            port = int(chunk)
            if 1 <= port <= 65535 and port not in ports:
                ports.append(port)
        return ports

    @property
    def port_scan_interval(self) -> int:
        """Seconds between two port-probing passes."""
        return max(
            60,
            int(self._option(CONF_PORT_SCAN_INTERVAL, DEFAULT_PORT_SCAN_INTERVAL)),
        )

    @property
    def default_open_port(self) -> int:
        """Port the panel's open button uses; 0 means pick automatically."""
        return int(self._option(CONF_DEFAULT_OPEN_PORT, DEFAULT_OPEN_PORT))

    @property
    def trackers_enabled(self) -> bool:
        """Whether a device_tracker is created per discovered host."""
        return bool(self._option(CONF_ENABLE_TRACKERS, DEFAULT_ENABLE_TRACKERS))

    @property
    def notify_services(self) -> list[str]:
        """Notify services called when an anomalous device appears."""
        return list(self._option(CONF_NOTIFY_SERVICES, []) or [])

    @property
    def _defaults(self) -> tuple[str, str]:
        """Fallback templates in the language Home Assistant is set to."""
        return default_templates(self.hass.config.language)

    @property
    def notify_title_template(self) -> str:
        """Jinja template for the notification title."""
        return str(self._option(CONF_NOTIFY_TITLE, self._defaults[0]))

    @property
    def notify_message_template(self) -> str:
        """Jinja template for the notification body."""
        return str(self._option(CONF_NOTIFY_MESSAGE, self._defaults[1]))

    @property
    def email_recipient(self) -> str | None:
        """Email address passed as ``target`` to email notify services."""
        return self._option(CONF_EMAIL_RECIPIENT, None) or None

    # ------------------------------------------------------------------
    # Exposed state
    # ------------------------------------------------------------------
    @property
    def devices(self) -> dict[str, DeviceRecord]:
        """Every device ever seen, keyed by MAC (or ip:<addr>)."""
        return self._devices

    @property
    def whitelist(self) -> list[WhitelistEntry]:
        """Trusted devices, from the UI store plus configuration.yaml."""
        return [*self._whitelist, *self._yaml_whitelist]

    @property
    def last_scan_at(self) -> datetime | None:
        """Timestamp of the most recent completed scan."""
        return self._last_scan_at

    @property
    def last_new_device_at(self) -> datetime | None:
        """Timestamp of the most recent first-time detection."""
        return self._last_new_device_at

    @property
    def last_used_method(self) -> str | None:
        """Scan back-end used most recently."""
        return self._scanner.last_used_method if self._scanner else None

    @property
    def watchlist(self) -> list[WhitelistEntry]:
        """Devices whose availability is monitored."""
        return self._watchlist

    def is_watched(self, record: DeviceRecord) -> bool:
        """Return True when this device is on the watchlist."""
        return any(rule.matches(record) for rule in self._watchlist)

    @property
    def watched_offline(self) -> list[DeviceRecord]:
        """Watched devices that are currently unreachable."""
        return [
            record
            for record in self._devices.values()
            if not record.online and self.is_watched(record)
        ]

    async def async_set_watched(self, key: str, watched: bool) -> bool:
        """Add or remove a device from the watchlist."""
        record = self._devices.get(key)
        if record is None:
            return False

        if watched:
            if self.is_watched(record):
                return True
            self._watchlist.append(
                WhitelistEntry(
                    mac=record.mac,
                    ip=None if record.mac else record.ip,
                    name=record.display_name,
                )
            )
        else:
            self._watchlist = [
                rule for rule in self._watchlist if not rule.matches(record)
            ]

        await self.async_save_store()
        self.async_update_listeners()
        return True

    def is_whitelisted(self, record: DeviceRecord) -> bool:
        """Return True when ``record`` matches any whitelist rule."""
        return any(rule.matches(record) for rule in self.whitelist)

    @property
    def anomalous_devices(self) -> list[DeviceRecord]:
        """Currently-online devices that are not whitelisted."""
        return [
            record
            for record in self._devices.values()
            if record.online and not self.is_whitelisted(record)
        ]

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    async def async_load_store(self) -> None:
        """Restore the device inventory and whitelist from disk."""
        stored = await self._store.async_load() or {}

        fields = {f.name for f in dataclass_fields(DeviceRecord)}
        for raw in stored.get("devices", []):
            try:
                record = DeviceRecord(
                    **{k: v for k, v in raw.items() if k in fields}
                )
            except TypeError:
                _LOGGER.debug("Skipping malformed stored device: %s", raw)
                continue
            # `online` is kept as it was saved. Forcing it to False here
            # made every watched device look like it had just come back on
            # the first scan after a restart, firing a recovery notification
            # for each one. Keeping it also means a device that really died
            # while Home Assistant was down is still reported as an outage.
            record.misses = 0
            # Older versions stored the IP as the hostname when there was no
            # PTR record; drop those so display_name can fall through.
            if record.hostname == record.ip:
                record.hostname = None
            # Re-run the label filter: earlier versions stored model names
            # ("Shelly1PM") and error pages ("404 - Page not found").
            record.web_name = clean_label(record.web_name)
            # Older versions copied the auto-generated label into the
            # user-name field when a device was whitelisted. Those are not
            # user choices and must not shadow a real name.
            if record.name and record.name in (
                record.ip,
                f"{record.vendor} ({record.ip})" if record.vendor else None,
            ):
                record.name = None
            self._devices[record.key] = record

        for key, target in (("whitelist", self._whitelist),
                            ("watchlist", self._watchlist)):
            for raw in stored.get(key, []):
                target.append(
                    WhitelistEntry(
                        mac=normalize_mac(raw.get("mac")),
                        ip=raw.get("ip"),
                        name=raw.get("name"),
                        source="ui",
                    )
                )

        _LOGGER.debug(
            "Restored %s devices and %s whitelist entries",
            len(self._devices),
            len(self._whitelist),
        )

    async def async_save_store(self) -> None:
        """Persist the device inventory and whitelist to disk."""
        await self._store.async_save(
            {
                "devices": [asdict(record) for record in self._devices.values()],
                "whitelist": [
                    {"mac": rule.mac, "ip": rule.ip, "name": rule.name}
                    for rule in self._whitelist
                ],
                "watchlist": [
                    {"mac": rule.mac, "ip": rule.ip, "name": rule.name}
                    for rule in self._watchlist
                ],
            }
        )
        self._last_saved_at = dt_util.utcnow()

    async def _async_save_if_needed(self, dirty: bool, now: datetime) -> None:
        """Write the store only when something changed, or periodically.

        Writing 40 kB on every scan was ~115 MB/day at a 30 s interval, all
        of it identical. The periodic checkpoint still flushes `last_seen`
        so it is not badly stale after a restart.
        """
        stale = (
            self._last_saved_at is None
            or (now - self._last_saved_at).total_seconds()
            >= STORE_CHECKPOINT_SECONDS
        )
        if not dirty and not stale:
            return
        await self.async_save_store()
        self._last_saved_at = now

    def async_apply_options(self) -> None:
        """Re-read the update interval after an options change."""
        self.update_interval = timedelta(
            seconds=self.scan_interval_from(self.config_entry)
        )
        self._scanner = None  # rebuilt on the next scan with fresh settings

    # ------------------------------------------------------------------
    # Scanning
    # ------------------------------------------------------------------
    async def _async_update_data(self) -> dict[str, DeviceRecord]:
        """Run one scan cycle and reconcile it with the known inventory."""
        if self._scanner is None:
            self._scanner = NetworkScanner(self.subnet, self.scan_method)

        self._discovery_running = True
        try:
            found = await self._scanner.async_scan()
        except ScannerError as err:
            raise UpdateFailed(str(err)) from err
        finally:
            self._discovery_running = False
        self._recovered: list[DeviceRecord] = []

        now = dt_util.utcnow()
        timestamp = now.isoformat()
        seen_keys: set[str] = set()
        new_records: list[DeviceRecord] = []
        self._recovered: list[DeviceRecord] = []
        went_down: list[DeviceRecord] = []
        dirty = False

        for device in found:
            record, changed = self._merge(device, timestamp)
            seen_keys.add(record.key)
            dirty |= changed
            if record.first_seen == timestamp:
                new_records.append(record)

        # A single dropped ARP reply is normal on a busy network. Only call a
        # host offline once it has missed `offline_after` scans in a row,
        # otherwise the online count oscillates every cycle.
        tolerance = self.offline_after
        for key, record in self._devices.items():
            if key in seen_keys:
                if record.misses:
                    record.misses = 0
                continue
            record.misses += 1
            if record.online and record.misses >= tolerance:
                record.online = False
                if self.is_watched(record):
                    went_down.append(record)

        self._last_scan_at = now

        if new_records:
            self._last_new_device_at = now
            # First run on an empty whitelist would log one warning per host.
            # Collapse that into a single summary line.
            bulk = not self.whitelist and len(new_records) > 5
            if bulk:
                _LOGGER.warning(
                    "First scan of %s found %s devices and the whitelist is "
                    "empty, so they all count as unauthorised. Add the ones "
                    "you recognise via Settings > Devices & Services > "
                    "Network monitor > Configure > Add trusted devices",
                    self.subnet,
                    len(new_records),
                )
            for record in new_records:
                await self._async_handle_new_device(record, quiet=bulk)

        if self.trackers_enabled:
            fresh = seen_keys - self._known_tracker_keys
            if fresh:
                self._known_tracker_keys |= fresh
                async_dispatcher_send(
                    self.hass, f"{SIGNAL_NEW_TRACKERS}_{self.config_entry.entry_id}"
                )

        for record in went_down:
            await self._async_notify_watched(record, up=False)
        for record in self._recovered:
            await self._async_notify_watched(record, up=True)

        await self._async_save_if_needed(
            dirty or bool(new_records) or bool(went_down) or bool(self._recovered),
            now,
        )
        self._async_maybe_scan_ports(now)
        return self._devices

    def _merge(
        self, device: DiscoveredDevice, timestamp: str
    ) -> tuple[DeviceRecord, bool]:
        """Insert or update the record for ``device``.

        Returns the record and whether anything worth persisting changed.
        `last_seen` alone does not count: it moves every single scan and
        would defeat the point of only writing the store on change.
        """
        key = device.key
        record = self._devices.get(key)

        if record is None:
            record = DeviceRecord(
                key=key,
                ip=device.ip,
                mac=device.mac,
                hostname=device.hostname,
                vendor=device.vendor,
                first_seen=timestamp,
            )
            if record.mac:
                record.ha_device = self._ha_device_name(record.mac)
            record.last_seen = timestamp
            record.online = True
            self._devices[key] = record
            return record, True

        was_offline = not record.online
        # `online` and `misses` are deliberately NOT part of `changed`:
        # async_load_store resets them on every restart, so persisting them
        # immediately buys nothing and battery devices that sleep and wake
        # would trigger a write on every single scan.
        changed = record.ip != device.ip
        record.ip = device.ip
        # Never overwrite good data with a None from a partial scan.
        for attr, value in (
            ("mac", device.mac),
            ("hostname", device.hostname),
            ("vendor", device.vendor),
        ):
            if value and getattr(record, attr) != value:
                setattr(record, attr, value)
                changed = True

        if record.ha_device is None and record.mac:
            if (name := self._ha_device_name(record.mac)) is not None:
                record.ha_device = name
                changed = True

        record.last_seen = timestamp
        record.online = True
        record.misses = 0
        if was_offline and self.is_watched(record):
            self._recovered.append(record)
        return record, changed

    def _ha_device_name(self, mac: str) -> str | None:
        """Look the MAC up in the device registry to get a real name.

        Most hosts on a smart-home LAN are already known to Home Assistant,
        so this turns an anonymous MAC into "Luce salotto" or "Frigorifero".
        """
        registry = dr.async_get(self.hass)
        device = registry.async_get_device(
            connections={(dr.CONNECTION_NETWORK_MAC, dr.format_mac(mac))}
        )
        if device is None:
            return None
        return device.name_by_user or device.name

    async def _async_handle_new_device(
        self, record: DeviceRecord, quiet: bool = False
    ) -> None:
        """Fire events and send notifications for a first-time detection."""
        payload = record.as_attributes()
        self.hass.bus.async_fire(EVENT_NEW_DEVICE, payload)

        if self.is_whitelisted(record):
            _LOGGER.debug("New but whitelisted device: %s", record.key)
            return

        self.hass.bus.async_fire(EVENT_ANOMALOUS_DEVICE, payload)
        log = _LOGGER.debug if quiet else _LOGGER.warning
        log(
            "Unauthorised device on %s: %s (mac=%s ip=%s)",
            self.subnet,
            record.display_name,
            record.mac,
            record.ip,
        )
        await self._async_notify(record)

    @property
    def in_startup_grace(self) -> bool:
        """True while availability alerts are still muted after a restart."""
        return (
            dt_util.utcnow() - self._started_at
        ).total_seconds() < STARTUP_GRACE_SECONDS

    async def _async_notify_watched(
        self, record: DeviceRecord, up: bool
    ) -> None:
        """Alert that a watched device went down or came back."""
        if self.in_startup_grace:
            # Right after a restart the picture is not trustworthy yet.
            # The state is still updated, only the alert is skipped.
            _LOGGER.debug(
                "Startup grace: not alerting for %s (%s)",
                record.display_name,
                "recovered" if up else "unreachable",
            )
            return

        self.hass.bus.async_fire(
            EVENT_WATCHED_UP if up else EVENT_WATCHED_DOWN,
            record.as_attributes(),
        )
        _LOGGER.warning(
            "Watched device %s: %s (%s)",
            "recovered" if up else "unreachable",
            record.display_name,
            record.ip,
        )
        if not self.notify_services:
            return

        last = dt_util.parse_datetime(record.last_seen) if record.last_seen else None
        local = dt_util.as_local(last) if last else None
        down_for = "-"
        if last is not None and not up:
            seconds = int((dt_util.utcnow() - last).total_seconds())
            down_for = (
                f"{seconds // 60} min" if seconds >= 60 else f"{seconds} s"
            )

        language = self.hass.config.language
        it = (language or "en").lower().startswith("it")
        variables = {
            "name": record.display_name,
            "mac": record.mac or "-",
            "ip": record.ip,
            "vendor": record.vendor or "-",
            "subnet": self.subnet,
            "seen": local.strftime("%d/%m/%Y %H:%M:%S") if local else "-",
            "emoji": "\U0001F7E2" if up else "\U0001F534",
            "state": ("tornato online" if it else "back online")
            if up
            else ("non raggiungibile" if it else "unreachable"),
            "down_for": down_for,
        }

        # Down and recovery have their own templates: the two events say
        # different things and deserve different wording.
        if up:
            fallback_title, fallback_message = recovery_templates(language)
            title_key, message_key = CONF_RECOVERY_TITLE, CONF_RECOVERY_MESSAGE
        else:
            fallback_title, fallback_message = watch_templates(language)
            title_key, message_key = CONF_WATCH_TITLE, CONF_WATCH_MESSAGE

        title = self._render(
            str(self._option(title_key, fallback_title)),
            variables,
            fallback_title,
        )
        message = self._render(
            str(self._option(message_key, fallback_message)),
            variables,
            fallback_message,
        )
        await self._async_send(title, message)

    async def _async_notify(self, record: DeviceRecord) -> None:
        """Send the configured notifications for an unauthorised device."""
        services = self.notify_services
        if not services:
            return

        seen = record.last_seen
        local = dt_util.as_local(dt_util.parse_datetime(seen)) if seen else None
        variables = {
            "name": record.display_name,
            "mac": record.mac or "sconosciuto",
            "ip": record.ip,
            "hostname": record.hostname or "sconosciuto",
            "vendor": record.vendor or "sconosciuto",
            "subnet": self.subnet,
            "seen": local.strftime("%d/%m/%Y %H:%M:%S") if local else "sconosciuto",
            "count": len(self.anomalous_devices),
            "emoji": record.device_type.emoji,
        }

        fallback_title, fallback_message = self._defaults
        title = self._render(self.notify_title_template, variables, fallback_title)
        message = self._render(
            self.notify_message_template, variables, fallback_message
        )

        await self._async_send(title, message)

    async def _async_send(self, title: str, message: str) -> None:
        """Deliver one notification to every configured target."""
        services = self.notify_services
        if not services:
            return

        recipient = self.email_recipient
        for service in services:
            domain, _, name = service.partition(".")
            if not name:
                domain, name = "notify", domain

            try:
                if self.hass.services.has_service(domain, name):
                    # Legacy notify service (notify.mobile_app_x, notify.smtp).
                    data: dict[str, Any] = {"title": title, "message": message}
                    # Mobile-app services address the device itself; email
                    # services need an explicit recipient in `target`.
                    if recipient and not name.startswith("mobile_app_"):
                        data["target"] = [recipient]
                    await self.hass.services.async_call(
                        domain, name, data, blocking=False
                    )
                elif self.hass.states.get(service) is not None:
                    # Entity-based notify platform. This is the model that
                    # survives the removal of legacy notify services in
                    # 2027.1; the recipient lives in the entity's own config.
                    await self.hass.services.async_call(
                        "notify",
                        "send_message",
                        {
                            "entity_id": service,
                            "title": title,
                            "message": message,
                        },
                        blocking=False,
                    )
                else:
                    _LOGGER.warning(
                        "Notification target %s does not exist (neither a "
                        "service nor an entity); check the integration options",
                        service,
                    )
            except Exception:  # noqa: BLE001 - one bad target must not break the scan
                _LOGGER.exception("Notification via %s failed", service)

    def _render(
        self, template: str, variables: dict[str, Any], fallback: str
    ) -> str:
        """Render a user-supplied template, falling back if it is broken.

        A typo in the options must not silence the alert entirely.
        """
        for candidate in (template, fallback):
            try:
                return Template(candidate, self.hass).async_render(
                    variables, parse_result=False
                )
            except Exception:  # noqa: BLE001 - bad template is user error
                _LOGGER.warning(
                    "Notification template failed to render: %s", candidate
                )
        return fallback

    # ------------------------------------------------------------------
    # Whitelist management
    # ------------------------------------------------------------------
    async def async_add_to_whitelist(
        self, mac: str | None = None, ip: str | None = None, name: str | None = None
    ) -> bool:
        """Trust a device. Returns False when nothing was added."""
        mac = normalize_mac(mac)
        if not mac and not ip:
            return False

        for rule in self._whitelist:
            if (mac and rule.mac == mac) or (ip and rule.ip == ip):
                rule.name = name or rule.name
                await self.async_save_store()
                return True

        self._whitelist.append(WhitelistEntry(mac=mac, ip=ip, name=name))

        # Deliberately NOT touching record.name here: trusting a device is
        # not the same as naming it. Writing the label of the moment into
        # record.name froze auto-generated names like "Espressif (192.168.1.2)"
        # and shadowed better names found later (HA device, web interface).

        await self.async_save_store()
        self.async_update_listeners()
        return True

    async def async_remove_from_whitelist(self, identifier: str) -> bool:
        """Stop trusting the device matching ``identifier`` (MAC or IP)."""
        normalized = normalize_mac(identifier) or identifier
        before = len(self._whitelist)
        self._whitelist = [
            rule
            for rule in self._whitelist
            if rule.mac != normalized and rule.ip != normalized
        ]
        if len(self._whitelist) == before:
            return False

        await self.async_save_store()
        self.async_update_listeners()
        return True

    async def async_update_device(
        self, key: str, name: str | None = None, note: str | None = None
    ) -> bool:
        """Set a custom name and/or a free-text note on a device."""
        record = self._devices.get(key)
        if record is None:
            return False
        if name is not None:
            record.name = name.strip() or None
        if note is not None:
            record.note = note.strip()
        await self.async_save_store()
        self.async_update_listeners()
        return True

    @callback
    def _async_maybe_scan_ports(self, now: datetime) -> None:
        """Kick off a port-probing pass if one is due.

        It runs as a detached task: probing 80 hosts takes seconds and must
        not delay the next discovery scan.
        """
        if not self.port_scan_enabled or self._port_scan_running:
            return
        if self._last_port_scan_at is not None and (
            now - self._last_port_scan_at
        ).total_seconds() < self.port_scan_interval:
            return
        self._last_port_scan_at = now
        self.config_entry.async_create_background_task(
            self.hass, self._async_scan_ports(), f"{DOMAIN}_port_scan"
        )

    async def _async_scan_ports(
        self, keys: list[str] | None = None, full: bool = False
    ) -> None:
        """Probe ports on online hosts and store the result.

        The periodic pass uses the configured list; a manual pass sweeps the
        whole range, which is why it is limited to one host at a time.
        """
        if self._port_scan_running:
            return
        if self._discovery_running:
            # nmap is already on the wire; adding hundreds of TCP probes on
            # top would put the two passes in each other's way. Clear the
            # timestamp so the next cycle retries instead of waiting a whole
            # interval.
            if keys is None:
                self._last_port_scan_at = None
            _LOGGER.debug("Port scan deferred: discovery in progress")
            return
        ports = list(ALL_PORTS) if full else self.port_list
        if not ports:
            return

        targets = {
            record.ip: record
            for record in self._devices.values()
            if record.online and (keys is None or record.key in keys)
        }
        if not targets:
            return

        self._port_scan_running = True
        self.async_update_listeners()
        try:
            if full:
                found = await async_scan_ports(
                    list(targets), ports, FULL_PORT_TIMEOUT, FULL_PORT_CONCURRENCY
                )
            else:
                found = await async_scan_ports(list(targets), ports)
        except Exception:  # noqa: BLE001 - probing must never break the scan loop
            _LOGGER.exception("Port scan failed")
            return
        finally:
            self._port_scan_running = False

        stamp = dt_util.utcnow().isoformat()
        changed = False
        for ip, open_ports in found.items():
            record = targets.get(ip)
            if record is None:
                continue
            if record.ports != open_ports:
                record.ports = open_ports
                changed = True
            record.ports_scanned_at = stamp

        _LOGGER.debug(
            "Port scan over %s hosts: %s with open ports",
            len(targets),
            sum(1 for v in found.values() if v),
        )

        changed |= await self._async_identify_web(list(targets.values()))
        if changed:
            await self.async_save_store()
        self.async_update_listeners()

    async def _async_identify_web(self, records: list[DeviceRecord]) -> bool:
        """Ask devices with a web interface what they call themselves.

        Runs right after the port probe, so it only contacts hosts that are
        actually listening on a web port.
        """
        urls: dict[str, str] = {}
        for record in records:
            url = self.device_url(record)
            if url:
                urls[record.ip] = url
        if not urls:
            return False

        try:
            found = await async_identify_web(urls)
        except Exception:  # noqa: BLE001 - identification is a nicety
            _LOGGER.exception("Web identification failed")
            return False

        by_ip = {record.ip: record for record in records}
        changed = False
        for ip, ident in found.items():
            record = by_ip.get(ip)
            if record is None:
                continue
            for attr, value in (
                ("web_name", ident.best),
                ("web_model", ident.model),
                ("web_server", ident.server),
            ):
                if value and getattr(record, attr) != value:
                    setattr(record, attr, value)
                    changed = True

        named = sum(1 for i in found.values() if i.best)
        _LOGGER.debug(
            "Web identification: %s of %s devices named themselves",
            named,
            len(urls),
        )
        return changed

    async def async_scan_ports_now(self, key: str | None = None) -> str:
        """Probe ports immediately. Returns "ok", "no_ports" or "busy".

        A manual scan on one device sweeps every port. That takes a couple of
        minutes, so it runs in the background and the panel follows its state
        instead of waiting on the call.
        """
        if self._discovery_running or self._port_scan_running:
            return "busy"

        if key is not None:
            self._port_scan_target = key
            self.async_update_listeners()
            self.config_entry.async_create_background_task(
                self.hass, self._async_full_scan(key), "cudy_full_port_scan"
            )
            return "ok"

        if not self.port_list:
            return "no_ports"
        await self._async_scan_ports(None)
        return "ok"

    async def _async_full_scan(self, key: str) -> None:
        """Scansione completa di un singolo dispositivo."""
        try:
            await self._async_scan_ports([key], full=True)
        finally:
            self._port_scan_target = None
            self.async_update_listeners()

    def device_url(self, record: DeviceRecord) -> str | None:
        """Best URL to reach this device's web interface, if any.

        A configured default port wins; otherwise the first well-known web
        port found open decides both port and scheme.
        """
        forced = self.default_open_port
        if forced:
            scheme = "https" if forced in (443, 8443) else "http"
            suffix = "" if forced in (80, 443) else f":{forced}"
            return f"{scheme}://{record.ip}{suffix}"

        for port, scheme in WEB_PORTS:
            if port in record.ports:
                suffix = "" if port in (80, 443) else f":{port}"
                return f"{scheme}://{record.ip}{suffix}"
        return None

    def panel_payload(self) -> dict[str, Any]:
        """Everything the sidebar panel needs, in one round trip."""
        whitelist_keys = {
            record.key
            for record in self._devices.values()
            if self.is_whitelisted(record)
        }
        watch_keys = {
            record.key
            for record in self._devices.values()
            if self.is_watched(record)
        }
        return {
            "devices": [
                {
                    "key": record.key,
                    "name": record.display_name,
                    "custom_name": record.name,
                    "ha_device": record.ha_device,
                    "hostname": record.hostname,
                    "mac": record.mac,
                    "ip": record.ip,
                    "vendor": record.vendor,
                    "note": record.note,
                    "ports": [
                        {"port": p, "name": PORT_NAMES.get(p, "")}
                        for p in record.ports
                    ],
                    "ports_scanned_at": record.ports_scanned_at,
                    "web_name": record.web_name,
                    "web_model": record.web_model,
                    "web_server": record.web_server,
                    "url": self.device_url(record),
                    "first_seen": record.first_seen,
                    "last_seen": record.last_seen,
                    "online": record.online,
                    "misses": record.misses,
                    "whitelisted": record.key in whitelist_keys,
                    "watched": record.key in watch_keys,
                    "emoji": record.device_type.emoji,
                    "icon": record.device_type.icon,
                }
                for record in self._devices.values()
            ],
            "last_scan": (
                self._last_scan_at.isoformat() if self._last_scan_at else None
            ),
            "scan_method": self.last_used_method,
            "subnet": self.subnet,
            "scan_interval": self.scan_interval_from(self.config_entry),
            "port_scan": self.port_scan_enabled,
            "port_scan_running": self._port_scan_running,
            "port_scan_target": self._port_scan_target,
            "default_open_port": self.default_open_port,
            "anomalous": len(self.anomalous_devices),
            "watched": len(watch_keys),
            "watched_offline": len(self.watched_offline),
            "online": sum(1 for r in self._devices.values() if r.online),
            "total": len(self._devices),
        }

    async def async_forget_device(self, identifier: str) -> bool:
        """Drop a device from the inventory so it counts as new again."""
        normalized = normalize_mac(identifier) or identifier
        for key, record in list(self._devices.items()):
            if normalized in (key, record.mac, record.ip):
                del self._devices[key]
                self._known_tracker_keys.discard(key)
                await self.async_save_store()
                self.async_update_listeners()
                return True
        return False
