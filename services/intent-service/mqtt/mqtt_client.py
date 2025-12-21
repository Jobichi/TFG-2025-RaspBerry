import json
import time
import paho.mqtt.client as mqtt

from config import MQTT_CFG, TOPICS, QOS, logger


class MQTTClient:
    """
    Cliente MQTT para el intent-service.
    - Solicita snapshot inicial al router
    - Recibe snapshot y respuestas
    - Recibe texto desde STT
    - Publica comandos SET
    """

    def __init__(self):
        self.client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2
        )

        # Autenticación
        self.client.username_pw_set(
            MQTT_CFG["user"],
            MQTT_CFG["password"]
        )

        # Callbacks
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

        # Callbacks externos (inyectados desde main.py)
        self.on_transcription_cb = None
        self.on_response_cb = None

    # ==========================================================
    #  CONEXIÓN
    # ==========================================================
    def connect(self):
        logger.info(
            f"[MQTT] Conectando a {MQTT_CFG['host']}:{MQTT_CFG['port']}..."
        )
        self.client.connect(
            MQTT_CFG["host"],
            MQTT_CFG["port"],
            MQTT_CFG["keepalive"]
        )

    def loop_forever(self):
        self.client.loop_forever()

    # ==========================================================
    #  CALLBACKS MQTT
    # ==========================================================
    def on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            logger.info("[MQTT] Conectado correctamente al broker")

            # Suscripción a transcripciones STT
            client.subscribe(
                TOPICS["transcription_in"],
                QOS["transcription_in"]
            )
            logger.info(
                f"[MQTT] Suscrito a {TOPICS['transcription_in']}"
            )

            # Suscripción a respuestas del router (snapshot + responses)
            client.subscribe(
                TOPICS["response_in"],
                QOS["response_in"]
            )
            logger.info(
                f"[MQTT] Suscrito a {TOPICS['response_in']}"
            )

            # Solicitar snapshot inicial
            self.request_snapshot()

        else:
            logger.error(
                f"[MQTT] Error al conectar al broker: {reason_code}"
            )

    def on_message(self, client, userdata, msg):
        topic = msg.topic
        raw_payload = msg.payload.decode("utf-8")

        try:
            payload = json.loads(raw_payload) if raw_payload else {}
        except json.JSONDecodeError:
            logger.warning(
                f"[MQTT] Payload no JSON en {topic}: {raw_payload}"
            )
            return

        # === Transcripción STT ===
        if topic == TOPICS["transcription_in"]:
            logger.info(
                f"[MQTT] Transcripción recibida: {payload}"
            )
            if self.on_transcription_cb:
                self.on_transcription_cb(payload)
            return

        # === Respuestas del router (snapshot / response) ===
        if topic.startswith(
            TOPICS["response_in"].rstrip("#")
        ):
            if self.on_response_cb:
                self.on_response_cb(topic, payload)
            return

        # === Mensaje no esperado ===
        logger.debug(
            f"[MQTT] Mensaje ignorado ({topic}): {payload}"
        )

    # ==========================================================
    #  PUBLICACIONES
    # ==========================================================
    def request_snapshot(self):
        """
        Solicita al mqtt-router el snapshot completo del sistema.
        """
        payload = {"request": "all"}

        self.client.publish(
            TOPICS["select_req"],
            json.dumps(payload),
            qos=QOS["select_req"]
        )

        logger.info(
            f"[MQTT] Snapshot solicitado -> {TOPICS['select_req']}"
        )

    def publish_set(self, command: dict):
        """
        Publica un comando SET estructurado hacia el router.
        """
        self.client.publish(
            TOPICS["set_out"],
            json.dumps(command),
            qos=QOS["set_out"]
        )

        logger.info(
            f"[MQTT] Comando SET publicado -> {command}"
        )
