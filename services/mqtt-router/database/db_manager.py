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
            self.conn = mysql.connector.connect(**DB_CFG)
            self.cursor = self.conn.cursor(dictionary=True)
            logger.info("[MQTT-DB] Conexión establecida.")

        except Error as e:
            logger.error(f"[MQTT-DB] Error de conexión: {e}")

    def execute(self, query, params=None, commit=False):
        try:
            self.cursor.execute(query, params)
            if commit:
                self.conn.commit()
            return self.cursor.fetchall() if self.cursor.with_rows else []

        except Error as e:
            logger.error(f"[MQTT-DB] Error ejecutando query: {e}")
            self.connect()

    def close(self):
        if self.conn:
            self.conn.close()
            logger.info("[MQTT-DB] Conexión cerrada.")
