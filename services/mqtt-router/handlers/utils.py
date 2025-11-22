import json
from datetime import datetime, date
from config import logger

def safe_json_dumps(obj):
    def default(o):
        if isinstance(o, (datetime, date)):
            return o.strftime("%Y-%m-%d %H:%M:%S")

        raise TypeError(f"Type {type(o)} not serializable")

    return json.dumps(obj, default=default)


def ensure_device(db, device):
    """Crea o refresca el dispositivo para cumplir FK y mantener last_seen."""
    if not device:
        return
    try:
        db.execute(
            """
            INSERT INTO devices (device_name, last_seen)
            VALUES (%s, NOW())
            ON DUPLICATE KEY UPDATE last_seen=NOW()
            """,
            (device,),
            commit=True
        )
    except Exception as e:
        logger.error(f"[DB] Error asegurando dispositivo {device}: {e}")


def ensure_component(db, comp_type, device, comp_id, name=None, location=None):
    """Garantiza que exista el componente en su tabla sin machacar datos previos."""
    if comp_type not in ["sensor", "actuator"] or device is None or comp_id is None:
        return

    if comp_type == "sensor":
        query = """
            INSERT INTO sensors (id, device_name, name, location, last_seen)
            VALUES (%s, %s, %s, %s, NOW())
            ON DUPLICATE KEY UPDATE
                name = IFNULL(sensors.name, VALUES(name)),
                location = IFNULL(sensors.location, VALUES(location)),
                last_seen = NOW()
        """
    else:
        query = """
            INSERT INTO actuators (id, device_name, name, location, last_seen)
            VALUES (%s, %s, %s, %s, NOW())
            ON DUPLICATE KEY UPDATE
                name = IFNULL(actuators.name, VALUES(name)),
                location = IFNULL(actuators.location, VALUES(location)),
                last_seen = NOW()
        """

    try:
        db.execute(query, (comp_id, device, name, location), commit=True)
    except Exception as e:
        logger.error(f"[DB] Error asegurando {comp_type} {device}/{comp_id}: {e}")
