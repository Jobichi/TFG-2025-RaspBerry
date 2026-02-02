# ============================
# stt-service/stt/vosk_client.py
# ============================
import asyncio
import json
import websockets

from stt.stt_client import STTClient
from config import VOSK_WS


class VoskClient(STTClient):
    """
    Cliente STT que se conecta a un microservicio Vosk mediante WebSocket.

    Flujo:
    - Envía PCM en chunks.
    - Envía EOF.
    - Recibe un único JSON de respuesta con el texto final.
    """

    async def process_audio(self, pcm_data: bytes) -> str:
        try:
            async with websockets.connect(VOSK_WS) as ws:
                await self._send_pcm(ws, pcm_data)
                return await self._receive_final(ws)
        except Exception as e:
            print(f"[VOSK][ERROR] Fallo en comunicación con Vosk: {e}")
            return ""

    async def _send_pcm(self, ws, pcm_data: bytes) -> None:
        chunk_size = 4000
        total = len(pcm_data)
        total_chunks = (total + chunk_size - 1) // chunk_size

        for i in range(0, total, chunk_size):
            await ws.send(pcm_data[i:i + chunk_size])
            chunk_id = i // chunk_size + 1

            if chunk_id % 10 == 0 or chunk_id == total_chunks:
                print(f"[VOSK] Enviado chunk {chunk_id}/{total_chunks}")

            await asyncio.sleep(0.01)

        await ws.send('{"eof": 1}')
        print("[VOSK] Audio enviado completamente (EOF).")

    async def _receive_final(self, ws) -> str:
        """
        Recibe una única respuesta JSON del servidor.
        Soporta:
        - Wrapper: {"final": true, "text": "...", "raw": {...}}
        - Directo: {"text": "..."}
        """
        message = await ws.recv()

        try:
            data = json.loads(message)
        except json.JSONDecodeError:
            print(f"[VOSK][WARN] Respuesta no válida: {message}")
            return ""

        text = str(data.get("text", "")).strip()
        print(f"[VOSK] Texto final: {text}")
        return text