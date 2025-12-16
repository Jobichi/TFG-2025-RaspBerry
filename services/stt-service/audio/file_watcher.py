import time
import os

class FileWatcher:
    
    def __init__(self, path, callback, interval = 2):
        self.path = path
        self.callback = callback
        self.interval = interval
        self.last_size = 0

    def is_stable(self):
        """Comprueba si se ha modificado el archivo respesto a su valor de tamaño anterior."""
        size1 = os.path.getsize(self.path)
        time.sleep(1)
        size2 = os.path.getsize(self.path)
        return size1 == size2 and size1 > 0
    
    def start(self):
        """Inicialización del bucle para comprobación del archivo"""
        print(f"[WATCHER] Vigilando {self.path}")

        while True:
            if os.path.exists(self.path):
                new_size = os.path.getsize(self.path)
                if new_size != self.last_size and self.is_stable():
                    print(f"[WATCHER] Archivo listo para procesar")
                    self.callback(self.path)
                    self.last_size = new_size
            time.sleep(self.interval)