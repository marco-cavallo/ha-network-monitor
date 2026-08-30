# Network monitor

[English](README.md) · **Italiano** · [Français](README.fr.md) · [Deutsch](README.de.md) · [Español](README.es.md)

*Integrazione Home Assistant che sorveglia la tua rete locale.*

*By Marco Cavallo*

---

## Cos'è

Un'integrazione per Home Assistant che scansiona la rete locale a intervalli regolari, riconosce i dispositivi già noti a Home Assistant, avvisa quando compare un dispositivo che non è nella lista degli attendibili, e tiene d'occhio quelli che non puoi permetterti di perdere: router, server DNS, coordinatori Zigbee, NVR.

Non richiede dipendenze Python né servizi cloud. Tutto gira sulla tua macchina.

## Cosa fa

**Scansione della rete**  
Analizza la subnet con `nmap`, ripiegando su ping e tabella ARP se nmap non è disponibile. Un dispositivo viene dato per offline solo dopo più scansioni mancate di fila, così un pacchetto perso non genera mai un falso allarme.

**Avvisi sui dispositivi non autorizzati**  
Ogni dispositivo che non è nella lista degli attendibili e risponde a una scansione viene segnalato, genera un evento e fa partire una notifica la prima volta che compare.

**Monitoraggio della disponibilità**  
Una lista separata di dispositivi critici. Quando uno smette di rispondere ricevi un avviso che indica da quanto tempo è assente, e un secondo avviso quando torna. Il riavvio di Home Assistant non genera falsi allarmi, e un dispositivo guasto mentre Home Assistant era spento viene comunque segnalato.

**Identificazione dei dispositivi**  
I nomi arrivano dal registro dispositivi di Home Assistant, dall'interfaccia web del dispositivo stesso e dal produttore ricavato dall'indirizzo MAC.

**Rilevamento delle porte aperte**  
Passata opzionale che prova le porte via TCP e riconosce quelle note. Le porte web generano un collegamento diretto all'interfaccia del dispositivo.

**Pannello laterale**  
Una pagina completa con tutti i dispositivi: ricerca, filtri, rinomina, note libere e un clic per rendere attendibile o mettere sotto monitoraggio.

**Notifiche**  
Push, email o qualsiasi servizio notify, con template modificabili in 24 lingue.

---

## Entità

| | |
|---|---|
| `sensor.network_anomalous_devices` | Dispositivi online non presenti in whitelist |
| `sensor.network_online_devices` | Dispositivi che rispondono |
| `sensor.network_watched_offline` | Dispositivi monitorati non raggiungibili |
| `binary_sensor.network_new_device_detected` | Acceso dopo un nuovo rilevamento |

---

## Installazione

### Tramite HACS (consigliato)

1. Apri **HACS** in Home Assistant
2. Menu a tre puntini in alto a destra → **Repository personalizzati**
3. Repository: `https://github.com/marco-cavallo/ha-network-monitor` — Tipo: **Integration**
4. **Aggiungi**, poi cerca **Network monitor** e scaricala
5. Riavvia Home Assistant
6. **Impostazioni → Dispositivi e servizi → Aggiungi integrazione → Network monitor**

### Manuale

1. Scarica l'ultima versione dalla pagina [Releases](https://github.com/marco-cavallo/ha-network-monitor/releases)
2. Copia `custom_components/network_device_monitor/` nella cartella `/config/custom_components/`
3. Riavvia Home Assistant
4. Aggiungi l'integrazione da **Impostazioni → Dispositivi e servizi**

---

## Primo avvio

Alla prima scansione nessun dispositivo è noto, quindi risultano tutti non autorizzati. Non impostare subito i servizi di notifica: esegui una scansione, apri **Configura → Aggiungi dispositivi attendibili**, seleziona tutto ciò che riconosci, e solo dopo configura le notifiche. Da quel momento sentirai parlare solo dei dispositivi davvero nuovi.

---

## Requisiti

Home Assistant **2026.1** o successivo. `nmap` è facoltativo: senza di esso l'integrazione ripiega su una scansione ping e ARP in puro Python.

> Scansiona solo reti di cui sei responsabile.

---

## Licenza

Apache License 2.0 — vedi [LICENSE](LICENSE) e [NOTICE](NOTICE).

Libera da usare, modificare e ridistribuire, **anche commercialmente e in ambito aziendale**. In cambio devi mantenere l'avviso di copyright, riprodurre il file `NOTICE`, dichiarare quali file hai modificato e non usare il nome dell'autore per promuovere il tuo prodotto derivato.

L'attribuzione a **Marco Cavallo** e il collegamento al progetto originale non possono essere rimossi.

---

Documentazione completa: [README (inglese)](README.md)
