import wave
from audio.audio_processing import AudioProcessor

class WavProccesor(AudioProcessor):
    """Procesador de archivos .wav"""

    def __init__(self):
        self.sample_rate = None
        self.channels = None
        self.frames = None
        self.pcm = None

    def load(self, path):
        with wave.open(path, "rb") as wav:
            self.sample_rate = wav.getframerate()
            self.channels = wav.getnchannels()
            n_frames = wav.getnframes()
            self.pcm = wav.readframes(n_frames)

    def get_sample_rate(self):
        return self.sample_rate
    
    def get_channels(self):
        return self.channels
    
    def as_pcm(self):
        return self.pcm
    
    