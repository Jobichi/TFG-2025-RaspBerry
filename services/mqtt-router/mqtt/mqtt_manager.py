import json
import paho.mqtt.client as mqtt
from database import db_manager
from config import MQTT_CFG, logger
from handlers import announce_handler, update_handler, alert_handler, response_handler, system_get_handler, system_select_handler

class MQTTRouter:
    def __init__(self):
        self.db = db_manager
        self.client = mqtt.Client()
        self.client.username_pw_set(MQTT_CFG["user"], MQTT_CFG["password"])
        self.client.on_message = self.on_message

    def start(self):
        self.client.connect(MQTT_CFG["host"], MQTT_CFG["port"], 60)
        for topic, qos in MQTT_CFG["topics"]:
            self.client.subscribe(topic, qos)
            logger.info(f"[MQTT] Subscrito a {topic}")
        logger.info("[MQTT] Esperando mensajes...")
        self.client.loop_forever()

    def on_mesage(self, client, userdata, msg):
        topic = msg.topic
        try:
            payload = json.load(msg.payload.decode())
        except Exception:
            logger.warning(f"[MQTT] JSON inválido en {topic}")
            return

        # Router de tópicos MQTT -  Deriba a sus handlers:
        if topic.startswith("announce/"):
            announce_handler.handle(self.db, client, topic, payload)
        elif topic.startswith("update/"):
            update_handler.handle(self.db, client, topic, payload)
        elif topic.startswith("alert/"):
            alert_handler.handle(self.db, client, topic, payload)
        elif topic.startswith("response/"):
            response_handler.handle(self.db, client, topic, payload)
        elif topic.startswith("system/get"):
            system_get_handler.handle(self.db, client, topic, payload)
        elif topic.startswith("system/select"):
            system_select_handler.handle(self.db, client, topic, payload)
        else:
            logger.debug(f"[MQTT] Mensaje no manejado: {topic}")
