import mysql.connector
from mysql.connector import Error
from config import DB_CFG, logger


class DBManager:
    def __init__(self):
        self.conn = None
        self.cursor = None
        self.connect()

    def connect(self):
        try:
            if self.conn:
                try:
                    self.conn.close()
                except:
                    pass

            self.conn = mysql.connector.connect(
                connection_timeout=5,
                **DB_CFG
            )
            self.cursor = self.conn.cursor(dictionary=True)
            logger.info("[MQTT-DB] Conexión establecida correctamente.")

        except Error as e:
            logger.error(f"[MQTT-DB] Error estableciendo conexión: {e}")
            self.conn = None
            self.cursor = None

    def ensure_connection(self):
        """Verifica si la conexión sigue viva, y la restaura si no."""
        try:
            if self.conn is None or not self.conn.is_connected():
                logger.warning("[MQTT-DB] Conexión perdida. Reintentando...")
                self.connect()
        except:
            logger.warning("[MQTT-DB] Estado de conexión inválido. Reintentando...")
            self.connect()

    def execute(self, query, params=None, commit=False):
        """Ejecuta consultas con auto-reconnect y doble intento."""

        self.ensure_connection()

        try:
            self.cursor.execute(query, params)
            if commit:
                self.conn.commit()
            return self.cursor.fetchall() if self.cursor.with_rows else []

        except Error as e:
            logger.error(f"[MQTT-DB] Error en query: {e}. Reintentando...")

            # === Reintento ===
            self.connect()
            try:
                self.cursor.execute(query, params)
                if commit:
                    self.conn.commit()
                return self.cursor.fetchall() if self.cursor.with_rows else []
            except Error as e2:
                logger.error(f"[MQTT-DB] Falla persistente ejecutando query: {e2}")
                return None  # Señal clara al handler

    def close(self):
        if self.conn:
            try:
                self.conn.close()
                logger.info("[MQTT-DB] Conexión cerrada.")
            except:
                pass
