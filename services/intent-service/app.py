import os
import json
import time
import logging
from rapidfuzz import fuzz
import paho.mqtt.client as mqtt

# === CONFIGURACIÓN ===
MQTT_HOST = os.getenv("MQTT_HOST", "mosquitto")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_USER = os.getenv("MQTT_USER", "admin")
MQTT_PASS = os.getenv("MQTT_PASS", "admin1234")

LISTEN_TOPIC = "transcription/text"
ACTUATOR_RESP_PREFIX = "system/response/intent-service/actuators/"
SYSTEM_REQ_TOPIC = "system/get/intent-service"

# === LOGGING ===
logging.basicConfig(
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    level=logging.INFO
)
logger = logging.getLogger("intent-service")

# === VARIABLES ===
actuators = {}  # {(device_name, id): {"name":..., "location":..., "state":...}}

# === CALLBACKS MQTT ===
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        logger.info("Conectado a MQTT correctamente.")
        client.subscribe(LISTEN_TOPIC)
        client.subscribe(ACTUATOR_RESP_PREFIX + "#")
        # Solicitamos los actuadores al listener
        req = {"request": "actuators"}
        client.publish(SYSTEM_REQ_TOPIC, json.dumps(req))
        logger.info("Solicitando lista de actuadores al listener...")
    else:
        logger.error(f"Error de conexión MQTT: {rc}")

def on_message(client, userdata, msg):
    topic = msg.topic
    try:
        payload = json.loads(msg.payload.decode())
    except json.JSONDecodeError:
        logger.warning(f"Payload inválido en {topic}")
        return

    # --- Transcripción entrante ---
    if topic == LISTEN_TOPIC:
        phrase = payload.get("text", "").lower()
        logger.info(f"Transcripción recibida: {phrase}")
        handle_phrase(client, phrase)

    # --- Respuesta del listener con actuadores ---
    elif topic.startswith(ACTUATOR_RESP_PREFIX):
        device = payload.get("device_name")
        id_ = payload.get("id")
        if device is not None and id_ is not None:
            actuators[(device, id_)] = payload
            logger.info(f"Actuador cargado: {device}/{id_} -> {payload['name']} ({payload['location']})")

# === FUNCIÓN PRINCIPAL DE INTERPRETACIÓN ===
def handle_phrase(client, phrase):
    if not actuators:
        logger.warning("No hay actuadores cargados todavía.")
        return

    # Determinar acción
    new_state = None
    if any(w in phrase for w in ["enciende", "activa", "prende"]):
        new_state = "ON"
    elif any(w in phrase for w in ["apaga", "desactiva"]):
        new_state = "OFF"
    elif any(w in phrase for w in ["abre", "sube"]):
        new_state = "OPEN"
    elif any(w in phrase for w in ["cierra", "baja"]):
        new_state = "CLOSE"
    elif any(w in phrase for w in ["para", "detén", "stop"]):
        new_state = "STOP"

    if not new_state:
        logger.warning("No se reconoció una acción válida en la frase.")
        return

    # Buscar coincidencia más cercana
    best_match = None
    best_score = 0
    for (device, id_), info in actuators.items():
        ref_text = f"{info['name']} {info['location']}".lower()
        score = fuzz.token_set_ratio(phrase, ref_text)
        if score > best_score:
            best_match = (device, id_, info)
            best_score = score

    if not best_match or best_score < 60:
        logger.warning(f"Coincidencia débil o nula ({best_score}%) para '{phrase}'")
        return

    device, id_, info = best_match
    logger.info(f"Match encontrado ({best_score}%): {info['name']} en {info['location']} -> {new_state}")

    payload = {"state": new_state}
    topic_set = f"set/{device}/actuator/{id_}"
    client.publish(topic_set, json.dumps(payload))
    logger.info(f"[MQTT] → {topic_set} -> {payload}")

# === CONFIGURACIÓN DEL CLIENTE MQTT ===
def setup_mqtt():
    client = mqtt.Client()
    client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(MQTT_HOST, MQTT_PORT, 60)
    return client

# === MAIN ===
if __name__ == "__main__":
    client = setup_mqtt()
    logger.info("Intent-service iniciado. Esperando transcripciones...")
    client.loop_forever()
