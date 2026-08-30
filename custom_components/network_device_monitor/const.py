"""Constants for the Network monitor integration.

Network monitor - By Marco Cavallo.
"""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "network_device_monitor"
INTEGRATION_NAME: Final = "Network monitor"
VERSION: Final = "1.0"
AUTHOR: Final = "Marco Cavallo"

PLATFORMS_KEY: Final = "platforms"

# --------------------------------------------------------------------------
# Configuration keys
# --------------------------------------------------------------------------
CONF_SUBNET: Final = "subnet"
CONF_SCAN_INTERVAL: Final = "scan_interval"
CONF_WHITELIST: Final = "whitelist"
CONF_EMAIL_RECIPIENT: Final = "email_recipient"
CONF_NOTIFY_SERVICES: Final = "notify_services"
CONF_SCAN_METHOD: Final = "scan_method"
CONF_NEW_DEVICE_HOLD: Final = "new_device_hold"
CONF_ENABLE_TRACKERS: Final = "enable_device_trackers"
CONF_OFFLINE_AFTER: Final = "offline_after"
CONF_ENABLE_PANEL: Final = "enable_panel"
CONF_PORT_SCAN: Final = "port_scan"
CONF_PORT_LIST: Final = "port_list"
CONF_PORT_SCAN_INTERVAL: Final = "port_scan_interval"
CONF_DEFAULT_OPEN_PORT: Final = "default_open_port"
CONF_WATCH_TITLE: Final = "watch_title"
CONF_WATCH_MESSAGE: Final = "watch_message"
CONF_RECOVERY_TITLE: Final = "recovery_title"
CONF_RECOVERY_MESSAGE: Final = "recovery_message"
CONF_NOTIFY_TITLE: Final = "notify_title"
CONF_NOTIFY_MESSAGE: Final = "notify_message"

CONF_MAC: Final = "mac"
CONF_IP: Final = "ip"
CONF_NAME: Final = "name"

# --------------------------------------------------------------------------
# Defaults
# --------------------------------------------------------------------------
DEFAULT_SCAN_INTERVAL: Final = 300          # seconds
DEFAULT_NEW_DEVICE_HOLD: Final = 300        # seconds the binary_sensor stays on
DEFAULT_ENABLE_TRACKERS: Final = False

# A host must be missed this many scans in a row before it counts as offline.
# One dropped ARP reply is normal; two in a row usually is not.
DEFAULT_OFFLINE_AFTER: Final = 2
DEFAULT_ENABLE_PANEL: Final = True

# Port probing is off by default: it is a second, heavier pass over the LAN.
DEFAULT_PORT_SCAN: Final = False
DEFAULT_PORT_LIST: Final = "21,22,23,53,80,139,443,445,554,1883,3389,5900,8080,8123,8443"
DEFAULT_PORT_SCAN_INTERVAL: Final = 1800   # seconds
DEFAULT_OPEN_PORT: Final = 0               # 0 = pick automatically

# Well-known ports, for the labels shown in the panel.
PORT_NAMES: Final[dict[int, str]] = {
    21: "FTP", 22: "SSH", 23: "Telnet", 25: "SMTP", 53: "DNS", 80: "HTTP",
    110: "POP3", 139: "SMB", 143: "IMAP", 443: "HTTPS", 445: "SMB",
    554: "RTSP", 587: "SMTP", 631: "IPP", 993: "IMAPS", 1883: "MQTT",
    3306: "MySQL", 3389: "RDP", 5432: "PostgreSQL", 5900: "VNC",
    6053: "ESPHome", 8080: "HTTP-alt", 8083: "HTTP-alt", 8123: "Home Assistant",
    8443: "HTTPS-alt", 8883: "MQTT-TLS", 9000: "HTTP-alt", 32400: "Plex",
}

# Ports that mean "there is a web UI here", best first.
WEB_PORTS: Final[tuple[tuple[int, str], ...]] = (
    (443, "https"), (8443, "https"), (80, "http"), (8123, "http"),
    (8080, "http"), (8083, "http"), (9000, "http"),
)

# Even with nothing to report, flush the store this often so `last_seen`
# survives a restart.
STORE_CHECKPOINT_SECONDS: Final = 900

# After a restart the network stack, the switches and the devices themselves
# need a moment. Availability alerts stay muted for this long so a slow boot
# does not look like an outage.
STARTUP_GRACE_SECONDS: Final = 180

# --------------------------------------------------------------------------
# Notification templates
#
# Three kinds of message, in every language we ship. Every placeholder carries
# a `default(...)` so the options-flow live preview renders sample values
# instead of failing on variables that only exist when a message is sent.
#
#   anomalous : an unauthorised device appeared
#   down      : a watched device became unreachable
#   up        : a watched device came back online
#
# Variables: name, mac, ip, hostname, vendor, subnet, seen, count, emoji and,
# for down/up, down_for.
# --------------------------------------------------------------------------
_MAC = "{{ mac | default('AA:BB:CC:DD:EE:FF') }}"
_IP = "{{ ip | default('192.168.1.42') }}"
_SEEN = "{{ seen | default('01/01/2026 12:00:00') }}"
_SUBNET = "{{ subnet | default('192.168.1.0/24') }}"
_DOWN_FOR = "{{ down_for | default('5 min') }}"
_EMOJI = "{{ emoji | default('\U0001F537') }}"


def _body(intro: str, pairs: tuple[tuple[str, str], ...]) -> str:
    """Lay out a message as an intro plus an aligned label/value block."""
    width = max(len(label) for label, _ in pairs) + 1
    rows = "\n".join(f"{label:<{width}} {value}" for label, value in pairs)
    return f"{intro}\n\n{rows}"


def _lang(
    unknown: str,
    titles: tuple[str, str, str],
    intros: tuple[str, str, str],
    labels: tuple[str, str, str, str, str],
    down_label: str,
) -> dict[str, tuple[str, str]]:
    """Build the three template pairs for one language.

    titles/intros are (anomalous, down, up); labels are the five field names
    (name, MAC, IP, vendor, last seen); down_label names the outage duration.
    """
    name = "{{ name | default('%s') }}" % unknown
    vendor = "{{ vendor | default('%s') }}" % unknown
    ln, lm, li, lv, ls = labels
    return {
        "anomalous": (
            f"{_EMOJI} {titles[0]}: {name}",
            _body(
                intros[0].replace("__SUBNET__", _SUBNET),
                ((ln, name), (lm, _MAC), (li, _IP), (lv, vendor), (ls, _SEEN)),
            ),
        ),
        "down": (
            f"\U0001F534 {titles[1]}: {name}",
            _body(
                intros[1].replace("__NAME__", name),
                ((ln, name), (lm, _MAC), (li, _IP), (ls, _SEEN),
                 (down_label, _DOWN_FOR)),
            ),
        ),
        "up": (
            f"\U0001F7E2 {titles[2]}: {name}",
            _body(
                intros[2].replace("__NAME__", name),
                ((ln, name), (lm, _MAC), (li, _IP), (ls, _SEEN)),
            ),
        ),
    }


TEMPLATES: Final[dict[str, dict[str, tuple[str, str]]]] = {}
DEFAULT_LANGUAGE: Final = "en"


def templates_for(language: str | None, kind: str) -> tuple[str, str]:
    """Return the (title, message) pair for a language and message kind.

    Accepts regional codes ("it-IT", "pt_BR") and falls back to English for
    any language we do not ship, which is what Home Assistant does too.
    """
    code = (language or DEFAULT_LANGUAGE).replace("_", "-").split("-")[0].lower()
    table = TEMPLATES.get(code) or TEMPLATES[DEFAULT_LANGUAGE]
    return table[kind]



# Language table. Home Assistant falls back to English for anything not
# listed here, which matches how its own translations behave.

TEMPLATES["en"] = _lang(
    'unknown',
    ('Unauthorised device', 'Critical device unreachable', 'Critical device back online'),
    ('An unknown device appeared on __SUBNET__.', 'Watched device __NAME__ is not responding.', 'Watched device __NAME__ is reachable again.'),
    ('Name:', 'MAC:', 'IP:', 'Vendor:', 'Last seen:'),
    'Down for:',
)
TEMPLATES["it"] = _lang(
    'sconosciuto',
    ('Dispositivo non autorizzato', 'Dispositivo critico non raggiungibile', 'Dispositivo critico tornato online'),
    ('Rilevato un dispositivo sconosciuto sulla rete __SUBNET__.', 'Il dispositivo sorvegliato __NAME__ non risponde.', 'Il dispositivo sorvegliato __NAME__ è di nuovo raggiungibile.'),
    ('Nome:', 'MAC:', 'IP:', 'Produttore:', 'Visto:'),
    'Assente da:',
)
TEMPLATES["de"] = _lang(
    'unbekannt',
    ('Nicht autorisiertes Gerät', 'Kritisches Gerät nicht erreichbar', 'Kritisches Gerät wieder online'),
    ('Ein unbekanntes Gerät wurde im Netzwerk __SUBNET__ erkannt.', 'Das überwachte Gerät __NAME__ antwortet nicht.', 'Das überwachte Gerät __NAME__ ist wieder erreichbar.'),
    ('Name:', 'MAC:', 'IP:', 'Hersteller:', 'Gesehen:'),
    'Ausfall seit:',
)
TEMPLATES["fr"] = _lang(
    'inconnu',
    ('Appareil non autorisé', 'Appareil critique injoignable', 'Appareil critique de nouveau en ligne'),
    ('Un appareil inconnu est apparu sur le réseau __SUBNET__.', "L'appareil surveillé __NAME__ ne répond plus.", "L'appareil surveillé __NAME__ est de nouveau joignable."),
    ('Nom :', 'MAC :', 'IP :', 'Fabricant :', 'Vu le :'),
    'Absent depuis :',
)
TEMPLATES["es"] = _lang(
    'desconocido',
    ('Dispositivo no autorizado', 'Dispositivo crítico inaccesible', 'Dispositivo crítico de nuevo en línea'),
    ('Se ha detectado un dispositivo desconocido en la red __SUBNET__.', 'El dispositivo vigilado __NAME__ no responde.', 'El dispositivo vigilado __NAME__ vuelve a ser accesible.'),
    ('Nombre:', 'MAC:', 'IP:', 'Fabricante:', 'Visto:'),
    'Ausente desde:',
)
TEMPLATES["pt"] = _lang(
    'desconhecido',
    ('Dispositivo não autorizado', 'Dispositivo crítico inacessível', 'Dispositivo crítico de novo online'),
    ('Foi detetado um dispositivo desconhecido na rede __SUBNET__.', 'O dispositivo vigiado __NAME__ não responde.', 'O dispositivo vigiado __NAME__ está novamente acessível.'),
    ('Nome:', 'MAC:', 'IP:', 'Fabricante:', 'Visto:'),
    'Ausente há:',
)
TEMPLATES["nl"] = _lang(
    'onbekend',
    ('Niet-geautoriseerd apparaat', 'Kritiek apparaat onbereikbaar', 'Kritiek apparaat weer online'),
    ('Er is een onbekend apparaat gevonden op netwerk __SUBNET__.', 'Bewaakt apparaat __NAME__ reageert niet.', 'Bewaakt apparaat __NAME__ is weer bereikbaar.'),
    ('Naam:', 'MAC:', 'IP:', 'Fabrikant:', 'Gezien:'),
    'Offline sinds:',
)
TEMPLATES["pl"] = _lang(
    'nieznane',
    ('Nieautoryzowane urządzenie', 'Krytyczne urządzenie niedostępne', 'Krytyczne urządzenie znów online'),
    ('W sieci __SUBNET__ pojawiło się nieznane urządzenie.', 'Monitorowane urządzenie __NAME__ nie odpowiada.', 'Monitorowane urządzenie __NAME__ jest znów dostępne.'),
    ('Nazwa:', 'MAC:', 'IP:', 'Producent:', 'Widziano:'),
    'Niedostępne od:',
)
TEMPLATES["sv"] = _lang(
    'okänd',
    ('Obehörig enhet', 'Kritisk enhet onåbar', 'Kritisk enhet online igen'),
    ('En okänd enhet dök upp på nätverket __SUBNET__.', 'Den övervakade enheten __NAME__ svarar inte.', 'Den övervakade enheten __NAME__ är nåbar igen.'),
    ('Namn:', 'MAC:', 'IP:', 'Tillverkare:', 'Sedd:'),
    'Nere sedan:',
)
TEMPLATES["da"] = _lang(
    'ukendt',
    ('Uautoriseret enhed', 'Kritisk enhed utilgængelig', 'Kritisk enhed online igen'),
    ('En ukendt enhed dukkede op på netværket __SUBNET__.', 'Den overvågede enhed __NAME__ svarer ikke.', 'Den overvågede enhed __NAME__ er tilgængelig igen.'),
    ('Navn:', 'MAC:', 'IP:', 'Producent:', 'Set:'),
    'Nede siden:',
)
TEMPLATES["nb"] = _lang(
    'ukjent',
    ('Uautorisert enhet', 'Kritisk enhet utilgjengelig', 'Kritisk enhet online igjen'),
    ('En ukjent enhet dukket opp på nettverket __SUBNET__.', 'Den overvåkede enheten __NAME__ svarer ikke.', 'Den overvåkede enheten __NAME__ er tilgjengelig igjen.'),
    ('Navn:', 'MAC:', 'IP:', 'Produsent:', 'Sett:'),
    'Nede siden:',
)
TEMPLATES["fi"] = _lang(
    'tuntematon',
    ('Valtuuttamaton laite', 'Kriittinen laite ei vastaa', 'Kriittinen laite taas verkossa'),
    ('Verkossa __SUBNET__ havaittiin tuntematon laite.', 'Valvottu laite __NAME__ ei vastaa.', 'Valvottu laite __NAME__ on taas tavoitettavissa.'),
    ('Nimi:', 'MAC:', 'IP:', 'Valmistaja:', 'Nähty:'),
    'Poissa:',
)
TEMPLATES["cs"] = _lang(
    'neznámé',
    ('Neautorizované zařízení', 'Kritické zařízení nedostupné', 'Kritické zařízení opět online'),
    ('V síti __SUBNET__ se objevilo neznámé zařízení.', 'Sledované zařízení __NAME__ neodpovídá.', 'Sledované zařízení __NAME__ je opět dostupné.'),
    ('Název:', 'MAC:', 'IP:', 'Výrobce:', 'Viděno:'),
    'Nedostupné:',
)
TEMPLATES["sk"] = _lang(
    'neznáme',
    ('Neautorizované zariadenie', 'Kritické zariadenie nedostupné', 'Kritické zariadenie opäť online'),
    ('V sieti __SUBNET__ sa objavilo neznáme zariadenie.', 'Sledované zariadenie __NAME__ neodpovedá.', 'Sledované zariadenie __NAME__ je opäť dostupné.'),
    ('Názov:', 'MAC:', 'IP:', 'Výrobca:', 'Videné:'),
    'Nedostupné:',
)
TEMPLATES["hu"] = _lang(
    'ismeretlen',
    ('Nem engedélyezett eszköz', 'Kritikus eszköz nem érhető el', 'Kritikus eszköz újra online'),
    ('Ismeretlen eszköz jelent meg a __SUBNET__ hálózaton.', 'A figyelt eszköz __NAME__ nem válaszol.', 'A figyelt eszköz __NAME__ újra elérhető.'),
    ('Név:', 'MAC:', 'IP:', 'Gyártó:', 'Látva:'),
    'Kiesve:',
)
TEMPLATES["ro"] = _lang(
    'necunoscut',
    ('Dispozitiv neautorizat', 'Dispozitiv critic inaccesibil', 'Dispozitiv critic din nou online'),
    ('Un dispozitiv necunoscut a apărut în rețeaua __SUBNET__.', 'Dispozitivul monitorizat __NAME__ nu răspunde.', 'Dispozitivul monitorizat __NAME__ este din nou accesibil.'),
    ('Nume:', 'MAC:', 'IP:', 'Producător:', 'Văzut:'),
    'Absent de:',
)
TEMPLATES["el"] = _lang(
    'άγνωστο',
    ('Μη εξουσιοδοτημένη συσκευή', 'Κρίσιμη συσκευή μη προσβάσιμη', 'Κρίσιμη συσκευή ξανά σε σύνδεση'),
    ('Εντοπίστηκε άγνωστη συσκευή στο δίκτυο __SUBNET__.', 'Η παρακολουθούμενη συσκευή __NAME__ δεν απαντά.', 'Η παρακολουθούμενη συσκευή __NAME__ είναι ξανά προσβάσιμη.'),
    ('Όνομα:', 'MAC:', 'IP:', 'Κατασκευαστής:', 'Εθεάθη:'),
    'Εκτός από:',
)
TEMPLATES["ru"] = _lang(
    'неизвестно',
    ('Неавторизованное устройство', 'Критическое устройство недоступно', 'Критическое устройство снова в сети'),
    ('В сети __SUBNET__ обнаружено неизвестное устройство.', 'Наблюдаемое устройство __NAME__ не отвечает.', 'Наблюдаемое устройство __NAME__ снова доступно.'),
    ('Имя:', 'MAC:', 'IP:', 'Производитель:', 'Замечено:'),
    'Недоступно:',
)
TEMPLATES["uk"] = _lang(
    'невідомо',
    ('Неавторизований пристрій', 'Критичний пристрій недоступний', 'Критичний пристрій знову онлайн'),
    ('У мережі __SUBNET__ виявлено невідомий пристрій.', 'Контрольований пристрій __NAME__ не відповідає.', 'Контрольований пристрій __NAME__ знову доступний.'),
    ('Назва:', 'MAC:', 'IP:', 'Виробник:', 'Побачено:'),
    'Недоступний:',
)
TEMPLATES["tr"] = _lang(
    'bilinmiyor',
    ('Yetkisiz cihaz', 'Kritik cihaza ulaşılamıyor', 'Kritik cihaz yeniden çevrimiçi'),
    ('__SUBNET__ ağında bilinmeyen bir cihaz tespit edildi.', 'İzlenen cihaz __NAME__ yanıt vermiyor.', 'İzlenen cihaz __NAME__ yeniden erişilebilir.'),
    ('Ad:', 'MAC:', 'IP:', 'Üretici:', 'Görülme:'),
    'Kapalı süre:',
)
TEMPLATES["ca"] = _lang(
    'desconegut',
    ('Dispositiu no autoritzat', 'Dispositiu crític inaccessible', 'Dispositiu crític de nou en línia'),
    ("S'ha detectat un dispositiu desconegut a la xarxa __SUBNET__.", 'El dispositiu vigilat __NAME__ no respon.', 'El dispositiu vigilat __NAME__ torna a ser accessible.'),
    ('Nom:', 'MAC:', 'IP:', 'Fabricant:', 'Vist:'),
    'Absent des de:',
)
TEMPLATES["sl"] = _lang(
    'neznano',
    ('Nepooblaščena naprava', 'Kritična naprava ni dosegljiva', 'Kritična naprava spet na voljo'),
    ('V omrežju __SUBNET__ je bila zaznana neznana naprava.', 'Nadzorovana naprava __NAME__ se ne odziva.', 'Nadzorovana naprava __NAME__ je spet dosegljiva.'),
    ('Ime:', 'MAC:', 'IP:', 'Proizvajalec:', 'Videno:'),
    'Nedosegljiva:',
)
TEMPLATES["hr"] = _lang(
    'nepoznato',
    ('Neovlašteni uređaj', 'Kritični uređaj nedostupan', 'Kritični uređaj ponovno online'),
    ('U mreži __SUBNET__ otkriven je nepoznati uređaj.', 'Nadzirani uređaj __NAME__ ne odgovara.', 'Nadzirani uređaj __NAME__ ponovno je dostupan.'),
    ('Naziv:', 'MAC:', 'IP:', 'Proizvođač:', 'Viđeno:'),
    'Nedostupan:',
)
TEMPLATES["bg"] = _lang(
    'неизвестно',
    ('Неоторизирано устройство', 'Критично устройство недостъпно', 'Критично устройство отново онлайн'),
    ('В мрежата __SUBNET__ е открито неизвестно устройство.', 'Наблюдаваното устройство __NAME__ не отговаря.', 'Наблюдаваното устройство __NAME__ е отново достъпно.'),
    ('Име:', 'MAC:', 'IP:', 'Производител:', 'Видяно:'),
    'Недостъпно от:',
)


def default_templates(language: str | None) -> tuple[str, str]:
    """Templates for the unauthorised-device notification."""
    return templates_for(language, "anomalous")


def watch_templates(language: str | None) -> tuple[str, str]:
    """Templates for a watched device becoming unreachable."""
    return templates_for(language, "down")


def recovery_templates(language: str | None) -> tuple[str, str]:
    """Templates for a watched device coming back online."""
    return templates_for(language, "up")

MIN_SCAN_INTERVAL: Final = 30

SCAN_METHOD_AUTO: Final = "auto"
SCAN_METHOD_NMAP: Final = "nmap"
SCAN_METHOD_ARP: Final = "arp"
SCAN_METHODS: Final = (SCAN_METHOD_AUTO, SCAN_METHOD_NMAP, SCAN_METHOD_ARP)
DEFAULT_SCAN_METHOD: Final = SCAN_METHOD_AUTO

# --------------------------------------------------------------------------
# Persistent storage -> /config/.storage/network_device_monitor_data.json
# --------------------------------------------------------------------------
STORAGE_KEY: Final = "network_device_monitor_data.json"
STORAGE_VERSION: Final = 1

# --------------------------------------------------------------------------
# Events and dispatcher signals
# --------------------------------------------------------------------------
EVENT_NEW_DEVICE: Final = f"{DOMAIN}_new_device"
EVENT_ANOMALOUS_DEVICE: Final = f"{DOMAIN}_anomalous_device"
EVENT_WATCHED_DOWN: Final = f"{DOMAIN}_watched_device_down"
EVENT_WATCHED_UP: Final = f"{DOMAIN}_watched_device_up"
SIGNAL_NEW_TRACKERS: Final = f"{DOMAIN}_new_trackers"

# --------------------------------------------------------------------------
# Services
# --------------------------------------------------------------------------
SERVICE_SCAN_NOW: Final = "scan_now"
SERVICE_ADD_TO_WHITELIST: Final = "add_to_whitelist"
SERVICE_REMOVE_FROM_WHITELIST: Final = "remove_from_whitelist"
SERVICE_FORGET_DEVICE: Final = "forget_device"
SERVICE_ADD_TO_WATCHLIST: Final = "add_to_watchlist"
SERVICE_REMOVE_FROM_WATCHLIST: Final = "remove_from_watchlist"

# --------------------------------------------------------------------------
# Attributes
# --------------------------------------------------------------------------
ATTR_MAC: Final = "mac"
ATTR_IP: Final = "ip"
ATTR_HOSTNAME: Final = "hostname"
ATTR_VENDOR: Final = "vendor"
ATTR_HA_DEVICE: Final = "ha_device"
ATTR_ICON: Final = "icon"
ATTR_EMOJI: Final = "emoji"
ATTR_NOTE: Final = "note"
ATTR_PORTS: Final = "ports"
ATTR_NAME: Final = "name"
ATTR_FIRST_SEEN: Final = "first_seen"
ATTR_LAST_SEEN: Final = "last_seen"
ATTR_ONLINE: Final = "online"
ATTR_ANOMALOUS_DEVICES: Final = "anomalous_devices"
ATTR_KNOWN_DEVICES: Final = "known_devices"
ATTR_WHITELIST: Final = "whitelist"
ATTR_WATCHED: Final = "watched"
ATTR_WATCHED_OFFLINE: Final = "watched_offline"
ATTR_SCAN_METHOD: Final = "scan_method"
ATTR_LAST_SCAN: Final = "last_scan"
ATTR_SUBNET: Final = "subnet"


# --------------------------------------------------------------------------
# Sidebar panel
# --------------------------------------------------------------------------
PANEL_URL_PATH: Final = "network-monitor"
PANEL_TITLE: Final = INTEGRATION_NAME
PANEL_ICON: Final = "mdi:radar"
PANEL_COMPONENT: Final = "network-monitor-panel"
PANEL_MODULE_URL: Final = f"/{DOMAIN}/panel.js"

# --------------------------------------------------------------------------
# WebSocket commands used by the panel
# --------------------------------------------------------------------------
WS_DEVICES: Final = f"{DOMAIN}/devices"
WS_UPDATE_DEVICE: Final = f"{DOMAIN}/update_device"
WS_SET_WHITELIST: Final = f"{DOMAIN}/set_whitelist"
WS_SCAN: Final = f"{DOMAIN}/scan"
WS_SCAN_PORTS: Final = f"{DOMAIN}/scan_ports"
WS_SET_WATCH: Final = f"{DOMAIN}/set_watch"
