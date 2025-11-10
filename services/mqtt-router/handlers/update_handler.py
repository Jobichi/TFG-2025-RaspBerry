from config import logger
from handlers.utils import safe_json_dumps
from datetime import datetime

def handle(db, client, topic, payload):
    """
    Gestiona las publicaciones 'update/#' desde los ESP32.
    Actualiza el estado o valor de sensores y actuadores en la base de datos.
    """
    try:
        # === Parsear tópico ===
        parts = topic.split("/")
        if len(parts) < 4:
            logger.warning(f"[UPDATE] Tópico inválido: {topic}")
            return

        _, device, comp_type, comp_id = parts[:4]

        # === Validar tipo de componente ===
        if comp_type not in ["sensor", "actuator"]:
            logger.warning(f"[UPDATE] Tipo de componente no válido: {comp_type}")
            return

        # === Validar payload ===
        value = payload.get("value")
        state = payload.get("state")
        unit = payload.get("unit")

        if comp_type == "sensor" and value is None:
            logger.warning(f"[UPDATE] Payload sin valor en sensor {device}/{comp_id}")
            return
        if comp_type == "actuator" and state is None:
            logger.warning(f"[UPDATE] Payload sin estado en actuador {device}/{comp_id}")
            return

        # === Actualizar base de datos ===
        if comp_type == "sensor":
            query = """
                UPDATE sensors
                SET value=%s, unit=%s, last_seen=NOW()
                WHERE device_name=%s AND id=%s
            """
            db.execute(query, (value, unit, device, comp_id), commit=True)
            logger.info(f"[DB] Sensor actualizado: {device}/{comp_id} -> {value} {unit or ''}")

        elif comp_type == "actuator":
            query = """
                UPDATE actuators
                SET state=%s, last_seen=NOW()
                WHERE device_name=%s AND id=%s
            """
            db.execute(query, (state, device, comp_id), commit=True)
            logger.info(f"[DB] Actuador actualizado: {device}/{comp_id} -> {state}")

        # === Actualizar last_seen del dispositivo ===
        query_dev = "UPDATE devices SET last_seen=NOW() WHERE device_name=%s"
        db.execute(query_dev, (device,), commit=True)

        # === Publicar notificación opcional ===
        notify_msg = {
            "device": device,
            "type": comp_type,
            "id": comp_id,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        if comp_type == "sensor":
            notify_msg.update({"value": value, "unit": unit})
        else:
            notify_msg.update({"state": state})

        client.publish(f"system/notify/{device}/update", safe_json_dumps(notify_msg))

    except Exception as e:
        logger.error(f"[UPDATE] Error procesando update: {e}")
