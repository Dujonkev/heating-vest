"""Constantes du gilet chauffant."""

DOMAIN = "heating_vest"
CONF_ADDRESS = "address"

# Niveau -> température de consigne envoyée (relevée dans l'appli officielle)
LEVEL_TEMPS = {"1": 40, "2": 50, "3": 60}

CMD_TEMP = 0x01
CMD_TIMER = 0x02
CMD_POWER = 0x03
POWER_ON = 0x97
POWER_OFF = 0x99

STATUS_PREFIX = bytes.fromhex("eebc35000a")
UNAVAILABLE_AFTER = 90  # secondes sans annonce
# Vérification de la disponibilité et rafraîchissement des capteurs de diagnostic
DIAGNOSTIC_INTERVAL = 30  # secondes

# Envoi d'une commande : nombre d'émissions, puis attente de la confirmation
COMMAND_ATTEMPTS = 3
CONFIRM_CHECKS = 6
CONFIRM_INTERVAL = 0.5  # secondes

# Émission des commandes : action ESPHome (recommandé) ou BlueZ local si vide
CONF_SERVICE = "esphome_action"
DEFAULT_SERVICE = "esphome.gilet_chauffant_ble_send_adv"
ADV_DURATION_MS = 1500
