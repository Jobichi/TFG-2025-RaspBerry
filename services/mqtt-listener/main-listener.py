import os
import json
import paho.mqtt.client as mqtt
import mysql.connector
from datetime import datetime, date

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
    "topics": [
        ("announce/#", 0),
        ("update/#", 0),
        ("alert/#", 0),
        ("system/get/#", 0),
    ]
}

# --- Serializador seguro para JSON ---
def safe_json_dumps(obj):
    def default(o):
        if isinstance(o, (datetime, date)):
            return o.strftime("%Y-%m-%d %H:%M:%S")
        raise TypeError(f"Type {type(o)} not serializable")
    return json.dumps(obj, default=default)

# --- Conexión a la DB ---
def connect_db():
    conn = mysql.connector.connect(**db_cfg)
    print("[DB] Conectado correctamente a MariaDB.")
    return conn

db = connect_db()
cursor = db.cursor(dictionary=True)
seen_devices = set()

# --- Funciones de gestión ---
def clear_device(device):
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
    print(f"[DB] {device}/{kind}/{idx} -> {payload['state']}")

def update_state(device, kind, idx, payload):
    table = "sensors" if kind == "sensor" else "actuators"
    cursor.execute(f"""
        UPDATE {table}
        SET state=%s
        WHERE id=%s AND device_name=%s
    """, (payload.get("state"), idx, device))
    cursor.execute("UPDATE devices SET last_seen=NOW() WHERE device_name=%s", (device,))
    db.commit()
    print(f"[DB] {device}/{kind}/{idx} actualizado -> {payload['state']}")

def save_alert(device, kind, idx, payload, mqtt_client=None):
    """Guarda una alerta en BBDD y la notifica inmediatamente."""
    cursor.execute("""
        INSERT INTO alerts (device_name, component_name, location, state, message)
        VALUES (%s, %s, %s, %s, %s)
    """, (
        device,
        payload.get("name", f"{kind}_{idx}"),
        payload.get("location"),
        payload.get("state"),
        payload.get("message", None)
    ))
    db.commit()

    print(f"[ALERT] {device}/{kind}/{idx} -> {payload.get('state')}")

    if mqtt_client:
        alert_msg = {
            "device": device,
            "component": payload.get("name"),
            "location": payload.get("location"),
            "state": payload.get("state"),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        mqtt_client.publish("system/alert", safe_json_dumps(alert_msg))
        print(f"[MQTT] -> system/alert -> {alert_msg}")

# --- Peticiones del sistema ---
def handle_get_request(client, topic, payload):
    """Procesa peticiones de lectura (sensors, actuators, alerts)."""
    try:
        parts = topic.split("/")
        if len(parts) < 3:
            print(f"[WARN] Petición MQTT inválida: {topic}")
            return

        requester = parts[2]
        req_type = payload.get("request")
        if not req_type:
            print("[WARN] Petición sin campo 'request'.")
            return

        if req_type in ["sensors", "actuators"]:
            table = req_type
            device = payload.get("device")
            comp_id = payload.get("id")

            if device and comp_id is not None:
                query = f"SELECT * FROM {table} WHERE device_name=%s AND id=%s"
                cursor.execute(query, (device, comp_id))
            elif device:
                query = f"SELECT * FROM {table} WHERE device_name=%s ORDER BY id"
                cursor.execute(query, (device,))
            else:
                query = f"SELECT * FROM {table} ORDER BY device_name, id"
                cursor.execute(query)

            results = cursor.fetchall()
            if not results:
                print(f"[SYSTEM] -> {table}: sin resultados para {device or 'todos'}")
                return

            for row in results:
                if device:
                    topic_resp = f"system/response/{requester}/{table}/{row['device_name']}/{row['id']}"
                else:
                    topic_resp = f"system/response/{requester}/{table}/{row['id']}"
                client.publish(topic_resp, safe_json_dumps(row))

            print(f"[SYSTEM] -> {table}: {len(results)} resultados enviados a {requester}")

        elif req_type == "alerts":
            limit = payload.get("limit", 10)
            cursor.execute(
                "SELECT * FROM alerts ORDER BY timestamp DESC LIMIT %s", (limit,)
            )
            alerts = cursor.fetchall()
            if not alerts:
                print("[SYSTEM] -> No hay alertas registradas.")
                return

            for alert in alerts:
                topic_resp = f"system/response/{requester}/alerts/{alert['id']}"
                client.publish(topic_resp, safe_json_dumps(alert))

            print(f"[SYSTEM] -> {len(alerts)} alertas enviadas a {requester}")

        else:
            print(f"[WARN] Tipo de petición desconocido: {req_type}")

    except Exception as e:
        print(f"[ERROR] handle_get_request: {e}")

# --- Callback MQTT ---
def on_message(client, userdata, msg):
    topic = msg.topic
    if topic.startswith("system/get/"):
        try:
            payload = json.loads(msg.payload.decode())
            handle_get_request(client, topic, payload)
        except Exception as e:
            print(f"[ERROR] procesando system/get/: {e}")
        return

    parts = topic.split("/")
    if len(parts) < 4:
        return

    mode, device, kind, idx = parts[:4]
    try:
        payload = json.loads(msg.payload.decode())
    except json.JSONDecodeError:
        print(f"[WARN] JSON inválido en {topic}")
        return

    if mode == "announce":
        if device not in seen_devices:
            clear_device(device)
            seen_devices.add(device)
        save_entity(device, kind, int(idx), payload)
    elif mode == "update":
        update_state(device, kind, int(idx), payload)
    elif mode == "alert":
        save_alert(device, kind, int(idx), payload, client)

# --- MQTT setup ---
def setup_mqtt():
    client = mqtt.Client()
    client.username_pw_set(mqtt_cfg["user"], mqtt_cfg["password"])
    client.on_message = on_message
    client.connect(mqtt_cfg["host"], mqtt_cfg["port"], 60)
    for topic, qos in mqtt_cfg["topics"]:
        client.subscribe(topic, qos)
        print(f"[MQTT] Subscrito a {topic}")
    return client

# --- MAIN ---
client = setup_mqtt()
print("[LISTENER] Esperando mensajes de announce/update/alert/system/get...")
client.loop_forever()
