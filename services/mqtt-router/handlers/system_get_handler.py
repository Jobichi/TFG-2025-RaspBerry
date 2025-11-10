from config import logger
import json

def handle(db, client, topic, payload):
    """
    Gestiona las peticiones 'system/get/#' enviadas por los microservicios.
    Valida en la base de datos la existencia del componente y redirige la
    solicitud al dispositivo físico correspondiente.
    """
    try:
        # === Identificación del solicitante ===
        parts = topic.split("/")
        requester = parts[2] if len(parts) > 2 else "unknown"

        # === Extracción de parámetros ===
        device = payload.get("device")
        comp_type = payload.get("type")   # 'sensor' o 'actuator'
        comp_id = payload.get("id")

        if not (device and comp_type and comp_id is not None):
            logger.warning(f"[SYSTEM/GET] Petición incompleta -> {payload}")
            return

        # === Validación de tipo permitido ===
        if comp_type not in ["sensor", "actuator"]:
            logger.warning(f"[SYSTEM/GET] Tipo inválido: {comp_type}")
            return

        # === Verificación de existencia en BBDD ===
        query = f"SELECT * FROM {comp_type}s WHERE device_name=%s AND id=%s"
        result = db.execute(query, (device, comp_id))
        if not result:
            logger.warning(f"[SYSTEM/GET] No se encontró {comp_type} {comp_id} en {device}")
            error_payload = {
                "error": "component_not_found",
                "device": device,
                "type": comp_type,
                "id": comp_id
            }
            topic_resp = f"system/response/{requester}/{comp_type}/{device}/{comp_id}"
            client.publish(topic_resp, json.dumps(error_payload))
            return

        # === Preparar reenvío al ESP32 ===
        esp_topic = f"get/{device}/{comp_type}/{comp_id}"

        # Payload con información del requester
        forward_payload = {"requester": requester}
        # Añadir campos opcionales si existen
        for key in ["extra", "timestamp"]:
            if key in payload:
                forward_payload[key] = payload[key]

        client.publish(esp_topic, json.dumps(forward_payload))
        logger.info(f"[SYSTEM/GET] Petición reenviada a {esp_topic} (solicitante: {requester})")

    except Exception as e:
        logger.error(f"[SYSTEM/GET] Error procesando petición: {e}")
