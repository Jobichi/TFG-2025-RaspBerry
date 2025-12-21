import time
import threading

from config import (
    logger,
    SNAPSHOT_TIMEOUT_S,
    REQUIRE_SNAPSHOT
)
from mqtt.mqtt_client import MQTTClient
from memory.snapshot import Snapshot
from nlp.intent_parser import parse_intent, Intent
from nlp.target_resolver import TargetResolver
from builder.command_builder import CommandBuilder


class IntentService:
    """
    Orquestador principal del intent-service.
    """

    def __init__(self):
        self.snapshot = Snapshot()
        self.mqtt = MQTTClient()

        # Inyectar callbacks MQTT
        self.mqtt.on_response_cb = self.on_router_response
        self.mqtt.on_transcription_cb = self.on_transcription
        self.resolver = TargetResolver(self.snapshot)
        self.builder = CommandBuilder()


        self._snapshot_timer = None

    # ==========================================================
    #  ARRANQUE
    # ==========================================================
    def start(self):
        logger.info("[INTENT] Iniciando intent-service")

        # Conectar MQTT
        self.mqtt.connect()

        # Arrancar temporizador de snapshot
        self._start_snapshot_timer()

        # Entrar en loop MQTT (bloqueante)
        self.mqtt.loop_forever()

    def _start_snapshot_timer(self):
        """
        Lanza un temporizador para marcar el snapshot como completo
        tras SNAPSHOT_TIMEOUT_S segundos.
        """
        if SNAPSHOT_TIMEOUT_S <= 0:
            logger.warning("[INTENT] SNAPSHOT_TIMEOUT_S <= 0, snapshot inmediato")
            self.snapshot.mark_complete()
            return

        logger.info(
            f"[INTENT] Esperando snapshot ({SNAPSHOT_TIMEOUT_S}s)"
        )

        self._snapshot_timer = threading.Timer(
            SNAPSHOT_TIMEOUT_S,
            self._on_snapshot_timeout
        )
        self._snapshot_timer.daemon = True
        self._snapshot_timer.start()

    def _on_snapshot_timeout(self):
        """
        Se ejecuta cuando expira el tiempo de espera del snapshot.
        """
        if not self.snapshot.is_ready():
            logger.info(
                "[INTENT] Timeout alcanzado. Marcando snapshot como completo"
            )
            self.snapshot.mark_complete()

    # ==========================================================
    #  CALLBACKS MQTT
    # ==========================================================
    def on_router_response(self, topic: str, payload: dict):
        self.snapshot.ingest(topic, payload)

        # Marcar snapshot como listo en cuanto sea usable
        if not self.snapshot.is_ready() and self.snapshot.is_usable():
            logger.info("[INTENT] Snapshot usable detectado")
            self.snapshot.mark_complete()

    def on_transcription(self, payload: dict):
        text = payload.get("text")

        if not text:
            return

        if REQUIRE_SNAPSHOT and not self.snapshot.is_ready():
            logger.warning(
                f"[INTENT] Transcripción ignorada (snapshot no listo): '{text}'"
            )
            return

        # 1. Intent
        intent = parse_intent(text)
        logger.info(f"[INTENT] Texto: '{text}' -> Intent: {intent.value}")

        if intent == Intent.UNKNOWN:
            logger.warning(
                f"[INTENT] No se pudo determinar la intención: '{text}'"
            )
            return

        # 2. Target
        target = self.resolver.resolve(text, intent)
        if not target:
            logger.warning(
                f"[INTENT] No se pudo resolver objetivo para: '{text}'"
            )
            return

        # 3. Command
        command = self.builder.build(intent, target)
        if not command:
            logger.warning(
                f"[INTENT] No se pudo construir comando para: '{text}'"
            )
            return

        # 4. Publicar SET
        self.mqtt.publish_set(command)
        logger.info(
            f"[INTENT] Comando enviado al router: {command}"
        )


    # ==========================================================
    #  DEBUG
    # ==========================================================
    def dump_snapshot(self):
        logger.debug(f"[INTENT] Snapshot actual: {self.snapshot.dump()}")


# ==========================================================
#  ENTRYPOINT
# ==========================================================
if __name__ == "__main__":
    service = IntentService()
    service.start()
