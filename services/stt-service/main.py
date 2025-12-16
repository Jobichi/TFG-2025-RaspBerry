# main.py
# Archivo principal del servicio de transcripción.
#
# Su responsabilidad es orquestar los distintos componentes del sistema:
# - Detección de nuevos archivos de audio mediante el watcher.
# - Selección del procesador de audio adecuado.
# - Selección del cliente STT mediante factoría.
# - Obtención del texto transcrito.
# - Publicación o procesamiento posterior (por ejemplo vía MQTT).
#
# Este archivo no conoce detalles internos del procesamiento del audio
# ni del backend STT. Mantiene una arquitectura desacoplada y extensible.

import asyncio
from audio.file_watcher import FileWatcher
from audio.factory import AudioProcessorFactory
from stt.factory import STTFactory
from mqtt.mqtt_client import create_mqtt_client
from config import RECORDING_PATH


async def process_file(path):
    """
    Flujo completo de procesamiento de un archivo de audio.
    1. Selecciona el procesador adecuado según la extensión del archivo.
    2. Carga y extrae audio PCM del archivo.
    3. Selecciona el backend STT mediante factoría.
    4. Envía PCM al servicio STT y obtiene texto.
    5. Muestra o publica la transcripción.

    Este método no contiene lógica específica de audio o STT,
    solo coordina a los módulos correspondientes.
    """

    # 1. Obtener procesador de audio (WAV, MP3, etc.)
    processor = AudioProcessorFactory.get_processor(path)
    processor.load(path)
    pcm_data = processor.as_pcm()

    # 2. Obtener cliente STT mediante factoría
    stt_client = STTFactory.get_client()

    # 3. Procesar audio en asincronía y obtener texto
    text = await stt_client.process_audio(pcm_data)

    # 4. Mostrar resultado
    print("[STT] Transcripción final:", text)

    # Si deseas publicar por MQTT desde aquí:
    # (puedes mover esta lógica al módulo mqtt si prefieres)
    # publish_transcription(text)


def main():
    """
    Punto de entrada del servicio.
    - Inicia el cliente MQTT.
    - Configura el watcher para detectar cambios en el archivo de Asterisk.
    - Ejecuta el flujo de transcripción cuando el archivo está listo.
    """

    # Inicializar cliente MQTT
    mqtt_client = create_mqtt_client()

    # Configurar watcher para detectar grabaciones nuevas o actualizadas
    watcher = FileWatcher(
        path=RECORDING_PATH,
        callback=lambda p: asyncio.run(process_file(p))
    )

    print("[MAIN] Servicio de transcripción iniciado. Vigilando grabaciones.")
    watcher.start()


if __name__ == "__main__":
    main()
