from config import logger
from handlers.utils import safe_json_dumps
from datetime import datetime

def handle(db, client, topic, payload):
    """
    Gestiona los mensajes 'alert/#' provenientes de los ESP32.
    Inserta la alerta en la base de datos y notifica al resto del sistema.
    """
    try:
        # === Parsear tópico ===
        parts = topic.split("/")
        if len(parts) < 4:
            logger.warning(f"[ALERT] Tópico inválido: {topic}")
            return

        _, device, comp_type, comp_id = parts[:4]

        # === Validar tipo de componente ===
        if comp_type not in ["sensor", "actuator"]:
            logger.warning(f"[ALERT] Tipo de componente no válido: {comp_type}")
            return

        # === Extraer datos del payload ===
        state = payload.get("state", "ALERT")
        message = payload.get("message", "Sin mensaje")
        location = payload.get("location")
        name = payload.get("name")

        if not location or not name:
            # Si el ESP32 no envía estos campos, podemos obtenerlos de la DB
            query_info = f"SELECT name, location FROM {comp_type}s WHERE device_name=%s AND id=%s"
            result = db.execute(query_info, (device, comp_id))
            if result and len(result) > 0:
                name = name or result[0].get("name")
                location = location or result[0].get("location")

        # === Insertar alerta en base de datos ===
        query_insert = """
            INSERT INTO alerts (device_name, component_name, location, state, message, timestamp)
            VALUES (%s, %s, %s, %s, %s, NOW())
        """
        db.execute(query_insert, (device, name, location, state, message), commit=True)
        logger.info(f"[DB] Alerta registrada: {device}/{comp_type}/{comp_id} -> {message}")

        # === Actualizar last_seen del dispositivo ===
        query_dev = "UPDATE devices SET last_seen=NOW() WHERE device_name=%s"
        db.execute(query_dev, (device,), commit=True)

        # === Notificación MQTT ===
        alert_msg = {
            "device": device,
            "type": comp_type,
            "id": comp_id,
            "name": name,
            "location": location,
            "state": state,
            "message": message,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        client.publish("system/notify/alert", safe_json_dumps(alert_msg))
        logger.info(f"[ALERT] Notificación publicada -> system/notify/alert")

    except Exception as e:
        logger.error(f"[ALERT] Error procesando alerta: {e}")
