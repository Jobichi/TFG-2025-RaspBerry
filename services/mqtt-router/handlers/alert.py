from config import logger
from handlers.utils import safe_json_dumps
from datetime import datetime


def handle(db, client, topic, payload):
    """
    Gestiona 'alert/#' desde los ESP32.
    Mantiene únicamente la alerta más reciente por componente.
    """

    try:
        # === Parsear tópico ===
        parts = topic.split("/")
        if len(parts) < 4:
            logger.warning(f"[ALERT] Tópico inválido: {topic}")
            return

        _, device, comp_type, comp_id = parts[:4]

        try:
            comp_id = int(comp_id)
        except ValueError:
            logger.warning(f"[ALERT] ID inválido: {comp_id}")
            return

        if comp_type not in ("sensor", "actuator"):
            logger.warning(f"[ALERT] Tipo no válido: {comp_type}")
            return

        # === Garantizar existencia del dispositivo (FK) ===
        db.execute(
            """
            INSERT INTO devices (device_name, last_seen)
            VALUES (%s, NOW())
            ON DUPLICATE KEY UPDATE last_seen=NOW()
            """,
            (device,),
            commit=True
        )

        # === Extraer datos del payload ===
        status   = payload.get("status", "ALERT")
        message  = payload.get("message", "Sin mensaje")
        severity = payload.get("severity", "medium")
        code     = payload.get("code")
        name     = payload.get("name")
        location = payload.get("location")

        # === Resolver name/location si no vienen en payload ===
        if not name or not location:
            row = db.execute(
                f"SELECT name, location FROM {comp_type}s WHERE device_name=%s AND id=%s",
                (device, comp_id)
            )
            if row:
                name     = name     or row[0]["name"]
                location = location or row[0]["location"]

        # === Upsert de alerta (solo la más reciente) ===
        db.execute(
            """
            INSERT INTO alerts (
                device_name,
                component_type,
                component_id,
                component_name,
                location,
                status,
                message,
                severity,
                code,
                timestamp
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            ON DUPLICATE KEY UPDATE
                component_name = VALUES(component_name),
                location       = VALUES(location),
                status         = VALUES(status),
                message        = VALUES(message),
                severity       = VALUES(severity),
                code           = VALUES(code),
                timestamp      = NOW()
            """,
            (
                device,
                comp_type,
                comp_id,
                name,
                location,
                status,
                message,
                severity,
                code
            ),
            commit=True
        )

        logger.info(
            f"[DB][ALERT] Estado actualizado: {device}/{comp_type}/{comp_id} "
            f"[{severity.upper()}] {message}"
        )

        # === Publicar notificación ===
        alert_msg = {
            "device": device,
            "type": comp_type,
            "id": comp_id,
            "name": name,
            "location": location,
            "status": status,
            "severity": severity,
            "message": message,
            "code": code,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        client.publish(
            "system/notify/alert",
            safe_json_dumps(alert_msg),
            qos=1
        )

        logger.info("[ALERT] Notificación publicada -> system/notify/alert")

    except Exception as e:
        logger.error(f"[ALERT] Error procesando alerta: {e}")
