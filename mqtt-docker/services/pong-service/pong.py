import paho.mqtt.client as mqtt
import os

BROKER = "mosquitto"
USER = "admin"
PASS = "admin1234"

def on_connect(client, userdata, flags, rc):
    print("Conectado al broker con código: ", rc)
    client.subscribe("+/ping")

def on_message(client, userdata, msg):
    topic = msg.topic
    device_id = topic.split("/")[0]
    pong_topic = f"{device_id}/pong"
    print(f"Ping recibido de {device_id} -> respondiendo en {pong_topic}")
    client.publish(pong_topic, "pong")

client = mqtt.Client()
client.username_pw_set(USER, PASS)
client.on_connect = on_connect
client.on_message = on_message

client.connect(BROKER, 1883, 60)
client.loop_forever()