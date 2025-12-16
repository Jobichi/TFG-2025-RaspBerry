from typing import Optional, Tuple
from config import logger
from memory.snapshot import Snapshot
from nlp.intent_parser import Intent
from rapidfuzz import fuzz


class TargetResolver:
    """
    Resuelve el objetivo (sensor o actuador) a partir del texto,
    la intención detectada y el snapshot del sistema.
    """

    def __init__(self, snapshot: Snapshot):
        self.snapshot = snapshot

    # ==========================================================
    #  API PRINCIPAL
    # ==========================================================
    def resolve(self, text: str, intent: Intent) -> Optional[dict]:
        if not text or intent == Intent.UNKNOWN:
            return None

        text_norm = text.lower()

        if intent in (Intent.ON, Intent.OFF):
            return self._resolve_component(text_norm, "actuator")

        if intent in (Intent.ENABLE, Intent.DISABLE):
            return self._resolve_component(text_norm, "sensor")

        return None

    # ==========================================================
    #  RESOLUCIÓN GENÉRICA (SENSOR / ACTUADOR)
    # ==========================================================
    def _resolve_component(self, text: str, comp_type: str) -> Optional[dict]:
        """
        Resuelve sensores o actuadores con estrategia:
        1. exacto (nombre + localización)
        2. exacto (nombre)
        3. exacto (localización)
        4. fuzzy matching global
        """

        # ---------- Intento 1: nombre + localización ----------
        for device, comps in self.snapshot.devices.items():
            for cid, comp in comps[f"{comp_type}s"].items():
                name = str(comp.get("name", "")).lower()
                location = str(comp.get("location", "")).lower()

                if name and location and name in text and location in text:
                    return self._build_target(device, comp_type, cid, comp)

        # ---------- Intento 2: solo nombre ----------
        for device, comps in self.snapshot.devices.items():
            for cid, comp in comps[f"{comp_type}s"].items():
                name = str(comp.get("name", "")).lower()
                if name and name in text:
                    return self._build_target(device, comp_type, cid, comp)

        # ---------- Intento 3: solo localización ----------
        for device, comps in self.snapshot.devices.items():
            for cid, comp in comps[f"{comp_type}s"].items():
                location = str(comp.get("location", "")).lower()
                if location and location in text:
                    return self._build_target(device, comp_type, cid, comp)

        # ---------- Intento 4: fuzzy matching ----------
        match = self._fuzzy_match_global(text, comp_type, threshold=85)

        if match:
            device, cid, comp = match
            logger.info(
                f"[TARGET] Fuzzy match {comp_type} -> {device}/{cid}"
            )
            return self._build_target(device, comp_type, cid, comp)

        logger.warning(
            f"[TARGET] No se pudo resolver {comp_type} para texto: '{text}'"
        )
        return None

    # ==========================================================
    #  FUZZY MATCHING GLOBAL (SEGURO)
    # ==========================================================
    def _fuzzy_match_global(
        self,
        text: str,
        comp_type: str,
        threshold: int = 85
    ) -> Optional[Tuple[str, int, dict]]:
        """
        Aplica fuzzy matching sobre todos los dispositivos.
        Devuelve solo si hay un único ganador claro.
        """

        best = None
        best_score = threshold
        tie = False

        for device, comps in self.snapshot.devices.items():
            for cid, comp in comps[f"{comp_type}s"].items():
                name = str(comp.get("name", "")).lower()
                location = str(comp.get("location", "")).lower()

                score_name = fuzz.partial_ratio(text, name) if name else 0
                score_loc = fuzz.partial_ratio(text, location) if location else 0
                score = max(score_name, score_loc)

                if score > best_score:
                    best_score = score
                    best = (device, cid, comp)
                    tie = False
                elif score == best_score:
                    tie = True

        if best and not tie:
            return best

        return None

    # ==========================================================
    #  UTILIDAD
    # ==========================================================
    @staticmethod
    def _build_target(
        device: str,
        comp_type: str,
        comp_id: int,
        data: dict
    ) -> dict:
        logger.info(
            f"[TARGET] Objetivo resuelto -> {comp_type} {device}/{comp_id}"
        )
        return {
            "device": device,
            "type": comp_type,
            "id": comp_id,
            "data": data
        }
