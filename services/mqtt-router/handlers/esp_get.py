from config import logger
import json

def handle(db, client, topic, payload):
    """
    Handler de system/get/# en mqtt-router.
    Valida componente en BD y reenvía GET al ESP32 correspondiente.
    """

    try:
        # === Parseo del tópico ===
        parts = topic.split("/")
        if len(parts) < 3:
            logger.warning(f"[SYSTEM/GET] Tópico inválido: {topic}")
            return

        _, action, requester = parts[:3]

        if action != "get":
            logger.warning(f"[SYSTEM/GET] Acción no válida: {action}")
            return

        # === Obtener campos obligatorios ===
        device = payload.get("device")
        comp_type = payload.get("type")
        comp_id = payload.get("id")

        comp_type = str(comp_type).lower() if comp_type else None
        comp_id = int(comp_id) if comp_id is not None else None

        # === Valida parámetros ===
        if not (device and comp_type and comp_id is not None):
            logger.warning(f"[SYSTEM/GET] Payload incompleto: {payload}")
            return

        if comp_type not in ["sensor", "actuator"]:
            logger.warning(f"[SYSTEM/GET] Tipo inválido: {comp_type}")
            return

        # === Validar existencia de dispositivo ===
        r_dev = db.execute(
            "SELECT device_name FROM devices WHERE device_name=%s",
            (device,)
        )
        if not r_dev:
            logger.warning(f"[SYSTEM/GET] Dispositivo '{device}' no registrado.")
            return

        # === Validación componente ===
        query = f"SELECT name, location FROM {comp_type}s WHERE device_name=%s AND id=%s"
        result = db.execute(query, (device, comp_id))

        if not result:
            logger.warning(f"[SYSTEM/GET] {comp_type} {comp_id} no encontrado en {device}")
            error_payload = {
                "error": "component_not_found",
                "device": device,
                "type": comp_type,
                "id": comp_id
            }
            topic_resp = f"system/response/{requester}/{comp_type}/{device}/{comp_id}"
            client.publish(topic_resp, json.dumps(error_payload))
            return

        name = result[0]["name"]
        location = result[0]["location"]

        # === Preparar reenvío al ESP32 ===
        esp_topic = f"get/{device}/{comp_type}/{comp_id}"

        forward_payload = {
            "requester": requester,
            "name": name,
            "location": location
        }

        client.publish(esp_topic, json.dumps(forward_payload))
        logger.info(f"[SYSTEM/GET] Reenviado a ESP32: {esp_topic}")

    except Exception as e:
        logger.error(f"[SYSTEM/GET] Error procesando petición: {e}")
