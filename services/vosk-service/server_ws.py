#!/usr/bin/env python3
import os
import json
import asyncio
import logging
import concurrent.futures

import websockets
from vosk import Model, SpkModel, KaldiRecognizer
from aiohttp import web

# --- Globales ---
model = None
spk_model = None
pool = None


# === Procesamiento de audio ===
def process_chunk(rec, message):
    """Procesa un bloque de audio y devuelve JSON (partial o final)."""
    if isinstance(message, (bytes, bytearray)):
        if rec.AcceptWaveform(message):
            return rec.Result(), False
        else:
            return rec.PartialResult(), False
    else:
        if message == '{"eof":1}' or '"eof"' in message:
            return rec.FinalResult(), True
        return json.dumps({"partial": ""}), False


# === WebSocket principal ===
async def recognize(websocket, path):
    global model, spk_model, pool

    loop = asyncio.get_running_loop()
    logging.info(f"[WS] Conexión establecida desde {websocket.remote_address}")

    sample_rate = float(os.environ.get("VOSK_SAMPLE_RATE", 16000))
    show_words = os.environ.get("VOSK_SHOW_WORDS", "true").lower() == "true"
    max_alternatives = int(os.environ.get("VOSK_ALTERNATIVES", 0))

    # Inicializa el reconocedor
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

            # Procesa en un hilo separado
            result_json, is_final = await loop.run_in_executor(pool, process_chunk, rec, message)

            if result_json:
                await websocket.send(result_json)

            if is_final:
                logging.info("[WS] Fin del audio recibido. Cerrando conexión.")
                await websocket.close()
                break

    except Exception as e:
        logging.error(f"[WS] Error en conexión: {e}", exc_info=True)
        await websocket.close()

    logging.info("[WS] Conexión finalizada.")


# === Endpoint /health ===
async def health_handler(_request):
    ok = model is not None
    return web.json_response({"status": "ok" if ok else "booting", "model_loaded": ok})


# === Arranque del servidor ===
async def start_servers():
    global model, spk_model, pool

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    # Entorno
    ws_interface = os.environ.get("VOSK_SERVER_INTERFACE", "0.0.0.0")
    ws_port = int(os.environ.get("VOSK_SERVER_PORT", 2700))
    model_path = os.environ.get("VOSK_MODEL_PATH", "model")
    spk_path = os.environ.get("VOSK_SPK_MODEL_PATH")
    health_port = int(os.environ.get("HEALTH_HTTP_PORT", 8080))

    # Carga de modelos
    logging.info(f"[INIT] Cargando modelo desde: {model_path}")
    model = Model(model_path)
    if spk_path:
        spk_model = SpkModel(spk_path)
        logging.info(f"[INIT] Modelo de hablante cargado desde: {spk_path}")
    logging.info("[INIT] Modelo principal cargado correctamente ✅")

    # Pool de threads
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=(os.cpu_count() or 1))

    # Servidor WebSocket
    ws_server = await websockets.serve(recognize, ws_interface, ws_port)
    logging.info(f"[WS] Servidor ASR activo en ws://{ws_interface}:{ws_port}")

    # Servidor HTTP /health
    app = web.Application()
    app.router.add_get("/health", health_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, ws_interface, health_port)
    await site.start()
    logging.info(f"[HTTP] Endpoint /health activo en http://{ws_interface}:{health_port}/health")

    # Mantener ambos servicios vivos
    await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(start_servers())
