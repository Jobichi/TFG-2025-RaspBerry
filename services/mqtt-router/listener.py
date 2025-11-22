import json
import sys
import paho.mqtt.client as mqtt
from config import logger, MQTT_CFG, DB_CFG
from database.db_manager import DBManager
from handlers import (
    announce,
    update,
    alert,
    response,
    esp_set,
    db_select,
    notify
)
# Mapeo tópico_base → handler
HANDLERS = {
    # Estos objetos ya son las funciones handle aliased en handlers/__init__.py
    "announce": announce,
    "update": update,
    "alert": alert,
    "response": response,
    "get": None,         # se procesan solo desde ESP32 → no hay handler aquí
    "set": None,         # idem
    "system/get": db_select,     # el handler select
    "system/set": esp_set,       # el handler set
    "system/select": db_select,
    "system/notify": notify,
}

# Conexión global a la BBDD para todos los handlers
db = DBManager()


def resolve_handler(topic: str):
    """
    Devuelve qué handler corresponde a un topic.
    """
    parts = topic.split("/")

    # Casos normales: "announce/#", "update/#", "alert/#", "response/#"
    if parts[0] in HANDLERS:
        return HANDLERS[parts[0]]

    # Casos system:
    if len(parts) >= 2:
        key = f"{parts[0]}/{parts[1]}"  # "system/get", "system/set", etc.
        return HANDLERS.get(key)

    return None


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        logger.info("[MQTT] Conectado correctamente al broker")

        for (topic, qos) in MQTT_CFG["topics"]:
            client.subscribe((topic, qos))
            logger.info(f"[MQTT] Suscrito a {topic}")

    else:
        logger.error(f"[MQTT] Error al conectar: código {rc}")


def on_message(client, userdata, msg):
    topic = msg.topic
    raw_payload = msg.payload.decode("utf-8")

    # Parse de JSON seguro
    try:
        payload = json.loads(raw_payload) if raw_payload.strip() else {}
    except json.JSONDecodeError:
        logger.warning(f"[MQTT] Payload no JSON en {topic}: {raw_payload}")
        payload = {}

    logger.info(f"[MQTT] Mensaje recibido: {topic} -> {payload}")

    handler = resolve_handler(topic)

    if handler is None:
        logger.debug(f"[MQTT] No hay handler para {topic}")
        return

    try:
        handler(db, client, topic, payload)
    except Exception as e:
        logger.error(f"[MQTT] Error ejecutando handler de {topic}: {e}")


def start_router():
    client = mqtt.Client()

    # Autenticación
    client.username_pw_set(MQTT_CFG["user"], MQTT_CFG["password"])

    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(MQTT_CFG["host"], MQTT_CFG["port"], keepalive=60)

    logger.info("[MQTT] Router iniciado. Esperando mensajes...")

    client.loop_forever()


if __name__ == "__main__":
    # Healthcheck simple: comprobar conexión a la DB
    if "--healthcheck" in sys.argv:
        test_db = DBManager()
        if test_db.conn and test_db.conn.is_connected():
            logger.info("[HEALTHCHECK] OK")
            sys.exit(0)
        logger.error("[HEALTHCHECK] Conexión a DB fallida")
        sys.exit(1)

    start_router()
