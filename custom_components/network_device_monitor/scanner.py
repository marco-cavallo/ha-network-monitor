"""Network scanning back-ends for the Network monitor integration.

Two strategies are implemented, both fully asynchronous:

* ``nmap``  -- shells out to ``nmap -sn -oX -`` and parses the XML report.
               Gives MAC address + vendor when Home Assistant runs as root
               (the default on Home Assistant OS / Supervised).
* ``arp``   -- pure-Python fallback: a bounded concurrent ping sweep to
               populate the kernel neighbour cache, then a read of the ARP
               table (``/proc/net/arp`` or ``ip neigh``).

Neither strategy needs a Python dependency, so the integration installs
with an empty ``requirements`` list.

Network monitor - By Marco Cavallo.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import shutil
import socket
from dataclasses import dataclass
from typing import Any
from ipaddress import IPv4Network, ip_network
from xml.etree import ElementTree

_LOGGER = logging.getLogger(__name__)

ARP_TABLE_PATH = "/proc/net/arp"
PING_CONCURRENCY = 48
PING_TIMEOUT = 2
NMAP_TIMEOUT = 600
RDNS_CONCURRENCY = 16
RDNS_TIMEOUT = 2
PORT_CONCURRENCY = 120
PORT_TIMEOUT = 1.5
HTTP_TIMEOUT = 3.0
HTTP_CONCURRENCY = 16
HTTP_MAX_BYTES = 65536          # a device page is small; never slurp a stream

_TITLE_RE = re.compile(rb"<title[^>]*>(.*?)</title>", re.I | re.S)
# "Shelly1PM", "Shelly Switch": the model, not this device's name. Devices
# whose owner set a real name return that instead, so these are noise.
_SHELLY_MODEL_RE = re.compile(
    r"^shelly\s*(plus\s*|pro\s*)?"
    r"(1pm|1l|1|2\.5|2pm|2|plug-?s?|dimmer2?|dimmer|rgbw2?|em3|em|i3|uni|"
    r"bulb|duo|vintage|motion2?|switch|gas|flood|door|ht|button|mini|addon)?"
    r"\s*(gen\s*\d)?$",
    re.I,
)
# "404 - Page not found", "500 Internal Server Error"
_HTTP_STATUS_RE = re.compile(r"^[1-5]\d\d\b")

_APPNAME_RE = re.compile(
    rb'<meta[^>]+name=["\']application-name["\'][^>]+content=["\']([^"\']+)',
    re.I,
)
MAX_SWEEP_HOSTS = 4096

_MAC_RE = re.compile(r"^[0-9a-f]{2}(:[0-9a-f]{2}){5}$", re.IGNORECASE)
_INCOMPLETE_MACS = {"00:00:00:00:00:00", "ff:ff:ff:ff:ff:ff"}


class ScannerError(Exception):
    """Base error raised by the network scanner."""


class ScannerNotAvailable(ScannerError):
    """Raised when no usable scan back-end is available."""


def normalize_mac(mac: str | None) -> str | None:
    """Return an upper-case colon-separated MAC, or None if unusable."""
    if not mac:
        return None
    cleaned = mac.strip().replace("-", ":").replace(".", ":").lower()
    if not _MAC_RE.match(cleaned) or cleaned in _INCOMPLETE_MACS:
        return None
    return cleaned.upper()


@dataclass(slots=True)
class DiscoveredDevice:
    """A single host observed on the network during one scan."""

    ip: str
    mac: str | None = None
    hostname: str | None = None
    vendor: str | None = None

    @property
    def key(self) -> str:
        """Stable identity for this host.

        The MAC address is preferred because DHCP leases move; hosts whose
        MAC could not be resolved fall back to an IP-scoped key.
        """
        return self.mac if self.mac else f"ip:{self.ip}"


class NetworkScanner:
    """Discover hosts on a subnet without blocking the event loop."""

    def __init__(self, subnet: str, method: str = "auto") -> None:
        """Initialise the scanner for ``subnet`` using ``method``."""
        self._subnet = subnet
        self._method = method
        self._last_used_method: str | None = None

    @property
    def last_used_method(self) -> str | None:
        """Back-end used by the most recent successful scan."""
        return self._last_used_method

    @staticmethod
    def validate_subnet(subnet: str) -> str:
        """Validate and normalise a CIDR subnet, raising ValueError if bad."""
        network = ip_network(subnet, strict=False)
        if not isinstance(network, IPv4Network):
            raise ValueError("only IPv4 subnets are supported")
        if network.num_addresses > MAX_SWEEP_HOSTS:
            raise ValueError("subnet is too large (max /20)")
        return str(network)

    async def async_scan(self) -> list[DiscoveredDevice]:
        """Run one scan and return every host found."""
        if self._method == "nmap":
            devices = await self._async_scan_nmap()
            self._last_used_method = "nmap"
        elif self._method == "arp":
            devices = await self._async_scan_arp()
            self._last_used_method = "arp"
        else:
            devices, self._last_used_method = await self._async_scan_auto()

        # nmap without root, and the ARP sweep, may leave gaps. Fill them in
        # from the neighbour cache and reverse DNS before returning.
        await self._async_enrich(devices)
        return devices

    # ------------------------------------------------------------------
    # Back-end selection
    # ------------------------------------------------------------------
    async def _async_scan_auto(self) -> tuple[list[DiscoveredDevice], str]:
        """Prefer nmap, fall back to the pure-Python sweep."""
        if await self.async_nmap_available():
            try:
                return await self._async_scan_nmap(), "nmap"
            except ScannerError as err:
                _LOGGER.warning(
                    "nmap scan failed (%s), falling back to ARP sweep", err
                )
        return await self._async_scan_arp(), "arp"

    @staticmethod
    async def async_nmap_available() -> bool:
        """Return True when the nmap binary is on PATH."""
        return await asyncio.get_running_loop().run_in_executor(
            None, lambda: shutil.which("nmap") is not None
        )

    # ------------------------------------------------------------------
    # nmap back-end
    # ------------------------------------------------------------------
    async def _async_scan_nmap(self) -> list[DiscoveredDevice]:
        """Run ``nmap -sn`` and parse its XML output."""
        binary = await asyncio.get_running_loop().run_in_executor(
            None, lambda: shutil.which("nmap")
        )
        if binary is None:
            raise ScannerNotAvailable(
                "nmap is not installed; install it or use the 'arp' scan method"
            )

        args = [
            binary,
            "-sn",              # ping scan: host discovery only, no port scan
            "-n",               # skip nmap's own DNS, we resolve selectively
            "-oX", "-",         # XML report on stdout
            "--host-timeout", "30s",
            self._subnet,
        ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except OSError as err:
            raise ScannerNotAvailable(f"cannot execute nmap: {err}") from err

        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=NMAP_TIMEOUT
            )
        except TimeoutError as err:
            proc.kill()
            await proc.wait()
            raise ScannerError("nmap timed out") from err

        if proc.returncode != 0:
            message = stderr.decode(errors="replace").strip() or "unknown error"
            raise ScannerError(f"nmap exited with {proc.returncode}: {message}")

        return self._parse_nmap_xml(stdout)

    @staticmethod
    def _parse_nmap_xml(payload: bytes) -> list[DiscoveredDevice]:
        """Turn an nmap XML report into DiscoveredDevice objects."""
        try:
            root = ElementTree.fromstring(payload)
        except ElementTree.ParseError as err:
            raise ScannerError(f"could not parse nmap output: {err}") from err

        devices: list[DiscoveredDevice] = []
        for host in root.iter("host"):
            status = host.find("status")
            if status is not None and status.get("state") != "up":
                continue

            ip: str | None = None
            mac: str | None = None
            vendor: str | None = None
            for address in host.iter("address"):
                addr_type = address.get("addrtype")
                if addr_type == "ipv4":
                    ip = address.get("addr")
                elif addr_type == "mac":
                    mac = normalize_mac(address.get("addr"))
                    vendor = address.get("vendor")

            if ip is None:
                continue

            hostname: str | None = None
            hostnames = host.find("hostnames")
            if hostnames is not None:
                entry = hostnames.find("hostname")
                if entry is not None:
                    hostname = entry.get("name")

            devices.append(
                DiscoveredDevice(ip=ip, mac=mac, hostname=hostname, vendor=vendor)
            )
        return devices

    # ------------------------------------------------------------------
    # Pure-Python fallback back-end
    # ------------------------------------------------------------------
    async def _async_scan_arp(self) -> list[DiscoveredDevice]:
        """Ping every address in the subnet, then read the neighbour cache."""
        network = ip_network(self._subnet, strict=False)
        hosts = [str(host) for host in network.hosts()]
        if not hosts:
            return []

        semaphore = asyncio.Semaphore(PING_CONCURRENCY)

        async def ping(target: str) -> str | None:
            async with semaphore:
                return target if await _async_ping(target) else None

        results = await asyncio.gather(*(ping(host) for host in hosts))
        alive = [host for host in results if host]

        arp = await _async_read_neighbours()
        return [
            DiscoveredDevice(ip=ip, mac=arp.get(ip))
            for ip in alive
        ]

    # ------------------------------------------------------------------
    # Enrichment
    # ------------------------------------------------------------------
    async def _async_enrich(self, devices: list[DiscoveredDevice]) -> None:
        """Fill in missing MAC addresses and hostnames in place."""
        if any(device.mac is None for device in devices):
            arp = await _async_read_neighbours()
            for device in devices:
                if device.mac is None:
                    device.mac = arp.get(device.ip)

        missing = [device for device in devices if not device.hostname]
        if not missing:
            return

        semaphore = asyncio.Semaphore(RDNS_CONCURRENCY)

        async def resolve(device: DiscoveredDevice) -> None:
            async with semaphore:
                device.hostname = await _async_reverse_dns(device.ip)

        await asyncio.gather(*(resolve(device) for device in missing))


# ----------------------------------------------------------------------
# Module-level helpers
# ----------------------------------------------------------------------
async def _async_ping(target: str) -> bool:
    """Return True when ``target`` answers a single ICMP echo request."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "ping", "-c", "1", "-W", str(PING_TIMEOUT), "-q", target,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
    except OSError:
        return False

    try:
        return await asyncio.wait_for(proc.wait(), timeout=PING_TIMEOUT + 1) == 0
    except TimeoutError:
        proc.kill()
        await proc.wait()
        return False


async def _async_read_neighbours() -> dict[str, str]:
    """Return an ``{ip: MAC}`` map from the kernel neighbour cache."""
    table = await asyncio.get_running_loop().run_in_executor(
        None, _read_proc_arp
    )
    if table:
        return table
    return await _async_read_ip_neigh()


def _read_proc_arp() -> dict[str, str]:
    """Parse /proc/net/arp. Runs in an executor: it does blocking file I/O."""
    result: dict[str, str] = {}
    try:
        with open(ARP_TABLE_PATH, encoding="utf-8") as handle:
            next(handle, None)  # skip the header row
            for line in handle:
                fields = line.split()
                if len(fields) < 4:
                    continue
                if (mac := normalize_mac(fields[3])) is not None:
                    result[fields[0]] = mac
    except OSError as err:
        _LOGGER.debug("Cannot read %s: %s", ARP_TABLE_PATH, err)
    return result


async def _async_read_ip_neigh() -> dict[str, str]:
    """Fallback neighbour lookup via ``ip neigh show``."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "ip", "neigh", "show",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
    except (OSError, TimeoutError) as err:
        _LOGGER.debug("Cannot read neighbour table: %s", err)
        return {}

    result: dict[str, str] = {}
    for line in stdout.decode(errors="replace").splitlines():
        fields = line.split()
        if len(fields) >= 5 and fields[3] == "lladdr":
            if (mac := normalize_mac(fields[4])) is not None:
                result[fields[0]] = mac
    return result


async def _async_reverse_dns(ip: str) -> str | None:
    """Best-effort reverse DNS lookup, never raising."""
    loop = asyncio.get_running_loop()
    try:
        hostname, _, _ = await asyncio.wait_for(
            loop.run_in_executor(None, socket.gethostbyaddr, ip),
            timeout=RDNS_TIMEOUT,
        )
    except (OSError, TimeoutError):
        return None
    # Without a PTR record gethostbyaddr echoes the address back; that is
    # not a hostname, so treat it as "unknown".
    return None if hostname == ip else hostname


# ----------------------------------------------------------------------
# Port probing
# ----------------------------------------------------------------------
async def async_probe_port(ip: str, port: int, timeout: float = PORT_TIMEOUT) -> bool:
    """Return True when a TCP connect to ``ip:port`` succeeds.

    A plain connect is enough to tell an open port from a closed one and,
    unlike an nmap port scan, needs no external binary and no root.
    """
    writer = None
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(ip, port), timeout=timeout
        )
        return True
    except (OSError, TimeoutError):
        return False
    finally:
        if writer is not None:
            writer.close()
            try:
                await writer.wait_closed()
            except (OSError, TimeoutError):
                pass


async def async_scan_ports(
    targets: list[str], ports: list[int], timeout: float = PORT_TIMEOUT
) -> dict[str, list[int]]:
    """Probe ``ports`` on every address in ``targets``.

    Returns {ip: [open ports, sorted]}. Concurrency is bounded so a large
    subnet cannot exhaust the event loop's socket budget.
    """
    semaphore = asyncio.Semaphore(PORT_CONCURRENCY)
    results: dict[str, list[int]] = {ip: [] for ip in targets}

    async def probe(ip: str, port: int) -> None:
        async with semaphore:
            if await async_probe_port(ip, port, timeout):
                results[ip].append(port)

    await asyncio.gather(
        *(probe(ip, port) for ip in targets for port in ports)
    )
    for ip in results:
        results[ip].sort()
    return results


# ----------------------------------------------------------------------
# HTTP identification
# ----------------------------------------------------------------------
@dataclass(slots=True)
class WebIdentity:
    """What a device's web interface says about itself."""

    name: str | None = None      # the device's own configured name
    title: str | None = None     # <title> of the landing page
    model: str | None = None
    server: str | None = None    # HTTP Server header

    @property
    def best(self) -> str | None:
        """The most trustworthy label found.

        A vendor-set name beats a page title; the model is a last resort
        and only helps when nothing else identifies the device.
        """
        return self.name or self.title


def _clean(value: str | None) -> str | None:
    """Tidy a label pulled off a device, or drop it if it says nothing."""
    if not value:
        return None
    text = " ".join(str(value).split())
    # "iliadbox OS :: Identificazione" -> "iliadbox OS": the part after the
    # separator names the page, not the device.
    # Only page/section separators: a dash often joins useful halves
    # ("NAS - Synology DiskStation"), so splitting on it loses information.
    for sep in (" :: ", " | ", "::"):
        if sep in text:
            head = text.split(sep)[0].strip()
            if len(head) >= 3:
                text = head
                break
    text = text[:64].strip(" -_|:")
    if len(text) < 3:
        return None

    lowered = text.lower()
    # Titles that describe the page or the firmware family rather than
    # this particular device: they would overwrite a better name with noise.
    GENERIC = {
        "index", "home", "login", "welcome", "router", "device", "web",
        "main", "index.html", "untitled", "web server", "administration",
        "401 unauthorized", "403 forbidden", "404 not found", "not found",
        "shelly web admin", "shelly", "esp8266 web server", "esp32",
        "web management", "management console", "dashboard", "sign in",
        "authentication", "identificazione", "accedi", "configuration",
        "setup", "admin", "administrator", "webserver", "http server",
        "document moved", "redirecting", "loading", "error",
    }
    if lowered in GENERIC:
        return None
    if any(lowered.startswith(g + " ") for g in ("welcome to", "login to")):
        return None
    if _SHELLY_MODEL_RE.match(text) or _HTTP_STATUS_RE.match(text):
        return None
    return text


async def async_identify_http(
    session: Any, ip: str, base: str
) -> WebIdentity:
    """Ask one device who it is over HTTP.

    Tries the vendor JSON endpoints that answer with a configured name
    first, then falls back to the page <title>. Every step is best-effort:
    a device that refuses to answer simply yields nothing.
    """
    ident = WebIdentity()

    # 1. Vendor JSON endpoints that answer with a configured name.
    #    Each entry is (path, section, name key, model key); "section" is the
    #    sub-object the fields live in, or None when they are at top level.
    for path, section, name_key, model_key in (
        # Shelly gen2 / gen3 / gen4
        ("/rpc/Shelly.GetDeviceInfo", None, "name", "model"),
        # SMLIGHT SLZB Zigbee coordinators: their page title is filled in by
        # JavaScript, so the HTML gives nothing and only this endpoint does.
        ("/ha_info", "Info", "hostname", "model"),
        # Shelly gen1
        ("/settings", None, "name", None),
        # Assorted ESP firmwares
        ("/api/v1/info", None, "name", "model"),
    ):
        try:
            async with session.get(f"{base}{path}", allow_redirects=False) as resp:
                if resp.status != 200:
                    continue
                raw = await resp.content.read(HTTP_MAX_BYTES)
                data = json.loads(raw)
        except Exception:  # noqa: BLE001 - any failure just means "try the next"
            continue

        if not isinstance(data, dict):
            continue
        payload = data.get(section) if section else data
        if not isinstance(payload, dict):
            continue

        ident.name = _clean(payload.get(name_key))
        if model_key:
            ident.model = _clean(payload.get(model_key)) or ident.model

        if path == "/settings" and not ident.name:
            # Shelly gen1 keeps the hostname one level down.
            device = payload.get("device") or {}
            ident.name = _clean(device.get("hostname"))
            ident.model = _clean(device.get("type")) or ident.model

        if ident.name:
            return ident

    # 2. Fall back to the landing page.
    try:
        async with session.get(base, allow_redirects=True) as resp:
            ident.server = _clean(resp.headers.get("Server"))
            body = await resp.content.read(HTTP_MAX_BYTES)
    except Exception:  # noqa: BLE001
        return ident

    if (m := _TITLE_RE.search(body)) is not None:
        ident.title = _clean(m.group(1).decode("utf-8", "replace"))
    if not ident.title and (m := _APPNAME_RE.search(body)) is not None:
        ident.title = _clean(m.group(1).decode("utf-8", "replace"))
    return ident


clean_label = _clean


async def async_identify_web(targets: dict[str, str]) -> dict[str, WebIdentity]:
    """Identify every {ip: base_url} target, with bounded concurrency."""
    import aiohttp  # noqa: PLC0415 - only needed when this path runs

    results: dict[str, WebIdentity] = {}
    semaphore = asyncio.Semaphore(HTTP_CONCURRENCY)
    timeout = aiohttp.ClientTimeout(total=HTTP_TIMEOUT)
    # LAN devices almost always use self-signed certificates.
    connector = aiohttp.TCPConnector(ssl=False, limit=HTTP_CONCURRENCY)

    async with aiohttp.ClientSession(
        timeout=timeout, connector=connector
    ) as session:

        async def one(ip: str, base: str) -> None:
            async with semaphore:
                try:
                    results[ip] = await async_identify_http(session, ip, base)
                except Exception:  # noqa: BLE001
                    results[ip] = WebIdentity()

        await asyncio.gather(*(one(ip, base) for ip, base in targets.items()))
    return results
