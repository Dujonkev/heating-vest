<p align="center"><img src="icon.png" width="128" alt="Gilet chauffant"></p>

# Gilet chauffant (HEATING VEST) pour Home Assistant

Intégration Home Assistant **locale** pour les gilets chauffants Bluetooth pilotés par l'appli Android
**HEATING VEST** (Kangerjian Intelligent Technology, `com.geecare.hotvest`).

> ⚠️ Projet expérimental, non affilié au fabricant. Utilisation à vos risques : c'est un appareil chauffant.

## Fonctionnement

Le gilet n'accepte aucune connexion Bluetooth : il **diffuse son état** dans ses annonces BLE (nom `ves…`)
et **écoute les annonces** du téléphone. L'intégration fait exactement pareil :

- lecture de l'état via le Bluetooth de Home Assistant (adaptateur local ou proxy ESPHome) ;
- envoi des commandes en diffusant une annonce BLE via **BlueZ** (adaptateur Bluetooth local du serveur HA, requis).

Chaque commande est répétée (jusqu'à 3 fois) tant que le gilet ne confirme pas le changement.

## Entités

| Entité | Rôle |
|---|---|
| `switch` Chauffage | Marche / arrêt |
| `select` Niveau | 1 (40 °C), 2 (50 °C), 3 (60 °C) |
| `number` Minuterie | Arrêt automatique (0–120 min) |
| `sensor` Température de consigne | Consigne actuelle |
| `sensor` Temps restant | Temps restant de la minuterie |

## Installation

### HACS (dépôt personnalisé)
1. HACS → ⋮ → *Dépôts personnalisés* → `https://github.com/Dujonkev/heating-vest`, catégorie **Intégration**.
2. Installez **Gilet chauffant (HEATING VEST)** puis redémarrez Home Assistant.
3. *Paramètres → Appareils et services → Ajouter une intégration → Gilet chauffant*
   (le gilet allumé est aussi découvert automatiquement).

### Manuelle
Copiez `custom_components/heating_vest` dans le dossier `config/custom_components/` puis redémarrez.

## Protocole (rétro-ingénierie)

Commande diffusée par le téléphone : nom `TSE` + UUID 128 bits dont les octets (little-endian) sont :

```
[MAC du gilet, 6 octets inversés][valeur u16][commande u16][séquence u16][01 00][EF BC]
```

| Commande | Valeur |
|---|---|
| `0x0001` consigne | température en °C (`0x28` = 40, `0x32` = 50, `0x3C` = 60) |
| `0x0002` minuterie | durée en secondes |
| `0x0003` alimentation | `0x97` marche, `0x99` arrêt |

État diffusé par le gilet (UUID 128 bits, octets LE) :

```
EE BC 35 00 0A .. .. .. [restant u16 s][minuterie active][marche][..][niveau][température][..]
```

## Licence

MIT
