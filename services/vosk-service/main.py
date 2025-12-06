# main.py
# Punto de entrada del vosk-service.
# Carga el motor STT, inicia MQTT y arranca el servidor WebSocket.

import asyncio
from stt.vosk_engine import VoskEngine
from mqtt.mqtt_client import MQTTClient
from server.ws_server import start_server


async def main():
    engine = VoskEngine()
    mqtt = MQTTClient()

    server = await start_server(engine, mqtt)
    print("[MAIN] vosk-service iniciado correctamente.")

    await asyncio.Future()  # Ejecutar para siempre


if __name__ == "__main__":
    asyncio.run(main())
