from config import logger
from handlers.utils import safe_json_dumps, ensure_device, ensure_component
from datetime import datetime


def handle(db, client, topic, payload):
    """
    Procesa 'update/#' desde ESP32:
    - sincroniza estado en BD
    - publica notificación de actualización
    """

    try:
        # === Parseo del tópico ===
        parts = topic.split("/")
        if len(parts) < 4:
            logger.warning(f"[UPDATE] Tópico inválido: {topic}")
            return

        _, device, comp_type, comp_id = parts[:4]

        try:
            comp_id = int(comp_id)
        except ValueError:
            logger.warning(f"[UPDATE] ID inválido: {comp_id}")
            return

        if comp_type not in ["sensor", "actuator"]:
            logger.warning(f"[UPDATE] Tipo no válido: {comp_type}")
            return

        # === Extraer valores ===
        value = payload.get("value")
        units = payload.get("units") or payload.get("unit")
        raw_state = payload.get("state")

        # === Asegurar existencia previa ===
        ensure_device(db, device)
        ensure_component(db, comp_type, device, comp_id)

        # === Actualizar BD ===
        if comp_type == "sensor":
            if value is None:
                logger.warning(f"[UPDATE] Sensor sin valor ({device}/{comp_id})")
                return

            db.execute(
                """
                UPDATE sensors
                SET value=%s, unit=%s, last_seen=NOW()
                WHERE device_name=%s AND id=%s
                """,
                (value, units, device, comp_id),
                commit=True
            )
            logger.info(f"[DB][UPDATE] Sensor {device}/{comp_id} -> {value} {units or ''}")

        else:  # actuator
            if raw_state is None:
                logger.warning(f"[UPDATE] Actuador sin estado ({device}/{comp_id})")
                return

            if isinstance(raw_state, str):
                raw_state = raw_state.strip().lower()
                state = raw_state in ["1", "true", "on", "enabled"]
            else:
                state = bool(raw_state)

            db.execute(
                """
                UPDATE actuators
                SET state=%s, last_seen=NOW()
                WHERE device_name=%s AND id=%s
                """,
                (state, device, comp_id),
                commit=True
            )
            logger.info(f"[DB][UPDATE] Actuador {device}/{comp_id} -> {state}")

        # === Mantener vivo el dispositivo ===
        db.execute(
            "UPDATE devices SET last_seen=NOW() WHERE device_name=%s",
            (device,),
            commit=True
        )

        # === Publicar notificación (QoS 1) ===
        notify_msg = {
            "device": device,
            "type": comp_type,
            "id": comp_id,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        if comp_type == "sensor":
            notify_msg.update({"value": value, "units": units})
        else:
            notify_msg.update({"state": state})

        topic_notify = f"system/notify/{device}/update"
        client.publish(
            topic_notify,
            safe_json_dumps(notify_msg),
            qos=1
        )

        logger.info(f"[UPDATE] Notificación publicada -> {topic_notify}")

    except Exception as e:
        logger.error(f"[UPDATE] Error procesando update: {e}")
