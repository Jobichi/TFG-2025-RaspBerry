import mysql.connector
import os
import time

# Variables de entorno (ajústalas según tu .env)
MYSQL_HOST = os.getenv("MYSQL_HOST", "mariadb-service")
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "root")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "tfg_db")

def get_connection():
    return mysql.connector.connect(
        host=MYSQL_HOST,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DATABASE
    )

def get_devices():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM actuators;")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows

if __name__ == "__main__":
    print("[DB-TEST] Esperando a que la base de datos esté lista...")
    time.sleep(5)  # espera inicial por si MariaDB tarda en arrancar

    try:
        devices = get_devices()
        print(f"[DB-TEST] Conexión exitosa. {len(devices)} dispositivos encontrados:")
        for d in devices:
            print(f"  - {d}")
    except Exception as e:
        print("[DB-TEST] ❌ Error de conexión o consulta:")
        print(e)
