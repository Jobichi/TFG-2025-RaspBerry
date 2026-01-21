from typing import Optional
from config import logger
from nlp.intent_parser import Intent


class CommandBuilder:
    """
    Traduce (intent + target) a un comando SET válido para el mqtt-router.

    Compatibilidad:
    - Actuadores ON/OFF -> {"state": bool}
    - Sensores ENABLE/DISABLE -> {"enable": bool}
    - Actuadores de movimiento (persianas/puertas) -> {"command": "OPEN|CLOSE|STOP", "speed": int}
    """

    # Mapas de conversión intención → boolean (compatibilidad con actuadores simples)
    ACTUATOR_INTENTS = {
        Intent.ON: True,
        Intent.OFF: False,
    }

    # Mapas de conversión intención → enable boolean (sensores)
    SENSOR_INTENTS = {
        Intent.ENABLE: True,
        Intent.DISABLE: False,
    }

    # Intenciones de movimiento (nuevo)
    MOTION_ACTUATOR_INTENTS = {
        Intent.FORWARD: "OPEN",
        Intent.BACKWARD: "CLOSE",
        Intent.STOP: "STOP",
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
            # 1) Actuadores simples ON/OFF
            if intent in CommandBuilder.ACTUATOR_INTENTS:
                command = {
                    "device": device,
                    "type": "actuator",
                    "id": comp_id,
                    "state": CommandBuilder.ACTUATOR_INTENTS[intent],
                }
                logger.info(f"[BUILDER] Comando actuador generado: {command}")
                return command

            # 2) Actuadores de movimiento (persianas/puertas)
            if intent in CommandBuilder.MOTION_ACTUATOR_INTENTS:
                cmd = CommandBuilder.MOTION_ACTUATOR_INTENTS[intent]

                command = {
                    "device": device,
                    "type": "actuator",
                    "id": comp_id,
                    "command": cmd,
                }

                # Para OPEN/CLOSE podemos adjuntar velocidad por defecto
                # (0-100). STOP no la necesita.
                if cmd in ("OPEN", "CLOSE"):
                    command["speed"] = 100

                logger.info(f"[BUILDER] Comando actuador (movimiento) generado: {command}")
                return command

            logger.warning(f"[BUILDER] Intent '{intent.value}' no válido para actuador")
            return None

        # ==========================
        # SENSORES
        # ==========================
        if comp_type == "sensor":
            if intent not in CommandBuilder.SENSOR_INTENTS:
                logger.warning(f"[BUILDER] Intent '{intent.value}' no válido para sensor")
                return None

            command = {
                "device": device,
                "type": "sensor",
                "id": comp_id,
                "enable": CommandBuilder.SENSOR_INTENTS[intent],
            }

            logger.info(f"[BUILDER] Comando sensor generado: {command}")
            return command

        # ==========================
        # DESCONOCIDO
        # ==========================
        logger.warning(f"[BUILDER] Tipo de componente desconocido: {comp_type}")
        return None
