from pydub import AudioSegment
from audio_processing import AudioProcessor

class Mp3Processor(AudioProcessor):
    """Procesador de archivos MP3."""

    def __init__(self):
        self.audio = None

    def load(self, path):
        self.audio = AudioSegment.from_mp3(path)
        self.audio = self.audio.set_channels(1).set_frame_rate(16000)

    def get_sample_rate(self):
        return self.audio.frame_rate
    
    def get_channels(self):
        return self.audio.channels
    
    def as_pcm(self):
        return self.audio.raw_data