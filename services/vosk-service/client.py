import websocket
import json
import time
import traceback

SERVER_URL = "ws://192.168.1.100:2700"

def main():
    try:
        print(f"🎙️ Conectando a {SERVER_URL} ...")
        ws = websocket.create_connection(SERVER_URL, timeout=10)
        ws.send(json.dumps({"config": {"sample_rate": 16000}}))
        print("Conexión establecida. Enviando audio...")

        # Enviar un ping inicial para mantener viva la sesión (importante en Windows)
        try:
            ws.sock.ping()
        except Exception:
            pass

        with open("test.wav", "rb") as f:
            f.read(44)  # Saltar cabecera WAV
            while True:
                data = f.read(8000)
                if not data:
                    break
                # Si la conexión se ha cerrado, salimos
                if not ws.connected:
                    print("Conexión cerrada, deteniendo envío.")
                    break
                try:
                    ws.send(data, websocket.ABNF.OPCODE_BINARY)
                except websocket.WebSocketConnectionClosedException:
                    print("El servidor cerró la conexión durante el envío.")
                    break
                except ConnectionAbortedError:
                    print("Conexión abortada por Windows.")
                    break
                time.sleep(0.02)

        # Avisar del fin del audio
        if ws.connected:
            try:
                ws.send('{"eof":1}')
            except Exception as e:
                print(f"No se pudo enviar EOF: {e}")

        # Recibir resultados
        while True:
            try:
                msg = ws.recv()
                print("→", msg)
            except websocket.WebSocketConnectionClosedException:
                print("Conexión finalizada correctamente por el servidor.")
                break
            except ConnectionAbortedError:
                print("Conexión abortada localmente.")
                break

    except Exception as e:
        print("Error general en el cliente:")
        traceback.print_exc()
    finally:
        try:
            ws.close()
        except Exception:
            pass

if __name__ == "__main__":
    main()
