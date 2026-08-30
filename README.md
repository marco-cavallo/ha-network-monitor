# Network monitor

**English** · [Italiano](README.it.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · [Español](README.es.md)

*Home Assistant integration that watches your local network.*

*By Marco Cavallo*

---

## What it is

A custom integration for Home Assistant that scans your local network on a schedule, recognises the devices Home Assistant already knows, warns you when a device that is not on your trusted list appears, and keeps an eye on the ones you cannot afford to lose: router, DNS server, Zigbee coordinators, NVR.

It needs no Python dependencies and no cloud service. Everything runs on your own machine.

## What it does

**Network scanning**  
Sweeps the subnet with `nmap`, falling back to a ping and ARP sweep when nmap is unavailable. A device is only marked offline after several missed scans in a row, so one lost packet never raises a false alarm.

**Unauthorised device alerts**  
Any device that is not on the trusted list and answers a scan is flagged, raises an event and triggers a notification the first time it appears.

**Availability monitoring**  
A separate list of critical devices. When one stops answering you get an alert saying how long it has been down, and another when it comes back. Restarting Home Assistant produces no false alerts, and a device that died while Home Assistant was off is still reported.

**Device identification**  
Names come from the Home Assistant device registry, from the device's own web interface, and from the hardware vendor behind the MAC address.

**Open port detection**  
Optional pass that probes ports over TCP and labels the well-known ones. Web ports produce a direct link to the device's interface.

**Sidebar panel**  
A full page with every device: search, filters, inline renaming, free-text notes, and one-click trust or monitoring.

**Notifications**  
Push, email or any notify target, with editable templates in 24 languages.

---

## Entities

| Entity | Meaning |
|---|---|
| `sensor.network_anomalous_devices` | Online devices that are not whitelisted. Full detail in the `anomalous_devices` attribute. |
| `sensor.network_online_devices` | Devices currently answering. |
| `sensor.network_watched_offline` | Monitored devices that are unreachable. |
| `binary_sensor.network_new_device_detected` | On for 5 minutes (configurable) after a first-time detection. |
| `device_tracker.network_*` | *Optional, off by default.* One tracker per device. |

## Services

`scan_now` · `add_to_whitelist` · `remove_from_whitelist` · `forget_device` ·
`add_to_watchlist` · `remove_from_watchlist`

## Events

`network_device_monitor_new_device` · `network_device_monitor_anomalous_device` ·
`network_device_monitor_watched_device_down` ·
`network_device_monitor_watched_device_up`

---

## Installation

### HACS (custom repository)

1. HACS → three-dot menu → **Custom repositories**
2. Repository: `https://github.com/marco-cavallo/ha-network-monitor`, type **Integration**
3. Search for **Network monitor**, download it
4. Restart Home Assistant
5. **Settings → Devices & Services → Add Integration → Network monitor**

### Manual

Copy `custom_components/network_device_monitor/` into your `/config/custom_components/`,
restart Home Assistant, then add the integration from the UI.

---

## Scanning back-ends

Three modes, selectable in the options:

* **`nmap`** — runs `nmap -sn -n -oX -` and parses the XML report. Gives MAC
  addresses and vendor names, but only reports MACs when Home Assistant runs as
  root (the default on Home Assistant OS and Supervised).
* **`arp`** — pure Python: a bounded concurrent ping sweep followed by a read of
  the kernel neighbour cache. No external binary beyond `ping`.
* **`auto`** (default) — uses nmap when present, silently falls back to `arp`.

There is deliberately **no `python-nmap` dependency**: it wraps the binary in a
blocking subprocess call, which would stall the Home Assistant event loop for the
whole scan. This integration calls nmap through `asyncio.create_subprocess_exec`
and parses the XML with the standard library.

### Installing nmap

Optional; without it the integration falls back to `arp`.

| Platform | Command |
|---|---|
| Home Assistant OS / Supervised / Container | Already present |
| Debian / Ubuntu | `sudo apt install nmap` |
| Fedora / RHEL | `sudo dnf install nmap` |
| Arch | `sudo pacman -S nmap` |
| Alpine | `sudo apk add nmap` |
| macOS | `brew install nmap` |
| Windows | <https://nmap.org/download.html>, with `nmap.exe` on `PATH` |

> **Scan only networks you are responsible for.** A ping sweep against someone
> else's network may violate their acceptable-use policy.

---

## Configuration

Everything is editable in the UI after setup. YAML is also supported and is
imported into a config entry on first start:

```yaml
network_device_monitor:
  subnet: "192.168.1.0/24"
  scan_interval: 300
  scan_method: auto           # auto | nmap | arp
  offline_after: 2            # missed scans before a device counts as offline
  new_device_hold: 300
  port_scan: false
  port_list: "22,80,443,3389,8123"
  enable_panel: true
  email_recipient: "you@example.com"
  notify_services:
    - notify.smtp
    - notify.mobile_app_your_phone
  whitelist:
    - mac: "AA:BB:CC:DD:EE:FF"
      name: "Router"
```

### Notification templates

Six templates, all Jinja, all editable, defaulting to the language Home Assistant
is set to: unauthorised device, watched device down, watched device recovered.

Variables: `name`, `mac`, `ip`, `hostname`, `vendor`, `subnet`, `seen`, `count`,
`emoji`, and `down_for` for the outage message.

Every placeholder ships with a `default(...)` so the live preview in the options
flow renders sample values instead of failing.

---

## Languages

Interface and notification templates in 24 languages: bg ca cs da de el en es fi
fr hr hu it nb nl pl pt ro ru sk sl sv tr uk. Home Assistant falls back to
English for anything else.

Long field descriptions are currently translated in English and Italian only.
Pull requests for other languages are welcome.

---

## Storage

The device inventory, the whitelist and the watchlist live in
`/config/.storage/network_device_monitor_data.json`. It is written only when
something actually changes, plus a checkpoint every 15 minutes, so a short scan
interval does not hammer the disk.

---

## Troubleshooting

```yaml
logger:
  default: warning
  logs:
    custom_components.network_device_monitor: debug
```

| Symptom | Cause and fix |
|---|---|
| Scan method shows `arp` although you chose `auto` | nmap is not on `PATH`. Install it, or ignore. |
| Devices with `mac: null` | nmap ran without root and the ARP table has no entry yet. |
| Nothing on a `/16` | Subnets larger than a `/20` are rejected on purpose. |
| Duplicate entries for one device | MAC randomisation. Whitelist it by IP with a DHCP reservation. |
| No email sent | `notify_services` is empty, or the service name is wrong. |

---

## License

Apache License 2.0 — see [LICENSE](LICENSE) and [NOTICE](NOTICE).

You are free to use this integration, including **commercially and inside a
company**, to modify it and to redistribute it. In exchange the License asks
three things:

- keep the copyright notice and reproduce the `NOTICE` file in any
  redistribution (section 4(d));
- state clearly which files you changed (section 4(b));
- do not use the name *Marco Cavallo* to endorse or promote your derivative
  product (section 6).

Attribution to the author and the link to the original project must not be
removed.
