import os
import json
import paho.mqtt.client as mqtt
import mysql.connector
from datetime import datetime

# --- Configuración de la base de datos ---
db_cfg = {
    "host": os.getenv("DB_HOST", "mariadb-service"),
    "user": os.getenv("DB_USER", "tfg"),
    "password": os.getenv("DB_PASS", "tfgpass"),
    "database": os.getenv("DB_NAME", "devices_db")
}

# --- Configuración del broker MQTT ---
mqtt_cfg = {
    "host": os.getenv("MQTT_HOST", "mosquitto"),
    "port": int(os.getenv("MQTT_PORT", 1883)),
    "user": os.getenv("MQTT_USER", "admin"),
    "password": os.getenv("MQTT_PASS", "admin1234"),
    "topics": [("announce/#", 0), ("update/#", 0)]
}

# --- Conexión a la DB ---
def connect_db():
    conn = mysql.connector.connect(**db_cfg)
    print("[DB] Conectado correctamente a MariaDB.")
    return conn

db = connect_db()
cursor = db.cursor()

# --- Memoria temporal para limpiar solo una vez por dispositivo ---
seen_devices = set()

def clear_device(device):
    """Elimina todos los sensores y actuadores de un dispositivo."""
    cursor.execute("DELETE FROM sensors WHERE device_name=%s", (device,))
    cursor.execute("DELETE FROM actuators WHERE device_name=%s", (device,))
    cursor.execute("""
        INSERT INTO devices (device_name, last_seen)
        VALUES (%s, NOW())
        ON DUPLICATE KEY UPDATE last_seen=NOW()
    """, (device,))
    db.commit()
    print(f"[DB] Limpieza completa del dispositivo {device}")

def save_entity(device, kind, idx, payload):
    """Inserta o actualiza sensores/actuadores."""
    table = "sensors" if kind == "sensor" else "actuators"
    cursor.execute(f"""
        INSERT INTO {table} (id, device_name, name, location, state)
        VALUES (%s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            name=VALUES(name),
            location=VALUES(location),
            state=VALUES(state)
    """, (idx, device, payload.get("name"), payload.get("location"), payload.get("state")))
    db.commit()
    print(f"[DB] {device}/{kind}/{idx} → {payload['state']}")

def update_state(device, kind, idx, payload):
    """Solo actualiza el estado de un sensor/actuador."""
    table = "sensors" if kind == "sensor" else "actuators"
    cursor.execute(f"""
        UPDATE {table}
        SET state=%s
        WHERE id=%s AND device_name=%s
    """, (payload.get("state"), idx, device))
    cursor.execute("UPDATE devices SET last_seen=NOW() WHERE device_name=%s", (device,))
    db.commit()
    print(f"[DB] {device}/{kind}/{idx} actualizado → {payload['state']}")

# --- Callback principal ---
def on_message(client, userdata, msg):
    topic = msg.topic
    parts = topic.split("/")  # Ejemplo: announce/esp32_sala/sensor/0
    if len(parts) < 4:
        return

    mode, device, kind, idx = parts[:4]

    try:
        payload = json.loads(msg.payload.decode())
    except json.JSONDecodeError:
        print(f"[WARN] JSON inválido en {topic}")
        return

    # --- Anuncios: se limpian los datos del dispositivo una sola vez ---
    if mode == "announce":
        if device not in seen_devices:
            clear_device(device)
            seen_devices.add(device)
        save_entity(device, kind, int(idx), payload)

    # --- Actualizaciones en tiempo real ---
    elif mode == "update":
        update_state(device, kind, int(idx), payload)

# --- Configuración MQTT ---
def setup_mqtt():
    client = mqtt.Client()
    client.username_pw_set(mqtt_cfg["user"], mqtt_cfg["password"])
    client.on_message = on_message
    client.connect(mqtt_cfg["host"], mqtt_cfg["port"], 60)

    for topic, qos in mqtt_cfg["topics"]:
        client.subscribe(topic, qos)
        print(f"[MQTT] Subscrito a {topic}")

    return client

client = setup_mqtt()
print("[LISTENER] Esperando mensajes de announce/update...")
client.loop_forever()
