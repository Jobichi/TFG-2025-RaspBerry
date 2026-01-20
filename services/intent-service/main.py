from config import (
    logger,
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


        # Snapshot se construye de forma reactiva a partir de:
        # - system/response/<service>/... (volcado inicial)
        # - system/notify/+/announce (eventos incrementales)

    # ==========================================================
    #  ARRANQUE
    # ==========================================================
    def start(self):
        logger.info("[INTENT] Iniciando intent-service")

        # Conectar MQTT
        self.mqtt.connect()

        # Entrar en loop MQTT (bloqueante)
        self.mqtt.loop_forever()

    # ==========================================================
    #  CALLBACKS MQTT
    # ==========================================================
    def on_router_response(self, topic: str, payload: dict):
        self.snapshot.ingest(topic, payload)

        # El snapshot se considera listo cuando es "usable".
        # (No se usa timeout para marcarlo como completo.)
        if self.snapshot.is_ready():
            return

        if self.snapshot.is_usable():
            logger.info("[INTENT] Snapshot usable detectado (reactivo)")
            # No forzamos "completo"; solo habilitamos el servicio.
            self.snapshot.mark_ready("respuesta router")

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
