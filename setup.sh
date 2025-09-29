#!/bin/bash
set -e

# Ruta del .env cifrado
ENV_FILE=".env"
ENV_GPG_FILE=".env.gpg"

# 1. Desencriptar .env.gpg a .env si no existe o es más viejo
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

# 2. Levantar docker-compose
echo "[INFO] Levantando contenedores con build..."
docker-compose up --build -d

# 3. Mostrar estado
echo "[INFO] Contenedores en ejecución:"
docker ps
