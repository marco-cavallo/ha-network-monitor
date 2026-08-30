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
"""Binary sensor platform for the Network monitor integration.

Network monitor - By Marco Cavallo.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import AUTHOR, DOMAIN, INTEGRATION_NAME
from .coordinator import NetworkMonitorConfigEntry, NetworkMonitorCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NetworkMonitorConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Network monitor binary sensors."""
    async_add_entities([NewDeviceDetectedBinarySensor(entry.runtime_data)])


class NewDeviceDetectedBinarySensor(
    CoordinatorEntity[NetworkMonitorCoordinator], BinarySensorEntity
):
    """On for `new_device_hold` seconds after a first-time detection.

    Produces `binary_sensor.network_new_device_detected`.
    """

    _attr_has_entity_name = False
    _attr_should_poll = False
    _attr_name = "Network new device detected"
    _attr_icon = "mdi:account-alert"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator: NetworkMonitorCoordinator) -> None:
        """Initialise the binary sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_new_device"
        # Pin the entity_id; see the note in sensor.py.
        self.entity_id = "binary_sensor.network_new_device_detected"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            name=INTEGRATION_NAME,
            manufacturer=AUTHOR,
            model="Network scanner",
            entry_type=DeviceEntryType.SERVICE,
        )
        self._unsub_expiry: Callable[[], None] | None = None

    @property
    def _expires_at(self) -> datetime | None:
        """Instant at which the sensor should fall back to off."""
        if (last := self.coordinator.last_new_device_at) is None:
            return None
        return last + timedelta(seconds=self.coordinator.new_device_hold)

    @property
    def is_on(self) -> bool:
        """Return True while the hold window is still open."""
        expiry = self._expires_at
        return expiry is not None and dt_util.utcnow() < expiry

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the timing of the last detection."""
        coordinator = self.coordinator
        expiry = self._expires_at
        return {
            "last_new_device": (
                coordinator.last_new_device_at.isoformat()
                if coordinator.last_new_device_at
                else None
            ),
            "clears_at": expiry.isoformat() if expiry else None,
            "hold_seconds": coordinator.new_device_hold,
        }

    @callback
    def _handle_coordinator_update(self) -> None:
        """Refresh state and (re)arm the timer that clears the sensor."""
        self._cancel_expiry()
        if (expiry := self._expires_at) is not None and dt_util.utcnow() < expiry:
            self._unsub_expiry = async_track_point_in_utc_time(
                self.hass, self._handle_expiry, expiry
            )
        super()._handle_coordinator_update()

    @callback
    def _handle_expiry(self, _now: datetime) -> None:
        """Clear the sensor once the hold window closes."""
        self._unsub_expiry = None
        self.async_write_ha_state()

    @callback
    def _cancel_expiry(self) -> None:
        """Drop any pending expiry callback."""
        if self._unsub_expiry is not None:
            self._unsub_expiry()
            self._unsub_expiry = None

    async def async_will_remove_from_hass(self) -> None:
        """Clean up the timer when the entity goes away."""
        self._cancel_expiry()
        await super().async_will_remove_from_hass()
