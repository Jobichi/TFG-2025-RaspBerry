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

        # Agregar usuario actual al grupo docker
        sudo usermod -aG docker $USER
        echo "[INFO] Usuario $USER agregado al grupo docker. Puede necesitar re-login."
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
            sudo chmod -R 755 "$target"
            echo "   → Permisos corregidos en $target"
        else
            echo "   → Creando directorio $target"
            sudo mkdir -p "$target"
            sudo chown -R ${MQTT_UID}:${MQTT_GID} "$target"
            sudo chmod -R 755 "$target"
        fi
    done
    echo "[INFO] Permisos de Mosquitto corregidos correctamente."
}

check_gpg_installation() {
    if ! command -v gpg &> /dev/null; then
        echo "[ERROR] GPG no instalado. Instala con: sudo apt-get install gnupg"
        exit 1
    fi
}

decrypt_env_file() {
    echo "[INFO] Verificando archivo encriptado $ENV_GPG_FILE..."

    if [ ! -f "$ENV_GPG_FILE" ]; then
        echo "[ERROR] No se encontró $ENV_GPG_FILE. Aborta."
        exit 1
    fi

    # Siempre desencriptar (forzar la entrada de contraseña)
    echo "[INFO] Desencriptando $ENV_GPG_FILE a $ENV_FILE ..."
    echo "[IMPORTANTE] Se te pedirá la contraseña GPG ahora..."

    # Desencriptar mostrando progreso
    if gpg --decrypt --output "$ENV_FILE" "$ENV_GPG_FILE"; then
        echo "[INFO] Archivo desencriptado correctamente."

        # Verificar que el archivo no esté vacío y tenga contenido válido
        if [ ! -s "$ENV_FILE" ]; then
            echo "[ERROR] Archivo .env está vacío después de desencriptar"
            exit 1
        fi

        # Verificar que contiene variables de entorno
        if grep -q "=" "$ENV_FILE"; then
            echo "[INFO] Archivo .env contiene variables de entorno válidas."
        else
            echo "[WARNING] Archivo .env no parece contener variables de entorno válidas."
        fi

        # Mostrar primeras líneas (sin valores sensibles)
        echo "[INFO] Primeras variables encontradas:"
        head -n 5 "$ENV_FILE" | sed 's/=.*/=***/g'

    else
        echo "[ERROR] Falló la desencriptación. Verifica la contraseña."
        exit 1
    fi
}

download_model() {
    local MODEL_DIR="./models/tiny-llama"
    local MODEL_REPO="https://huggingface.co/TinyLlama/TinyLlama-1.1B-Chat-v1.0"

    if [ ! -d "$MODEL_DIR" ] || [ -z "$(ls -A $MODEL_DIR)" ]; then
        echo "[INFO] Descargando modelo Tiny-LLaMA (puede tardar varios minutos)..."
        mkdir -p "$MODEL_DIR"

        # Instalar git-lfs si no está
        if ! command -v git-lfs &> /dev/null; then
            echo "[INFO] Instalando git-lfs..."
            sudo apt-get update
            sudo apt-get install -y git-lfs
            git lfs install
        fi

        # Guardar directorio actual
        local current_dir=$(pwd)
        cd "$MODEL_DIR"

        # Intentar descarga con timeout
        if timeout 1200 git clone "$MODEL_REPO" . ; then
            echo "[INFO] Modelo descargado correctamente en $MODEL_DIR"
        else
            echo "[WARNING] Descarga falló o timeout. Continuando sin modelo completo."
            echo "[INFO] Puedes descargarlo manualmente después con:"
            echo "  cd $MODEL_DIR && git clone $MODEL_REPO ."
        fi

        # Volver al directorio original
        cd "$current_dir"
    else
        echo "[INFO] Modelo Tiny-LLaMA ya presente en $MODEL_DIR"
    fi
}

# --- 1. Comprobar dependencias ---
echo "=== Verificando e instalando dependencias ==="
check_and_install_docker
check_and_install_docker_compose_plugin
check_gpg_installation

# --- 2. Desencriptar .env.gpg ---
echo ""
echo "=== Configurando variables de entorno ==="
decrypt_env_file

# --- 3. Preparar entorno de Mosquitto ---
echo ""
echo "=== Configurando Mosquitto MQTT ==="
fix_mosquitto_permissions

# --- 4. Descargar modelo Tiny-LLaMA si no existe ---
echo ""
echo "=== Verificando modelo de IA ==="
download_model

# --- 5. Levantar contenedores ---
echo ""
echo "=== Desplegando contenedores ==="

# Cargar variables de entorno para Docker Compose
echo "[INFO] Cargando variables de entorno..."
set -a
source "$ENV_FILE"
set +a

echo "[INFO] Construyendo imágenes (puede tardar)..."
sudo docker compose build --no-cache

echo "[INFO] Iniciando contenedores..."
sudo docker compose up -d

# --- 6. Verificar que los contenedores estén corriendo ---
echo ""
echo "=== Verificando despliegue ==="
echo "[INFO] Esperando 10 segundos para que los contenedores inicien..."
sleep 10

echo "[INFO] Contenedores en ejecución:"
sudo docker ps

# --- 7. Mostrar logs iniciales ---
echo ""
echo "[INFO] Últimas líneas de logs:"
sudo docker compose logs --tail=20

# --- 8. Mensaje final ---
echo ""
echo "=== DESPLIEGUE COMPLETADO ==="
echo ""
echo "✅ Todos los servicios están en ejecución"
echo ""
echo "📊 Para ver los logs en tiempo real:"
echo "   sudo docker compose logs -f"
echo ""
echo "🔌 Para probar MQTT:"
echo "   mosquitto_sub -h 127.0.0.1 -p 1883 -t 'announce/#' -u \$MQTT_USER -P \$MQTT_PASS -v"
echo ""
echo "🐛 Para detener los contenedores:"
echo "   sudo docker compose down"
echo ""
echo "🔄 Para reiniciar:"
echo "   sudo docker compose restart"
