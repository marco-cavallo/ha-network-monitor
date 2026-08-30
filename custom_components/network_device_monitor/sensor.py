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
"""Sensor platform for the Network monitor integration.

Network monitor - By Marco Cavallo.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_ANOMALOUS_DEVICES,
    ATTR_WATCHED_OFFLINE,
    ATTR_KNOWN_DEVICES,
    ATTR_LAST_SCAN,
    ATTR_SCAN_METHOD,
    ATTR_SUBNET,
    ATTR_WHITELIST,
    AUTHOR,
    DOMAIN,
    INTEGRATION_NAME,
)
from .coordinator import NetworkMonitorConfigEntry, NetworkMonitorCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NetworkMonitorConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Network monitor sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        [
            AnomalousDevicesSensor(coordinator),
            OnlineDevicesSensor(coordinator),
            WatchedOfflineSensor(coordinator),
        ]
    )


class NetworkMonitorSensorBase(
    CoordinatorEntity[NetworkMonitorCoordinator], SensorEntity
):
    """Shared plumbing for the Network monitor sensors."""

    _attr_has_entity_name = False
    _attr_should_poll = False

    def __init__(self, coordinator: NetworkMonitorCoordinator) -> None:
        """Attach the sensor to the integration's service device."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            name=INTEGRATION_NAME,
            manufacturer=AUTHOR,
            model="Network scanner",
            entry_type=DeviceEntryType.SERVICE,
        )


class AnomalousDevicesSensor(NetworkMonitorSensorBase):
    """Number of online devices that are not on the whitelist.

    Produces `sensor.network_anomalous_devices`.
    """

    _attr_name = "Network anomalous devices"
    _attr_icon = "mdi:shield-alert"
    _attr_native_unit_of_measurement = "devices"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: NetworkMonitorCoordinator) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_anomalous_devices"
        )
        # Pin the entity_id. Without this Home Assistant prefixes the device
        # name and we would get sensor.network_monitor_network_anomalous_...
        self.entity_id = "sensor.network_anomalous_devices"

    @property
    def native_value(self) -> int:
        """Return how many unauthorised devices are currently online."""
        return len(self.coordinator.anomalous_devices)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the full detail of every anomalous device."""
        coordinator = self.coordinator
        return {
            ATTR_ANOMALOUS_DEVICES: [
                record.as_attributes() for record in coordinator.anomalous_devices
            ],
            ATTR_KNOWN_DEVICES: len(coordinator.devices),
            ATTR_WHITELIST: [
                {"mac": rule.mac, "ip": rule.ip, "name": rule.name,
                 "source": rule.source}
                for rule in coordinator.whitelist
            ],
            ATTR_SUBNET: coordinator.subnet,
            ATTR_SCAN_METHOD: coordinator.last_used_method,
            ATTR_LAST_SCAN: (
                coordinator.last_scan_at.isoformat()
                if coordinator.last_scan_at
                else None
            ),
        }


class OnlineDevicesSensor(NetworkMonitorSensorBase):
    """Total number of devices currently answering on the network.

    Produces `sensor.network_online_devices`.
    """

    _attr_name = "Network online devices"
    _attr_icon = "mdi:lan-connect"
    _attr_native_unit_of_measurement = "devices"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: NetworkMonitorCoordinator) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_online_devices"
        self.entity_id = "sensor.network_online_devices"

    @property
    def native_value(self) -> int:
        """Return how many known devices are online right now."""
        return sum(
            1 for record in self.coordinator.devices.values() if record.online
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose every online device."""
        return {
            "online_devices": [
                record.as_attributes()
                for record in self.coordinator.devices.values()
                if record.online
            ]
        }


class WatchedOfflineSensor(NetworkMonitorSensorBase):
    """How many monitored devices are unreachable.

    Produces `sensor.network_watched_offline`.
    """

    _attr_name = "Network watched offline"
    _attr_icon = "mdi:lan-disconnect"
    _attr_native_unit_of_measurement = "devices"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: NetworkMonitorCoordinator) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_watched_offline"
        )
        self.entity_id = "sensor.network_watched_offline"

    @property
    def native_value(self) -> int:
        """Return how many watched devices are down."""
        return len(self.coordinator.watched_offline)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose which watched devices are down, and the full watchlist."""
        coordinator = self.coordinator
        return {
            ATTR_WATCHED_OFFLINE: [
                record.as_attributes() for record in coordinator.watched_offline
            ],
            "watchlist": [
                {"mac": rule.mac, "ip": rule.ip, "name": rule.name}
                for rule in coordinator.watchlist
            ],
            "watched_total": len(coordinator.watchlist),
        }
