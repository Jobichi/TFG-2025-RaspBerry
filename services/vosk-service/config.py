# config.py
# Configuración del microservicio Vosk mediante variables de entorno.

import os

# Ruta al modelo montado desde el host
MODEL_PATH = os.getenv("VOSK_MODEL_PATH", "/model")

# Frecuencia de muestreo para KaldiRecognizer
SAMPLE_RATE = float(os.getenv("VOSK_SAMPLE_RATE", "16000"))

# Configuración MQTT
MQTT_HOST = os.getenv("MQTT_HOST", "mosquitto")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USER = os.getenv("MQTT_USER", "user")
MQTT_PASS = os.getenv("MQTT_PASS", "pass")
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "vosk/transcriptions")

# WebSocket server
WS_HOST = os.getenv("WS_HOST", "0.0.0.0")
WS_PORT = int(os.getenv("WS_PORT", "2700"))
