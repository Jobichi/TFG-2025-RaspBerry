#!/bin/bash
set -e

# === VARIABLES GLOBALES ===
ENV_FILE="./.env"
ENV_ENCRYPTED="./.env.gpg"
DOCKER_COMPOSE="docker compose"

# === COLORES ===
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[1;34m'
NC='\033[0m'

echo -e "${BLUE}=== Verificando e instalando dependencias ===${NC}"

# --- Verificar Docker ---
if ! command -v docker &> /dev/null; then
  echo "[INFO] Docker no encontrado. Instalando..."
  curl -fsSL https://get.docker.com | sh
else
  echo "[INFO] Docker ya está instalado."
fi

# --- Verificar Docker Compose plugin ---
if ! docker compose version &> /dev/null; then
  echo "[INFO] Plugin de Docker Compose no encontrado. Instalando..."
  sudo apt-get install -y docker-compose-plugin
else
  echo "[INFO] Docker Compose plugin ya está instalado."
fi

# --- Verificar GPG ---
if ! command -v gpg &> /dev/null; then
  echo "[INFO] GPG no encontrado. Instalando..."
  sudo apt-get install -y gnupg
else
  echo "[INFO] GPG ya está instalado."
fi

# === CONFIGURAR VARIABLES DE ENTORNO ===
echo -e "\n${BLUE}=== Configurando variables de entorno ===${NC}"

# --- Desencriptar .env si existe versión cifrada ---
if [ -f "$ENV_ENCRYPTED" ]; then
  echo "[INFO] Se detectó .env.gpg — desencriptando..."
  gpg --quiet --batch --yes -o "$ENV_FILE" -d "$ENV_ENCRYPTED" || {
    echo "[ERROR] No se pudo desencriptar .env.gpg"
    exit 1
  }
  echo "[INFO] .env desencriptado correctamente."
else
  echo "[INFO] .env.gpg no encontrado. Se usará o generará .env local."
  touch "$ENV_FILE"
fi

# --- Función para generar variables faltantes ---
ensure_env_var() {
  local key="$1"
  local gen_cmd="$2"
  local current
  current=$(grep -E "^${key}=" "$ENV_FILE" | cut -d'=' -f2- || true)
  if [ -z "$current" ]; then
    local value
    value=$(eval "$gen_cmd")
    sed -i "/^${key}=.*/d" "$ENV_FILE" 2>/dev/null || true
    echo "${key}=${value}" >> "$ENV_FILE"
    echo "[ENV] ${key} generado."
  fi
}

# --- Generar valores si faltan ---
ensure_env_var "MYSQL_ROOT_PASSWORD" "openssl rand -hex 16"
ensure_env_var "MYSQL_DATABASE" "echo tfgdb"
ensure_env_var "MYSQL_USER" "echo tfguser"
ensure_env_var "MYSQL_PASSWORD" "openssl rand -hex 16"
ensure_env_var "MQTT_USER" "echo admin"
ensure_env_var "MQTT_PASS" "openssl rand -hex 12"
ensure_env_var "MQTT_PORT" "echo 1883"
ensure_env_var "TELEGRAM_BOT_TOKEN" "echo REEMPLAZAR_CON_TU_TOKEN"
echo "[INFO] .env verificado y actualizado."

# --- Volver a cifrar (si quieres mantenerlo seguro) ---
if [ -f "$ENV_ENCRYPTED" ]; then
  echo "[INFO] Actualizando versión cifrada de .env..."
  gpg --yes -o "$ENV_ENCRYPTED" -c "$ENV_FILE"
fi

# === CONFIGURAR MOSQUITTO MQTT ===
echo -e "\n${BLUE}=== Configurando Mosquitto MQTT ===${NC}"

MQTT_PATH="./mqtt-docker"
if [ -d "$MQTT_PATH" ]; then
  echo "[INFO] Ajustando permisos para Mosquitto..."
  sudo chown -R 1883:1883 "$MQTT_PATH/config" "$MQTT_PATH/data" "$MQTT_PATH/log" 2>/dev/null || true
  sudo chmod -R 755 "$MQTT_PATH/config" "$MQTT_PATH/data" "$MQTT_PATH/log" 2>/dev/null || true
  echo "[INFO] Permisos de Mosquitto corregidos correctamente."
else
  echo "[WARN] No se encontró el directorio mqtt-docker. Saltando..."
fi

# === VERIFICAR MODELOS DE IA ===
echo -e "\n${BLUE}=== Verificando modelos de IA ===${NC}"

# --- Tiny-LLaMA ---
if [ -d "./models/tiny-llama" ]; then
  echo "[INFO] Modelo Tiny-LLaMA ya presente."
else
  echo "[INFO] Descargando modelo Tiny-LLaMA..."
  mkdir -p ./models/tiny-llama
  wget -q https://huggingface.co/TheBloke/TinyLlama-1.1B-Chat-v1.0/resolve/main/model.safetensors -O ./models/tiny-llama/model.safetensors
  echo "[INFO] Modelo Tiny-LLaMA descargado correctamente."
fi

# --- Vosk ---
if [ -d "./services/vosk-service/model" ]; then
  echo "[INFO] Modelo Vosk ya presente."
else
  echo "[INFO] Descargando modelo pequeño de Vosk (español)..."
  mkdir -p ./services/vosk-service
  wget -q https://alphacephei.com/vosk/models/vosk-model-small-es-0.42.zip -O ./services/vosk-service/vosk-model-small-es-0.42.zip
  unzip -qq ./services/vosk-service/vosk-model-small-es-0.42.zip -d ./services/vosk-service/
  mv ./services/vosk-service/vosk-model-small-es-0.42 ./services/vosk-service/model
  rm ./services/vosk-service/vosk-model-small-es-0.42.zip
  echo "[INFO] Modelo Vosk instalado correctamente."
fi

# === DESPLEGAR CONTENEDORES ===
echo -e "\n${BLUE}=== Desplegando contenedores Docker ===${NC}"
$DOCKER_COMPOSE build
$DOCKER_COMPOSE up -d

echo -e "\n${GREEN}✅ Todos los contenedores se han desplegado correctamente.${NC}"
echo "Puedes verificar su estado con:"
echo "   docker compose ps"
