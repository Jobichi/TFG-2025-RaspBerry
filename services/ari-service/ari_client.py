import os
import json
import asyncio
import logging
import aiohttp
import websockets
import paho.mqtt.client as mqtt

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

ASTERISK_ARI_URL = os.getenv("ASTERISK_ARI_URL", "http://asterisk:8088/ari")
ASTERISK_ARI_USER = os.getenv("ASTERISK_ARI_USER", "user_ari")
ASTERISK_ARI_PASS = os.getenv("ASTERISK_ARI_PASS", "ari123")
ASTERISK_APP_NAME = os.getenv("ASTERISK_APP_NAME", "stt_app")

VOSK_WS_URL = os.getenv("VOSK_WS_URL", "ws://vosk-service:2700")
MQTT_HOST = os.getenv("MQTT_HOST", "mosquitto")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USER = os.getenv("MQTT_USER", "user")
MQTT_PASS = os.getenv("MQTT_PASS", "pass")
MQTT_TOPIC_OUT = os.getenv("MQTT_TOPIC_OUT", "transcription/text")


class ARIClient:
    def __init__(self):
        self.session = None
        self.mqtt_client = None

    async def connect_mqtt(self):
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.username_pw_set(MQTT_USER, MQTT_PASS)
        self.mqtt_client.connect(MQTT_HOST, MQTT_PORT, 60)
        self.mqtt_client.loop_start()
        logging.info("[MQTT] Conectado a broker")

    async def connect_ari(self):
        """Establece conexión con Asterisk ARI WebSocket."""
        ws_url = f"{ASTERISK_ARI_URL.replace('http', 'ws')}/events?api_key={ASTERISK_ARI_USER}:{ASTERISK_ARI_PASS}&app={ASTERISK_APP_NAME}"
        session = aiohttp.ClientSession()
        self.session = session
        logging.info(f"[ARI] Conectando a {ws_url}")
        self.ws = await session.ws_connect(ws_url)
        logging.info("[ARI] Conectado a ARI WebSocket")

    async def process_audio(self, audio_path):
        """Envía el audio a Vosk y publica la transcripción."""
        try:
            async with websockets.connect(VOSK_WS_URL, max_size=2**24) as ws:
                logging.info(f"[VOSK] Enviando {audio_path}")
                with open(audio_path, "rb") as f:
                    await ws.send(f.read())
                await ws.send('{"eof" : 1}')
                result = await ws.recv()
                result_dict = json.loads(result)
                text = result_dict.get("text", "")
                if text:
                    self.mqtt_client.publish(MQTT_TOPIC_OUT, json.dumps({"text": text}))
                    logging.info(f"[MQTT] Publicado texto: {text}")
        except Exception as e:
            logging.error(f"[VOSK] Error procesando audio: {e}")

    async def run(self):
        await self.connect_mqtt()
        await self.connect_ari()
        logging.info("[ARI] Esperando eventos...")
        async for msg in self.ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                event = json.loads(msg.data)
                logging.info(f"[ARI] Evento: {event.get('type')}")
                if event.get("type") == "StasisStart":
                    channel = event["channel"]["id"]
                    # Graba el audio a un archivo temporal
                    await self.record_audio(channel)
            elif msg.type == aiohttp.WSMsgType.ERROR:
                logging.error("[ARI] Error en WebSocket.")
                break

    async def record_audio(self, channel):
        """Ejecuta grabación del canal actual."""
        record_url = f"{ASTERISK_ARI_URL}/channels/{channel}/record"
        params = {
            "name": f"recording-{channel}",
            "format": "wav",
            "maxDurationSeconds": 10,
            "beep": "false",
            "terminateOn": "none"
        }
        auth = aiohttp.BasicAuth(ASTERISK_ARI_USER, ASTERISK_ARI_PASS)
        async with self.session.post(record_url, params=params, auth=auth) as resp:
            if resp.status == 200:
                logging.info(f"[ARI] Grabando canal {channel}")
            else:
                logging.error(f"[ARI] Error al grabar: {resp.status}")
