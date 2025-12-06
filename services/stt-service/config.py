# config.py

import os

# Archivo de audio o webshocket
RECORDING_PATH = "/asterisk/recordings/grabacion.wav16"
VOSK_WS = "ws://vosk-service:2700"

# MQTT (para escuchar confirmaciones)
MQTT_BROKER = os.getenv("MQTT_HOST", "mosquitto")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_USER = os.getenv("MQTT_USER", "admin")
MQTT_PASS = os.getenv("MQTT_PASS", "admin1234")
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "transcription/text")

# Control de detección de archivo
CHECK_INTERVAL = 2
STABLE_THRESHOLD = 5