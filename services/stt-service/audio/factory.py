from wav_processing import WavProccesor
from mp3_procesing import Mp3Processor

class AudioProcessorFactory:
    """Devuelve el procesador adeucado según la extensión del archivo de audio."""

    registry = {
        ".wav": WavProccesor,
        ".wav16": WavProccesor,
        ".mp3": Mp3Processor,
    }

    @staticmethod
    def get_processor(path):
        for ext, cls in AudioProcessorFactory.registry.items():
            if path.lower().endswith(ext):
                return cls()
            
        raise ValueError(f"Formato no soportado para el archivo: {path}")
    
