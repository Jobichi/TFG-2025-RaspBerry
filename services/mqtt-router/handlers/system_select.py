from config import logger
from handlers.utils import safe_json_dumps
from datetime import datetime
import json


def handle(db, client, topic, payload):
    """
    Handler para system/select/# (acceso a BBDD para microservicios internos).
    """

    try:
        # === Identificar requester ===
        parts = topic.split("/")
        requester = parts[2] if len(parts) > 2 else "unknown"

        # === Extraer parámetros ===
        req_type = payload.get("request")
        device = payload.get("device")
        comp_id = payload.get("id")

        try:
            comp_id = int(comp_id) if comp_id is not None else None
        except ValueError:
            logger.warning(f"[SYSTEM/SELECT] ID inválido: {comp_id}")
            return

        if not req_type:
            logger.warning("[SYSTEM/SELECT] Falta campo 'request'")
            return

        # ===============================================================
        # ALERTAS
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
                client.publish(
                    f"system/response/{requester}/alerts/empty",
                    json.dumps({"status": "no_alerts"}),
                    qos=1
                )
                return

            for row in results:
                client.publish(
                    f"system/response/{requester}/alerts/{row['id']}",
                    safe_json_dumps(row),
                    qos=1
                )

            logger.info(f"[SYSTEM/SELECT] Enviadas {len(results)} alertas")
            return

        # ===============================================================
        # DISPOSITIVOS
        # ===============================================================
        if req_type == "devices":
            results = db.execute("SELECT * FROM devices ORDER BY device_name")

            if not results:
                client.publish(
                    f"system/response/{requester}/devices/empty",
                    json.dumps({"status": "no_devices"}),
                    qos=1
                )
                return

            for row in results:
                client.publish(
                    f"system/response/{requester}/devices/{row['device_name']}",
                    safe_json_dumps(row),
                    qos=1
                )
            return

        # ===============================================================
        # SENSORES / ACTUADORES
        # ===============================================================
        if req_type in ["sensors", "actuators"]:
            table = req_type

            if device and comp_id is not None:
                query = f"SELECT * FROM {table} WHERE device_name=%s AND id=%s"
                params = (device, comp_id)
            elif device:
                query = f"SELECT * FROM {table} WHERE device_name=%s ORDER BY id"
                params = (device,)
            else:
                query = f"SELECT * FROM {table} ORDER BY device_name, id"
                params = ()

            results = db.execute(query, params)

            if not results:
                client.publish(
                    f"system/response/{requester}/{table}/empty",
                    json.dumps({"status": "no_results"}),
                    qos=1
                )
                return

            for row in results:
                client.publish(
                    f"system/response/{requester}/{table}/{row['device_name']}/{row['id']}",
                    safe_json_dumps(row),
                    qos=1
                )
            return

        # ===============================================================
        # GLOBAL
        # ===============================================================
        if req_type == "all":
            snapshot_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            for table in ["devices", "sensors", "actuators"]:
                results = db.execute(f"SELECT * FROM {table}")

                for row in results:
                    row["snapshot_ts"] = snapshot_ts
                    row_id = row.get("id", row.get("device_name"))
                    client.publish(
                        f"system/response/{requester}/{table}/{row_id}",
                        safe_json_dumps(row),
                        qos=1
                    )

            logger.info("[SYSTEM/SELECT] Enviado dump completo del sistema")
            return

        # ===============================================================
        # DESCONOCIDO
        # ===============================================================
        logger.warning(f"[SYSTEM/SELECT] Tipo de petición desconocido: {req_type}")

    except Exception as e:
        logger.error(f"[SYSTEM/SELECT] Error procesando petición: {e}")
