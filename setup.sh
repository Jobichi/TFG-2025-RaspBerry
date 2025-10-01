#!/bin/bash
set -e

# Ruta del .env cifrado
ENV_FILE=".env"
ENV_GPG_FILE=".env.gpg"

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

# --- 3. Levantar contenedores ---
echo "[INFO] Levantando contenedores con build..."
docker compose up --build -d

# --- 4. Mostrar estado ---
echo "[INFO] Contenedores en ejecución:"
docker ps
