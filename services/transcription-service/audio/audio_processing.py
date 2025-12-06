from abc import ABC, abstractmethod
class AudioProcessor(ABC):
    """Interfaz que define los métodos a implementar por un procesador de audio."""

    @classmethod
    @abstractmethod
    def load(self, path):
        """Carga el archivo de audio y devuelve los datos en crudo"""
        pass

    @classmethod
    @abstractmethod
    def get_sample_rate(self):
        """Devuelve la frecuencia de muestreo."""
        pass

    @classmethod
    @abstractmethod
    def get_channels(self):
        """Devuelve el número de canales."""
        pass

    @classmethod
    @abstractmethod
    def as_pcm(self):
        """Devuelve el audio convertido a PCM crudo (bytes)."""
        pass