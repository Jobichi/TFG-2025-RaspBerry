# stt/vosk_engine.py
# Motor de reconocimiento Vosk aislado del servidor WebSocket.

from vosk import Model, KaldiRecognizer
from config import MODEL_PATH, SAMPLE_RATE


class VoskEngine:
    """
    Encapsula el modelo Vosk y ofrece una interfaz simple
    para crear nuevas sesiones de reconocimiento.
    """

    def __init__(self):
        print(f"[VOSK] Cargando modelo desde: {MODEL_PATH}")
        self.model = Model(MODEL_PATH)
        print("[VOSK] Modelo cargado correctamente.")

    def create_session(self):
        """
        Devuelve un reconocedor KaldiRecognizer listo para recibir audio.
        """
        return KaldiRecognizer(self.model, SAMPLE_RATE)
