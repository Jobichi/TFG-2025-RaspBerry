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

        # === Extraer parámetros ===
        device = payload.get("device")
        comp_type = payload.get("type")
        comp_id = payload.get("id")

        comp_type = str(comp_type).strip().lower() if comp_type else None

        try:
            comp_id = int(comp_id) if comp_id is not None else None
        except ValueError:
            logger.warning(f"[SYSTEM/GET] ID inválido: {comp_id}")
            return

        if not (device and comp_type and comp_id is not None):
            logger.warning(f"[SYSTEM/GET] Payload incompleto: {payload}")
            return

        if comp_type not in ["sensor", "actuator"]:
            logger.warning(f"[SYSTEM/GET] Tipo inválido: {comp_type}")
            return

        # === Validar existencia del dispositivo ===
        if not db.execute(
            "SELECT device_name FROM devices WHERE device_name=%s",
            (device,)
        ):
            logger.warning(f"[SYSTEM/GET] Dispositivo '{device}' no registrado.")
            return

        # === Validar componente ===
        query = f"SELECT name, location FROM {comp_type}s WHERE device_name=%s AND id=%s"
        result = db.execute(query, (device, comp_id))

        if not result:
            error_payload = {
                "error": "component_not_found",
                "device": device,
                "type": comp_type,
                "id": comp_id
            }
            client.publish(
                f"system/response/{requester}/{comp_type}/{device}/{comp_id}",
                json.dumps(error_payload),
                qos=1
            )
            return

        # === Reenvío al ESP32 ===
        esp_topic = f"get/{device}/{comp_type}/{comp_id}"
        forward_payload = {
            "requester": requester
        }

        client.publish(
            esp_topic,
            json.dumps(forward_payload),
            qos=1
        )

        logger.info(f"[SYSTEM/GET] Reenviado a ESP32: {esp_topic}")

    except Exception as e:
        logger.error(f"[SYSTEM/GET] Error procesando petición: {e}")
