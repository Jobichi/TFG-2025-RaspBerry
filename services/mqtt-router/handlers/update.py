from config import logger
from handlers.utils import safe_json_dumps, ensure_device, ensure_component
from datetime import datetime


def _normalize_actuator_state_for_db(raw_state):
    """
    Persistencia en BBDD (actuators.state):
      - Abierto = 1
      - Cerrado = 0
    Devuelve None si no es estado estable y no debe persistirse.
    """
    if raw_state is None:
        return None

    # Compatibilidad: bool/num -> 0/1
    if isinstance(raw_state, bool):
        return 1 if raw_state else 0
    if isinstance(raw_state, (int, float)):
        return 1 if raw_state != 0 else 0

    if isinstance(raw_state, str):
        v = raw_state.strip().lower()

        # Si llega "OPEN:100", nos quedamos con "open"
        if ":" in v:
            v = v.split(":", 1)[0].strip()

        # Estados estables (persiana/puerta)
        if v in ["open", "opened", "abierto"]:
            return 1
        if v in ["close", "closed", "cerrado"]:
            return 0

        # Compatibilidad ON/OFF para otros actuadores
        if v in ["on", "true", "1", "enabled", "active", "yes"]:
            return 1
        if v in ["off", "false", "0", "disabled", "inactive", "no"]:
            return 0

        # Transitorios: no persistir
        if v in ["opening", "closing", "stop", "stopped", "forward", "backward", "moving"]:
            return None

    return None


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
        state_db = None
        state_text = None

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

            state_db = _normalize_actuator_state_for_db(raw_state)
            if isinstance(raw_state, str):
                state_text = raw_state.strip()

            # Persistimos solo si es estado estable
            if state_db is not None:
                db.execute(
                    """
                    UPDATE actuators
                    SET state=%s, last_seen=NOW()
                    WHERE device_name=%s AND id=%s
                    """,
                    (state_db, device, comp_id),
                    commit=True
                )
                logger.info(f"[DB][UPDATE] Actuador {device}/{comp_id} -> state={state_db}")
            else:
                # Al menos marcamos last_seen del actuador (sin tocar state)
                db.execute(
                    """
                    UPDATE actuators
                    SET last_seen=NOW()
                    WHERE device_name=%s AND id=%s
                    """,
                    (device, comp_id),
                    commit=True
                )
                logger.info(
                    f"[DB][UPDATE] Actuador {device}/{comp_id} -> state no estable (no persistido): {raw_state}"
                )

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
            # En notify damos el estado persistible (0/1) si existe,
            # y además el texto original para depurar o UI.
            notify_msg["state"] = state_db
            if state_text is not None:
                notify_msg["state_text"] = state_text

        topic_notify = f"system/notify/{device}/update"
        client.publish(
            topic_notify,
            safe_json_dumps(notify_msg),
            qos=1
        )

        logger.info(f"[UPDATE] Notificación publicada -> {topic_notify}")

    except Exception as e:
        logger.error(f"[UPDATE] Error procesando update: {e}")
