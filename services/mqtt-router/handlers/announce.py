from config import logger
from handlers.utils import safe_json_dumps
from datetime import datetime


def handle(db, client, topic, payload):
    """
    Gestiona 'announce/#' desde los ESP32.
    Registra dinámicamente dispositivos, sensores y actuadores.
    """

    try:
        # === Parsear tópico ===
        parts = topic.split("/")
        if len(parts) < 4:
            logger.warning(f"[ANNOUNCE] Tópico inválido: {topic}")
            return

        _, device, comp_type, comp_id = parts[:4]

        try:
            comp_id = int(comp_id)
        except ValueError:
            logger.warning(f"[ANNOUNCE] ID inválido: {comp_id}")
            return

        if comp_type not in ["sensor", "actuator"]:
            logger.warning(f"[ANNOUNCE] Tipo no válido: {comp_type}")
            return

        # === Extraer datos del payload ===
        name = payload.get("name")
        location = payload.get("location")

        if not name or not location:
            logger.warning(f"[ANNOUNCE] Payload incompleto en {topic}: {payload}")
            return

        # === Registrar / actualizar dispositivo ===
        db.execute(
            """
            INSERT INTO devices (device_name, last_seen)
            VALUES (%s, NOW())
            ON DUPLICATE KEY UPDATE last_seen=NOW()
            """,
            (device,),
            commit=True
        )

        # === Registrar componente ===
        if comp_type == "sensor":
            db.execute(
                """
                INSERT INTO sensors (id, device_name, name, location, last_seen)
                VALUES (%s, %s, %s, %s, NOW())
                ON DUPLICATE KEY UPDATE
                    name=VALUES(name),
                    location=VALUES(location),
                    last_seen=NOW()
                """,
                (comp_id, device, name, location),
                commit=True
            )

        else:  # actuator
            db.execute(
                """
                INSERT INTO actuators (id, device_name, name, location, last_seen)
                VALUES (%s, %s, %s, %s, NOW())
                ON DUPLICATE KEY UPDATE
                    name=VALUES(name),
                    location=VALUES(location),
                    last_seen=NOW()
                """,
                (comp_id, device, name, location),
                commit=True
            )

        logger.info(f"[DB][ANNOUNCE] {comp_type} registrado: {device}/{comp_id}")

        # === Publicar confirmación (QoS 1) ===
        confirm_msg = {
            "device": device,
            "type": comp_type,
            "id": comp_id,
            "name": name,
            "location": location,
            "status": "registered",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        client.publish(
            f"system/notify/{device}/announce",
            safe_json_dumps(confirm_msg),
            qos=1
        )

        logger.info(f"[ANNOUNCE] Notificación enviada -> system/notify/{device}/announce")

    except Exception as e:
        logger.error(f"[ANNOUNCE] Error: {e}")
