import os
import json
import logging
import asyncio
import time
import threading
import paho.mqtt.client as mqtt

from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# =========================
# LOGGING
# =========================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# =========================
# ENV / CONFIG
# =========================
TOKEN = os.getenv("TELEGRAM_API_KEY")

MQTT_HOST = os.getenv("MQTT_HOST", "mosquitto")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_USER = os.getenv("MQTT_USER", "admin")
MQTT_PASS = os.getenv("MQTT_PASS", "admin1234")

# IMPORTANTE: Debe coincidir con el "requester" al que publica mqtt-router en system/response/<requester>/...
SERVICE_NAME = os.getenv("MQTT_SERVICE_NAME", "telegram-service")

TOPIC_SELECT = f"system/select/{SERVICE_NAME}"
TOPIC_GET = f"system/get/{SERVICE_NAME}"
TOPIC_SET = f"system/set/{SERVICE_NAME}"

TOPIC_RESPONSE_PREFIX = f"system/response/{SERVICE_NAME}/"
TOPIC_NOTIFY_ALERT = "system/notify/alert"

mqtt_client = None
mqtt_connected = threading.Event()

# Cache de inventario (desde BBDD via system/select)
device_cache = {"sensors": {}, "actuators": {}}

# Sesiones por usuario: control básico de “pending”
user_sessions = {}

# =========================
# HELPERS / NORMALIZERS
# =========================
def normalize_bool_state(value):
    """
    Normaliza estados/booleanos desde bool, numérico o texto.
    Devuelve True/False.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        v = value.strip().lower()
        return v in ("1", "true", "on", "yes", "active", "enabled")
    return False


def get_enabled_field(d, default=None):
    """
    Acepta 'enabled' o 'enable' y lo normaliza a bool.
    Si no existe ninguno, devuelve default.
    """
    if not isinstance(d, dict):
        return default
    if "enabled" in d:
        return normalize_bool_state(d.get("enabled"))
    if "enable" in d:
        return normalize_bool_state(d.get("enable"))
    return default


def normalize_inventory_payload(data):
    """
    Normaliza payloads de inventario para que siempre exista la clave 'enabled'
    cuando el broker mande 'enable' (sin 'd').
    """
    if isinstance(data, dict) and "enabled" not in data and "enable" in data:
        data["enabled"] = data.get("enable")
    return data


# =========================
# HELPERS UI
# =========================
def build_main_keyboard():
    keyboard = [
        ["Sensores", "Actuadores"],
        ["Alertas", "Actualizar"],
        ["Ayuda", "Menu principal"],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)


def build_device_menu(req_type):
    devices = list(device_cache[req_type].keys())

    if not devices:
        return InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("Actualizar", callback_data=f"refresh|{req_type}")],
                [InlineKeyboardButton("Volver", callback_data="main_menu")],
            ]
        )

    keyboard = []
    for dev in devices:
        components = device_cache[req_type].get(dev, [])
        button_text = f"{dev} ({len(components)})"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"device|{req_type}|{dev}")])

    keyboard.append([InlineKeyboardButton("Actualizar", callback_data=f"refresh|{req_type}")])
    keyboard.append([InlineKeyboardButton("Volver", callback_data="main_menu")])
    return InlineKeyboardMarkup(keyboard)


def build_component_menu(req_type, device):
    items = device_cache[req_type].get(device, [])

    if not items:
        return InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("Actualizar", callback_data=f"refresh_component|{req_type}|{device}")],
                [InlineKeyboardButton("Atras", callback_data=f"back|{req_type}")],
            ]
        )

    keyboard = []
    for item in items:
        button_text = f"{item.get('name', 'SinNombre')} (ID {item.get('id')})"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"component|{req_type}|{device}|{item['id']}")])

    keyboard.append(
        [
            InlineKeyboardButton("Actualizar", callback_data=f"refresh_component|{req_type}|{device}"),
            InlineKeyboardButton("Atras", callback_data=f"back|{req_type}"),
        ]
    )
    return InlineKeyboardMarkup(keyboard)


# =========================
# SESSION HELPERS
# =========================
def get_user_session(user_id):
    if user_id not in user_sessions:
        user_sessions[user_id] = {
            "last_action": time.time(),
            "pending_requests": set(),  # {"sensors","actuators","alerts"}
            "last_chat_id": None,       # para responder al chat correcto
        }
    return user_sessions[user_id]


def update_user_session(user_id, chat_id=None):
    session = get_user_session(user_id)
    session["last_action"] = time.time()
    if chat_id is not None:
        session["last_chat_id"] = chat_id
    return session


# =========================
# MQTT PUBLISH HELPERS
# =========================
def mqtt_select(request, device=None, comp_id=None, limit=None):
    global mqtt_client
    if mqtt_client is None or not mqtt_connected.is_set():
        logger.warning("[MQTT] No conectado aún; mqtt_select ignorado.")
        return

    payload = {"request": request}
    if device is not None:
        payload["device"] = device
    if comp_id is not None:
        payload["id"] = int(comp_id)
    if limit is not None:
        payload["limit"] = int(limit)

    logger.info("[MQTT][PUB] %s %s", TOPIC_SELECT, payload)
    mqtt_client.publish(TOPIC_SELECT, json.dumps(payload), qos=1)


def mqtt_get(device, comp_type, comp_id):
    global mqtt_client
    if mqtt_client is None or not mqtt_connected.is_set():
        logger.warning("[MQTT] No conectado aún; mqtt_get ignorado.")
        return

    payload = {"device": device, "type": comp_type, "id": int(comp_id)}
    logger.info("[MQTT][PUB] %s %s", TOPIC_GET, payload)
    mqtt_client.publish(TOPIC_GET, json.dumps(payload), qos=1)


# =========================
# TELEGRAM COMMANDS
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat_id = update.effective_chat.id
    update_user_session(user.id, chat_id=chat_id)

    app = context.application
    if "active_chats" not in app.bot_data:
        app.bot_data["active_chats"] = set()
    app.bot_data["active_chats"].add(chat_id)

    text = (
        "Bot de sistema:\n"
        "- Sensores: consulta de inventario y lectura en tiempo real\n"
        "- Actuadores: consulta de inventario y lectura en tiempo real\n"
        "- Alertas: notificaciones desde system/notify/alert\n\n"
        f"MQTT service: {SERVICE_NAME}\n"
        f"Escuchando: {TOPIC_RESPONSE_PREFIX}#\n"
    )
    await update.message.reply_text(text, reply_markup=build_main_keyboard())


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "Guia rapida:\n"
        "1) Sensores -> eliges dispositivo -> eliges sensor (lectura en tiempo real)\n"
        "2) Actuadores -> eliges dispositivo -> eliges actuador (lectura en tiempo real)\n"
        "3) Alertas -> consulta ultimas alertas en BBDD\n"
        "4) Actualizar -> refresca inventario desde BBDD\n"
    )
    await update.message.reply_text(text, reply_markup=build_main_keyboard())


# =========================
# MENU HANDLERS
# =========================
async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat_id = update.effective_chat.id
    update_user_session(user.id, chat_id=chat_id)

    text = (update.message.text or "").strip().lower()

    if "sensor" in text:
        await handle_sensors_request(update, context)
        return
    if "actuador" in text:
        await handle_actuators_request(update, context)
        return
    if "alerta" in text:
        await handle_alerts_request(update, context)
        return
    if "actualizar" in text:
        await handle_refresh_request(update, context)
        return
    if "ayuda" in text:
        await help_command(update, context)
        return
    if "menu" in text or "menú" in text:
        await start(update, context)
        return

    await update.message.reply_text("Opcion no reconocida.", reply_markup=build_main_keyboard())


async def handle_sensors_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    session = get_user_session(user.id)

    if not device_cache["sensors"]:
        session["pending_requests"].add("sensors")
        await update.message.reply_text("Consultando sensores (BBDD)...")
        mqtt_select("sensors")

        await asyncio.sleep(2)
        menu = build_device_menu("sensors")
        await update.message.reply_text("Sensores disponibles:", reply_markup=menu)
        return

    menu = build_device_menu("sensors")
    await update.message.reply_text("Sensores disponibles:", reply_markup=menu)


async def handle_actuators_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    session = get_user_session(user.id)

    if not device_cache["actuators"]:
        session["pending_requests"].add("actuators")
        await update.message.reply_text("Consultando actuadores (BBDD)...")
        mqtt_select("actuators")

        await asyncio.sleep(2)
        menu = build_device_menu("actuators")
        await update.message.reply_text("Actuadores disponibles:", reply_markup=menu)
        return

    menu = build_device_menu("actuators")
    await update.message.reply_text("Actuadores disponibles:", reply_markup=menu)


async def handle_alerts_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    session = get_user_session(user.id)
    session["pending_requests"].add("alerts")

    await update.message.reply_text("Consultando alertas (BBDD)...")
    mqtt_select("alerts", limit=10)


async def handle_refresh_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    session = get_user_session(user.id)

    device_cache["sensors"].clear()
    device_cache["actuators"].clear()

    session["pending_requests"].add("sensors")
    session["pending_requests"].add("actuators")

    await update.message.reply_text("Actualizando inventario (BBDD)...")

    mqtt_select("sensors")
    mqtt_select("actuators")

    await asyncio.sleep(2)
    await update.message.reply_text(
        f"Actualizado.\nSensores: {len(device_cache['sensors'])} dispositivos\nActuadores: {len(device_cache['actuators'])} dispositivos",
        reply_markup=build_main_keyboard(),
    )


# =========================
# CALLBACK HANDLER
# =========================
async def handle_submenu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    await query.answer()

    choice = query.data or ""
    update_user_session(user.id, chat_id=query.message.chat.id)

    try:
        if choice.startswith("refresh|"):
            _, req_type = choice.split("|", 1)
            device_cache[req_type].clear()
            await query.edit_message_text("Actualizando inventario...")
            mqtt_select(req_type)
            return

        if choice.startswith("refresh_component|"):
            _, req_type, device = choice.split("|", 2)
            device_cache[req_type][device] = []
            await query.edit_message_text(f"Actualizando componentes de {device}...")
            mqtt_select(req_type, device=device)
            return

        if choice.startswith("device|"):
            _, req_type, device = choice.split("|", 2)
            menu = build_component_menu(req_type, device)
            await query.edit_message_text(f"{device} ({req_type})", reply_markup=menu)
            return

        if choice.startswith("back|"):
            _, req_type = choice.split("|", 1)
            menu = build_device_menu(req_type)
            await query.edit_message_text(f"{req_type} disponibles:", reply_markup=menu)
            return

        if choice.startswith("component|"):
            _, req_type, device, cid = choice.split("|", 3)
            cid_int = int(cid)

            comp_type = "sensor" if req_type == "sensors" else "actuator"
            mqtt_get(device=device, comp_type=comp_type, comp_id=cid_int)

            await query.edit_message_text(f"Solicitando lectura en tiempo real: {device} {comp_type} {cid_int}")
            return

        if choice == "main_menu":
            await query.edit_message_text("Menu principal")
            return

    except Exception as e:
        logger.error(f"Error en callback: {e}")
        await query.edit_message_text("Error procesando la solicitud.")


# =========================
# MQTT RECEIVE
# =========================
def cache_add_component(req_type, device, data):
    """
    Inserta componentes en cache evitando duplicados por id.
    Normaliza 'enable' -> 'enabled' para sensores.
    """
    data = normalize_inventory_payload(data)

    existing = device_cache[req_type].get(device, [])
    if not any(int(e.get("id", -1)) == int(data.get("id", -2)) for e in existing):
        device_cache[req_type].setdefault(device, []).append(data)


def find_component_meta(req_type, device, comp_id):
    """
    Devuelve metadatos de un componente desde cache (nombre, ubicación y enabled).
    """
    for item in device_cache[req_type].get(device, []):
        if int(item.get("id", -1)) == int(comp_id):
            enabled_val = get_enabled_field(item, default=True)
            return {
                "name": item.get("name"),
                "location": item.get("location"),
                "enabled": enabled_val,
            }
    return {}


def on_message(client, userdata, msg):
    try:
        topic = msg.topic
        payload_raw = msg.payload.decode(errors="replace")
        data = json.loads(payload_raw) if payload_raw else {}

        app = userdata.get("app")
        loop = userdata.get("loop")

        logger.info("[MQTT][IN] %s %s", topic, payload_raw[:200])

        if topic == TOPIC_NOTIFY_ALERT:
            asyncio.run_coroutine_threadsafe(show_alert_notify(app, data), loop)
            return

        if not topic.startswith(TOPIC_RESPONSE_PREFIX):
            return

        tail = topic[len(TOPIC_RESPONSE_PREFIX):]
        parts = tail.split("/")
        if not parts:
            return

        category = parts[0]

        if category in ("sensors", "actuators"):
            # Esperado: <table>/<device>/<id>  OR  <table>/empty
            if len(parts) >= 2 and parts[1] == "empty":
                logger.info("[CACHE] %s: sin resultados", category)
                return

            if len(parts) < 3:
                return

            # Solo cachea si hay id numérico (evita respuestas parciales)
            if not parts[2].isdigit():
                return

            device = parts[1]
            data = normalize_inventory_payload(data)

            cache_add_component(category, device, data)
            asyncio.run_coroutine_threadsafe(notify_cache_update(app, category, device), loop)
            return

        if category in ("sensor", "actuator"):
            # Esperado: <type>/<device>/<id>
            if len(parts) < 3 or not parts[2].isdigit():
                return

            device = parts[1]
            comp_id = int(parts[2])

            if category == "sensor":
                meta = find_component_meta("sensors", device, comp_id)

                # Si el payload de tiempo real incluye enable/enabled, lo usamos.
                # Si no, usamos lo que haya en cache.
                enabled_from_payload = get_enabled_field(data, default=None)
                enabled_final = enabled_from_payload if enabled_from_payload is not None else meta.get("enabled", True)

                merged = {
                    "device_name": device,
                    "id": comp_id,
                    "name": meta.get("name", f"Sensor {comp_id}"),
                    "location": meta.get("location", "N/A"),
                    "enabled": enabled_final,
                    "value": data.get("value"),
                    "unit": data.get("unit") or data.get("units"),
                }
                asyncio.run_coroutine_threadsafe(show_sensor_reading(app, merged), loop)
                return

            meta = find_component_meta("actuators", device, comp_id)
            merged = {
                "device_name": device,
                "id": comp_id,
                "name": meta.get("name", f"Actuator {comp_id}"),
                "location": meta.get("location", "N/A"),
                "state": data.get("state"),
            }
            asyncio.run_coroutine_threadsafe(show_actuator_state(app, merged), loop)
            return

        if category == "alerts":
            asyncio.run_coroutine_threadsafe(show_alert_row(app, data), loop)
            return

    except Exception as e:
        logger.error(f"[MQTT] Error procesando mensaje: {e}")


# =========================
# TELEGRAM OUTPUT
# =========================
async def notify_cache_update(app, req_type, device_name):
    for user_id, session in list(user_sessions.items()):
        if req_type not in session.get("pending_requests", set()):
            continue

        chat_id = session.get("last_chat_id")
        if not chat_id:
            continue

        try:
            await app.bot.send_message(
                chat_id=chat_id,
                text=f"Inventario actualizado: {req_type} -> {device_name}",
                reply_markup=build_main_keyboard(),
            )
            session["pending_requests"].discard(req_type)
        except Exception as e:
            logger.warning(f"Error notificando a user_id={user_id}: {e}")


async def show_sensor_reading(app, data):
    enabled_bool = normalize_bool_state(data.get("enabled"))
    enabled_txt = "1" if enabled_bool else "0"

    text = (
        "Lectura de sensor (tiempo real)\n\n"
        f"Dispositivo: {data.get('device_name')}\n"
        f"Sensor: {data.get('name')}\n"
        f"Ubicacion: {data.get('location')}\n"
        f"ID: {data.get('id')}\n"
        f"Valor: {data.get('value')} {data.get('unit') or ''}\n"
        f"Enabled: {enabled_txt}\n"
    )
    for chat_id in list(app.bot_data.get("active_chats", [])):
        try:
            await app.bot.send_message(chat_id=chat_id, text=text, reply_markup=build_main_keyboard())
        except Exception as e:
            logger.warning(f"Error enviando lectura a chat {chat_id}: {e}")


async def show_actuator_state(app, data):
    state_bool = normalize_bool_state(data.get("state"))
    state_txt = "ON" if state_bool else "OFF"

    text = (
        "Estado de actuador (tiempo real)\n\n"
        f"Dispositivo: {data.get('device_name')}\n"
        f"Actuador: {data.get('name')}\n"
        f"Ubicacion: {data.get('location')}\n"
        f"ID: {data.get('id')}\n"
        f"Estado: {state_txt}\n"
    )
    for chat_id in list(app.bot_data.get("active_chats", [])):
        try:
            await app.bot.send_message(chat_id=chat_id, text=text, reply_markup=build_main_keyboard())
        except Exception as e:
            logger.warning(f"Error enviando estado a chat {chat_id}: {e}")


async def show_alert_notify(app, data):
    text = (
        "ALERTA (notify)\n\n"
        f"Device: {data.get('device')}\n"
        f"Type: {data.get('type')}\n"
        f"ID: {data.get('id')}\n"
        f"Name: {data.get('name')}\n"
        f"Location: {data.get('location')}\n"
        f"Severity: {data.get('severity')}\n"
        f"Status: {data.get('status')}\n"
        f"Message: {data.get('message')}\n"
        f"Code: {data.get('code')}\n"
        f"Timestamp: {data.get('timestamp')}\n"
    )
    for chat_id in list(app.bot_data.get("active_chats", [])):
        try:
            await app.bot.send_message(chat_id=chat_id, text=text, reply_markup=build_main_keyboard())
        except Exception as e:
            logger.warning(f"Error enviando alerta a chat {chat_id}: {e}")


async def show_alert_row(app, data):
    text = (
        "ALERTA (BBDD)\n\n"
        f"Device: {data.get('device_name')}\n"
        f"Component type: {data.get('component_type')}\n"
        f"Component id: {data.get('component_id')}\n"
        f"Component name: {data.get('component_name')}\n"
        f"Location: {data.get('location')}\n"
        f"Severity: {data.get('severity')}\n"
        f"Status: {data.get('status')}\n"
        f"Message: {data.get('message')}\n"
        f"Code: {data.get('code')}\n"
        f"Timestamp: {data.get('timestamp')}\n"
    )
    for chat_id in list(app.bot_data.get("active_chats", [])):
        try:
            await app.bot.send_message(chat_id=chat_id, text=text, reply_markup=build_main_keyboard())
        except Exception as e:
            logger.warning(f"Error enviando alerta(BBDD) a chat {chat_id}: {e}")


# =========================
# MQTT LOOP
# =========================
def mqtt_loop(app, loop):
    global mqtt_client

    while True:
        try:
            mqtt_connected.clear()
            mqtt_client = mqtt.Client(userdata={"app": app, "loop": loop})
            mqtt_client.username_pw_set(MQTT_USER, MQTT_PASS)

            def on_connect(client, userdata, flags, rc):
                if rc != 0:
                    logger.error(f"[MQTT] Error de conexion: rc={rc}")
                    return

                logger.info("[MQTT] Conectado")
                mqtt_connected.set()

                client.subscribe(f"{TOPIC_RESPONSE_PREFIX}#", qos=1)
                client.subscribe(TOPIC_NOTIFY_ALERT, qos=1)

                logger.info(f"[MQTT] Subscribed: {TOPIC_RESPONSE_PREFIX}#")
                logger.info(f"[MQTT] Subscribed: {TOPIC_NOTIFY_ALERT}")

            mqtt_client.on_connect = on_connect
            mqtt_client.on_message = on_message

            logger.info(f"[MQTT] Conectando a {MQTT_HOST}:{MQTT_PORT}...")
            mqtt_client.connect(MQTT_HOST, MQTT_PORT, 60)
            mqtt_client.loop_forever()

        except Exception as e:
            logger.error(f"[MQTT] Error en loop: {e}. Reintentando en 5s...")
            time.sleep(5)


# =========================
# MAIN
# =========================
async def post_init(app: Application) -> None:
    loop = asyncio.get_running_loop()
    mqtt_thread = threading.Thread(target=mqtt_loop, args=(app, loop), daemon=True)
    mqtt_thread.start()
    logger.info("MQTT thread iniciado desde post_init.")


if __name__ == "__main__":
    if not TOKEN:
        raise RuntimeError("Falta TELEGRAM_API_KEY en variables de entorno")

    logger.info("Iniciando bot Telegram...")

    application = Application.builder().token(TOKEN).post_init(post_init).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_menu))
    application.add_handler(CallbackQueryHandler(handle_submenu))

    application.run_polling()
