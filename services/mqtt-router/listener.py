import json
import sys
import paho.mqtt.client as mqtt
from config import logger, MQTT_CFG
from database.db_manager import DBManager
from handlers import (
    announce,
    update,
    alert,
    response,
    esp_set,
    esp_get,
    system_select,
    system_notify
)

# ============================
#  Mapeo tópico → handler
# ============================
HANDLERS = {
    # ESP32 → Router
    "announce": announce,
    "update": update,
    "alert": alert,
    "response": response,

    # Sistema → Router -> ESP32/SYSTEM
    "system/set": esp_set,
    "system/get": esp_get,
    "system/select": system_select,
    "system/notify": system_notify,
}

# Conexión global a la BBDD
db = DBManager()


def resolve_handler(topic: str):
    """
    Devuelve el handler correspondiente a un topic MQTT.
    """
    parts = topic.split("/")

    # Casos simples: announce/#, update/#, alert/#, response/#
    if parts[0] in HANDLERS:
        return HANDLERS[parts[0]]

    # Casos system/*
    if len(parts) >= 2:
        key = f"{parts[0]}/{parts[1]}"
        return HANDLERS.get(key)

    return None


def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        logger.info("[MQTT] Conectado correctamente al broker")

        for topic, qos in MQTT_CFG["topics"]:
            client.subscribe(topic, qos)
            logger.info(f"[MQTT] Suscrito a {topic} (QoS {qos})")
    else:
        logger.error(f"[MQTT] Error al conectar: código {reason_code}")



def on_message(client, userdata, msg):
    topic = msg.topic
    raw_payload = msg.payload.decode("utf-8")

    # Parse seguro del JSON
    try:
        payload = json.loads(raw_payload) if raw_payload.strip() else {}
    except json.JSONDecodeError:
        logger.warning(f"[MQTT] Payload no JSON en {topic}: {raw_payload}")
        return

    handler = resolve_handler(topic)

    if handler is None:
        logger.debug(f"[MQTT] No hay handler para {topic}")
        return

    try:
        handler(db, client, topic, payload)
    except Exception as e:
        logger.error(f"[MQTT] Error ejecutando handler de {topic}: {e}")


def start_router():
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2
    )

    client.username_pw_set(
        MQTT_CFG["user"],
        MQTT_CFG["password"]
    )

    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(
        MQTT_CFG["host"],
        MQTT_CFG["port"],
        keepalive=60
    )

    logger.info("[MQTT] Router iniciado. Esperando mensajes...")
    client.loop_forever()


if __name__ == "__main__":
    # Healthcheck para Docker
    if "--healthcheck" in sys.argv:
        test_db = DBManager()
        if test_db.conn and test_db.conn.is_connected():
            logger.info("[HEALTHCHECK] OK")
            sys.exit(0)

        logger.error("[HEALTHCHECK] Conexión a DB fallida")
        sys.exit(1)

    start_router()
