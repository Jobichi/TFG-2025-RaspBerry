# server/websocket_server.py
# Servidor WebSocket que gestiona sesiones de reconocimiento de audio.

import json
import websockets
from config import WS_HOST, WS_PORT


async def recognize_connection(websocket, path, engine, mqtt):
    """
    Maneja una conexión WebSocket con un cliente STT.
    """
    recognizer = engine.create_session()

    print(f"[WS] Nueva conexión desde {websocket.remote_address}")

    try:
        while True:
            message = await websocket.recv()

            # Señal de fin de transmisión
            if isinstance(message, str) and '"eof"' in message:
                result = recognizer.FinalResult()
                result_dict = json.loads(result)
                text = result_dict.get("text", "").strip()

                await websocket.send(result)
                print(f"[WS] Resultado final: {text}")

                if text:
                    mqtt.publish(text)

                await websocket.close()
                break

            # Se recibe audio binario
            if isinstance(message, (bytes, bytearray)):
                recognizer.AcceptWaveform(message)

    except websockets.ConnectionClosed:
        print("[WS] Cliente desconectado.")
    except Exception as e:
        print(f"[WS] Error en sesión: {e}")


async def start_server(engine, mqtt):
    """
    Arranca el servidor WebSocket.
    """
    print(f"[WS] Servidor escuchando en ws://{WS_HOST}:{WS_PORT}")

    return await websockets.serve(
        lambda ws, path: recognize_connection(ws, path, engine, mqtt),
        WS_HOST,
        WS_PORT,
        max_size=2**24
    )
