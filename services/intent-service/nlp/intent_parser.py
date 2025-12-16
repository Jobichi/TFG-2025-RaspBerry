from enum import Enum
from typing import Optional
from config import logger


class Intent(Enum):
    """
    Intenciones soportadas por el sistema.
    """
    ON = "on"
    OFF = "off"
    ENABLE = "enable"
    DISABLE = "disable"
    UNKNOWN = "unknown"


# Palabras clave asociadas a cada intención
INTENT_KEYWORDS = {
    Intent.ON: [
        "enciende",
        "encender",
        "activa",
        "activar",
        "prende",
        "prender",
    ],
    Intent.OFF: [
        "apaga",
        "apagar",
        "desactiva",
        "desactivar",
    ],
    Intent.ENABLE: [
        "habilita",
        "habilitar",
    ],
    Intent.DISABLE: [
        "deshabilita",
        "deshabilitar",
        "inhabilita",
    ],
}


def parse_intent(text: str) -> Intent:
    """
    Analiza el texto plano y devuelve la intención detectada.

    Implementación rule-based:
    - Determinista
    - Explicable
    - Fácil de extender
    """

    if not text:
        return Intent.UNKNOWN

    text_norm = text.lower().strip()

    for intent, keywords in INTENT_KEYWORDS.items():
        for kw in keywords:
            if kw in text_norm:
                logger.debug(
                    f"[INTENT_PARSER] Detectada intención '{intent.value}' por keyword '{kw}'"
                )
                return intent

    logger.debug(
        f"[INTENT_PARSER] No se detectó intención en texto: '{text_norm}'"
    )
    return Intent.UNKNOWN
