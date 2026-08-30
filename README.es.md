# Network monitor

[English](README.md) · [Italiano](README.it.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · **Español**

*Integración de Home Assistant que vigila tu red local.*

*By Marco Cavallo*

---

## Qué es

Una integración para Home Assistant que escanea la red local a intervalos regulares, reconoce los dispositivos que Home Assistant ya conoce, avisa cuando aparece uno que no está en tu lista de confianza y vigila aquellos de los que no puedes prescindir: router, servidor DNS, coordinadores Zigbee, NVR.

Sin dependencias de Python ni servicios en la nube. Todo funciona en tu propia máquina.

## Qué hace

**Escaneo de red**  
Recorre la subred con `nmap` y recurre a un barrido de ping y ARP cuando nmap no está disponible. Un dispositivo solo se marca sin conexión tras varios escaneos fallidos seguidos, así un paquete perdido nunca provoca una falsa alarma.

**Avisos de dispositivos no autorizados**  
Cualquier dispositivo que no esté en la lista de confianza y responda a un escaneo se señala, genera un evento y lanza una notificación la primera vez que aparece.

**Supervisión de disponibilidad**  
Una lista aparte de dispositivos críticos. Cuando uno deja de responder recibes un aviso que indica cuánto lleva caído, y otro cuando vuelve. Reiniciar Home Assistant no genera falsas alarmas.

**Identificación de dispositivos**  
Los nombres provienen del registro de dispositivos de Home Assistant, de la propia interfaz web del dispositivo y del fabricante deducido de la dirección MAC.

**Detección de puertos abiertos**  
Pasada opcional que comprueba puertos por TCP e identifica los servicios conocidos. Los puertos web generan un enlace directo a la interfaz del dispositivo.

**Panel lateral**  
Una página completa con todos los dispositivos: búsqueda, filtros, renombrado, notas libres y un clic para marcar como de confianza o supervisar.

**Notificaciones**  
Push, correo o cualquier servicio notify, con plantillas editables en 24 idiomas.

---

## Entidades

| | |
|---|---|
| `sensor.network_anomalous_devices` | Dispositivos en línea que no son de confianza |
| `sensor.network_online_devices` | Dispositivos que responden |
| `sensor.network_watched_offline` | Dispositivos supervisados inaccesibles |
| `binary_sensor.network_new_device_detected` | Activo tras una primera detección |

---

## Instalación

### Mediante HACS (recomendado)

1. Abre **HACS** en Home Assistant
2. Menú de tres puntos arriba a la derecha → **Repositorios personalizados**
3. Repositorio: `https://github.com/marco-cavallo/ha-network-monitor` — Tipo: **Integration**
4. **Añadir**, luego busca **Network monitor** y descárgala
5. Reinicia Home Assistant
6. **Ajustes → Dispositivos y servicios → Añadir integración → Network monitor**

### Manual

1. Descarga la última versión desde [Releases](https://github.com/marco-cavallo/ha-network-monitor/releases)
2. Copia `custom_components/network_device_monitor/` en tu carpeta `/config/custom_components/`
3. Reinicia Home Assistant
4. Añade la integración desde **Ajustes → Dispositivos y servicios**

---

## Primer arranque

En el primer escaneo ningún dispositivo es conocido, así que todos aparecen como no autorizados. No configures todavía los servicios de notificación: ejecuta un escaneo, abre **Configurar → Añadir dispositivos de confianza**, marca todo lo que reconozcas y solo entonces configura las notificaciones.

---

## Requisitos

Home Assistant **2026.1** o posterior. `nmap` es opcional: sin él la integración recurre a un barrido de ping y ARP en Python puro.

> Escanea solo redes de las que seas responsable.

---

## Licencia

Apache License 2.0 — consulta [LICENSE](LICENSE) y [NOTICE](NOTICE).

Libre para usar, modificar y redistribuir, **incluido el uso comercial y empresarial**. A cambio debes conservar el aviso de copyright, reproducir el archivo `NOTICE`, indicar qué archivos has modificado y no usar el nombre del autor para promocionar tu producto derivado.

La atribución a **Marco Cavallo** y el enlace al proyecto original no pueden eliminarse.

---

Documentación completa: [README (inglés)](README.md)
