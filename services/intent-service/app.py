import os
import json
import time
import paho.mqtt.client as mqtt

BROKER = os.getenv("MQTT_BROKER", "mosquitto")
PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_USER = os.getenv("MQTT_USER")
MQTT_PASS = os.getenv("MQTT_PASS")

actuators_db = {}

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"[INTENT] ✅ Conectado a MQTT ({BROKER}:{PORT})")
        client.subscribe("transcriptions/text")
        client.subscribe("system/response/intent/actuators/#")
        print("[INTENT] 📡 Suscrito a transcriptions/text y respuestas de actuadores.")
    else:
        print(f"[INTENT] ❌ Error al conectar con MQTT (rc={rc})")

def on_message(client, userdata, msg):
    global actuators_db
    topic = msg.topic
    payload = msg.payload.decode()

    # --- Respuestas del listener con actuadores ---
    if topic.startswith("system/response/intent/actuators/"):
        try:
            data = json.loads(payload)
            actuators_db[data["id"]] = data
        except Exception as e:
            print(f"[INTENT] ⚠️ Error parseando actuador: {e}")
        return

    # --- Nueva transcripción ---
    if topic == "transcriptions/text":
        text = payload.lower().strip()
        print(f"[INTENT] 🗣️ Texto recibido: {text}")

        # Solicita al listener la lista de actuadores
        actuators_db.clear()
        client.publish("system/request/intent/actuators", "")
        print("[INTENT] 📥 Solicitando actuadores al listener...")
        time.sleep(2.5)

        # Analiza intención
        action = "ON" if any(k in text for k in ["encender", "prender", "activar"]) else None
        if not action and any(k in text for k in ["apagar", "desactivar"]):
            action = "OFF"
        elif "subir" in text:
            action = "UP"
        elif "bajar" in text:
            action = "DOWN"
        elif any(k in text for k in ["parar", "detener", "stop"]):
            action = "STOP"

        if not action:
            print("[INTENT] ⚠️ No se detectó acción válida.")
            return

        # Busca coincidencias de actuador
        for a in actuators_db.values():
            name = a["name"].lower()
            if any(word in text for word in name.split()):
                topic_set = f"set/{a['device_name']}/actuator/{a['id']}"
                print(f"[INTENT] 🚀 Ejecutando: {topic_set} -> {action}")
                client.publish(topic_set, action)
                return

        print("[INTENT] ⚠️ No se encontró coincidencia con ningún actuador.")

client = mqtt.Client()
if MQTT_USER and MQTT_PASS:
    client.username_pw_set(MQTT_USER, MQTT_PASS)

client.on_connect = on_connect
client.on_message = on_message
client.connect(BROKER, PORT, 60)
client.loop_forever()
