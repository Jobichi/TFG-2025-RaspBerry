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

# IMPORTANTE: el nombre de servicio debe coincidir con el que usa mqtt-router en system/<action>/<service>
# En tu documentación aparecen ejemplos tipo: system/get/telegram-service
SERVICE_NAME = os.getenv("MQTT_SERVICE_NAME", "telegram-service")

TOPIC_SELECT = f"system/select/{SERVICE_NAME}"
TOPIC_GET = f"system/get/{SERVICE_NAME}"
TOPIC_SET = f"system/set/{SERVICE_NAME}"

TOPIC_RESPONSE_PREFIX = f"system/response/{SERVICE_NAME}/"
TOPIC_NOTIFY_ALERT = "system/notify/alert"

mqtt_client = None

# Cache de inventario (desde BBDD via system/select)
device_cache = {"sensors": {}, "actuators": {}}

# Sesiones por usuario: control básico de “pending”
user_sessions = {}


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
            "pending_requests": set(),   # {"sensors","actuators","alerts"}
            "last_chat_id": None,        # para responder al chat correcto
        }
    return user_sessions[user_id]


def update_user_session(user_id, chat_id=None, action=None):
    session = get_user_session(user_id)
    session["last_action"] = time.time()
    if chat_id is not None:
        session["last_chat_id"] = chat_id


# =========================
# MQTT PUBLISH HELPERS
# =========================
def mqtt_select(request, device=None, comp_id=None, limit=None):
    payload = {"request": request}
    if device is not None:
        payload["device"] = device
    if comp_id is not None:
        payload["id"] = int(comp_id)
    if limit is not None:
        payload["limit"] = int(limit)
    mqtt_client.publish(TOPIC_SELECT, json.dumps(payload), qos=1)


def mqtt_get(device, comp_type, comp_id):
    payload = {"device": device, "type": comp_type, "id": int(comp_id)}
    mqtt_client.publish(TOPIC_GET, json.dumps(payload), qos=1)


def normalize_bool_state(value):
    # DB puede traer bool / 0-1; runtime puede traer "ON"/"OFF"
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        v = value.strip().lower()
        return v in ("1", "true", "on", "yes", "active", "enabled")
    return False


# =========================
# TELEGRAM COMMANDS
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat_id = update.effective_chat.id
    update_user_session(user.id, chat_id=chat_id, action="start")

    app = context.application
    if "active_chats" not in app.bot_data:
        app.bot_data["active_chats"] = set()
    app.bot_data["active_chats"].add(chat_id)

    text = (
        "Bot de sistema:\n"
        "- Sensores: consulta de inventario y lectura en tiempo real\n"
        "- Actuadores: consulta de inventario y lectura en tiempo real\n"
        "- Alertas: notificaciones desde system/notify/alert\n"
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

        # Inventario persistente
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

        # Inventario persistente
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

    # Consulta persistente (ultimas N alertas)
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
            mqtt_select(req_type)  # req_type: sensors/actuators
            return

        if choice.startswith("refresh_component|"):
            _, req_type, device = choice.split("|", 2)
            device_cache[req_type][device] = []
            await query.edit_message_text(f"Actualizando componentes de {device}...")
            mqtt_select(req_type, device=device)  # inventario por dispositivo
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

            # Lectura en tiempo real (system/get)
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
    # req_type: "sensors" | "actuators"
    existing = device_cache[req_type].get(device, [])
    if not any(int(e.get("id", -1)) == int(data.get("id", -2)) for e in existing):
        device_cache[req_type].setdefault(device, []).append(data)


def find_component_meta(req_type, device, comp_id):
    # Devuelve dict con name/location si está en cache
    for item in device_cache[req_type].get(device, []):
        if int(item.get("id", -1)) == int(comp_id):
            return {
                "name": item.get("name"),
                "location": item.get("location"),
                "enabled": item.get("enabled", True),
            }
    return {}


def on_message(client, userdata, msg):
    try:
        topic = msg.topic
        payload_raw = msg.payload.decode(errors="replace")
        data = json.loads(payload_raw) if payload_raw else {}

        app = userdata.get("app")
        loop = userdata.get("loop")

        # 1) Alertas instantaneas del router
        if topic == TOPIC_NOTIFY_ALERT:
            asyncio.run_coroutine_threadsafe(show_alert_notify(app, data), loop)
            return

        # 2) Respuestas del router: system/response/<service>/...
        if not topic.startswith(TOPIC_RESPONSE_PREFIX):
            return

        tail = topic[len(TOPIC_RESPONSE_PREFIX):]  # e.g. "sensors/esp32/1" o "sensor/esp32/1" o "alerts/7"
        parts = tail.split("/")
        if not parts:
            return

        category = parts[0]  # sensors|actuators|sensor|actuator|alerts|devices|...
        if category in ("sensors", "actuators"):
            # Inventario desde BBDD: system/select -> system/response/<service>/<table>/<device>/<id>
            if len(parts) < 3:
                return
            device = parts[1]
            cache_add_component(category, device, data)

            asyncio.run_coroutine_threadsafe(notify_cache_update(app, category, device), loop)
            return

        if category in ("sensor", "actuator"):
            # Respuesta de lectura en tiempo real: system/get -> .../<type>/<device>/<id>
            if len(parts) < 3:
                return
            device = parts[1]
            comp_id = int(parts[2])

            if category == "sensor":
                meta = find_component_meta("sensors", device, comp_id)
                merged = {
                    "device_name": device,
                    "id": comp_id,
                    "name": meta.get("name", f"Sensor {comp_id}"),
                    "location": meta.get("location", "N/A"),
                    "enabled": meta.get("enabled", True),
                    "value": data.get("value"),
                    "unit": data.get("unit"),
                }
                asyncio.run_coroutine_threadsafe(show_sensor_reading(app, merged), loop)
                return

            if category == "actuator":
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
            # Respuesta desde BBDD: system/response/<service>/alerts/<id>
            asyncio.run_coroutine_threadsafe(show_alert_row(app, data), loop)
            return

    except Exception as e:
        logger.error(f"[MQTT] Error procesando mensaje: {e}")


# =========================
# TELEGRAM OUTPUT
# =========================
async def notify_cache_update(app, req_type, device_name):
    # req_type: "sensors" | "actuators"
    # Notifica solo a usuarios con pending_requests (si los hay)
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
    text = (
        "Lectura de sensor (tiempo real)\n\n"
        f"Dispositivo: {data.get('device_name')}\n"
        f"Sensor: {data.get('name')}\n"
        f"Ubicacion: {data.get('location')}\n"
        f"ID: {data.get('id')}\n"
        f"Valor: {data.get('value')} {data.get('unit') or ''}\n"
        f"Enabled: {data.get('enabled')}\n"
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
    # payload de system/notify/alert (router) incluye device/type/id/name/location/status/severity/message/code/timestamp
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
    # payload de system/select alerts (BBDD) suele incluir device_name/component_type/component_id/component_name/location/status/message/severity/code/timestamp
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
            mqtt_client = mqtt.Client(userdata={"app": app, "loop": loop})
            mqtt_client.username_pw_set(MQTT_USER, MQTT_PASS)

            def on_connect(client, userdata, flags, rc):
                if rc != 0:
                    logger.error(f"[MQTT] Error de conexion: rc={rc}")
                    return

                logger.info("[MQTT] Conectado")
                # Respuestas del router a este servicio
                client.subscribe(f"{TOPIC_RESPONSE_PREFIX}#", qos=1)
                # Alertas asíncronas
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
if __name__ == "__main__":
    if not TOKEN:
        raise RuntimeError("Falta TELEGRAM_API_KEY en variables de entorno")

    logger.info("Iniciando bot Telegram...")

    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_menu))
    application.add_handler(CallbackQueryHandler(handle_submenu))

    loop = asyncio.get_event_loop()
    mqtt_thread = threading.Thread(target=mqtt_loop, args=(application, loop), daemon=True)
    mqtt_thread.start()

    application.run_polling()
