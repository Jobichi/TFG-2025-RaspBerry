# mqtt/mqtt_client.py
# Cliente MQTT simple para publicar resultados de transcripción.

import json
import time
import paho.mqtt.client as mqtt
from config import MQTT_HOST, MQTT_PORT, MQTT_USER, MQTT_PASS, MQTT_TOPIC


class MQTTClient:
    """
    Cliente MQTT para publicar textos reconocidos.
    """

    def __init__(self):
        self.client = mqtt.Client()
        self.client.username_pw_set(MQTT_USER, MQTT_PASS)

        try:
            self.client.connect(MQTT_HOST, MQTT_PORT, 60)
            self.client.loop_start()
            print(f"[MQTT] Conectado a {MQTT_HOST}:{MQTT_PORT}")
        except Exception as e:
            print(f"[MQTT] Error al conectar: {e}")
            self.client = None

    def publish(self, text):
        """
        Publica texto procesado en el topic configurado.
        """
        if not self.client:
            print("[MQTT] Cliente no disponible.")
            return

        payload = json.dumps({
            "text": text,
            "timestamp": time.time()
        })

        self.client.publish(MQTT_TOPIC, payload, qos=1)
        print(f"[MQTT] Publicado en {MQTT_TOPIC}: {text}")
