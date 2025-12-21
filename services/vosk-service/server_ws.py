#!/usr/bin/env python3
import os
import json
import asyncio
import logging
import paho.mqtt.client as mqtt
import websockets
from vosk import Model, KaldiRecognizer

# ==========================================================
# CONFIGURACIÓN GENERAL
# ==========================================================
MODEL_PATH = os.getenv("VOSK_MODEL_PATH", "/models/vosk")
SAMPLE_RATE = float(os.getenv("VOSK_SAMPLE_RATE", "16000"))

# MQTT
MQTT_HOST = os.getenv("MQTT_HOST", "mosquitto")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USER = os.getenv("MQTT_USER", "user")
MQTT_PASS = os.getenv("MQTT_PASS", "pass")
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "system/transcription/text")

# ==========================================================
# LOGGING
# ==========================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# Silenciar definitivamente el ruido de handshake inválido de websockets
ws_logger = logging.getLogger("websockets")
ws_logger.setLevel(logging.CRITICAL)
ws_logger.propagate = False

# ==========================================================
# MQTT
# ==========================================================
mqtt_client = None


def setup_mqtt():
    """Configura y conecta el cliente MQTT."""
    global mqtt_client

    mqtt_client = mqtt.Client()
    mqtt_client.username_pw_set(MQTT_USER, MQTT_PASS)

    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            logging.info(f"[MQTT] Conectado a {MQTT_HOST}:{MQTT_PORT}")
        else:
            logging.error(f"[MQTT] Error de conexión: {rc}")

    def on_disconnect(client, userdata, rc):
        logging.warning(f"[MQTT] Desconectado: {rc}")

    mqtt_client.on_connect = on_connect
    mqtt_client.on_disconnect = on_disconnect

    mqtt_client.connect(MQTT_HOST, MQTT_PORT, 60)
    mqtt_client.loop_start()


def publish_to_mqtt(text: str):
    """Publica el texto reconocido en MQTT."""
    if not mqtt_client or not mqtt_client.is_connected():
        logging.warning("[MQTT] Cliente no conectado, no se puede publicar")
        return

    payload = json.dumps({
        "text": text,
        "timestamp": asyncio.get_event_loop().time()
    })

    result = mqtt_client.publish(MQTT_TOPIC, payload, qos=1)

    if result.rc == mqtt.MQTT_ERR_SUCCESS:
        logging.info(f"[MQTT] Publicado en {MQTT_TOPIC}: {text}")
    else:
        logging.error(f"[MQTT] Error publicando: {result.rc}")


# ==========================================================
# CARGA DEL MODELO VOSK
# ==========================================================
logging.info(f"[INIT] Cargando modelo desde: {MODEL_PATH}")
model = Model(MODEL_PATH)
logging.info("[INIT] Modelo cargado correctamente.")

# ==========================================================
# INICIALIZACIÓN MQTT
# ==========================================================
setup_mqtt()

# ==========================================================
# LÓGICA DE RECONOCIMIENTO (WEBSOCKET)
# ==========================================================
async def recognize(websocket):
    rec = KaldiRecognizer(model, SAMPLE_RATE)
    logging.info(f"[WS] Nueva conexión desde {websocket.remote_address}")

    try:
        while True:
            message = await websocket.recv()

            # Mensaje EOF
            if isinstance(message, str) and ('"eof"' in message or message == '{"eof":1}'):
                result = rec.FinalResult()
                result_dict = json.loads(result)
                text = result_dict.get("text", "").strip()

                await websocket.send(result)
                logging.info(f"[WS] Resultado final: {result}")

                if text:
                    publish_to_mqtt(text)

                await websocket.close()
                break

            # Audio binario
            if isinstance(message, (bytes, bytearray)):
                rec.AcceptWaveform(message)

    except websockets.ConnectionClosed:
        logging.info("[WS] Cliente desconectado")
    except Exception as e:
        logging.error(f"[WS] Error en sesión: {e}", exc_info=True)
        await websocket.close()


# ==========================================================
# SERVIDOR PRINCIPAL
# ==========================================================
async def main():
    async with websockets.serve(
        recognize,
        "0.0.0.0",
        2700,
        max_size=2 ** 24
    ):
        logging.info("[WS] Servidor ASR activo en ws://0.0.0.0:2700")
        await asyncio.Future()


# ==========================================================
# ENTRYPOINT
# ==========================================================
if __name__ == "__main__":
    asyncio.run(main())
