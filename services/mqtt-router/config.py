import os
import logging

# === CONFIGURACIÓN DE MQTT ===
MQTT_CFG = {
    "host": os.getenv("MQTT_HOST", "mosquitto"),
    "port": int(os.getenv("MQTT_PORT", 1883)),
    "user": os.getenv("MQTT_USER", "admin"),
    "password": os.getenv("MQTT_PASS", "admin1234"),
    "topics": [
        ("announce/#", 0),
        ("update/#", 0),
        ("alert/#", 0),
        ("get/#", 0),
        ("set/#", 0),
        ("response/#", 0),
        ("system/get/#", 0),
        ("system/select/#", 0),
        ("system/set/#", 0),
    ]
}

# === CONFIGURACIÓN BBDD ===
DB_CFG = {
    "host": os.getenv("DB_HOST", "mariadb-service"),
    "user": os.getenv("DB_USER", "admin"),
    "password": os.getenv("DB_PASS", "admin1234"),
    "database": os.getenv("DB_NAME", "devices_db"),
}

# === LOGGING ===
logging.basicConfig(
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    level=logging.INFO
)
logger = logging.getLogger("mqtt-router")

# === ZONA HORARIA LOCAL (opcional) ===
os.environ["TZ"] = "Europe/Madrid"
