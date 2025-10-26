#!/bin/sh
set -eu

# Asegura rutas
mkdir -p /mosquitto/config /mosquitto/data /mosquitto/log

# Si config está vacío (primer arranque con volumen montado) y faltara el conf, crea uno básico
if [ ! -f /mosquitto/config/mosquitto.conf ]; then
  echo "WARN: /mosquitto/config/mosquitto.conf no existe; creando uno básico."
  cat > /mosquitto/config/mosquitto.conf <<'EOF'
persistence true
persistence_location /mosquitto/data/
log_dest file /mosquitto/log/mosquitto.log

listener 1883
allow_anonymous false
password_file /mosquitto/config/passwordfile
EOF
fi

# Crear / Regenerar passwordfile si falta o si se fuerza con MQTT_FORCE_REGEN=1
if [ ! -f /mosquitto/config/passwordfile ] || [ "${MQTT_FORCE_REGEN:-0}" = "1" ]; then
  : "${MQTT_USER:?MQTT_USER no definido}"
  : "${MQTT_PASS:?MQTT_PASS no definido}"
  mosquitto_passwd -c -b /mosquitto/config/passwordfile "$MQTT_USER" "$MQTT_PASS"
  chmod 600 /mosquitto/config/passwordfile
fi

exec "$@"
