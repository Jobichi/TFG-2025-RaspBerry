import os
import logging

# =========================
#  IDENTIDAD DEL SERVICIO
# =========================
SERVICE_NAME = os.getenv("SERVICE_NAME", "intent-service")

# =========================
#  MQTT
# =========================
MQTT_CFG = {
    "host": os.getenv("MQTT_HOST", "mosquitto"),
    "port": int(os.getenv("MQTT_PORT", "1883")),
    "user": os.getenv("MQTT_USER", "admin"),
    "password": os.getenv("MQTT_PASS", "admin1234"),
    "keepalive": int(os.getenv("MQTT_KEEPALIVE", "60")),
}

# Tópicos del sistema (contrato con stt-service y mqtt-router)
TOPICS = {
    # Entrada desde STT
    "transcription_in": os.getenv("MQTT_TRANS_TOPIC", "system/transcription/text"),

    # Solicitud snapshot al router (memoria inicial)
    "select_req": os.getenv("MQTT_SELECT_REQ_TOPIC", f"system/select/{SERVICE_NAME}"),

    # Respuestas del router al requester (snapshot / respuestas GET/SET)
    "response_in": os.getenv("MQTT_RESPONSE_IN_TOPIC", f"system/response/{SERVICE_NAME}/#"),

    # Salida: comandos al router (SET)
    "set_out": os.getenv("MQTT_SET_OUT_TOPIC", f"system/set/{SERVICE_NAME}"),
}

# QoS por defecto (puedes afinar si quieres)
QOS = {
    # El texto de STT puede ser QoS 1 si no quieres perder frases
    "transcription_in": int(os.getenv("MQTT_QOS_TRANSCRIPTION_IN", "1")),

    # Snapshot y respuestas: recomendado QoS 1
    "response_in": int(os.getenv("MQTT_QOS_RESPONSE_IN", "1")),
    "select_req": int(os.getenv("MQTT_QOS_SELECT_REQ", "1")),

    # Comandos SET: recomendado QoS 1
    "set_out": int(os.getenv("MQTT_QOS_SET_OUT", "1")),
}

# =========================
#  SNAPSHOT / MEMORIA
# =========================
# Tiempo máximo recomendado para esperar a que llegue el snapshot antes de procesar STT
SNAPSHOT_TIMEOUT_S = int(os.getenv("SNAPSHOT_TIMEOUT_S", "10"))

# Si quieres exigir snapshot antes de procesar transcripciones
REQUIRE_SNAPSHOT = os.getenv("REQUIRE_SNAPSHOT", "true").strip().lower() in ("1", "true", "yes", "on")

# =========================
#  LOGGING
# =========================
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

logging.basicConfig(
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    level=getattr(logging, LOG_LEVEL, logging.INFO),
)

logger = logging.getLogger(SERVICE_NAME)

# Zona horaria (opcional, útil para logs coherentes)
os.environ["TZ"] = os.getenv("TZ", "Europe/Madrid")
