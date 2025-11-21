from config import logger
from handlers.utils import safe_json_dumps
from datetime import datetime
import json

def handle(db, client, topic, payload):
    """
    Handler para system/select/# (acceso a BBDD para microservicios internos).
    Permite consultar:
    - sensores
    - actuadores
    - alertas
    - dispositivos
    - todo el sistema
    """

    try:
        # === Identificar requester ===
        parts = topic.split("/")
        requester = parts[2] if len(parts) > 2 else "unknown"

        # === Extraer parámetros ===
        req_type = payload.get("request")   # 'sensors', 'actuators', 'alerts', 'devices', 'all'
        device = payload.get("device")
        comp_id = payload.get("id")

        # Normalizar id
        try:
            comp_id = int(comp_id) if comp_id is not None else None
        except ValueError:
            logger.warning(f"[SYSTEM/SELECT] ID inválido: {comp_id}")
            return

        if not req_type:
            logger.warning("[SYSTEM/SELECT] Falta campo 'request'")
            return

        # ===============================================================
        #                   CONSULTA DE ALERTAS
        # ===============================================================
        if req_type == "alerts":
            limit = payload.get("limit", 10)

            if isinstance(limit, int) and limit == 0:
                query = "SELECT * FROM alerts ORDER BY severity DESC, timestamp DESC"
                params = ()
            else:
                query = "SELECT * FROM alerts ORDER BY severity DESC, timestamp DESC LIMIT %s"
                params = (limit,)

            results = db.execute(query, params)

            if not results:
                topic_resp = f"system/response/{requester}/alerts/empty"
                client.publish(topic_resp, json.dumps({"status": "no_alerts"}))
                return

            for row in results:
                topic_resp = f"system/response/{requester}/alerts/{row['id']}"
                client.publish(topic_resp, safe_json_dumps(row))

            logger.info(f"[SYSTEM/SELECT] Enviadas {len(results)} alertas")
            return

        # ===============================================================
        #                   CONSULTA DE DISPOSITIVOS
        # ===============================================================
        if req_type == "devices":
            query = "SELECT * FROM devices ORDER BY device_name"
            results = db.execute(query)

            if not results:
                topic_resp = f"system/response/{requester}/devices/empty"
                client.publish(topic_resp, json.dumps({"status": "no_devices"}))
                return

            for row in results:
                topic_resp = f"system/response/{requester}/devices/{row['device_name']}"
                client.publish(topic_resp, safe_json_dumps(row))

            return

        # ===============================================================
        #        CONSULTA DE SENSORES / ACTUADORES (específica o global)
        # ===============================================================
        if req_type in ["sensors", "actuators"]:

            table = req_type

            # SELECT por device e ID
            if device and comp_id is not None:
                query = f"SELECT * FROM {table} WHERE device_name=%s AND id=%s"
                params = (device, comp_id)

            # SELECT por device (todos los componentes)
            elif device:
                query = f"SELECT * FROM {table} WHERE device_name=%s ORDER BY id"
                params = (device,)

            # SELECT global del tipo
            else:
                query = f"SELECT * FROM {table} ORDER BY device_name, id"
                params = ()

            results = db.execute(query, params)

            if not results:
                topic_resp = f"system/response/{requester}/{table}/empty"
                client.publish(topic_resp, json.dumps({"status": "no_results"}))
                return

            for row in results:
                topic_resp = f"system/response/{requester}/{table}/{row['device_name']}/{row['id']}"
                client.publish(topic_resp, safe_json_dumps(row))

            return

        # ===============================================================
        #                   CONSULTA GLOBAL ("all")
        # ===============================================================
        if req_type == "all":
            for table in ["devices", "sensors", "actuators", "alerts"]:
                query = f"SELECT * FROM {table}"
                results = db.execute(query)

                for row in results:
                    row_id = row.get('id', row.get('device_name'))
                    topic_resp = f"system/response/{requester}/{table}/{row_id}"
                    client.publish(topic_resp, safe_json_dumps(row))

            logger.info("[SYSTEM/SELECT] Enviado dump completo del sistema")
            return

        # ===============================================================
        #                   Tipo desconocido
        # ===============================================================
        logger.warning(f"[SYSTEM/SELECT] Tipo de petición desconocido: {req_type}")

    except Exception as e:
        logger.error(f"[SYSTEM/SELECT] Error procesando petición: {e}")
