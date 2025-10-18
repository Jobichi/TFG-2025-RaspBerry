#!/usr/bin/env python3
import os
import json
import asyncio
import logging
import websockets
from vosk import Model, KaldiRecognizer

# ======== Configuración ========
# Usar la ruta correcta donde están realmente los archivos del modelo
MODEL_PATH = os.getenv("VOSK_MODEL_PATH", "model")
SAMPLE_RATE = float(os.getenv("VOSK_SAMPLE_RATE", "16000"))
# ================================

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Cargar modelo
logging.info(f"[INIT] Cargando modelo desde: {MODEL_PATH}")
model = Model(MODEL_PATH)
logging.info("[INIT] Modelo cargado correctamente.")

# ======== Lógica de reconocimiento ========
async def recognize(websocket):
    rec = KaldiRecognizer(model, SAMPLE_RATE)
    logging.info(f"[WS] Nueva conexión desde {websocket.remote_address}")

    try:
        while True:
            message = await websocket.recv()

            # Fin de audio
            if isinstance(message, str) and ('"eof"' in message or message == '{"eof":1}'):
                result = rec.FinalResult()
                await websocket.send(result)
                logging.info(f"[WS] Resultado final: {result}")
                await websocket.close()
                break

            # Audio binario
            if isinstance(message, (bytes, bytearray)):
                rec.AcceptWaveform(message)
            else:
                logging.debug(f"[WS] Mensaje no binario: {message}")

    except websockets.ConnectionClosed:
        logging.info("[WS] Cliente desconectado.")
    except Exception as e:
        logging.error(f"[WS] Error en sesión: {e}", exc_info=True)
        await websocket.close()

# ======== Servidor principal ========
async def main():
    async with websockets.serve(recognize, "0.0.0.0", 2700, max_size=2**24):
        logging.info("[WS] Servidor ASR activo en ws://0.0.0.0:2700")
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
