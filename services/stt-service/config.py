# ============================
# stt-service/config.py
# ============================
import os

# Archivo de audio y WebSocket del motor STT
RECORDING_PATH = "/asterisk/recordings/grabacion.wav16"
VOSK_WS = os.getenv("VOSK_WS", "ws://vosk-service:2700")

# MQTT
MQTT_BROKER = os.getenv("MQTT_HOST", "mosquitto")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_USER = os.getenv("MQTT_USER", "admin")
MQTT_PASS = os.getenv("MQTT_PASS", "admin1234")

# Compatibilidad: si solo existe MQTT_TOPIC, se usa para publicar
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "system/transcription/text")

# Recomendado: separar publicación y suscripción (opcional)
MQTT_PUB_TOPIC = os.getenv("MQTT_PUB_TOPIC", MQTT_TOPIC)
MQTT_SUB_TOPIC = os.getenv("MQTT_SUB_TOPIC", "")  # vacío => no suscribirse

# Control de detección de archivo
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", 2))
STABLE_THRESHOLD = int(os.getenv("STABLE_THRESHOLD", 5))