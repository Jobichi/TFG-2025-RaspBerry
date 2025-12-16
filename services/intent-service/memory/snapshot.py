import threading
from typing import Dict, Optional
from config import logger


class Snapshot:
    """
    Mantiene una copia en memoria del estado del sistema:
    - devices
    - sensors
    - actuators

    Se construye a partir de los mensajes recibidos en:
    system/response/<service>/devices/#
    system/response/<service>/sensors/#
    system/response/<service>/actuators/#
    """

    def __init__(self):
        # Estructura interna:
        # {
        #   device_name: {
        #       "sensors": { id: {...} },
        #       "actuators": { id: {...} }
        #   }
        # }
        self.devices: Dict[str, Dict] = {}

        self.snapshot_ts: Optional[str] = None
        self.ready = False

        self._lock = threading.Lock()

    # ==========================================================
    #  INGESTA DE MENSAJES DEL SNAPSHOT
    # ==========================================================
    def ingest(self, topic: str, payload: dict):
        """
        Ingesta una fila del snapshot proveniente del router.
        El topic determina si es device, sensor o actuator.
        """
        parts = topic.split("/")

        # system/response/<service>/<table>/<id>
        if len(parts) < 5:
            logger.debug(f"[SNAPSHOT] Topic inválido: {topic}")
            return

        table = parts[3]

        with self._lock:
            if table == "devices":
                self._add_device(payload)

            elif table == "sensors":
                self._add_sensor(payload)

            elif table == "actuators":
                self._add_actuator(payload)

            else:
                logger.debug(f"[SNAPSHOT] Tabla desconocida: {table}")

    def mark_complete(self):
        """
        Marca el snapshot como completo.
        Debe llamarse cuando el main considere que ya se recibió todo.
        """
        with self._lock:
            self.ready = True
            logger.info(
                f"[SNAPSHOT] Snapshot completo. Devices cargados: {len(self.devices)}"
            )

    # ==========================================================
    #  MÉTODOS INTERNOS DE CONSTRUCCIÓN
    # ==========================================================
    def _add_device(self, data: dict):
        device_name = data.get("device_name")
        if not device_name:
            return

        if device_name not in self.devices:
            self.devices[device_name] = {
                "sensors": {},
                "actuators": {}
            }

        self._update_snapshot_ts(data)

        logger.debug(f"[SNAPSHOT] Device cargado: {device_name}")

    def _add_sensor(self, data: dict):
        device = data.get("device_name")
        sensor_id = data.get("id")

        if device is None or sensor_id is None:
            return

        if device not in self.devices:
            self.devices[device] = {
                "sensors": {},
                "actuators": {}
            }

        self.devices[device]["sensors"][sensor_id] = data
        self._update_snapshot_ts(data)

        logger.debug(f"[SNAPSHOT] Sensor cargado: {device}/{sensor_id}")

    def _add_actuator(self, data: dict):
        device = data.get("device_name")
        actuator_id = data.get("id")

        if device is None or actuator_id is None:
            return

        if device not in self.devices:
            self.devices[device] = {
                "sensors": {},
                "actuators": {}
            }

        self.devices[device]["actuators"][actuator_id] = data
        self._update_snapshot_ts(data)

        logger.debug(f"[SNAPSHOT] Actuator cargado: {device}/{actuator_id}")

    def _update_snapshot_ts(self, data: dict):
        ts = data.get("snapshot_ts")
        if ts and self.snapshot_ts is None:
            self.snapshot_ts = ts

    # ==========================================================
    #  CONSULTAS (API PARA NLP / RESOLVER)
    # ==========================================================
    def is_ready(self) -> bool:
        return self.ready

    def get_device_names(self):
        return list(self.devices.keys())

    def find_actuator(
        self,
        name: Optional[str] = None,
        location: Optional[str] = None
    ) -> Optional[dict]:
        """
        Busca un actuador por nombre y/o localización.
        Devuelve el primer match.
        """
        for device, comps in self.devices.items():
            for aid, actuator in comps["actuators"].items():
                if name and name.lower() not in str(actuator.get("name", "")).lower():
                    continue
                if location and location.lower() not in str(actuator.get("location", "")).lower():
                    continue

                return {
                    "device": device,
                    "id": aid,
                    "data": actuator
                }
        return None

    def find_sensor(
        self,
        name: Optional[str] = None,
        location: Optional[str] = None
    ) -> Optional[dict]:
        """
        Busca un sensor por nombre y/o localización.
        """
        for device, comps in self.devices.items():
            for sid, sensor in comps["sensors"].items():
                if name and name.lower() not in str(sensor.get("name", "")).lower():
                    continue
                if location and location.lower() not in str(sensor.get("location", "")).lower():
                    continue

                return {
                    "device": device,
                    "id": sid,
                    "data": sensor
                }
        return None

    # ==========================================================
    #  DEBUG
    # ==========================================================
    def dump(self):
        """
        Devuelve el snapshot completo (solo para debug).
        """
        return {
            "snapshot_ts": self.snapshot_ts,
            "devices": self.devices
        }
