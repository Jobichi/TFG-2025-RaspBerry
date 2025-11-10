from config import logger
from handlers.utils import safe_json_dumps

def handle(db, client, topic, payload):
    """
    Procesa peticiones 'system/select/#' provenientes de microservicios internos.
    Obtiene información de la base de datos (solo lectura) y publica las respuestas.
    """

    try:
        # === Identificación del solicitante ===
        parts = topic.split("/")
        requester = parts[2] if len(parts) > 2 else "unknown"

        # === Extracción de parámetros ===
        req_type = payload.get("request")   # 'sensors', 'actuators' o 'all'
        device = payload.get("device")      # nombre del dispositivo o 'all'
        comp_id = payload.get("id")         # opcional

        if not req_type:
            logger.warning(f"[SYSTEM/SELECT] Petición sin campo 'request' ({topic})")
            return

        # === Caso 1: Solicitud global de todos los dispositivos ===
        if req_type == "all" or device == "all":
            for table in ["sensors", "actuators"]:
                query = f"SELECT * FROM {table} ORDER BY device_name, id"
                results = db.execute(query)
                for row in results:
                    topic_resp = f"system/response/{requester}/{table}/{row['device_name']}/{row['id']}"
                    client.publish(topic_resp, safe_json_dumps(row))
            logger.info(f"[SYSTEM/SELECT] Enviados todos los sensores y actuadores a {requester}")
            return

        # === Caso 2: Solicitud específica de tipo 'sensors' o 'actuators' ===
        if req_type in ["sensors", "actuators"]:
            if device and comp_id is not None:
                query = f"SELECT * FROM {req_type} WHERE device_name=%s AND id=%s"
                params = (device, comp_id)
            elif device:
                query = f"SELECT * FROM {req_type} WHERE device_name=%s ORDER BY id"
                params = (device,)
            else:
                query = f"SELECT * FROM {req_type} ORDER BY device_name, id"
                params = ()

            results = db.execute(query, params)
            if not results:
                logger.info(f"[SYSTEM/SELECT] Sin resultados para {req_type} ({device or 'todos'})")
                return

            for row in results:
                topic_resp = f"system/response/{requester}/{req_type}/{row['device_name']}/{row['id']}"
                client.publish(topic_resp, safe_json_dumps(row))
            logger.info(f"[SYSTEM/SELECT] {len(results)} registros de {req_type} enviados a {requester}")
            return

        # === Caso 3: Solicitud de alertas ===
        if req_type == "alerts":
            limit = payload.get("limit", 10)

            if isinstance(limit, int) and limit == 0:
                # Enviar todas las alertas sin límite
                query = "SELECT * FROM alerts ORDER BY timestamp DESC"
                params = ()
                logger.info(f"[SYSTEM/SELECT] Solicitadas TODAS las alertas por {requester}")
            else:
                # Enviar las N más recientes
                query = "SELECT * FROM alerts ORDER BY timestamp DESC LIMIT %s"
                params = (limit,)

            results = db.execute(query, params)
            if not results:
                logger.info("[SYSTEM/SELECT] No hay alertas registradas.")
                return

            for row in results:
                topic_resp = f"system/response/{requester}/alerts/{row['id']}"
                client.publish(topic_resp, safe_json_dumps(row))

            logger.info(f"[SYSTEM/SELECT] {len(results)} alertas enviadas a {requester}")
            return

        # === Tipo no reconocido ===
        logger.warning(f"[SYSTEM/SELECT] Tipo de petición desconocido: {req_type}")

    except Exception as e:
        logger.error(f"[SYSTEM/SELECT] Error procesando petición: {e}")
