"""Optional per-device tracker platform for the Network monitor integration.

Disabled by default; switch "Create a device_tracker per device" on in the
integration options to enable it.

Network monitor - By Marco Cavallo.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.device_tracker import ScannerEntity, SourceType
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_FIRST_SEEN,
    ATTR_HOSTNAME,
    ATTR_IP,
    ATTR_LAST_SEEN,
    ATTR_MAC,
    ATTR_VENDOR,
    SIGNAL_NEW_TRACKERS,
)
from .coordinator import NetworkMonitorConfigEntry, NetworkMonitorCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NetworkMonitorConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up device trackers, adding new ones as devices appear."""
    coordinator = entry.runtime_data
    if not coordinator.trackers_enabled:
        return

    tracked: set[str] = set()

    @callback
    def _add_new_entities() -> None:
        """Create a tracker for every device we have not covered yet."""
        new = [
            NetworkDeviceTracker(coordinator, key)
            for key in coordinator.devices
            if key not in tracked
        ]
        if new:
            tracked.update(entity.device_key for entity in new)
            async_add_entities(new)

    _add_new_entities()

    entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            f"{SIGNAL_NEW_TRACKERS}_{entry.entry_id}",
            _add_new_entities,
        )
    )


class NetworkDeviceTracker(
    CoordinatorEntity[NetworkMonitorCoordinator], ScannerEntity
):
    """Presence of a single discovered host."""

    _attr_has_entity_name = False
    _attr_should_poll = False
    _attr_source_type = SourceType.ROUTER

    def __init__(
        self, coordinator: NetworkMonitorCoordinator, device_key: str
    ) -> None:
        """Track the device stored under ``device_key``."""
        super().__init__(coordinator)
        self.device_key = device_key
        slug = device_key.replace(":", "").replace(".", "_").lower()
        self._unique_id = f"{coordinator.config_entry.entry_id}_{slug}"

    @property
    def unique_id(self) -> str:
        """Stable ID.

        ScannerEntity's default unique_id is the MAC address, which is None
        for hosts whose MAC could not be resolved -- those entities would
        never reach the registry. Override it with an entry-scoped ID.
        """
        return self._unique_id

    @property
    def _record(self) -> Any:
        """Current inventory record, or None if it was forgotten."""
        return self.coordinator.devices.get(self.device_key)

    @property
    def available(self) -> bool:
        """Entity is unavailable once the device is forgotten."""
        return super().available and self._record is not None

    @property
    def name(self) -> str:
        """Human-readable name for the tracked host."""
        if (record := self._record) is None:
            return f"Network {self.device_key}"
        label = record.name or record.hostname or record.mac or record.ip
        return f"Network {label}"

    @property
    def is_connected(self) -> bool:
        """Return True while the device answers scans."""
        record = self._record
        return bool(record and record.online)

    @property
    def mac_address(self) -> str | None:
        """MAC address, when it could be resolved."""
        record = self._record
        return record.mac if record else None

    @property
    def ip_address(self) -> str | None:
        """Most recently observed IP address."""
        record = self._record
        return record.ip if record else None

    @property
    def hostname(self) -> str | None:
        """Reverse-DNS hostname, when available."""
        record = self._record
        return record.hostname if record else None

    @property
    def icon(self) -> str | None:
        """Icon inferred from the device name or hardware vendor."""
        record = self._record
        return record.device_type.icon if record else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose discovery metadata."""
        if (record := self._record) is None:
            return {}
        return {
            ATTR_MAC: record.mac,
            ATTR_IP: record.ip,
            ATTR_HOSTNAME: record.hostname,
            ATTR_VENDOR: record.vendor,
            ATTR_FIRST_SEEN: record.first_seen,
            ATTR_LAST_SEEN: record.last_seen,
            "whitelisted": self.coordinator.is_whitelisted(record),
        }
