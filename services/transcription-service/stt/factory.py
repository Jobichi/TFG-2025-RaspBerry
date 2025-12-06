# factory.py
# Factoría para seleccionar dinámicamente el backend STT.
#
# Permite cambiar el modelo de reconocimiento sin modificar la lógica del
# servicio de transcripción. Solo requiere cambiar la variable de entorno
# STT_PROVIDER para utilizar Vosk, Whisper, Deepgram u otro proveedor futuro.

import os

from stt.vosk_client import VoskClient
# from stt.whisper_client import WhisperClient  # Ejemplo para futuro


class STTFactory:
    """
    Factoría que genera instancias de clientes STT según configuración.
    """

    @staticmethod
    def get_client():
        """
        Devuelve una implementación concreta de STTClient según la variable STT_PROVIDER.

        Proveedores soportados:
        - vosk     → VoskClient
        - whisper  → WhisperClient (cuando lo implementes)

        :return: Instancia de un cliente STT.
        """
        provider = os.getenv("STT_PROVIDER", "vosk").lower()

        if provider == "vosk":
            print("[STT] Usando backend Vosk")
            return VoskClient()

        # if provider == "whisper":
        #     print("[STT] Usando backend Whisper")
        #     return WhisperClient()

        raise ValueError(f"Proveedor STT no soportado: {provider}")
