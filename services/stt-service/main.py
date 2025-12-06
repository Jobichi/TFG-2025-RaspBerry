# main.py
# Archivo principal del servicio STT.
# Su única responsabilidad es orquestar todos los módulos:
# - Watcher encargado de detectar nuevos archivos de audio
# - Procesador de audio (interfaz + implementaciones)
# - Cliente STT (como Vosk)
# - Cliente MQTT (para notificaciones o integraciones)
#
# Este archivo NO contiene lógica de audio, ni lógica STT, ni lógica MQTT.
# Únicamente coordina a los módulos y define el flujo de ejecución.

import asyncio
from audio.file_watcher import FileWatcher
from audio.factory import AudioProcessorFactory
from clients.vosk_client import VoskClient
from mqtt.mqtt_client import create_mqtt_client
from config import RECORDING_PATH


async def process_file(path):
    """
    Función asíncrona encargada de:
    1. Seleccionar el procesador adecuado según el formato del archivo.
    2. Cargar el audio.
    3. Convertirlo a PCM.
    4. Enviarlo al cliente STT seleccionado.
    5. Obtener la transcripción final y mostrarla.

    Este método NO sabe nada de:
    - cómo funciona un procesador WAV
    - cómo se decodifica un MP3
    - cómo funciona el WebSocket de Vosk

    Simplemente usa los métodos definidos por las interfaces para obtener los datos
    y enviarlos al motor STT.
    """

    # Obtener el procesador correcto según el tipo de fichero
    processor = AudioProcessorFactory.get_processor(path)
    processor.load(path)

    # Convertir a PCM y obtener la frecuencia de muestreo si fuese necesario
    pcm_data = processor.as_pcm()

    # Cliente STT (en este caso Vosk, pero gracias a la interfaz es intercambiable)
    stt_client = VoskClient()

    # Procesar el audio y obtener texto
    text = await stt_client.process_audio(pcm_data)

    print("[STT] Transcripción final:", text)


def main():
    """
    Punto de entrada principal del servicio.

    Sus responsabilidades son:
    - Crear el cliente MQTT (si se requiere interacción con otros servicios).
    - Crear el watcher que vigila la aparición/modificación del archivo de audio.
    - Especificar qué debe ocurrir cuando un archivo esté listo para procesar.
    - Lanzar el watcher, el cual se encarga del ciclo de espera y eventos.

    Este archivo NO debe contener lógica de análisis de audio ni de STT.
    Solo coordina módulos.
    """

    # Inicialización del cliente MQTT
    # Esto permite recibir o enviar mensajes al resto del sistema IoT.
    mqtt_client = create_mqtt_client()

    # El watcher vigila el archivo que genera Asterisk.
    # Cuando detecta un archivo estable, ejecuta la función asíncrona process_file.
    # Se usa lambda para encapsular la llamada a asyncio.run.
    watcher = FileWatcher(
        path=RECORDING_PATH,
        callback=lambda p: asyncio.run(process_file(p))
    )

    print("[MAIN] Servicio iniciado. Vigilando grabaciones de audio.")
    watcher.start()


if __name__ == "__main__":
    # Como es un microservicio Docker, el main se ejecuta al arrancar el contenedor.
    main()
