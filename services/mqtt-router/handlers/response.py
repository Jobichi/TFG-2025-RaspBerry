from config import logger
import json
from handlers.utils import ensure_device, ensure_component

def handle(db, client, topic, payload):
    """
    Procesa 'response/#' de ESP32:
    - actualiza BD
    - reenvía al requester correspondiente
    """

    try:
        # === Parseo del tópico ===
        parts = topic.split("/")
        if len(parts) < 4:
            logger.warning(f"[RESPONSE] Tópico inválido: {topic}")
            return

        _, device, comp_type, comp_id = parts[:4]
        comp_id = int(comp_id)

        # === Validación del tipo ===
        if comp_type not in ["sensor", "actuator"]:
            logger.warning(f"[RESPONSE] Tipo inválido: {comp_type}")
            return

        # === Asegurar que existan device y componente antes de actualizar ===
        ensure_device(db, device)
        ensure_component(db, comp_type, device, comp_id)

        # === Parseo del JSON ===
        if not isinstance(payload, dict):
            try:
                payload = json.loads(payload)
            except Exception:
                logger.warning(f"[RESPONSE] Payload no JSON: {topic}")
                return

        requester = payload.pop("requester", None)

        # Unificar claves:
        value = payload.get("value")
        units = payload.get("units") or payload.get("unit")
        state = payload.get("state")

        # === Actualizar BD ===
        try:
            if comp_type == "sensor" and value is not None:
                query = """
                    UPDATE sensors
                    SET value=%s, unit=%s, last_seen=NOW()
                    WHERE device_name=%s AND id=%s
                """
                db.execute(query, (value, units, device, comp_id), commit=True)
                logger.info(f"[DB] Sensor actualizado: {device}/{comp_id} = {value} {units or ''}")

            elif comp_type == "actuator" and state is not None:
                query = """
                    UPDATE actuators
                    SET state=%s, last_seen=NOW()
                    WHERE device_name=%s AND id=%s
                """
                db.execute(query, (state, device, comp_id), commit=True)
                logger.info(f"[DB] Actuador actualizado: {device}/{comp_id} = {state}")

        except Exception as e:
            logger.error(f"[DB] Error en actualización de {comp_type}: {e}")

        # === Reenvío a requester ===
        if requester:

            topic_resp = f"system/response/{requester}/{comp_type}/{device}/{comp_id}"

            # Payload final limpio y coherente con ESP32
            payload_resp = {
                "device": device,
                "type": comp_type,
                "id": comp_id
            }

            if comp_type == "sensor":
                payload_resp.update({"value": value, "units": units})
            else:
                payload_resp.update({"state": state})

            client.publish(topic_resp, json.dumps(payload_resp))
            logger.info(f"[SYSTEM/RESPONSE] Enviado a {requester}: {topic_resp}")

        else:
            logger.debug(f"[SYSTEM/RESPONSE] Sin requester en {topic}")

    except Exception as e:
        logger.error(f"[RESPONSE] Error procesando respuesta: {e}")
