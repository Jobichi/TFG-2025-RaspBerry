from config import logger
from datetime import datetime
import json
from handlers.utils import ensure_device, ensure_component

def handle(db, client, topic, payload):
    """
    Handler de system/notify/#.
    Observa eventos internos, los registra y opcionalmente los almacena.
    """

    try:
        parts = topic.split("/")

        if len(parts) < 3:
            logger.warning(f"[SYSTEM/NOTIFY] Tópico inválido: {topic}")
            return

        # === Detectar tipo de evento ===
        # system/notify/<event>
        if len(parts) == 3:
            event_type = parts[2]

        # system/notify/<device>/<event>
        elif len(parts) >= 4:
            event_type = parts[3]

        else:
            event_type = "unknown"

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # === Validación del payload ===
        if not isinstance(payload, dict):
            try:
                payload = json.loads(payload)
            except Exception:
                logger.warning(f"[SYSTEM/NOTIFY] Payload no JSON en {topic}")
                return

        # === Log detallado ===
        logger.info(f"[SYSTEM/NOTIFY] [{event_type.upper()}] {payload}")

        # === Persistir updates si vienen directamente por notify ===
        if event_type == "update":
            try:
                device = payload.get("device")
                comp_type = payload.get("type")
                comp_id = payload.get("id")

                if not (device and comp_type and comp_id is not None):
                    logger.warning(f"[SYSTEM/NOTIFY] Update incompleto: {payload}")
                elif comp_type not in ["sensor", "actuator"]:
                    logger.warning(f"[SYSTEM/NOTIFY] Tipo inválido: {comp_type}")
                else:
                    # Garantizar filas previas para que el UPDATE funcione
                    ensure_device(db, device)
                    ensure_component(
                        db,
                        comp_type,
                        device,
                        comp_id,
                        payload.get("name"),
                        payload.get("location"),
                    )

                    if comp_type == "sensor":
                        value = payload.get("value")
                        unit = payload.get("units") or payload.get("unit")

                        # Si no viene unidad, intentar reutilizar la que ya tenga el sensor
                        if unit in (None, ""):
                            try:
                                prev = db.execute(
                                    "SELECT unit FROM sensors WHERE device_name=%s AND id=%s LIMIT 1",
                                    (device, comp_id),
                                )
                                if prev and prev[0].get("unit"):
                                    unit = prev[0]["unit"]
                            except Exception:
                                # Si falla la lectura, seguimos sin unidad
                                pass

                        if value is None:
                            logger.warning(f"[SYSTEM/NOTIFY] Sensor sin valor ({device}/{comp_id})")
                        else:
                            db.execute(
                                """
                                UPDATE sensors
                                SET value=%s, unit=%s, last_seen=NOW()
                                WHERE device_name=%s AND id=%s
                                """,
                                (value, unit, device, comp_id),
                                commit=True
                            )
                            logger.info(f"[DB] Sensor (notify) actualizado: {device}/{comp_id} -> {value} {unit or ''}")
                    else:
                        state = payload.get("state")
                        if state is None:
                            logger.warning(f"[SYSTEM/NOTIFY] Actuador sin estado ({device}/{comp_id})")
                        else:
                            db.execute(
                                """
                                UPDATE actuators
                                SET state=%s, last_seen=NOW()
                                WHERE device_name=%s AND id=%s
                                """,
                                (state, device, comp_id),
                                commit=True
                            )
                            logger.info(f"[DB] Actuador (notify) actualizado: {device}/{comp_id} -> {state}")

                    # Mantener vivo el dispositivo si pudimos procesar algo
                    if device:
                        db.execute(
                            "UPDATE devices SET last_seen=NOW() WHERE device_name=%s",
                            (device,),
                            commit=True
                        )

            except Exception as e:
                logger.error(f"[SYSTEM/NOTIFY] Error persistiendo update: {e}")

        # === Almacenamiento opcional ===
        try:
            query = """
                INSERT INTO system_logs (timestamp, topic, event_type, payload)
                VALUES (%s, %s, %s, %s)
            """
            db.execute(query, (timestamp, topic, event_type, json.dumps(payload)), commit=True)

        except Exception:
            # Si la tabla no existe o no deseas logs persistentes → ignoramos
            pass

    except Exception as e:
        logger.error(f"[SYSTEM/NOTIFY] Error procesando notificación: {e}")
