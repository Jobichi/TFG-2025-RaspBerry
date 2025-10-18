#!/usr/bin/env python3
import asyncio
import websockets
import json
import soundfile as sf
import numpy as np
import struct

WS_URL = "ws://localhost:2700"  # Cambiar por la IP de la Raspberry si es remoto
AUDIO_FILE = "luz.wav"         # Archivo a enviar (16kHz mono preferible)

async def send_audio():
    # Cargar audio y convertir a 16kHz mono int16
    data, samplerate = sf.read(AUDIO_FILE)
    if len(data.shape) > 1:  # Estéreo → mono
        data = np.mean(data, axis=1)
    if samplerate != 16000:
        print(f"El audio tiene {samplerate}Hz, idealmente usa 16000Hz.")
    pcm16 = (data * 32767).astype(np.int16).tobytes()

    async with websockets.connect(WS_URL) as ws:
        chunk_size = 8000  # 0.5s aprox.
        for i in range(0, len(pcm16), chunk_size):
            await ws.send(pcm16[i:i+chunk_size])
            await asyncio.sleep(0.05)  # Simula streaming

        await ws.send(json.dumps({"eof": 1}))

        result = await ws.recv()
        print("Resultado final:")
        print(result)

if __name__ == "__main__":
    asyncio.run(send_audio())
