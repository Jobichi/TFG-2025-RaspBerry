import os, json
import paho.mqtt.client as mqtt
import mysql.connector

# --- Configuración DB ---
db_cfg = {
    "host": os.getenv("DB_HOST", "mariadb-service"),
    "user": os.getenv("DB_USER", "tfg"),
    "password": os.getenv("DB_PASS", "tfgpass"),
    "database": os.getenv("DB_NAME", "devices_db")
}

# --- Configuración MQTT ---
mqtt_cfg = {
    "host": os.getenv("MQTT_HOST", "mosquitto"),
    "port": int(os.getenv("MQTT_PORT", 1883)),
    "user": os.getenv("MQTT_USER", "admin"),
    "password": os.getenv("MQTT_PASS", "admin1234"),
    "topics": [("announce/#", 0), ("update/#", 0)]
}

# --- Conexión DB ---
def connect_db():
    conn = mysql.connector.connect(**db_cfg)
    print("[DB] Conectado a MariaDB.")
    return conn

db = connect_db()
cursor = db.cursor()

def ensure_device(device):
    cursor.execute("""
        INSERT INTO devices (device_name, last_seen)
        VALUES (%s, NOW())
        ON DUPLICATE KEY UPDATE last_seen = NOW()
    """, (device,))
    db.commit()

def save_entity(device, kind, idx, payload, mode):
    ensure_device(device)
    table = "sensors" if kind == "sensor" else "actuators"

    if mode == "announce":
        cursor.execute(f"""
            INSERT INTO {table} (id, device_name, name, location, state)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                name=VALUES(name),
                location=VALUES(location),
                state=VALUES(state)
        """, (idx, device, payload["name"], payload["location"], payload["state"]))
        print(f"[DB] {device}/{kind}/{idx} registrado → {payload}")

    elif mode == "update":
        cursor.execute(f"""
            UPDATE {table}
            SET state=%s
            WHERE id=%s AND device_name=%s
        """, (payload["state"], idx, device))
        print(f"[DB] {device}/{kind}/{idx} actualizado → {payload['state']}")

    db.commit()

# --- Callback MQTT ---
def on_message(client, userdata, msg):
    topic = msg.topic
    parts = topic.split("/")  # ej: announce/device/sensor/id
    if len(parts) < 4:
        print(f"[WARN] Topic no esperado: {topic}")
        return

    mode, device, kind, idx = parts[:4]
    try:
        payload = json.loads(msg.payload.decode())
    except json.JSONDecodeError:
        print(f"[WARN] JSON inválido: {msg.payload}")
        return

    save_entity(device, kind, int(idx), payload, mode)

# --- MQTT Setup ---
def setup_mqtt():
    client = mqtt.Client()
    client.username_pw_set(mqtt_cfg["user"], mqtt_cfg["password"])
    client.on_message = on_message
    client.connect(mqtt_cfg["host"], mqtt_cfg["port"], 60)
    for topic, qos in mqtt_cfg["topics"]:
        client.subscribe(topic, qos)
        print(f"[MQTT] Subscrito a: {topic}")
    return client

client = setup_mqtt()
print("[LISTENER] Esperando mensajes...")
client.loop_forever()
