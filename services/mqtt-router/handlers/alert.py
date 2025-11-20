from config import logger
from handlers.utils import safe_json_dumps
from datetime import datetime

def handle(db, client, topic, payload):
    """
    Gestiona 'alert/#' desde los ESP32.
    Registra alerta en BD y notifica a system.
    """

    try:
        # === Parsear tópico ===
        parts = topic.split("/")
        if len(parts) < 4:
            logger.warning(f"[ALERT] Tópico inválido: {topic}")
            return

        _, device, comp_type, comp_id = parts[:4]
        comp_id = int(comp_id)

        if comp_type not in ["sensor", "actuator"]:
            logger.warning(f"[ALERT] Tipo no válido: {comp_type}")
            return

        # === Extraer datos del payload ===
        status   = payload.get("status", "ALERT")
        message  = payload.get("message", "Sin mensaje")
        severity = payload.get("severity", "medium")
        code     = payload.get("code")
        name     = payload.get("name")
        location = payload.get("location")

        # === Resolver name/location si no vienen en payload ===
        if not name or not location:
            q = f"SELECT name, location FROM {comp_type}s WHERE device_name=%s AND id=%s"
            row = db.execute(q, (device, comp_id))
            if row:
                name     = name     or row[0]["name"]
                location = location or row[0]["location"]

        # === Insertar en BD ===
        q_ins = """
            INSERT INTO alerts (device_name, component_type, component_id, component_name,
                                location, status, message, severity, code, timestamp)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        """

        db.execute(q_ins, (
            device, comp_type, comp_id,
            name, location,
            status, message, severity, code
        ), commit=True)

        logger.info(
            f"[DB] ALERTA registrada: {device}/{comp_type}/{comp_id} "
            f"[{severity.upper()}] -> {message}"
        )

        # === Actualizar last_seen ===
        db.execute(
            "UPDATE devices SET last_seen=NOW() WHERE device_name=%s",
            (device,),
            commit=True
        )

        # === Construir notificación ===
        alert_msg = {
            "device":   device,
            "type":     comp_type,
            "id":       comp_id,
            "name":     name,
            "location": location,
            "status":   status,
            "severity": severity,
            "message":  message,
            "code":     code,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        client.publish("system/notify/alert", safe_json_dumps(alert_msg))
        logger.info("[ALERT] Notificación publicada -> system/notify/alert")

    except Exception as e:
        logger.error(f"[ALERT] Error procesando alerta: {e}")
