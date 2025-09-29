import paho.mqtt.client as mqtt

BROKER = "mosquitto"  # nombre del servicio en docker-compose
USER = "admin"
PASS = "admin1234"

def on_connect(client, userdata, flags, rc, properties=None):
    print("Conectado al broker con código:", rc, flush=True)
    client.subscribe("+/ping")

def on_message(client, userdata, msg):
    device_id = msg.topic.split("/")[0]
    pong_topic = f"{device_id}/pong"
    print(f"Ping de {device_id} → respondiendo en {pong_topic}", flush=True)
    client.publish(pong_topic, "pong")

# Usar la API moderna para evitar warnings
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.username_pw_set(USER, PASS)
client.on_connect = on_connect
client.on_message = on_message

client.connect(BROKER, 1883, 60)
client.loop_forever()
