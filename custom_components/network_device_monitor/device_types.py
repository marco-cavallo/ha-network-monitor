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
"""Classify a discovered host so it can get a meaningful icon.

Matching runs against the Home Assistant device name first (most specific),
then the hardware vendor reported by nmap, and finally falls back to a
generic network device.

Network monitor - By Marco Cavallo.
"""

from __future__ import annotations

from typing import NamedTuple


class DeviceType(NamedTuple):
    """An icon pair for one class of device."""

    emoji: str
    icon: str


GENERIC = DeviceType("🔷", "mdi:lan-connect")

# Matched against the Home Assistant device name, lower-cased.
_BY_NAME: tuple[tuple[tuple[str, ...], DeviceType], ...] = (
    (("luce", "led", "lampad", "alimentatore"), DeviceType("💡", "mdi:lightbulb")),
    (("tapparella", "tenda", "serranda"), DeviceType("🪟", "mdi:window-shutter")),
    (("presa", "plug", "prolunga"), DeviceType("🔌", "mdi:power-socket-eu")),
    (("cam", "telecamera", "camera ", "videocitofono"), DeviceType("📷", "mdi:cctv")),
    (("tv", "firetv", "appletv", "chromecast"), DeviceType("📺", "mdi:television")),
    (("echo", "alexa", "sonos", "speaker"), DeviceType("🔊", "mdi:speaker")),
    (("frigo", "lavatrice", "lavastoviglie", "asciugatrice", "forno",
      "microonde", "macchina caffe"), DeviceType("🧺", "mdi:washing-machine")),
    (("termostato", "clima", "condizionatore", "pompa di calore"),
     DeviceType("🌡️", "mdi:thermostat")),
    (("serratura", "lock", "porta"), DeviceType("🔒", "mdi:lock")),
    (("sensore", "presenza", "movimento", "meteo"), DeviceType("📊", "mdi:motion-sensor")),
    (("router", "switch", "gateway", "access point", "ap "),
     DeviceType("📡", "mdi:router-network")),
    (("stampante", "printer"), DeviceType("🖨️", "mdi:printer")),
    (("nas", "server", "raspberry", "mini"), DeviceType("🖥️", "mdi:server")),
)

# Matched against the nmap vendor string, lower-cased.
_BY_VENDOR: tuple[tuple[tuple[str, ...], DeviceType], ...] = (
    (("ezviz", "hangzhou", "hikvision", "dahua", "ring", "reolink", "axis"),
     DeviceType("📷", "mdi:cctv")),
    (("cudy", "tenda", "tp-link", "ubiquiti", "mikrotik", "netgear", "zyxel",
      "asustek", "avm", "d-link"), DeviceType("📡", "mdi:router-network")),
    (("amazon",), DeviceType("📺", "mdi:television-classic")),
    (("apple",), DeviceType("📱", "mdi:apple")),
    (("samsung", "xiaomi", "oneplus", "google", "motorola", "huawei"),
     DeviceType("📱", "mdi:cellphone")),
    (("raspberry", "intel", "micro-star", "asrock", "gigabyte", "supermicro",
      "synology", "qnap"), DeviceType("🖥️", "mdi:server")),
    (("espressif", "shelly", "tuya", "sonoff", "shenzhen bilian"),
     DeviceType("🔌", "mdi:chip")),
    (("silicon lab", "texas instruments", "nordic"),
     DeviceType("📶", "mdi:zigbee")),
    (("hp inc", "hewlett", "canon", "epson", "brother"),
     DeviceType("🖨️", "mdi:printer")),
    (("sonos", "bose", "yamaha", "denon"), DeviceType("🔊", "mdi:speaker")),
    (("lg electronics", "hisense", "philips", "sony", "tcl", "vestel"),
     DeviceType("📺", "mdi:television")),
)


def classify(ha_device: str | None, vendor: str | None) -> DeviceType:
    """Return the icon pair that best matches this host."""
    if ha_device:
        haystack = ha_device.lower()
        for needles, device_type in _BY_NAME:
            if any(needle in haystack for needle in needles):
                return device_type

    if vendor:
        haystack = vendor.lower()
        for needles, device_type in _BY_VENDOR:
            if any(needle in haystack for needle in needles):
                return device_type

    return GENERIC
