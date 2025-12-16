from config import logger
import json
from datetime import datetime
from handlers.utils import safe_json_dumps


def handle(db, client, topic, payload):
    """
    Gestiona 'system/set/#' desde los microservicios internos.
    Valida datos, normaliza comandos a booleanos y reenvía la orden al ESP32.
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

        # Comando: state (actuadores) o enable (sensores)
        raw_cmd = payload.get("state", payload.get("enable"))

        if not (device and comp_type and comp_id is not None and raw_cmd is not None):
            logger.warning(f"[SYSTEM/SET] Petición incompleta -> {payload}")
            return

        if comp_type not in ["sensor", "actuator"]:
            logger.warning(f"[SYSTEM/SET] Tipo inválido: {comp_type}")
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
        forward_payload = {
            "requester": requester
        }

        # === Normalización a booleanos ===
        if isinstance(raw_cmd, str):
            raw_cmd = raw_cmd.strip().lower()
            value = raw_cmd in ["1", "true", "on", "enabled"]
        else:
            value = bool(raw_cmd)

        if comp_type == "actuator":
            forward_payload["state"] = value
            command = value
        else:
            forward_payload["enable"] = value
            command = value

        # === Publicar al ESP32 (QoS 1) ===
        client.publish(
            esp_topic,
            json.dumps(forward_payload),
            qos=1
        )
        logger.info(f"[SET] Enviado -> {esp_topic} ({command})")

        # === Actualizar BD (solo actuadores) ===
        if comp_type == "actuator":
            db.execute(
                """
                UPDATE actuators
                SET state=%s, last_seen=NOW()
                WHERE device_name=%s AND id=%s
                """,
                (command, device, comp_id),
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
            "value": command,
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
