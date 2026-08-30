# Network monitor

[English](README.md) · [Italiano](README.it.md) · [Français](README.fr.md) · **Deutsch** · [Español](README.es.md)

*Home-Assistant-Integration, die Ihr lokales Netzwerk überwacht.*

*By Marco Cavallo*

---

## Überblick

Eine Integration für Home Assistant, die das lokale Netzwerk regelmäßig scannt, bereits bekannte Home-Assistant-Geräte erkennt, bei nicht vertrauenswürdigen Geräten warnt und jene im Blick behält, auf die Sie nicht verzichten können: Router, DNS-Server, Zigbee-Koordinatoren, NVR.

Keine Python-Abhängigkeiten, kein Cloud-Dienst. Alles läuft auf Ihrem eigenen Rechner.

## Funktionen

**Netzwerk-Scan**  
Durchsucht das Subnetz mit `nmap` und weicht auf einen Ping- und ARP-Scan aus, wenn nmap fehlt. Ein Gerät gilt erst nach mehreren verpassten Scans in Folge als offline, sodass ein verlorenes Paket nie einen Fehlalarm auslöst.

**Warnungen bei nicht autorisierten Geräten**  
Jedes Gerät, das nicht auf der Vertrauensliste steht und auf einen Scan antwortet, wird markiert, löst ein Ereignis aus und beim ersten Auftreten eine Benachrichtigung.

**Verfügbarkeitsüberwachung**  
Eine separate Liste kritischer Geräte. Antwortet eines nicht mehr, erhalten Sie eine Warnung mit der Ausfalldauer und eine weitere bei der Rückkehr. Ein Neustart von Home Assistant erzeugt keine Fehlalarme.

**Geräteerkennung**  
Namen stammen aus der Home-Assistant-Geräteregistrierung, aus der Weboberfläche des Geräts selbst und vom Hersteller hinter der MAC-Adresse.

**Erkennung offener Ports**  
Optionaler Durchlauf, der Ports per TCP prüft und bekannte Dienste benennt. Web-Ports erzeugen einen direkten Link zur Oberfläche des Geräts.

**Seitenleisten-Panel**  
Eine vollständige Seite mit allen Geräten: Suche, Filter, Umbenennen, freie Notizen und ein Klick zum Vertrauen oder Überwachen.

**Benachrichtigungen**  
Push, E-Mail oder jedes Notify-Ziel, mit bearbeitbaren Vorlagen in 24 Sprachen.

---

## Entitäten

| | |
|---|---|
| `sensor.network_anomalous_devices` | Online-Geräte, die nicht vertrauenswürdig sind |
| `sensor.network_online_devices` | Geräte, die antworten |
| `sensor.network_watched_offline` | Überwachte Geräte, die nicht erreichbar sind |
| `binary_sensor.network_new_device_detected` | Aktiv nach einer Erstererkennung |

---

## Installation

### Über HACS (empfohlen)

1. Öffnen Sie **HACS** in Home Assistant
2. Drei-Punkte-Menü oben rechts → **Benutzerdefinierte Repositories**
3. Repository: `https://github.com/marco-cavallo/ha-network-monitor` — Typ: **Integration**
4. **Hinzufügen**, dann nach **Network monitor** suchen und herunterladen
5. Home Assistant neu starten
6. **Einstellungen → Geräte & Dienste → Integration hinzufügen → Network monitor**

### Manuell

1. Laden Sie die neueste Version unter [Releases](https://github.com/marco-cavallo/ha-network-monitor/releases) herunter
2. Kopieren Sie `custom_components/network_device_monitor/` nach `/config/custom_components/`
3. Home Assistant neu starten
4. Integration über **Einstellungen → Geräte & Dienste** hinzufügen

---

## Erster Start

Beim ersten Scan ist kein Gerät bekannt, alle gelten daher als nicht autorisiert. Richten Sie die Benachrichtigungsdienste noch nicht ein: führen Sie einen Scan aus, öffnen Sie **Konfigurieren → Vertrauenswürdige Geräte hinzufügen**, markieren Sie alles Bekannte, und erst danach die Benachrichtigungen.

---

## Voraussetzungen

Home Assistant **2026.1** oder neuer. `nmap` ist optional: ohne es nutzt die Integration einen reinen Python-Ping- und ARP-Scan.

> Scannen Sie nur Netzwerke, für die Sie verantwortlich sind.

---

## Lizenz

Apache License 2.0 — siehe [LICENSE](LICENSE) und [NOTICE](NOTICE).

Frei nutzbar, veränderbar und weiterverteilbar, **auch kommerziell und im Unternehmenseinsatz**. Im Gegenzug müssen Sie den Copyright-Hinweis behalten, die Datei `NOTICE` wiedergeben, geänderte Dateien kennzeichnen und den Namen des Autors nicht zur Bewerbung Ihres abgeleiteten Produkts verwenden.

Die Nennung von **Marco Cavallo** und der Link zum Originalprojekt dürfen nicht entfernt werden.

---

Vollständige Dokumentation: [README (Englisch)](README.md)
