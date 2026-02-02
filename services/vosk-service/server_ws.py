# ============================
# vosk-service/main.py
# ============================
#!/usr/bin/env python3
import os
import json
import logging
import asyncio
import time
import websockets
from vosk import Model, KaldiRecognizer

# ==========================================================
# CONFIGURACIÓN GENERAL
# ==========================================================
MODEL_PATH = os.getenv("VOSK_MODEL_PATH", "/models/vosk")
SAMPLE_RATE = float(os.getenv("VOSK_SAMPLE_RATE", "16000"))

# ==========================================================
# LOGGING
# ==========================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# Silenciar ruido de handshake inválido de websockets (si aparece)
ws_logger = logging.getLogger("websockets")
ws_logger.setLevel(logging.CRITICAL)
ws_logger.propagate = False

# ==========================================================
# CARGA DEL MODELO VOSK
# ==========================================================
logging.info(f"[INIT] Cargando modelo desde: {MODEL_PATH}")
model = Model(MODEL_PATH)
logging.info("[INIT] Modelo cargado correctamente.")

# ==========================================================
# LÓGICA DE RECONOCIMIENTO (WEBSOCKET)
# ==========================================================
async def recognize(websocket):
    """
    Servidor WS que recibe audio PCM (bytes) en chunks y un mensaje EOF.
    Devuelve un único JSON con el texto final y cierra.

    Métrica:
    - tiempo_transcripcion_ms: desde el primer chunk recibido hasta FinalResult().
    """
    rec = KaldiRecognizer(model, SAMPLE_RATE)
    logging.info(f"[WS] Nueva conexión desde {websocket.remote_address}")

    # Medición de tiempo de transcripción
    t0 = None  # se inicia al recibir el primer chunk de audio
    total_audio_bytes = 0

    try:
        while True:
            message = await websocket.recv()

            # Audio binario
            if isinstance(message, (bytes, bytearray)):
                if t0 is None:
                    t0 = time.perf_counter()
                    logging.info("[METRIC] Inicio de sesión STT (primer chunk recibido).")

                total_audio_bytes += len(message)
                rec.AcceptWaveform(message)
                continue

            # Mensaje EOF
            if isinstance(message, str) and (message == '{"eof":1}' or message == '{"eof": 1}' or '"eof"' in message):
                # Si por algún motivo llega EOF sin audio, iniciamos el contador aquí
                if t0 is None:
                    t0 = time.perf_counter()
                    logging.warning("[METRIC] EOF recibido sin audio previo; iniciando métrica en EOF.")

                final_json = rec.FinalResult()
                final_dict = json.loads(final_json)
                text = final_dict.get("text", "").strip()

                t1 = time.perf_counter()
                elapsed_ms = (t1 - t0) * 1000.0

                logging.info(
                    "[METRIC] Fin de sesión STT | bytes_audio=%d | tiempo_transcripcion_ms=%.2f",
                    total_audio_bytes,
                    elapsed_ms
                )
                logging.info(f"[WS] Resultado final: {text}")

                # Respuesta estable para el cliente (STT-Service)
                response = {
                    "final": True,
                    "text": text,
                    "raw": final_dict,
                    "metrics": {
                        "audio_bytes": total_audio_bytes,
                        "transcription_ms": elapsed_ms
                    }
                }

                await websocket.send(json.dumps(response, ensure_ascii=False))
                await websocket.close()
                break

    except websockets.ConnectionClosed:
        logging.info("[WS] Cliente desconectado")
    except Exception as e:
        logging.error(f"[WS] Error en sesión: {e}", exc_info=True)
        try:
            await websocket.close()
        except Exception:
            pass

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

if __name__ == "__main__":
    asyncio.run(main())
