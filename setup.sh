#!/bin/bash
set -e

# --- Variables ---
ENV_FILE=".env"
ENV_GPG_FILE=".env.gpg"

MQTT_PATH="./mqtt-docker"
MQTT_UID=1883
MQTT_GID=1883

# --- Funciones auxiliares ---
check_and_install_docker() {
    if ! command -v docker &> /dev/null; then
        echo "[INFO] Docker no encontrado. Instalando..."
        curl -fsSL https://get.docker.com -o get-docker.sh
        sh get-docker.sh
        rm get-docker.sh
        echo "[INFO] Docker instalado correctamente."
    else
        echo "[INFO] Docker ya está instalado."
    fi
}

check_and_install_docker_compose_plugin() {
    if ! docker compose version &> /dev/null; then
        echo "[INFO] Docker Compose plugin no encontrado. Instalando..."
        sudo apt-get update
        sudo apt-get install -y docker-compose-plugin
        echo "[INFO] Docker Compose plugin instalado correctamente."
    else
        echo "[INFO] Docker Compose plugin ya está instalado."
    fi
}

fix_mosquitto_permissions() {
    echo "[INFO] Ajustando permisos para Mosquitto..."
    for dir in config data log; do
        local target="${MQTT_PATH}/${dir}"
        if [ -d "$target" ]; then
            sudo chown -R ${MQTT_UID}:${MQTT_GID} "$target"
            echo "   → Permisos corregidos en $target"
        else
            echo "   → Creando directorio $target"
            mkdir -p "$target"
            sudo chown -R ${MQTT_UID}:${MQTT_GID} "$target"
        fi
    done
    echo "[INFO] Permisos de Mosquitto corregidos correctamente."
}

# --- 1. Comprobar dependencias ---
check_and_install_docker
check_and_install_docker_compose_plugin

# --- 2. Desencriptar .env.gpg ---
if [ -f "$ENV_GPG_FILE" ]; then
    if [ ! -f "$ENV_FILE" ] || [ "$ENV_GPG_FILE" -nt "$ENV_FILE" ]; then
        echo "[INFO] Desencriptando $ENV_GPG_FILE a $ENV_FILE ..."
        gpg --decrypt "$ENV_GPG_FILE" > "$ENV_FILE"
    else
        echo "[INFO] $ENV_FILE ya está actualizado, no se desencripta."
    fi
else
    echo "[ERROR] No se encontró $ENV_GPG_FILE. Aborta."
    exit 1
fi

# --- 3. Preparar entorno de Mosquitto ---
fix_mosquitto_permissions

# --- 3.5. Descargar modelo Tiny-LLaMA si no existe ---
MODEL_DIR="./models/tiny-llama"
MODEL_REPO="https://huggingface.co/TinyLlama/TinyLlama-1.1B-Chat-v1.0"

if [ ! -d "$MODEL_DIR" ] || [ -z "$(ls -A $MODEL_DIR)" ]; then
    echo "[INFO] Descargando modelo Tiny-LLaMA..."
    mkdir -p "$MODEL_DIR"
    cd "$MODEL_DIR"

    # Instalar git-lfs si no está
    if ! command -v git-lfs &> /dev/null; then
        echo "[INFO] Instalando git-lfs..."
        sudo apt-get update
        sudo apt-get install -y git-lfs
        git lfs install
    fi

    git clone "$MODEL_REPO" .
    echo "[INFO] Modelo descargado en $MODEL_DIR"
    cd - > /dev/null
else
    echo "[INFO] Modelo Tiny-LLaMA ya presente en $MODEL_DIR"
fi


# --- 4. Levantar contenedores ---
echo "[INFO] Levantando contenedores con build..."
docker compose build --no-cache
docker compose up -d

# --- 5. Mostrar estado ---
echo "[INFO] Contenedores en ejecución:"
docker ps

# --- 6. Mensaje final ---
echo ""
echo "[OK] Despliegue completado."
echo "Puedes probar MQTT con:"
echo "  mosquitto_sub -h 127.0.0.1 -p 1883 -t 'announce/#' -u \$MQTT_USER -P \$MQTT_PASS -v"
