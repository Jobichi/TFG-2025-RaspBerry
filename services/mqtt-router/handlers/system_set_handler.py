from config import logger
import json
from datetime import datetime
from handlers.utils import safe_json_dumps

def handle(db, client, topic, payload):
    """
    Gestiona las peticiones 'system/set/#' de los microservicios internos.
    Valida los datos y reenvía la orden al ESP32 correspondiente.
    """
    try:
        # === Identificar servicio solicitante ===
        parts = topic.split("/")
        requester = parts[2] if len(parts) > 2 else "unknown"

        # === Extraer datos ===
        device = payload.get("device")
        comp_type = payload.get("type")
        comp_id = payload.get("id")
        command = payload.get("state") or payload.get("enabled")

        if not (device and comp_type and comp_id is not None and command is not None):
            logger.warning(f"[SYSTEM/SET] Petición incompleta -> {payload}")
            return

        # === Validar tipo de componente ===
        if comp_type not in ["actuator", "sensor"]:
            logger.warning(f"[SYSTEM/SET] Tipo de componente inválido: {comp_type}")
            return

        # === Verificar existencia en BBDD ===
        query = f"SELECT * FROM {comp_type}s WHERE device_name=%s AND id=%s"
        result = db.execute(query, (device, comp_id))
        if not result:
            logger.warning(f"[SYSTEM/SET] {comp_type} {comp_id} no encontrado en {device}")
            error_msg = {"error": "component_not_found", "device": device, "id": comp_id}
            client.publish(f"system/response/{requester}/{comp_type}/{device}/{comp_id}", json.dumps(error_msg))
            return

        # === Preparar tópico y payload de envío ===
        esp_topic = f"set/{device}/{comp_type}/{comp_id}"
        forward_payload = {}

        if comp_type == "actuator":
            forward_payload["state"] = command
        elif comp_type == "sensor":
            # En sensores, el comando se interpreta como habilitar/deshabilitar
            forward_payload["enabled"] = command

        forward_payload["requester"] = requester

        # === Publicar al ESP32 ===
        client.publish(esp_topic, json.dumps(forward_payload))
        logger.info(f"[SET] Orden enviada -> {esp_topic} ({command})")

        # === Actualizar DB (solo actuadores) ===
        if comp_type == "actuator":
            query_upd = """
                UPDATE actuators SET state=%s, last_seen=NOW()
                WHERE device_name=%s AND id=%s
            """
            db.execute(query_upd, (command, device, comp_id), commit=True)
            logger.info(f"[DB] Estado actualizado: {device}/{comp_type}/{comp_id} -> {command}")

        # === Publicar notificación de acción ===
        notify_msg = {
            "device": device,
            "type": comp_type,
            "id": comp_id,
            "command": command,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "source": requester
        }
        client.publish("system/notify/set", safe_json_dumps(notify_msg))

    except Exception as e:
        logger.error(f"[SYSTEM/SET] Error procesando petición: {e}")
