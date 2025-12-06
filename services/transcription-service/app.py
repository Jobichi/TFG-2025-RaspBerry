import os
import time
import json
import asyncio
import websockets
import paho.mqtt.client as mqtt
import wave

# === CONFIGURACIÓN ===
RECORDING_PATH = "/asterisk/recordings/grabacion.wav16"
VOSK_WS = "ws://vosk-service:2700"

# MQTT (para escuchar confirmaciones)
MQTT_BROKER = os.getenv("MQTT_HOST", "mosquitto")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_USER = os.getenv("MQTT_USER", "admin")
MQTT_PASS = os.getenv("MQTT_PASS", "admin1234")
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "transcription/text")

# Control de detección de archivo
CHECK_INTERVAL = 2
STABLE_THRESHOLD = 5


def extract_pcm_from_wav(wav_path):
    """Extrae solo los datos PCM raw de un archivo WAV."""
    try:
        with wave.open(wav_path, 'rb') as wav_file:
            # Verificar formato
            sample_rate = wav_file.getframerate()
            n_channels = wav_file.getnchannels()
            samp_width = wav_file.getsampwidth()
            n_frames = wav_file.getnframes()
            
            print(f"[AUDIO] WAV: {sample_rate}Hz, {n_channels} canal(es), {samp_width} bytes/muestra")
            print(f"[AUDIO] Frames: {n_frames}, Tiempo: {n_frames/sample_rate:.2f}s")
            
            # Leer solo los datos PCM (sin cabecera)
            pcm_data = wav_file.readframes(n_frames)
            print(f"[AUDIO] PCM extraído: {len(pcm_data)} bytes")
            
            return pcm_data, sample_rate
            
    except Exception as e:
        print(f"[ERROR] Extrayendo PCM: {e}")
        return None, 0


async def process_audio():
    """Envía solo el PCM raw a Vosk."""
    if not os.path.exists(RECORDING_PATH):
        print(f"[ERROR] No existe: {RECORDING_PATH}")
        return

    # Extraer PCM del WAV
    pcm_data, sample_rate = extract_pcm_from_wav(RECORDING_PATH)
    
    if pcm_data is None or len(pcm_data) == 0:
        print("[ERROR] No se pudo extraer PCM")
        return

    try:
        async with websockets.connect(VOSK_WS) as ws:
            print(f"[WS] Conectado a Vosk, enviando {len(pcm_data)} bytes PCM...")
            
            # Vosk ya sabe que es 16kHz por el formato del PCM
            # Enviar en chunks pequeños
            chunk_size = 4000  # bytes
            total_chunks = (len(pcm_data) + chunk_size - 1) // chunk_size
            
            for i in range(0, len(pcm_data), chunk_size):
                chunk = pcm_data[i:i + chunk_size]
                await ws.send(chunk)
                
                # Mostrar progreso
                chunk_num = i // chunk_size + 1
                if chunk_num % 10 == 0:
                    print(f"[WS] Enviado chunk {chunk_num}/{total_chunks}")
                
                # Pequeña pausa para no saturar
                await asyncio.sleep(0.05)
            
            # Señal de fin
            await ws.send('{"eof": 1}')
            print("[WS] Audio completo enviado, esperando resultados...")
            
            # Recibir resultados
            results_received = 0
            async for message in ws:
                result = json.loads(message)
                results_received += 1
                
                if 'text' in result:
                    text = result['text'].strip()
                    if text:
                        print(f"[RESULTADO {results_received}] '{text}'")
                
                # Si recibimos varios resultados sin texto, puede ser el final
                if results_received >= 3 and not text:
                    break
                    
            print("[WS] Transcripción completada")
            
    except websockets.exceptions.ConnectionClosed as e:
        print(f"[ERROR] Conexión cerrada: {e}")
    except Exception as e:
        print(f"[ERROR] Comunicación Vosk: {e}")


def is_file_stable(file_path):
    """Espera a que el archivo deje de crecer."""
    if not os.path.exists(file_path):
        return False
        
    for _ in range(3):  # Verificar 3 veces
        size1 = os.path.getsize(file_path)
        time.sleep(1)
        size2 = os.path.getsize(file_path)
        if size1 != size2:
            return False
            
    return size1 > 0


# === MQTT ===
def on_message(client, userdata, msg):
    """Recibe confirmación de transcripción."""
    try:
        payload = msg.payload.decode()
        data = json.loads(payload)
        text = data.get("text", "")
        ts = data.get("timestamp", None)
        print(f"[MQTT] Confirmación: '{text}' (ts: {ts})")
    except Exception as e:
        print(f"[MQTT][ERROR] {e}")


def start_mqtt_listener():
    """Inicializa MQTT."""
    client = mqtt.Client()
    client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.on_message = on_message
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    client.subscribe(MQTT_TOPIC)
    client.loop_start()
    print(f"[INFO] MQTT escuchando en {MQTT_TOPIC}")
    return client


# === MAIN ===
def main():
    last_processed_size = 0
    print(f"[INFO] Monitorizando: {RECORDING_PATH} (formato: WAV 16kHz mono 16-bit)")

    mqtt_client = start_mqtt_listener()

    while True:
        try:
            if os.path.exists(RECORDING_PATH):
                current_size = os.path.getsize(RECORDING_PATH)
                if current_size > 1000 and current_size != last_processed_size:
                    if is_file_stable(RECORDING_PATH):
                        print(f"[INFO] Grabación lista: {current_size} bytes")
                        asyncio.run(process_audio())
                        last_processed_size = current_size
                        print("[INFO] Esperando siguiente grabación...")
                    else:
                        print(f"[DEBUG] Grabación en progreso: {current_size} bytes")
            
            time.sleep(CHECK_INTERVAL)
            
        except Exception as e:
            print(f"[ERROR] {e}")
            time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
