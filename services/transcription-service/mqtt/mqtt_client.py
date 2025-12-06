# mqtt_client.py

import json
import paho.mqtt.client as mqtt
from config import MQTT_BROKER, MQTT_PORT, MQTT_USER, MQTT_PASS, MQTT_TOPIC


def on_connect(client, userdata, flags, reason_code, properties):
    """Callback cuando el cliente se conecta al broker."""
    print(f"[MQTT] Conectado al broker ({MQTT_BROKER}:{MQTT_PORT}), code={reason_code}")
    client.subscribe(MQTT_TOPIC)
    print(f"[MQTT] Suscrito a: {MQTT_TOPIC}")


def on_message(client, userdata, msg):
    """Callback para mensajes entrantes."""
    try:
        payload = msg.payload.decode()
        data = json.loads(payload)
        text = data.get("text", "")
        ts = data.get("timestamp", None)
        print(f"[MQTT] Mensaje recibido: '{text}' (ts={ts})")
    except Exception as e:
        print(f"[MQTT][ERROR] {e}")


def create_mqtt_client():
    """Inicializa y configura el cliente MQTT."""
    client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
    client.username_pw_set(MQTT_USER, MQTT_PASS)

    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
    client.loop_start()

    print("[MQTT] Cliente inicializado y escuchando.")
    return client
