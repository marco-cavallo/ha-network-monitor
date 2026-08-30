# Network monitor

[English](README.md) · [Italiano](README.it.md) · **Français** · [Deutsch](README.de.md) · [Español](README.es.md)

*Intégration Home Assistant qui surveille votre réseau local.*

*By Marco Cavallo*

---

## Présentation

Une intégration pour Home Assistant qui analyse le réseau local à intervalles réguliers, reconnaît les appareils déjà connus de Home Assistant, vous alerte lorsqu'un appareil absent de votre liste de confiance apparaît, et surveille ceux dont vous ne pouvez pas vous passer : routeur, serveur DNS, coordinateurs Zigbee, NVR.

Aucune dépendance Python, aucun service cloud. Tout fonctionne sur votre machine.

## Fonctionnalités

**Analyse du réseau**  
Balaie le sous-réseau avec `nmap`, avec repli sur un balayage ping et ARP si nmap est absent. Un appareil n'est déclaré hors ligne qu'après plusieurs analyses manquées d'affilée, donc un paquet perdu ne déclenche jamais de fausse alerte.

**Alertes sur les appareils non autorisés**  
Tout appareil absent de la liste de confiance qui répond à une analyse est signalé, génère un événement et déclenche une notification lors de sa première apparition.

**Surveillance de disponibilité**  
Une liste distincte d'appareils critiques. Lorsqu'un appareil cesse de répondre, vous recevez une alerte indiquant depuis combien de temps, puis une autre à son retour. Le redémarrage de Home Assistant ne produit aucune fausse alerte.

**Identification des appareils**  
Les noms proviennent du registre des appareils de Home Assistant, de l'interface web de l'appareil et du fabricant déduit de l'adresse MAC.

**Détection des ports ouverts**  
Passe optionnelle qui teste les ports en TCP et identifie les services connus. Les ports web produisent un lien direct vers l'interface de l'appareil.

**Panneau latéral**  
Une page complète avec tous les appareils : recherche, filtres, renommage, notes libres, et un clic pour approuver ou surveiller.

**Notifications**  
Push, e-mail ou tout service notify, avec des modèles modifiables en 24 langues.

---

## Entités

| | |
|---|---|
| `sensor.network_anomalous_devices` | Appareils en ligne absents de la liste de confiance |
| `sensor.network_online_devices` | Appareils qui répondent |
| `sensor.network_watched_offline` | Appareils surveillés injoignables |
| `binary_sensor.network_new_device_detected` | Actif après une première détection |

---

## Installation

### Via HACS (recommandé)

1. Ouvrez **HACS** dans Home Assistant
2. Menu à trois points en haut à droite → **Dépôts personnalisés**
3. Dépôt : `https://github.com/marco-cavallo/ha-network-monitor` — Type : **Integration**
4. **Ajouter**, puis cherchez **Network monitor** et téléchargez-la
5. Redémarrez Home Assistant
6. **Paramètres → Appareils et services → Ajouter une intégration → Network monitor**

### Manuelle

1. Téléchargez la dernière version depuis [Releases](https://github.com/marco-cavallo/ha-network-monitor/releases)
2. Copiez `custom_components/network_device_monitor/` dans votre dossier `/config/custom_components/`
3. Redémarrez Home Assistant
4. Ajoutez l'intégration depuis **Paramètres → Appareils et services**

---

## Première utilisation

Lors de la première analyse, aucun appareil n'est connu : ils apparaissent donc tous comme non autorisés. Ne configurez pas encore les services de notification. Lancez une analyse, ouvrez **Configurer → Ajouter des appareils de confiance**, cochez tout ce que vous reconnaissez, et configurez les notifications seulement ensuite.

---

## Prérequis

Home Assistant **2026.1** ou plus récent. `nmap` est facultatif : sans lui, l'intégration utilise un balayage ping et ARP en Python pur.

> N'analysez que les réseaux dont vous êtes responsable.

---

## Licence

Apache License 2.0 — voir [LICENSE](LICENSE) et [NOTICE](NOTICE).

Libre d'utilisation, de modification et de redistribution, **y compris commercialement et en entreprise**. En contrepartie, vous devez conserver l'avis de droit d'auteur, reproduire le fichier `NOTICE`, indiquer les fichiers modifiés et ne pas utiliser le nom de l'auteur pour promouvoir votre produit dérivé.

L'attribution à **Marco Cavallo** et le lien vers le projet original ne doivent pas être supprimés.

---

Documentation complète : [README (anglais)](README.md)
