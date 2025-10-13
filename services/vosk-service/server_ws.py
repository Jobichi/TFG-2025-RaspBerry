#!/usr/bin/env python3
import os
import json
import asyncio
import logging
import concurrent.futures

import websockets
from vosk import Model, SpkModel, KaldiRecognizer
from aiohttp import web
import paho.mqtt.client as mqtt

# ======================
# Configuración Global
# ======================
model = None
spk_model = None
pool = None

# MQTT Config
MQTT_HOST = os.getenv("MQTT_HOST", "mosquitto")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USER = os.getenv("MQTT_USER", "user")
MQTT_PASS = os.getenv("MQTT_PASS", "pass")
MQTT_TOPIC = os.getenv("VOSK_MQTT_TOPIC", "vosk/text")

# ======================
# Funciones principales
# ======================

async def recognize(websocket, path):
    global model, spk_model, pool

    loop = asyncio.get_running_loop()
    logging.info(f"[WS] Nueva conexión desde {websocket.remote_address}")

    sample_rate = float(os.getenv("VOSK_SAMPLE_RATE", "16000"))
    show_words = os.getenv("VOSK_SHOW_WORDS", "true").lower() == "true"
    max_alternatives = int(os.getenv("VOSK_ALTERNATIVES", "0"))

    rec = KaldiRecognizer(model, sample_rate)
    rec.SetWords(show_words)
    rec.SetMaxAlternatives(max_alternatives)
    if spk_model:
        rec.SetSpkModel(spk_model)

    try:
        while True:
            try:
                message = await websocket.recv()
            except websockets.ConnectionClosed:
                logging.info("[WS] Cliente desconectado.")
                break

            # Fin del audio
            if isinstance(message, str) and ('"eof"' in message or message == '{"eof":1}'):
                logging.info("→ Fin del audio recibido, generando resultado final...")
                result = rec.FinalResult()
                await websocket.send(result)

                # ====== Publicar resultado en MQTT ======
                try:
                    result_json = json.loads(result)
                    texto = result_json.get("text", "").strip()
                    if texto:
                        mqtt_client = mqtt.Client()
                        mqtt_client.username_pw_set(MQTT_USER, MQTT_PASS)
                        mqtt_client.connect(MQTT_HOST, MQTT_PORT)
                        payload = json.dumps({"text": texto}, ensure_ascii=False)
                        mqtt_client.publish(MQTT_TOPIC, payload)
                        mqtt_client.disconnect()
                        logging.info(f"[MQTT] Publicado en {MQTT_TOPIC} → {payload}")
                    else:
                        logging.info("[MQTT] Texto vacío, no se publica.")
                except Exception as e:
                    logging.error(f"[MQTT] Error publicando resultado: {e}")
                # ========================================

                await websocket.close()
                logging.info("→ Conexión cerrada correctamente.")
                break

            # Datos de audio
            if isinstance(message, (bytes, bytearray)):
                if rec.AcceptWaveform(message):
                    pass
            else:
                # Mensaje de control (eof o texto)
                logging.debug(f"[WS] Mensaje de texto: {message}")

    except Exception as e:
        logging.error(f"[WS] Error en sesión: {e}", exc_info=True)
        await websocket.close()

# ======================
# Endpoint /health
# ======================
async def health_handler(_request):
    ok = model is not None
    return web.json_response({"status": "ok" if ok else "booting", "model_loaded": ok})

# ======================
# Servidor principal
# ======================
async def start_servers():
    global model, spk_model, pool

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    ws_interface = os.getenv("VOSK_SERVER_INTERFACE", "0.0.0.0")
    ws_port = int(os.getenv("VOSK_SERVER_PORT", "2700"))
    model_path = os.getenv("VOSK_MODEL_PATH", "model")
    spk_path = os.getenv("VOSK_SPK_MODEL_PATH")
    health_port = int(os.getenv("HEALTH_HTTP_PORT", "8080"))

    logging.info(f"[INIT] Cargando modelo desde: {model_path}")
    model = Model(model_path)
    if spk_path:
        spk_model = SpkModel(spk_path)
    logging.info("[INIT] Modelo cargado correctamente ✅")

    pool = concurrent.futures.ThreadPoolExecutor(max_workers=(os.cpu_count() or 1))

    ws_server = await websockets.serve(recognize, ws_interface, ws_port)
    logging.info(f"[WS] Servidor ASR activo en ws://{ws_interface}:{ws_port}")

    app = web.Application()
    app.router.add_get("/health", health_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, ws_interface, health_port)
    await site.start()
    logging.info(f"[HTTP] Endpoint /health activo en http://{ws_interface}:{health_port}/health")

    await asyncio.Future()  # Mantener corriendo

if __name__ == "__main__":
    asyncio.run(start_servers())
