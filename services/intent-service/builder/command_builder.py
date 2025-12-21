from typing import Optional
from config import logger
from nlp.intent_parser import Intent


class CommandBuilder:
    """
    Traduce (intent + target) a un comando SET válido para el mqtt-router.
    """

    # Mapas de conversión intención → boolean
    ACTUATOR_INTENTS = {
        Intent.ON: True,
        Intent.OFF: False,
    }

    SENSOR_INTENTS = {
        Intent.ENABLE: True,
        Intent.DISABLE: False,
    }

    @staticmethod
    def build(intent: Intent, target: dict) -> Optional[dict]:
        """
        Devuelve el payload final para system/set/intent-service.

        target esperado:
        {
            "device": "...",
            "type": "sensor|actuator",
            "id": <int>,
            "data": {...}
        }
        """

        if not intent or not target:
            logger.warning("[BUILDER] Intent o target vacío")
            return None

        device = target.get("device")
        comp_type = target.get("type")
        comp_id = target.get("id")

        if device is None or comp_type is None or comp_id is None:
            logger.warning(f"[BUILDER] Target incompleto: {target}")
            return None

        # ==========================
        # ACTUADORES
        # ==========================
        if comp_type == "actuator":
            if intent not in CommandBuilder.ACTUATOR_INTENTS:
                logger.warning(
                    f"[BUILDER] Intent '{intent.value}' no válido para actuador"
                )
                return None

            command = {
                "device": device,
                "type": "actuator",
                "id": comp_id,
                "state": CommandBuilder.ACTUATOR_INTENTS[intent]
            }

            logger.info(f"[BUILDER] Comando actuador generado: {command}")
            return command

        # ==========================
        # SENSORES
        # ==========================
        if comp_type == "sensor":
            if intent not in CommandBuilder.SENSOR_INTENTS:
                logger.warning(
                    f"[BUILDER] Intent '{intent.value}' no válido para sensor"
                )
                return None

            command = {
                "device": device,
                "type": "sensor",
                "id": comp_id,
                "enable": CommandBuilder.SENSOR_INTENTS[intent]
            }

            logger.info(f"[BUILDER] Comando sensor generado: {command}")
            return command

        # ==========================
        # DESCONOCIDO
        # ==========================
        logger.warning(f"[BUILDER] Tipo de componente desconocido: {comp_type}")
        return None
