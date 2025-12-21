from config import logger
import json
from handlers.utils import ensure_device, ensure_component


def handle(db, client, topic, payload):
    """
    Procesa 'response/#' de ESP32:
    - actualiza BD con estado real
    - reenvía al requester correspondiente
    """

    try:
        # === Parseo del tópico ===
        parts = topic.split("/")
        if len(parts) < 4:
            logger.warning(f"[RESPONSE] Tópico inválido: {topic}")
            return

        _, device, comp_type, comp_id = parts[:4]

        try:
            comp_id = int(comp_id)
        except ValueError:
            logger.warning(f"[RESPONSE] ID inválido: {comp_id}")
            return

        if comp_type not in ["sensor", "actuator"]:
            logger.warning(f"[RESPONSE] Tipo inválido: {comp_type}")
            return

        # === Garantizar existencia previa ===
        ensure_device(db, device)
        ensure_component(db, comp_type, device, comp_id)

        # === Parseo del payload ===
        if not isinstance(payload, dict):
            try:
                payload = json.loads(payload)
            except Exception:
                logger.warning(f"[RESPONSE] Payload no JSON: {topic}")
                return

        requester = payload.pop("requester", None)

        # Campos comunes
        value = payload.get("value")
        units = payload.get("units") or payload.get("unit")
        raw_state = payload.get("state")

        # === Actualizar BD ===
        try:
            if comp_type == "sensor" and value is not None:
                db.execute(
                    """
                    UPDATE sensors
                    SET value=%s, unit=%s, last_seen=NOW()
                    WHERE device_name=%s AND id=%s
                    """,
                    (value, units, device, comp_id),
                    commit=True
                )
                logger.info(f"[DB][RESPONSE] Sensor {device}/{comp_id} -> {value} {units or ''}")

            elif comp_type == "actuator" and raw_state is not None:
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
                logger.info(f"[DB][RESPONSE] Actuador {device}/{comp_id} -> {state}")

        except Exception as e:
            logger.error(f"[DB][RESPONSE] Error actualizando {comp_type}: {e}")

        # === Reenvío al requester ===
        if requester:
            topic_resp = f"system/response/{requester}/{comp_type}/{device}/{comp_id}"

            payload_resp = {
                "device": device,
                "type": comp_type,
                "id": comp_id
            }

            if comp_type == "sensor":
                payload_resp.update({"value": value, "units": units})
            else:
                payload_resp.update({"state": state})

            client.publish(
                topic_resp,
                json.dumps(payload_resp),
                qos=1
            )

            logger.info(f"[SYSTEM/RESPONSE] Enviado a {requester}: {topic_resp}")

        else:
            logger.debug(f"[SYSTEM/RESPONSE] Respuesta sin requester: {topic}")

    except Exception as e:
        logger.error(f"[RESPONSE] Error procesando respuesta: {e}")
