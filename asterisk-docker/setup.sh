#!/bin/bash
set -e

if [ ! -f ".env.gpg" ]; then
  echo "[ERROR] Falta el archivo .env.gpg"
  exit 1
fi

echo "[INFO] Introduce la contraseña para desencriptar .env:"
gpg -d .env.gpg > .env || {
  echo "[ERROR] Contraseña incorrecta o fallo al desencriptar"
  exit 1
}

echo "[INFO] Lanzando Docker Compose..."
sudo docker compose up -d --build

chmod 600 .env
echo "[OK] Despliegue completado, .env preservado para futuros down/restart"
