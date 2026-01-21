from config import logger
import json
from datetime import datetime
from handlers.utils import safe_json_dumps


def _normalize_bool(raw_cmd):
    if isinstance(raw_cmd, str):
        v = raw_cmd.strip().lower()
        return v in ["1", "true", "on", "enabled", "yes", "active"]
    return bool(raw_cmd)


def _motion_bool_from_command(cmd: str) -> bool:
    """
    Para mantener compatibilidad con actuators.state (0/1).
    OPEN/CLOSE => True (en movimiento/activo)
    STOP/CLOSED/OFF => False
    """
    v = (cmd or "").strip().lower()
    return v in ["open", "close", "forward", "backward", "opening", "closing", "up", "down"]


def handle(db, client, topic, payload):
    """
    Gestiona 'system/set/#' desde los microservicios internos.
    Soporta:
      - Actuadores simples:   payload.state (bool/str)
      - Sensores:            payload.enable (bool/str)
      - Actuadores movimiento: payload.command ("OPEN|CLOSE|STOP") + opcional payload.speed (0-100)
    Reenvía la orden al ESP32 en set/<device>/<type>/<id>.
    """
    try:
        # === Identificar requester ===
        parts = topic.split("/")
        requester = parts[2] if len(parts) > 2 else "unknown"

        # === Extraer valores ===
        device = payload.get("device")
        comp_type = str(payload.get("type", "")).strip().lower()

        comp_id = payload.get("id")
        comp_id = int(comp_id) if comp_id is not None else None

        # Comandos soportados
        raw_state = payload.get("state", None)
        raw_enable = payload.get("enable", None)
        raw_command = payload.get("command", None)
        raw_speed = payload.get("speed", None)

        if not (device and comp_type and comp_id is not None):
            logger.warning(f"[SYSTEM/SET] Petición incompleta -> {payload}")
            return

        if comp_type not in ["sensor", "actuator"]:
            logger.warning(f"[SYSTEM/SET] Tipo inválido: {comp_type}")
            return

        # Validación mínima del comando según tipo
        if comp_type == "sensor":
            if raw_enable is None:
                logger.warning(f"[SYSTEM/SET] Petición incompleta (sensor sin enable) -> {payload}")
                return
        else:
            # actuator
            if raw_state is None and raw_command is None:
                logger.warning(f"[SYSTEM/SET] Petición incompleta (actuator sin state/command) -> {payload}")
                return

        # === Comprobación de existencia en base de datos ===
        query = f"SELECT name, location FROM {comp_type}s WHERE device_name=%s AND id=%s"
        result = db.execute(query, (device, comp_id))

        if not result:
            error = {
                "error": "component_not_found",
                "device": device,
                "type": comp_type,
                "id": comp_id
            }
            client.publish(
                f"system/response/{requester}/{comp_type}/{device}/{comp_id}",
                json.dumps(error),
                qos=1
            )
            return

        name = result[0].get("name")
        location = result[0].get("location")

        # === Preparar payload para ESP32 ===
        esp_topic = f"set/{device}/{comp_type}/{comp_id}"
        forward_payload = {"requester": requester}

        command_for_db = None     # lo que persistimos en actuators.state (0/1)
        notify_value = None       # lo que ponemos en system/notify/set

        # ==========================
        # SENSOR: enable boolean
        # ==========================
        if comp_type == "sensor":
            value = _normalize_bool(raw_enable)
            forward_payload["enable"] = value
            command_for_db = None
            notify_value = value

        # ==========================
        # ACTUATOR: state boolean (simple) o command/speed (movimiento)
        # ==========================
        else:
            if raw_command is not None:
                # Movimiento: reenviamos command + speed (si existe)
                if not isinstance(raw_command, str) or not raw_command.strip():
                    logger.warning(f"[SYSTEM/SET] command inválido -> {payload}")
                    return

                cmd = raw_command.strip().upper()
                forward_payload["command"] = cmd

                # Speed opcional (0-100)
                if raw_speed is not None:
                    try:
                        speed = int(raw_speed)
                        speed = max(0, min(100, speed))
                        forward_payload["speed"] = speed
                    except Exception:
                        logger.warning(f"[SYSTEM/SET] speed inválido (se ignora) -> {raw_speed}")

                # Para mantener compatibilidad en BBDD (0/1)
                command_for_db = 1 if _motion_bool_from_command(cmd) else 0
                notify_value = {"command": cmd, "speed": forward_payload.get("speed")}

            else:
                # Actuador simple ON/OFF
                value = _normalize_bool(raw_state)
                forward_payload["state"] = value
                command_for_db = 1 if value else 0
                notify_value = value

        # === Publicar al ESP32 (QoS 1) ===
        client.publish(
            esp_topic,
            json.dumps(forward_payload),
            qos=1
        )
        logger.info(f"[SET] Enviado -> {esp_topic} ({notify_value})")

        # === Actualizar BD (solo actuadores) ===
        if comp_type == "actuator" and command_for_db is not None:
            db.execute(
                """
                UPDATE actuators
                SET state=%s, last_seen=NOW()
                WHERE device_name=%s AND id=%s
                """,
                (command_for_db, device, comp_id),
                commit=True
            )

        # === Actualizar estado del dispositivo ===
        db.execute(
            "UPDATE devices SET last_seen=NOW() WHERE device_name=%s",
            (device,),
            commit=True
        )

        # === Publicar notificación global (QoS 1) ===
        notify_msg = {
            "device": device,
            "type": comp_type,
            "id": comp_id,
            "name": name,
            "location": location,
            "value": notify_value,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "source": requester
        }

        client.publish(
            "system/notify/set",
            safe_json_dumps(notify_msg),
            qos=1
        )
        logger.info("[NOTIFY] Publicado -> system/notify/set")

    except Exception as e:
        logger.error(f"[SYSTEM/SET] Error procesando petición: {e}")
