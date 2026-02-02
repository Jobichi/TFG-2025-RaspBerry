# ============================
# stt-service/main.py
# ============================
import asyncio
import os
from audio.file_watcher import FileWatcher
from audio.factory import AudioProcessorFactory
from stt.factory import STTFactory
from mqtt.mqtt_client import create_mqtt_client, publish_transcription
from config import RECORDING_PATH


async def process_file(path: str, mqtt_client):
    processor = AudioProcessorFactory.get_processor(path)
    processor.load(path)
    pcm_data = processor.as_pcm()

    stt_client = STTFactory.get_client()
    text = await stt_client.process_audio(pcm_data)

    print("[STT] Transcripción final:", text)
    publish_transcription(mqtt_client, text)


def main():
    mqtt_client = create_mqtt_client()

    armed = False

    def guarded_callback(p: str):
        nonlocal armed

        if not armed:
            # Primer evento tras arranque: no procesar.
            armed = True
            print("[MAIN] Watcher armado. Se ignora el primer evento tras reinicio.")
            return

        asyncio.run(process_file(p, mqtt_client))

    watcher = FileWatcher(
        path=RECORDING_PATH,
        callback=guarded_callback
    )

    print("[MAIN] Servicio de transcripción iniciado. Vigilando grabaciones.")
    watcher.start()


if __name__ == "__main__":
    main()