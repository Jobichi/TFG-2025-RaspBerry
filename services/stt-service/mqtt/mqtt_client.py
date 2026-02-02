# ============================
# stt-service/mqtt/mqtt_client.py
# ============================
import json
import time
import paho.mqtt.client as mqtt
from config import MQTT_BROKER, MQTT_PORT, MQTT_USER, MQTT_PASS, MQTT_PUB_TOPIC, MQTT_SUB_TOPIC


def on_connect(client, userdata, flags, reason_code, properties):
    """Callback cuando el cliente se conecta al broker."""
    print(f"[MQTT] Conectado al broker ({MQTT_BROKER}:{MQTT_PORT}), code={reason_code}")

    if MQTT_SUB_TOPIC:
        client.subscribe(MQTT_SUB_TOPIC)
        print(f"[MQTT] Suscrito a: {MQTT_SUB_TOPIC}")


def on_message(client, userdata, msg):
    """Callback para mensajes entrantes (si MQTT_SUB_TOPIC está configurado)."""
    try:
        payload = msg.payload.decode()
        data = json.loads(payload)
        text = data.get("text", "")
        ts = data.get("timestamp", None)
        print(f"[MQTT] Mensaje recibido en '{msg.topic}': '{text}' (ts={ts})")
    except Exception as e:
        print(f"[MQTT][ERROR] {e}")


def publish_transcription(client: mqtt.Client, text: str, topic: str = MQTT_PUB_TOPIC, qos: int = 1) -> bool:
    """Publica una transcripción en MQTT."""
    if not text or not text.strip():
        print("[MQTT] Transcripción vacía, no se publica.")
        return False

    payload = json.dumps(
        {
            "text": text.strip(),
            "timestamp": int(time.time())
        },
        ensure_ascii=False
    )

    result = client.publish(topic, payload, qos=qos, retain=False)

    if result.rc == mqtt.MQTT_ERR_SUCCESS:
        print(f"[MQTT] Publicado en {topic}: {text.strip()}")
        return True

    print(f"[MQTT][ERROR] Error publicando en {topic}: rc={result.rc}")
    return False


def create_mqtt_client():
    """Inicializa y configura el cliente MQTT."""
    client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
    client.username_pw_set(MQTT_USER, MQTT_PASS)

    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
    client.loop_start()

    print("[MQTT] Cliente inicializado.")
    if not MQTT_SUB_TOPIC:
        print("[MQTT] MQTT_SUB_TOPIC vacío: no se realizará suscripción.")
    print(f"[MQTT] Publicación configurada en: {MQTT_PUB_TOPIC}")

    return client