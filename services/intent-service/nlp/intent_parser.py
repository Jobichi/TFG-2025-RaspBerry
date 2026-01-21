import re
from enum import Enum
from typing import List, Tuple
from config import logger


class Intent(Enum):
    """
    Intenciones soportadas por el sistema.
    """
    ON = "on"
    OFF = "off"
    ENABLE = "enable"
    DISABLE = "disable"
    FORWARD = "forward"     # abrir/subir (persiana/puerta)
    BACKWARD = "backward"   # cerrar/bajar (persiana/puerta)
    STOP = "stop"
    UNKNOWN = "unknown"


# Patrones en orden de prioridad (STOP primero para evitar ambigüedades tipo "para de abrir")
# Usamos raíces (\w*) para cubrir conjugaciones: "levantan", "levantar", "levanta", etc.
INTENT_PATTERNS: List[Tuple[Intent, List[str]]] = [
    (Intent.STOP, [
        r"\bpar\w*\b",        # para, parar, paren...
        r"\bdeten\w*\b",      # detén, detener, detengan...
        r"\balto\b",
        r"\bstop\b",
    ]),
    (Intent.FORWARD, [
        r"\babr\w*\b",        # abre, abrir, abran...
        r"\blevant\w*\b",     # levanta, levantar, levantan...
        r"\bsub\w*\b",        # sube, subir, suban...
    ]),
    (Intent.BACKWARD, [
        r"\bcierr\w*\b",      # cierra, cerrar, cierran...
        r"\bcerr\w*\b",       # cerrar (fallback)
        r"\bbaj\w*\b",        # baja, bajar, bajan...
    ]),
    (Intent.ON, [
        r"\benciend\w*\b",    # enciende, encender...
        r"\bactiv\w*\b",      # activa, activar...
        r"\bprend\w*\b",      # prende, prender...
    ]),
    (Intent.OFF, [
        r"\bapag\w*\b",       # apaga, apagar...
        r"\bdesactiv\w*\b",   # desactiva, desactivar...
    ]),
    (Intent.ENABLE, [
        r"\bhabilit\w*\b",    # habilita, habilitar...
    ]),
    (Intent.DISABLE, [
        r"\bdeshabilit\w*\b", # deshabilita, deshabilitar...
        r"\bin\w*habilit\w*\b",  # inhabilita, inhabilitar...
    ]),
]


def parse_intent(text: str) -> Intent:
    """
    Analiza el texto plano y devuelve la intención detectada.

    Implementación rule-based:
    - Determinista
    - Explicable
    - Fácil de extender

    Notas:
    - STOP tiene prioridad frente a FORWARD/BACKWARD (p.ej. "para de abrir").
    - Se usan patrones con raíces para cubrir conjugaciones habituales en español.
    """
    if not text:
        return Intent.UNKNOWN

    text_norm = text.lower().strip()

    for intent, patterns in INTENT_PATTERNS:
        for pattern in patterns:
            if re.search(pattern, text_norm):
                logger.debug(
                    f"[INTENT_PARSER] Detectada intención '{intent.value}' por patrón '{pattern}'"
                )
                return intent

    logger.debug(f"[INTENT_PARSER] No se detectó intención en texto: '{text_norm}'")
    return Intent.UNKNOWN
