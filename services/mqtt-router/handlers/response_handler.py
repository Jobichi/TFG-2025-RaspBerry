from config import logger
import json

def handle(db, client, topic, payload):
    """
    Captura respuestas de los ESP32 ('response/#'), actualiza la BBDD
    y reenvía la información al microservicio solicitante.
    """
    try:
        # === Parsear tópico ===
        parts = topic.split("/")
        if len(parts) < 4:
            logger.warning(f"[RESPONSE] Tópico inválido: {topic}")
            return

        device, comp_type, comp_id = parts[1:4]

        # === Validar payload ===
        if not isinstance(payload, dict):
            try:
                payload = json.loads(payload)
            except Exception:
                logger.warning(f"[RESPONSE] Payload no JSON en {topic}")
                return

        requester = payload.pop("requester", None)
        value = payload.get("value")
        state = payload.get("state")
        unit = payload.get("unit")

        # === Actualizar base de datos ===
        try:
            if comp_type == "sensor" and value is not None:
                query = "UPDATE sensors SET value=%s, unit=%s, last_seen=NOW() WHERE device_name=%s AND id=%s"
                db.execute(query, (value, unit, device, comp_id), commit=True)
                logger.info(f"[DB] Sensor actualizado: {device}/{comp_id} -> {value} {unit or ''}")

            elif comp_type == "actuator" and state is not None:
                query = "UPDATE actuators SET state=%s, last_seen=NOW() WHERE device_name=%s AND id=%s"
                db.execute(query, (state, device, comp_id), commit=True)
                logger.info(f"[DB] Actuador actualizado: {device}/{comp_id} -> {state}")

        except Exception as e:
            logger.error(f"[DB] Error actualizando {comp_type} en {device}/{comp_id}: {e}")

        # === Reenviar al microservicio solicitante ===
        if requester:
            topic_resp = f"system/response/{requester}/{comp_type}/{device}/{comp_id}"
            client.publish(topic_resp, json.dumps(payload))
            logger.info(f"[SYSTEN/RESPONSE] {device}/{comp_type}/{comp_id} → {requester}")
        else:
            logger.debug(f"[SYSTEM/RESPONSE] Sin requester en {topic}")

    except Exception as e:
        logger.error(f"[RESPONSE] Error procesando respuesta: {e}")
