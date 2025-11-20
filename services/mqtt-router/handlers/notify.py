from config import logger
from datetime import datetime
import json

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
