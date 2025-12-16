from abc import ABC, abstractmethod

class STTClient(ABC):
    """Interfaz para clientes de transcripción.
    Toda clase que procese audio y devuelva texto debe implementar este contrato."""

    @classmethod
    @abstractmethod
    async def process_audio(self, pcm_data: bytes) -> str:
        """
        Procesa audio PCM y devuelve texto reconocido.

        :param pcm_data: Audio en formato PCM 16-bit.
        :return: Cadena de texto con la transcripción final.
        """
        raise NotImplementedError      