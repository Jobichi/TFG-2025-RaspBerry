from config import logger
from handlers.utils import safe_json_dumps, ensure_device, ensure_component
from datetime import datetime

def handle(db, client, topic, payload):
    try:
        parts = topic.split("/")
        if len(parts) < 4:
            logger.warning(f"[UPDATE] Tópico inválido: {topic}")
            return

        _, device, comp_type, comp_id = parts[:4]
        comp_id = int(comp_id)

        if comp_type not in ["sensor", "actuator"]:
            logger.warning(f"[UPDATE] Tipo no válido: {comp_type}")
            return

        value = payload.get("value")
        units = payload.get("units") or payload.get("unit")
        state = payload.get("state")

        # Asegurar dispositivo/componente existen (por si announce no llegó antes)
        ensure_device(db, device)
        ensure_component(db, comp_type, device, comp_id)

        if comp_type == "sensor":
            if value is None:
                logger.warning(f"[UPDATE] Sensor sin valor ({device}/{comp_id})")
                return
            if units is None:
                logger.warning(f"[UPDATE] Sensor sin unidad ({device}/{comp_id})")

            query = """
                UPDATE sensors
                SET value=%s, unit=%s, last_seen=NOW()
                WHERE device_name=%s AND id=%s
            """
            db.execute(query, (value, units, device, comp_id), commit=True)
            logger.info(f"[DB] Sensor actualizado: {device}/{comp_id} -> {value} {units or ''}")

        elif comp_type == "actuator":
            if state is None:
                logger.warning(f"[UPDATE] Actuador sin estado ({device}/{comp_id})")
                return

            query = """
                UPDATE actuators
                SET state=%s, last_seen=NOW()
                WHERE device_name=%s AND id=%s
            """
            db.execute(query, (state, device, comp_id), commit=True)
            logger.info(f"[DB] Actuador actualizado: {device}/{comp_id} -> {state}")

        db.execute(
            "UPDATE devices SET last_seen=NOW() WHERE device_name=%s",
            (device,),
            commit=True
        )

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
        client.publish(topic_notify, safe_json_dumps(notify_msg))
        logger.info(f"[UPDATE] Notificación publicada -> {topic_notify}")

    except Exception as e:
        logger.error(f"[UPDATE] Error procesando update: {e}")
