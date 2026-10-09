<p align="center"><img src="icon.png" width="128" alt="Gilet chauffant"></p>

# Gilet chauffant (HEATING VEST) pour Home Assistant

Intégration Home Assistant **locale** pour les gilets chauffants Bluetooth pilotés par l'appli Android
**HEATING VEST** (Kangerjian Intelligent Technology, `com.geecare.hotvest`).

> ⚠️ Projet expérimental, non affilié au fabricant. Utilisation à vos risques : c'est un appareil chauffant.

## Fonctionnement

Le gilet n'accepte aucune connexion Bluetooth : il **diffuse son état** dans ses annonces BLE (nom `ves…`)
et **écoute les annonces** du téléphone. L'intégration fait exactement pareil :

- **lecture de l'état** : en passif, via le Bluetooth de Home Assistant (adaptateur local ou proxy ESPHome) ;
- **envoi des commandes** : via un **ESP32 dédié sous ESPHome** qui diffuse l'annonce
  (firmware fourni dans [`esphome/gilet-chauffant-ble.yaml`](esphome/gilet-chauffant-ble.yaml)).

Chaque commande est répétée (jusqu'à 3 fois) tant que le gilet ne confirme pas le changement.

> ℹ️ Un repli « adaptateur Bluetooth local » (BlueZ) existe si le champ *Action ESPHome* est laissé vide,
> mais il est **déconseillé** : sur certains serveurs il a déstabilisé la pile Bluetooth de Home Assistant.

## Entités

| Entité | Rôle |
|---|---|
| `switch` Chauffage | Marche / arrêt |
| `select` Niveau | 1 (40 °C), 2 (50 °C), 3 (60 °C) |
| `number` Minuterie | Arrêt automatique (0–120 min) |
| `sensor` Température de consigne | Consigne actuelle |
| `sensor` Temps restant | Temps restant de la minuterie |

## Installation

### 1. L'ESP32 émetteur (ESPHome)
1. Dans le tableau de bord ESPHome, créez un appareil à partir de
   [`esphome/gilet-chauffant-ble.yaml`](esphome/gilet-chauffant-ble.yaml)
   (secrets nécessaires : voir [`esphome/secrets.example.yaml`](esphome/secrets.example.yaml)).
2. Flashez un ESP32 (classique, type `esp32dev`) et placez-le près de l'endroit où vous portez le gilet.
3. Ajoutez l'appareil ESPHome dans Home Assistant (il est découvert automatiquement). L'action
   `esphome.gilet_chauffant_ble_send_adv` doit alors apparaître dans *Outils de développement → Actions*.

> Utilisez un ESP32 **dédié** : un proxy Bluetooth qui scanne en continu émet mal en parallèle.

### 2. L'intégration
**HACS (dépôt personnalisé)** : HACS → ⋮ → *Dépôts personnalisés* → `https://github.com/Dujonkev/heating-vest`,
catégorie **Intégration**, installez **Gilet chauffant (HEATING VEST)** puis redémarrez Home Assistant.

**Manuelle** : copiez `custom_components/heating_vest` dans `config/custom_components/` puis redémarrez.

Ensuite : *Paramètres → Appareils et services → Ajouter une intégration → Gilet chauffant*
(le gilet allumé est aussi découvert automatiquement). Le champ **Action ESPHome** vaut par défaut
`esphome.gilet_chauffant_ble_send_adv` ; il est modifiable plus tard dans les options de l'intégration.

## Protocole (rétro-ingénierie)

Commande diffusée par le téléphone (annonce brute `04 09 'TSE' 11 07` + 16 octets) : UUID 128 bits dont les octets (little-endian) sont :

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
