from config import logger
from handlers.utils import safe_json_dumps
from datetime import datetime

def handle(db, client, topic, payload):
    """
    Gestiona los mensajes 'announce/#' enviados por los ESP32.
    Registra o actualiza dispositivos, sensores y actuadores en la base de datos.
    """
    try:
        # === Parsear tópico ===
        parts = topic.split("/")
        if len(parts) < 4:
            logger.warning(f"[ANNOUNCE] Tópico inválido: {topic}")
            return

        _, device, comp_type, comp_id = parts[:4]

        # === Validar payload ===
        name = payload.get("name")
        location = payload.get("location")
        state = payload.get("state")

        if not name or not location:
            logger.warning(f"[ANNOUNCE] Payload incompleto en {topic}: {payload}")
            return

        # === Registrar / actualizar el dispositivo principal ===
        try:
            query_dev = """
                INSERT INTO devices (device_name, last_seen)
                VALUES (%s, NOW())
                ON DUPLICATE KEY UPDATE last_seen=NOW()
            """
            db.execute(query_dev, (device,), commit=True)
        except Exception as e:
            logger.error(f"[DB] Error registrando dispositivo {device}: {e}")
            return

        # === Registrar / actualizar el componente (sensor o actuador) ===
        if comp_type not in ["sensor", "actuator"]:
            logger.warning(f"[ANNOUNCE] Tipo de componente no válido: {comp_type}")
            return

        try:
            query_comp = f"""
                INSERT INTO {comp_type}s (id, device_name, name, location, state, last_seen)
                VALUES (%s, %s, %s, %s, %s, NOW())
                ON DUPLICATE KEY UPDATE
                    name=VALUES(name),
                    location=VALUES(location),
                    state=VALUES(state),
                    last_seen=NOW()
            """
            db.execute(query_comp, (comp_id, device, name, location, state), commit=True)
            logger.info(f"[DB] {device}/{comp_type}/{comp_id} registrado o actualizado ({state})")

        except Exception as e:
            logger.error(f"[DB] Error actualizando {comp_type} en {device}/{comp_id}: {e}")
            return

        # === Notificación opcional de confirmación ===
        confirm_msg = {
            "device": device,
            "type": comp_type,
            "id": comp_id,
            "status": "registered",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        client.publish(f"system/notify/{device}/announce", safe_json_dumps(confirm_msg))
        logger.info(f"[ANNOUNCE] Confirmación publicada -> system/notify/{device}/announce")

    except Exception as e:
        logger.error(f"[ANNOUNCE] Error procesando announce: {e}")
