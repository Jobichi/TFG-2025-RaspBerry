# ============================
# stt-service/stt/factory.py
# ============================
import os
from stt.vosk_client import VoskClient
# from stt.whisper_client import WhisperClient  # Para futuro


class STTFactory:
    """Factoría que genera instancias de clientes STT según configuración."""

    @staticmethod
    def get_client():
        provider = os.getenv("STT_PROVIDER", "vosk").lower()

        if provider == "vosk":
            print("[STT] Usando backend Vosk")
            return VoskClient()

        # if provider == "whisper":
        #     print("[STT] Usando backend Whisper")
        #     return WhisperClient()

        raise ValueError(f"Proveedor STT no soportado: {provider}")
