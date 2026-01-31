import threading
from typing import Dict, Optional, Any
from config import logger


class Snapshot:
    """
    Mantiene una copia en memoria del estado del sistema:
    - devices
    - sensors
    - actuators

    Fuentes de datos soportadas:
    1) Full dump (router):
       system/response/<service>/devices/<id>
       system/response/<service>/sensors/<id>
       system/response/<service>/actuators/<id>

    2) Eventos (router -> notify):
       system/notify/<device>/announce
       Payload esperado:
       {"device": "...", "type": "sensor|actuator", "id": <int>, "name": "...",
        "location": "...", "status": "registered|unregistered|...", "timestamp": "..."}
    """

    def __init__(self):
        self.devices: Dict[str, Dict[str, Dict[Any, dict]]] = {}
        self.snapshot_ts: Optional[str] = None
        self.ready = False
        # RLock para permitir llamadas internas (p.ej. ingest -> mark_ready)
        self._lock = threading.RLock()

    # ==========================================================
    #  INGESTA DE MENSAJES
    # ==========================================================
    def ingest(self, topic: str, payload: dict):
        """
        Ingesta mensajes del router para construir/actualizar el snapshot.
        Soporta tanto full dump (system/response/...) como eventos (system/notify/...).
        """
        if not topic:
            return

        parts = topic.split("/")

        if len(parts) < 3:
            logger.debug(f"[SNAPSHOT] Topic inválido: {topic}")
            return

        root = parts[0]

        with self._lock:
            if root == "system" and len(parts) >= 2:
                subroot = parts[1]

                if subroot == "response":
                    self._ingest_response(parts, topic, payload)
                    # Nota: aquí NO marcamos ready automáticamente; lo controla el caller
                    return

                if subroot == "notify":
                    self._ingest_notify(parts, topic, payload)
                    # Un evento notify puede hacer el snapshot "usable" aunque no haya full dump
                    self.mark_ready("evento notify/announce")
                    return

            # Compat: si el topic que te llega no es system/*, se ignora
            logger.debug(f"[SNAPSHOT] Topic no soportado: {topic}")

    def mark_complete(self):
        """
        Marca el snapshot como completo.
        Útil tras recibir el full dump inicial (system/response/...).
        """
        with self._lock:
            self.ready = True
            logger.info(f"[SNAPSHOT] Snapshot completo. Devices cargados: {len(self.devices)}")

    def mark_ready(self, reason: str = ""):
        """Marca el snapshot como listo en cuanto sea usable.

        No implica que el snapshot esté "completo" (volcado total), solo que hay datos
        suficientes para resolver objetivos (sensores/actuadores).
        """
        with self._lock:
            if self.ready:
                return
            if not self.is_usable():
                return
            self.ready = True
            extra = f" ({reason})" if reason else ""
            logger.info(f"[SNAPSHOT] Snapshot listo{extra}")

    # ==========================================================
    #  INGESTA: system/response/...
    # ==========================================================
    def _ingest_response(self, parts: list, topic: str, payload: dict):
        # system/response/<service>/<table>/<id>
        if len(parts) < 5:
            logger.debug(f"[SNAPSHOT] Topic response inválido: {topic}")
            return

        table = parts[3]

        if table == "devices":
            self._add_device(payload)
        elif table == "sensors":
            self._add_sensor(payload)
        elif table == "actuators":
            self._add_actuator(payload)
        else:
            logger.debug(f"[SNAPSHOT] Tabla desconocida en response: {table}")

    # ==========================================================
    #  INGESTA: system/notify/...
    # ==========================================================
    def _ingest_notify(self, parts: list, topic: str, payload: dict):
        # system/notify/<device>/announce
        if len(parts) < 4:
            logger.debug(f"[SNAPSHOT] Topic notify inválido: {topic}")
            return

        event = parts[3]

        if event != "announce":
            # Si mañana metes system/notify/<device>/status, etc., puedes extender aquí
            logger.debug(f"[SNAPSHOT] Evento notify no soportado: {event}")
            return

        self._apply_announce(payload)

    def _apply_announce(self, data: dict):
        """
        Aplica un announce incremental al snapshot.
        """
        device = data.get("device")
        comp_type = data.get("type")
        comp_id = data.get("id")
        status = str(data.get("status", "registered")).lower()

        if device is None or comp_type is None or comp_id is None:
            return

        # Normaliza id (por si llega como string)
        try:
            comp_id = int(comp_id)
        except (TypeError, ValueError):
            pass

        # Garantiza estructura base del device
        self._ensure_device(device)

        # Normaliza estructura interna parecida a la del full dump
        normalized = {
            "device_name": device,
            "id": comp_id,
            "name": data.get("name"),
            "location": data.get("location"),
            "status": data.get("status"),
            # opcional: para tu lógica de "last_seen"/auditoría
            "last_seen": data.get("timestamp"),
        }

        # Si quieres que snapshot_ts refleje el último evento recibido:
        self._update_snapshot_ts({"snapshot_ts": data.get("timestamp")})

        bucket = None
        if comp_type == "sensor":
            bucket = "sensors"
        elif comp_type == "actuator":
            bucket = "actuators"
        else:
            logger.debug(f"[SNAPSHOT] Tipo announce desconocido: {comp_type}")
            return

        if status == "unregistered":
            # Si en algún momento publicas bajas, esto limpia el snapshot
            if comp_id in self.devices[device][bucket]:
                del self.devices[device][bucket][comp_id]
                logger.debug(f"[SNAPSHOT] {bucket[:-1].capitalize()} eliminado: {device}/{comp_id}")
            return

        # Por defecto: upsert
        self.devices[device][bucket][comp_id] = normalized
        logger.debug(f"[SNAPSHOT] {bucket[:-1].capitalize()} upsert: {device}/{comp_id}")

    # ==========================================================
    #  MÉTODOS INTERNOS DE CONSTRUCCIÓN
    # ==========================================================
    def _ensure_device(self, device_name: str):
        if device_name not in self.devices:
            self.devices[device_name] = {"sensors": {}, "actuators": {}}

    def _add_device(self, data: dict):
        device_name = data.get("device_name")
        if not device_name:
            return

        self._ensure_device(device_name)
        self._update_snapshot_ts(data)
        logger.debug(f"[SNAPSHOT] Device cargado: {device_name}")

    def _add_sensor(self, data: dict):
        device = data.get("device_name")
        sensor_id = data.get("id")

        if device is None or sensor_id is None:
            return

        self._ensure_device(device)

        try:
            sensor_id = int(sensor_id)
        except (TypeError, ValueError):
            pass

        self.devices[device]["sensors"][sensor_id] = data
        self._update_snapshot_ts(data)
        logger.debug(f"[SNAPSHOT] Sensor cargado: {device}/{sensor_id}")

    def _add_actuator(self, data: dict):
        device = data.get("device_name")
        actuator_id = data.get("id")

        if device is None or actuator_id is None:
            return

        self._ensure_device(device)

        try:
            actuator_id = int(actuator_id)
        except (TypeError, ValueError):
            pass

        self.devices[device]["actuators"][actuator_id] = data
        self._update_snapshot_ts(data)
        logger.debug(f"[SNAPSHOT] Actuator cargado: {device}/{actuator_id}")

    def _update_snapshot_ts(self, data: dict):
        ts = data.get("snapshot_ts")
        if not ts:
            return

        # Si prefieres mantener el primero, deja como lo tenías.
        # Si prefieres "último evento", sobrescribe siempre.
        self.snapshot_ts = ts

    # ==========================================================
    #  CONSULTAS (API PARA NLP / RESOLVER)
    # ==========================================================
    def is_ready(self) -> bool:
        return self.ready

    def is_usable(self) -> bool:
        for dev in self.devices.values():
            if dev["sensors"] or dev["actuators"]:
                return True
        return False

    def get_device_names(self):
        return list(self.devices.keys())

    def find_actuator(self, name: Optional[str] = None, location: Optional[str] = None) -> Optional[dict]:
        for device, comps in self.devices.items():
            for aid, actuator in comps["actuators"].items():
                if name and name.lower() not in str(actuator.get("name", "")).lower():
                    continue
                if location and location.lower() not in str(actuator.get("location", "")).lower():
                    continue
                return {"device": device, "id": aid, "data": actuator}
        return None

    def find_sensor(self, name: Optional[str] = None, location: Optional[str] = None) -> Optional[dict]:
        for device, comps in self.devices.items():
            for sid, sensor in comps["sensors"].items():
                if name and name.lower() not in str(sensor.get("name", "")).lower():
                    continue
                if location and location.lower() not in str(sensor.get("location", "")).lower():
                    continue
                return {"device": device, "id": sid, "data": sensor}
        return None

    # ==========================================================
    #  DEBUG
    # ==========================================================
    def dump(self):
        return {"snapshot_ts": self.snapshot_ts, "devices": self.devices}
