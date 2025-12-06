import json
import asyncio
import websockets
from config import VOSK_WS

class VoskClient:
    """Cliente vosk asincrono para procesar audio usando Vosk."""

    async def process_audio(self, pcm_data):
        """Envía PCM a Vosk y devuelve la trancripción final."""
        try:
            async with websockets.connect(VOSK_WS) as ws:
                await self._send_pcm(ws, pcm_data)
                text = await self._receive_results(ws)
                return text
            
        except Exception as e:
            print(f"[VOSK][ERROR] {e}")
            return ""

    async def _send_pcm(self, ws, pcm_data):
        """Envía el audio en chunks."""
        chunk_size = 4000
        total = len(pcm_data)

        for i in range(0, total, chunk_size):
            await ws.send(pcm_data[i:i + chunk_size])
            await asyncio.sleep(0.01)

        await ws.send('{"eof": 1}')

    async def _receive_results(self, ws):
        """Espera resultados hasta que Vosk envía uno final."""
        final_text = ""

        async for msg in ws:
            data = json.loads(msg)
            text = data.get("text", "").strip()

            if text:
                final_text = text
                print(f"[VOSK] Parcial: {text}")

            # Cuando Vosk envía resutados vacíos al final -> Fin del stream
            if "final" in data or data.get("partial") == "":
                break

        print(f"[VOSK] Texto final: {final_text}")
        return final_text