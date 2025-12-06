# vosk_client.py
# Implementación concreta del cliente STT utilizando un servicio Vosk vía WebSocket.
#
# La clase VoskClient implementa la interfaz STTClient y permite que el
# servicio de transcripción interactúe con Vosk sin conocer su funcionamiento
# interno. El envío se realiza en chunks pequeños para simular streaming, y el
# cliente recoge los resultados devueltos por el backend STT hasta obtener el texto final.

import asyncio
import json
import websockets

from stt.stt_client import STTClient
from config import VOSK_WS


class VoskClient(STTClient):
    """
    Cliente STT que se conecta a un microservicio Vosk mediante WebSocket.
    """

    async def process_audio(self, pcm_data: bytes) -> str:
        """
        Envía el audio PCM al microservicio Vosk y obtiene la transcripción final.

        :param pcm_data: Audio PCM 16-bit.
        :return: Texto reconocido por el modelo Vosk.
        """
        try:
            async with websockets.connect(VOSK_WS) as ws:
                await self._send_pcm(ws, pcm_data)
                text = await self._receive_results(ws)
                return text
        except Exception as e:
            print(f"[VOSK][ERROR] Fallo en comunicación con Vosk: {e}")
            return ""

    async def _send_pcm(self, ws, pcm_data: bytes) -> None:
        """
        Envía el audio en pequeños bloques para simular transmisión progresiva.

        :param ws: Conexión WebSocket activa.
        :param pcm_data: Datos PCM en bruto.
        """
        chunk_size = 4000
        total = len(pcm_data)
        total_chunks = (total + chunk_size - 1) // chunk_size

        for i in range(0, total, chunk_size):
            await ws.send(pcm_data[i:i + chunk_size])
            chunk_id = i // chunk_size + 1

            if chunk_id % 10 == 0 or chunk_id == total_chunks:
                print(f"[VOSK] Enviado chunk {chunk_id}/{total_chunks}")

            await asyncio.sleep(0.01)

        await ws.send(b'{"eof": 1}')
        print("[VOSK] Audio enviado completamente.")

    async def _receive_results(self, ws) -> str:
        """
        Recibe los mensajes devueltos por Vosk hasta obtener el texto final.

        :param ws: Conexión WebSocket activa.
        :return: Texto reconocido.
        """
        final_text = ""

        async for message in ws:
            try:
                data = json.loads(message)
            except json.JSONDecodeError:
                print(f"[VOSK][WARN] Respuesta no válida: {message}")
                continue

            text = data.get("text", "").strip()
            if text:
                final_text = text
                print(f"[VOSK] Parcial: {text}")

            if data.get("final") or data.get("partial", "") == "":
                break

        print(f"[VOSK] Texto final: {final_text}")
        return final_text
