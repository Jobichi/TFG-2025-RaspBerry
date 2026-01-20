from config import logger
import json
from handlers.utils import ensure_device, ensure_component


def _normalize_state(raw_state):
    if isinstance(raw_state, bool):
        return raw_state
    if isinstance(raw_state, (int, float)):
        return raw_state != 0
    if isinstance(raw_state, str):
        v = raw_state.strip().lower()
        return v in ["1", "true", "on", "enabled", "yes", "active"]
    return False


def _extract_enabled(payload):
    """
    Extrae 'enabled' o 'enable' del payload y lo normaliza a bool.
    Devuelve None si no existe.
    """
    if not isinstance(payload, dict):
        return None

    enabled_raw = payload.get("enabled")
    if enabled_raw is None:
        enabled_raw = payload.get("enable")

    if enabled_raw is None:
        return None

    return _normalize_state(enabled_raw)


def handle(db, client, topic, payload):
    """
    Procesa 'response/#' de ESP32:
    - actualiza BD con estado real
    - reenvía al requester correspondiente
    - si requester != telegram-service (o no viene), también enruta a telegram-service
      evitando duplicar cuando requester ya es telegram-service

    Notas:
    - Para sensores, además de value/unit, soporta enable/enabled (p.ej. ack de SET).
    """
    try:
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

        ensure_device(db, device)
        ensure_component(db, comp_type, device, comp_id)

        if not isinstance(payload, dict):
            try:
                payload = json.loads(payload)
            except Exception:
                logger.warning(f"[RESPONSE] Payload no JSON: {topic}")
                return

        requester = payload.pop("requester", None)

        value = payload.get("value")
        units = payload.get("units") or payload.get("unit")

        raw_state = payload.get("state")
        state = None
        if comp_type == "actuator" and raw_state is not None:
            state = _normalize_state(raw_state)

        enabled = None
        if comp_type == "sensor":
            enabled = _extract_enabled(payload)

        # === Actualizar BD ===
        try:
            if comp_type == "sensor":
                # Actualiza lectura si viene
                if value is not None:
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

                # Actualiza enabled si viene (ack de SET)
                if enabled is not None:
                    db.execute(
                        """
                        UPDATE sensors
                        SET enabled=%s, last_seen=NOW()
                        WHERE device_name=%s AND id=%s
                        """,
                        (1 if enabled else 0, device, comp_id),
                        commit=True
                    )
                    logger.info(f"[DB][RESPONSE] Sensor {device}/{comp_id} -> enabled={enabled}")

            elif comp_type == "actuator" and raw_state is not None:
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

        # === Construir payload de respuesta ===
        payload_resp = {"device": device, "type": comp_type, "id": comp_id}
        if comp_type == "sensor":
            payload_resp.update({"value": value, "units": units})
            if enabled is not None:
                payload_resp["enabled"] = 1 if enabled else 0
        else:
            payload_resp.update({"state": state})

        payload_json = json.dumps(payload_resp)

        # === 1) Responder al requester original (si existe) ===
        if requester:
            topic_resp = f"system/response/{requester}/{comp_type}/{device}/{comp_id}"
            client.publish(topic_resp, payload_json, qos=1)
            logger.info(f"[SYSTEM/RESPONSE] Enviado a requester={requester}: {topic_resp}")

        # === 2) Tap hacia telegram-service SIEMPRE que requester no sea telegram-service ===
        telegram_requester = "telegram-service"
        if requester != telegram_requester:
            topic_tg = f"system/response/{telegram_requester}/{comp_type}/{device}/{comp_id}"
            client.publish(topic_tg, payload_json, qos=1)
            logger.info(f"[SYSTEM/RESPONSE] Tap a {telegram_requester}: {topic_tg}")

    except Exception as e:
        logger.error(f"[RESPONSE] Error procesando respuesta: {e}")
